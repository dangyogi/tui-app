# print_sheet.py

from subprocess import run


class sheet:
    def __init__(self, name, gid, margins=None, lp_options=[], portrait=True):
        self.name = name
        self.gid = gid
        self.margins = margins
        self.lp_options = lp_options
        self.portrait = portrait

    def url_params(self):
        params = f"format=pdf&gid={self.gid}&size=letter" \
                 f"&portrait={str(self.portrait).lower()}"
        if self.margins:
            params += f"&top_margin={self.margins[0]}" \
                      f"&bottom_margin={self.margins[1]}" \
                      f"&left_margin={self.margins[2]}" \
                      f"&right_margin={self.margins[3]}"
        # can also add "&fitw=true" and/or "&gridlines=false"
        return params

class spreadsheet:
    def __init__(self, name, id, *sheets):
        self.name = name
        self.id = id
        self.sheets = to_dict(sheets)

    def base_url(self):
        return f"https://docs.google.com/spreadsheets/d/{self.id}/export"


def to_dict(items):
    return {item.name: item for item in items}

Google_spreadsheets = to_dict([
    spreadsheet("forms", "1KMnse9Voc8twPKq7Z0YcoZWWCC_kiv_B3u3IEy91WrQ",
                sheet("member_sign_in", "1346632090",
                      margins=(0.2, 0.2, 0.25, 0.25)),
                sheet("fifty_fifty", "786021892",
                      margins=(0.25, 0.25, 0.25, 0.25),
                      portrait=False),
                sheet("adv_ticket_sales", "159428219",
                      margins=(0.2, 0.2, 0.25, 0.25)),
                sheet("door_ticket_sales", "534095283",
                      margins=(0.25, 0.2, 0.2, 0.2),
                      portrait=False),
                sheet("donations", "1961262711",
                      margins=(0.2, 0.2, 0.25, 0.25),
                      portrait=False),
                sheet("receipts", "750601876",
                      margins=(0.65, 0.65, 0.25, 0.25),
                      portrait=False),
                sheet("petty_cash_record", "1517507686",
                      margins=(0.2, 0.2, 0.2, 0.2),
                      portrait=False),
                sheet("t_check_list", "998825988"),
                sheet("inv_check_list", "235656604"),
    ),
])

def print_sheet(sheet_name, copies=1, spread_sheet_name="forms"):
    ss = Google_spreadsheets[spread_sheet_name]
    sheet = ss.sheets[sheet_name]

    url = f"{ss.base_url()}?{sheet.url_params()}"

    curl_proc = run(
        ["curl", "-sL", url],
        capture_output=True,  # Captures stdout as bytes
    )
    if curl_proc.returncode != 0:
        raise ValueError(f"Failed to download sheet {sheet_name}")

    print_proc = run(
        ["lp", "-n", str(copies)] + sheet.lp_options,
        input=curl_proc.stdout,
        capture_output=True,  # Captures stdout as bytes
    )
    if print_proc.returncode != 0:
        raise ValueError(f"Print failed for sheet {sheet_name}")



if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--spreadsheet-name", "-s", default="forms")
    parser.add_argument("--copies", "-c", type=int, default=1)
    parser.add_argument("sheet_name",
                        choices=Google_spreadsheets["forms"].sheets.keys())
    args = parser.parse_args()
    print_sheet(args.sheet_name, args.copies, args.spreadsheet_name)


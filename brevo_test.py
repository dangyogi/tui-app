# brevo_test.py
#
# - SMTP server: smtp-relay.brevo.com
# - port: 587
# - login: aed342001@smtp-brevo.com
# - Password: kDZnGm8HsytUV5EI

import os
from smtplib import SMTP
from email.message import EmailMessage
import mimetypes

SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_KEY = os.getenv("SMTP_KEY")

def mkmsg(to_addr, subject="Test email from Raspberry Pi", _from="dangyogi@gmail.com", text=None):
    msg = EmailMessage()
    msg['Subject'] = "Test email from Raspberry Pi"
    msg['From'] = "dangyogi@gmail.com"
    msg['To'] = to_addr
    if text is not None:
        msg.set_content(text)
    return msg

def add_attachment(msg, path):
    mime_type, _ = mimetypes.guess_type(path)
    print(f"{path=}, {mime_type=}")
    maintype, subtype = mime_type.split("/", 1)
    with open(path, "rb") as f:
        file_data = f.read()
        file_name = f.name
    msg.add_attachment(file_data, maintype=maintype, subtype=subtype, filename=file_name)

def send(msg):
    with SMTP(SMTP_SERVER, SMTP_PORT) as server:
       #server.starttls()
        server.login(SMTP_USER, SMTP_KEY)
        server.send_message(msg)



if __name__ == "__main__":
    #msg = mkmsg("This is an important message!", "dangyogi@gmail.com")
    msg = mkmsg("Sent from python app on Raspberry PI.\r\nDid you get this message?", "matzomaan2006@gmail.com")
    print(msg)
    send(msg)


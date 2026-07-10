# table_screen.py

from functools import partial

from csv_app.trace import trace
from . import tui_base
from .field import field_shared, read_only_field, editable_field


class table_screen(tui_base.screen):
    scroll_amount = 3
    error_attr = 0x01

    def __init__(self, table, back=None, validate_fn=None, **select):
        r'''The validate_fn is passed the table and returns an error_message or None.
        '''
        super().__init__(table.name, back)
        self.table = table
        self.first_row = 0
        self.validate_fn = validate_fn
        self.select = select

    @property
    def screen_popup_commands(self):
        ans = self.table.screen_popup_commands
        if self.back is not None:
            ans += 'Back',
        if self.app.changed:
            ans += 'Abort',
        else:
            ans += 'Exit',
        return ans

    def init(self):
        r'''Run each time run is called, but _not_ each time the screen is resized.
        '''
        trace(f"table_screen.init({self.table.name=})")
        self.columns = self.table.columns

    def validate(self):
        if self.validate_fn is not None:
            msg = self.validate_fn(self.table)
            if msg:
                self.popup = tui_base.popup_message('Error', self, msg, self.error_attr)
                return False
        return True

    def process_mouse(self, mouse_event):
        if self.popup is not None:
            mouse_event = self.popup.process_mouse(mouse_event)
            if tui_base.event_handled(mouse_event):
                return mouse_event
        _, x, y, _, bstate = mouse_event
        trace(f"screen.process_mouse({y=}, {x=}, bstate={tui_base.bstate_str(bstate)})")
        if bstate == tui_base.curses.BUTTON3_CLICKED:
            if y >= 2:
                # row popup
                if self.popup is not None:
                    self.popup.delete()
                self.popup_y = y - 2  # selected row#
                row = self.rows[self.first_row + self.popup_y]
                trace(f"screen.process_mouse creating popup for row {self.first_row + self.popup_y}, "
                               f"{row=}, commands={row.row_popup_commands}")
                self.popup = tui_base.popup_menu(row.human_key(), self, row.row_popup_commands,
                                                 partial(row.execute, self.app), y + 1, 4)
            else:
                # table level popup at top of screen
                if self.popup is not None:
                    if self.popup_y is not None:   # this is a row popup, replace it
                        self.popup.delete()
                    else:
                        return None                # this is a table level popup, just keep using it...
                self.popup_y = None
                self.popup = tui_base.popup_menu("Screen", self, self.screen_popup_commands,
                                                 self.app.execute, 1, 4)
        elif bstate == tui_base.curses.BUTTON4_PRESSED:
            self.scroll_down(self.scroll_amount)
        elif bstate == tui_base.curses.BUTTON5_PRESSED:
            self.scroll_up(self.scroll_amount)
        else:
            return mouse_event

    def process_key(self, key):
        if self.popup is not None:
            key = self.popup.process_key(key)
            if tui_base.event_handled(key):
                return key
        trace(f"screen.process_key({key=})")
        if key == 'KEY_DOWN':
            self.scroll_up(self.scroll_amount)
        elif key == 'KEY_UP':
            self.scroll_down(self.scroll_amount)
        elif key == 'KEY_PPAGE':  # page down
            self.scroll_down(self.lines - 3)
        elif key == 'KEY_NPAGE':  # page up
            self.scroll_up(self.lines - 3)
        elif key == 'KEY_HOME':
            if self.first_row:
                self.scroll_down(self.first_row)
        elif key == 'KEY_END':
            rows_left = len(self.rows) - self.first_row
            if rows_left > self.lines - 2:
                self.scroll_up(rows_left - (self.lines - 3))
       #elif key == 'p':
       #    self.app.stdscr.move(4, 4)
       #elif key == 'r':
       #    self.app.stdscr.chgat(5, 4, 1, tui_base.curses.A_REVERSE)  # matches curses.curs_set(1) (1 = normal)
       #elif key == 'u':
       #    self.app.stdscr.chgat(6, 4, 1, tui_base.curses.A_UNDERLINE)  # works, not sure how useful it is...
        else:
            return key

    def scroll_up(self, nlines):
        trace(f"scroll_up({nlines})")
        if len(self.rows) - self.first_row - nlines < self.lines - 3:
            first_row = len(self.rows) - (self.lines - 3)
            nlines = first_row - self.first_row
            trace(f"adjusted {nlines=}")
        if nlines > 0:
            self.first_row += nlines
            self.app.stdscr.move(2, 0)
            if nlines > self.lines - 2:
                trace(f"scroll_up: {nlines=} too great, clear whole screen insdelln({-(self.lines - 2)})")
                self.app.stdscr.insdelln(-(self.lines - 2))
                self.draw_rows(self.first_row)
            else:
                trace(f"scroll_up: insdelln(-{nlines=})")
                self.app.stdscr.insdelln(-nlines)
                self.draw_rows(self.first_row + (self.lines - 2) - nlines, self.lines - nlines)

    def scroll_down(self, nlines):
        trace(f"scroll_down({nlines})")
        if self.first_row - nlines < 0:
            first_row = 0
            nlines = self.first_row
        assert nlines >= 0, f"{nlines=} < 0"
        if nlines:
            self.first_row -= nlines
            self.app.stdscr.move(2, 0)
            if nlines > self.lines - 2:
                trace(f"scroll_down: {nlines=} too great, clear whole screen insdelln({-(self.lines - 2)})")
                self.app.stdscr.insdelln(-(self.lines - 2))
                self.draw_rows(self.first_row)
            else:
                self.app.stdscr.insdelln(nlines)
                self.draw_rows(self.first_row, 2, nlines)

    def draw_body(self):
        self.rows = self.table.get_rows(self.app, **self.select)
        trace(f"draw_body(): {len(self.rows)=}")
        self.max_lens = []
        self.column_names = []
        self.field_shareds = []
        begin_x = 0
        for column in self.columns:
            if column.min_width is not None:
                max_len = column.min_width
            else:
                max_len = 0
                for row in self.rows:
                    value = row.get(column.name)
                    if len(value) > max_len:
                        max_len = len(value)
            if len(column.name) > max_len:
                name = column.abbr
            else:
                name = column.name
            self.column_names.append(name)
            if len(name) > max_len:
                max_len = len(name)
            self.max_lens.append(max_len)
            self.field_shareds.append(field_shared(name, 1, begin_x, max_len, self.app, column.validate,
                                                   column.alignment, left_placeholder="<", right_placeholder=">"))
            begin_x += max_len + 1
        self.width = begin_x - 1
        trace(f"table_screen.draw_body({self.table.name=}, {self.width=})")
        for col, max_len in zip(self.column_names, self.max_lens):
            trace(f"{col=}, {max_len=}")
        values = [f"{name:<{max_len}}" if column.alignment == 'left' else f"{name:>{max_len}}"
                  for column, name, max_len
                   in zip(self.columns, self.column_names, self.max_lens)]
        self.app.stdscr.addstr(1, 0, ' '.join(values),
                          #tui_base.curses.A_PROTECT)    # no effect
                          #tui_base.curses.A_UNDERLINE)  # not too bad
                          #tui_base.curses.A_LOW)        # no effect
                          #tui_base.curses.A_BOLD)       # just barely...
                           tui_base.curses.A_REVERSE)    # just barely...
                          #tui_base.curses.color_pair(0xF0))       # not seeing a difference between high/low white...
                          #tui_base.curses.color_pair(0xFf))       # solid white...
        self.draw_rows(self.first_row)

    def draw_rows(self, first_row=0, first_line=2, nlines=None):
        if nlines is None:
            nlines = self.lines - first_line
        trace(f"draw_rows({first_row=}, {first_line=}, {nlines=})")
        for lineno, row in enumerate(self.rows[first_row:], first_line):
            if lineno - first_line == nlines:
                break
            self.fields = []
            begin_x = 0
            for column, max_len, field_shared in zip(self.columns, self.max_lens, self.field_shareds):
                if column.can_edit:
                    f_type = editable_field
                else:
                    f_type = read_only_field
                self.fields.append(f_type(len(self.fields), row.get(column.name), field_shared, lineno,
                                          attr_pair=column.column_attr_pair(row)))
                begin_x += max_len + 1
        trace()


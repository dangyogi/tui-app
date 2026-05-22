# tui.py

r'''This is a generic TUI front-end for database type applications.

It provides a tables view (list of rows with column headings) and a row view (similar to a form).

It builds on three classes that you must write with the following interfaces:

    table:
        .name
        .columns
        .table_commands          # list of strings, tui will add Back and Abort/Exit to the end of these.
        .row_commands            # list of strings, or None
        .get_rows(**select)      # returns a complete list of row objects.
                                 # This library does not support paging to the data.
        .execute(app, command)   # for anything other than table_names or Abort/Exit

    column:
        .name
        .abbr       # abbr name to save space on the screen.  May be None.
        .min_width  # may be None, used for table view to fit all of the columns on the screen
        .alignment  # "left" or "right"
        .can_edit   # True/False

    row:
        .table_name
        .columns
        .human_key()       # may be row_num
        .get(column_name)  # returns string to display
        .delete()
        .update(**kws)     # given display strings as values
        .execute(app, command)  # for anything other than View/Edit/Delete
'''

import math

from . import tui_base


def start(tables, top_screen=None):
    app_instance = app(tables, top_screen)
    tui_base.curses.wrapper(app_instance.run)

class app:
    r'''Created and run by `start` fn.
    '''
    def __init__(self, tables, top_screen=None):
        self.tables = tables
        if top_screen is None:
            self.top_screen = list(tables.keys())[0]
        else:
            self.top_screen = top_screen
        self.changed = False

    def run(self, stdscr):   # called by curses.wrapper in start fn
        self.stdscr = stdscr
        tui_base.init_screen(stdscr)
        self.screen = table_screen(self.tables[self.top_screen])
        with open("trace.txt", "wt") as self.trace_file:
            while self.screen is not None:
                self.screen = self.screen.run(self)

    def execute(self, command):
        r'''Called for screen popup.

        Calls self.screen.table.execute if it does not recognize the command.
        '''
        print(f"app.execute({command=})", file=self.trace_file)
        if command in self.tables:
            print("command is table, returning table_screen", file=self.trace_file)
            return table_screen(self.tables[command])
        if command == 'Exit' or command == 'Abort':
            print(f"command is {command!r}, returning 'APP_EXIT'", file=self.trace_file)
            return 'APP_EXIT'
        print(f"app.execute({command=}): forwarding to screen", file=self.trace_file)
        return self.screen.table.execute(self, command)


class table_screen(tui_base.screen):
    scroll_amount = 3

    def __init__(self, table, back=None):
        super().__init__(table.name, back)
        self.table = table

    @property
    def commands(self):
        ans = self.table.table_commands
        if self.back is not None:
            ans.append('Back')
        if self.app.changed:
            ans.append('Abort')
        else:
            ans.append('Exit')
        return ans

    def init(self):
        print(f"table_screen.init({self.table.name=})", file=self.app.trace_file)
        self.rows = self.table.get_rows(self.app)
        self.row_commands = self.table.row_commands
        self.columns = self.table.columns
        self.max_lens = []
        self.column_names = []
        for column in self.columns:
            max_len = 0
            for row in self.rows:
                value = row.get(column.name)
                if len(value) > max_len:
                    max_len = len(value)
            if column.min_width is not None:
                max_len = column.min_width
            if len(column.name) > max_len:
                name = column.abbr
            else:
                name = column.name
            self.column_names.append(name)
            if len(name) > max_len:
                max_len = len(name)
            self.max_lens.append(max_len)
        self.width = sum(self.max_lens) + len(self.max_lens) - 1
        self.first_row = 0
        print(f"table_screen.init({self.table.name=}, {self.width=})", file=self.app.trace_file)
        for col, max_len in zip(self.column_names, self.max_lens):
            print(f"{col=}, {max_len=}", file=self.app.trace_file)

    def process_mouse(self, mouse_event):
        if self.popup is not None:
            mouse_event = self.popup.process_mouse(mouse_event)
            if mouse_event is None or mouse_event == 'APP_EXIT' or isinstance(mouse_event, tui_base.screen):
                return mouse_event
        _, x, y, _, bstate = mouse_event
        print(f"screen.process_mouse({y=}, {x=}, bstate={tui_base.bstate_str(bstate)})", file=self.app.trace_file)
        if bstate == tui_base.curses.BUTTON3_CLICKED:
            if y >= 2:
                # row popup
                self.popup_y = y - 2  # selected row#
                self.popup = tui_base.popup(self.rows[self.first_row + self.popup_y].human_key(), self,
                                            self.row_commands, self.row_execute, y + 1, 4)
            else:
                # table level popup at top of screen
                if self.popup is not None and self.popup_y >= 2:
                    self.popup.delete()
                self.popup_y = None
                self.popup = tui_base.popup("Screen", self, self.commands, self.app.execute, 1, 4)
        elif bstate == tui_base.curses.BUTTON4_PRESSED:
            self.scroll_down(self.scroll_amount)
        elif bstate == tui_base.curses.BUTTON5_PRESSED:
            self.scroll_up(self.scroll_amount)
        else:
            return mouse_event

    def process_key(self, key):
        if self.popup is not None:
            key = self.popup.process_key(key)
            if key is None or key == 'APP_EXIT' or isinstance(key, tui_base.screen):
                return key
        print(f"screen.process_key({key=})", file=self.app.trace_file)
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
        else:
            return key

    def row_execute(self, command):
        r'''Called for row popup.

        Calls self.screen.table.execute if it does not recognize the command.
        '''
        print(f"row_execute({self.popup_y=}, {command=})", file=self.app.trace_file)
        row = self.rows[self.first_row + self.popup_y]
        match command:
            case "View/Edit":
                return row_screen(row)
            case "Cancel":
                return None
            case _:
                return row.execute(self.app, command)

    def scroll_up(self, nlines):
        print(f"scroll_up({nlines})", file=self.app.trace_file)
        if len(self.rows) - self.first_row - nlines < self.lines - 3:
            first_row = len(self.rows) - (self.lines - 3)
            nlines = first_row - self.first_row
            print(f"adjusted {nlines=}", file=self.app.trace_file)
        if nlines > 0:
            self.first_row += nlines
            self.app.stdscr.move(2, 0)
            if nlines > self.lines - 2:
                print(f"scroll_up: {nlines=} too great, clear whole screen insdelln({-(self.lines - 2)})",
                      file=self.app.trace_file)
                self.app.stdscr.insdelln(-(self.lines - 2))
                self.draw_rows(self.first_row)
            else:
                print(f"scroll_up: insdelln(-{nlines=})", file=self.app.trace_file)
                self.app.stdscr.insdelln(-nlines)
                self.draw_rows(self.first_row + (self.lines - 2) - nlines, self.lines - nlines)

    def scroll_down(self, nlines):
        print(f"scroll_down({nlines})", file=self.app.trace_file)
        if self.first_row - nlines < 0:
            first_row = 0
            nlines = self.first_row
        assert nlines >= 0, f"{nlines=} < 0"
        if nlines:
            self.first_row -= nlines
            self.app.stdscr.move(2, 0)
            if nlines > self.lines - 2:
                print(f"scroll_down: {nlines=} too great, clear whole screen insdelln({-(self.lines - 2)})",
                      file=self.app.trace_file)
                self.app.stdscr.insdelln(-(self.lines - 2))
                self.draw_rows(self.first_row)
            else:
                self.app.stdscr.insdelln(nlines)
                self.draw_rows(self.first_row, 2, nlines)

    def draw_body(self):
        print(f"draw_body(): {len(self.rows)=}", file=self.app.trace_file)
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
        self.draw_rows()

    def draw_rows(self, first_row=0, first_line=2, nlines=None):
        if nlines is None:
            nlines = self.lines - first_line
        print(f"draw_rows({first_row=}, {first_line=}, {nlines=})", file=self.app.trace_file)
        for lineno, row in enumerate(self.rows[first_row:], first_line):
            if lineno - first_line == nlines:
                break
            columns = []
            for column, max_len in zip(self.columns, self.max_lens):
                value = row.get(column.name)
                if len(value) > max_len:
                    value = value[: max_len - 1] + '>'
                columns.append(f"{value:<{max_len}}" if column.alignment == 'left' else f"{value:>{max_len}}")
           #print(f"draw_rows: addstr({lineno=}, ...)", file=self.app.trace_file)
            self.app.stdscr.addstr(lineno, 0, ' '.join(columns))


class row_screen(tui_base.screen):
    def __init__(self, row):
        super().__init__(f"{row.table_name}: {row.human_key()}")
        self.row = row
        self.columns = self.row.columns

    def init(self):
        self.value_lens = []
        self.max_col_name_len = 0
        for column in self.columns:
            self.value_lens.append(self.row.get(column.name))
            if len(column.name) > self.max_col_name_len:
                self.max_col_name_len = len(column.name)
        print(f"row_screen.init({self.row.table_name}) {self.max_col_name_len=}", file=self.app.trace_file)

    def process_mouse(self, mouse_event):
        if self.popup is not None:
            mouse_event = self.popup.process_mouse(mouse_event)
            if mouse_event is None or mouse_event == 'APP_EXIT' or isinstance(mouse_event, tui_base.screen):
                return mouse_event
        _, x, y, _, bstate = mouse_event
        print(f"screen.process_mouse({y=}, {x=}, bstate={tui_base.bstate_str(bstate)})", file=self.app.trace_file)
        if bstate == tui_base.curses.BUTTON3_CLICKED:
            if y < 2:
                # table level popup at top of screen
                if self.popup is not None:
                    self.popup.delete()
                self.popup_y = None
                self.popup = tui_base.popup("Screen", self, self.commands, self.app.execute, 1, 4)
        else:
            return mouse_event

    def process_key(self, key):
        if self.popup is not None:
            key = self.popup.process_key(key)
            if key is None or key == 'APP_EXIT' or isinstance(key, tui_base.screen):
                return key
        print(f"screen.process_key({key=})", file=self.app.trace_file)
        if key == 'KEY_DOWN':
            self.scroll_up(self.scroll_amount)
        elif key == 'KEY_UP':
            self.scroll_down(self.scroll_amount)
        else:
            return key

    def draw_body(self):
        print(f"draw_body(): {len(self.columns)=}", file=self.app.trace_file)
        begin_x = self.max_col_name_len + 2
        width = self.cols - begin_x
        self.subwins = []
        lineno = 2
        for column in self.columns:
            self.app.stdscr.addstr(lineno, 0, f"{column.name}:")
            value = self.row.get(column.name)
            value_len = len(value)
            nlines = math.ceil(value_len * 1.2 / width)
            print(f"{column.name=}, {value_len=}, {nlines=}", file=self.app.trace_file)
            subwin = self.app.stdscr.subwin(nlines, width, lineno, begin_x)
            subwin.addstr(0, 0, value)
            self.subwins.append(subwin)
            lineno += nlines



if __name__ == "__main__":
    import database

    database.load_database()
    start(database.Tables)

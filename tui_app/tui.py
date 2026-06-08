# tui.py

r'''This is a generic TUI front-end for database type applications.

It provides a tables view (list of rows with column headings) and a row view (similar to a form).

It builds on three classes that you must write with the following interfaces:

    table:
        .name
        .columns
        .screen_popup_commands   # list of strings, tui will add Back and Abort/Exit to the end of these.
        .row_popup_commands      # list of strings, or None for row popup in table screen
        .get_rows(app, **select) # returns a list of selected row objects.
                                 # select keys are column_name (__eq assumed), or column_name__<lt|le|eq|ne|ge|gt>
                                 # results of select keys are and-ed.
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

See the tui_base.py module doc string for how the tui library works.
'''

import math

from . import tui_base
from .field import field_shared, read_only_field, editable_field


def start(tables, top_screen=None):
    app_instance = app(tables, top_screen)
    tui_base.curses.wrapper(app_instance.run)

class app:
    r'''Created and run by `start` fn.
    '''
    screen = None
    trace_file = None

    def __init__(self, tables, top_screen=None):
        self.tables = tables
        if top_screen is None:
            self.top_screen = list(tables.keys())[0]
        else:
            self.top_screen = top_screen
        self.changed = False

    def trace(self, *objects, sep=' ', end='\n', flush=False):
        if self.trace_file is not None:
            print(*objects, sep=sep, end=end, file=self.trace_file, flush=flush)

    def run(self, stdscr):   # called by curses.wrapper in start fn
        self.stdscr = stdscr
        tui_base.init_screen(stdscr)
        self.screen = table_screen(self.tables[self.top_screen])
        with open("trace.txt", "wt") as self.trace_file:
            while self.screen is not None:
                next_screen = self.screen.run(self)
                self.screen.delete()
                self.screen = next_screen

    def draw_changed(self, title_x):
        self.title_x = title_x
        if self.changed:
            self.draw_changed_banner()

    def set_changed(self):
        if not self.changed:
            self.changed = True
            self.draw_changed_banner()

    def draw_changed_banner(self):
        self.stdscr.addstr(0, 6, "Changed", tui_base.curses.color_pair(0xb1))  # was 0xf1

    def execute(self, command):
        r'''Called for screen popup.

        Calls self.screen.table.execute if it does not recognize the command.
        '''
        self.trace(f"app.execute({command=})")
        if command in self.tables:
            self.trace("command is table, returning table_screen")
            return table_screen(self.tables[command], self.screen)
        if command == 'Back':
            return self.screen.back
        if command == 'Exit':
            self.trace(f"command is {command!r}, returning 'APP_EXIT'")
            return 'APP_EXIT'
        if command == 'Abort':
            self.trace(f"command is {command!r}, returning 'APP_ABORT'")
            return 'APP_ABORT'
        if command == 'Change':
            # for testing
            self.set_changed()
            return None
        self.trace(f"app.execute({command=}): forwarding to screen")
        return self.screen.table.execute(self, command)


class table_screen(tui_base.screen):
    scroll_amount = 3

    def __init__(self, table, back=None, **select):
        super().__init__(table.name, back)
        self.table = table
        self.first_row = 0
        self.select = select

    @property
    def commands(self):
        ans = self.table.screen_popup_commands
        if self.back is not None:
            ans.append('Back')
        if self.app.changed:
            ans.append('Abort')
        else:
            ans.append('Change')
            ans.append('Exit')
        return ans

    def init(self):
        r'''Run each time run is called, but _not_ each time the screen is resized.
        '''
        self.app.trace(f"table_screen.init({self.table.name=})")
        self.rows = self.table.get_rows(self.app, **self.select)
        self.row_popup_commands = self.table.row_popup_commands
        self.columns = self.table.columns
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
            self.field_shareds.append(field_shared(name, 1, begin_x, max_len, self.app, column.alignment,
                                                   left_placeholder="<", right_placeholder=">"))
            begin_x += max_len + 1
        self.width = begin_x - 1
        self.app.trace(f"table_screen.init({self.table.name=}, {self.width=})")
        for col, max_len in zip(self.column_names, self.max_lens):
            self.app.trace(f"{col=}, {max_len=}")

    def process_mouse(self, mouse_event):
        if self.popup is not None:
            mouse_event = self.popup.process_mouse(mouse_event)
            if mouse_event is None or mouse_event in ('APP_EXIT', 'APP_ABORT') \
               or isinstance(mouse_event, tui_base.screen):
                return mouse_event
        _, x, y, _, bstate = mouse_event
        self.app.trace(f"screen.process_mouse({y=}, {x=}, bstate={tui_base.bstate_str(bstate)})")
        if bstate == tui_base.curses.BUTTON3_CLICKED:
            if y >= 2:
                # row popup
                if self.popup is not None:
                    self.popup.delete()
                self.popup_y = y - 2  # selected row#
                self.popup = tui_base.popup(self.rows[self.first_row + self.popup_y].human_key(), self,
                                            self.row_popup_commands, self.row_execute, y + 1, 4)
            else:
                # table level popup at top of screen
                if self.popup is not None:
                    if self.popup_y is not None:   # this is a row popup, replace it
                        self.popup.delete()
                    else:
                        return None                # this is a table level popup, just keep using it...
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
            if key is None or key in ('APP_EXIT', 'APP_ABORT') or isinstance(key, tui_base.screen):
                return key
        self.app.trace(f"screen.process_key({key=})")
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

    def row_execute(self, command):
        r'''Called for row popup.

        Calls self.screen.table.execute if it does not recognize the command.
        '''
        self.app.trace(f"row_execute({self.popup_y=}, {command=})")
        row = self.rows[self.first_row + self.popup_y]
        match command:
            case "View/Edit":
                return row_screen(row, self)
            case "Cancel":
                return None
            case _:
                return row.execute(self.app, command)

    def scroll_up(self, nlines):
        self.app.trace(f"scroll_up({nlines})")
        if len(self.rows) - self.first_row - nlines < self.lines - 3:
            first_row = len(self.rows) - (self.lines - 3)
            nlines = first_row - self.first_row
            self.app.trace(f"adjusted {nlines=}")
        if nlines > 0:
            self.first_row += nlines
            self.app.stdscr.move(2, 0)
            if nlines > self.lines - 2:
                self.app.trace(f"scroll_up: {nlines=} too great, clear whole screen insdelln({-(self.lines - 2)})")
                self.app.stdscr.insdelln(-(self.lines - 2))
                self.draw_rows(self.first_row)
            else:
                self.app.trace(f"scroll_up: insdelln(-{nlines=})")
                self.app.stdscr.insdelln(-nlines)
                self.draw_rows(self.first_row + (self.lines - 2) - nlines, self.lines - nlines)

    def scroll_down(self, nlines):
        self.app.trace(f"scroll_down({nlines})")
        if self.first_row - nlines < 0:
            first_row = 0
            nlines = self.first_row
        assert nlines >= 0, f"{nlines=} < 0"
        if nlines:
            self.first_row -= nlines
            self.app.stdscr.move(2, 0)
            if nlines > self.lines - 2:
                self.app.trace(f"scroll_down: {nlines=} too great, clear whole screen insdelln({-(self.lines - 2)})")
                self.app.stdscr.insdelln(-(self.lines - 2))
                self.draw_rows(self.first_row)
            else:
                self.app.stdscr.insdelln(nlines)
                self.draw_rows(self.first_row, 2, nlines)

    def draw_body(self):
        self.app.trace(f"draw_body(): {len(self.rows)=}")
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
        self.app.trace(f"draw_rows({first_row=}, {first_line=}, {nlines=})")
        for lineno, row in enumerate(self.rows[first_row:], first_line):
            if lineno - first_line == nlines:
                break
            fields = []
            begin_x = 0
            for column, max_len, field_shared in zip(self.columns, self.max_lens, self.field_shareds):
                if column.can_edit:
                    f_type = editable_field
                else:
                    f_type = read_only_field
                fields.append(f_type(row.get(column.name), field_shared, lineno))
                begin_x += max_len + 1


class row_screen(tui_base.screen):
    active_field = None

    def __init__(self, row, back=None):
        super().__init__(f"{row.table_name}: {row.human_key()}", back)
        self.row = row
        self.columns = self.row.columns
        self.commands = list(row.commands) + ['Cancel', 'Submit']
        self.fields = ()

    def init(self):
        self.max_col_name_len = 0
        for column in self.columns:
            if len(column.name) > self.max_col_name_len:
                self.max_col_name_len = len(column.name)
        self.app.trace(f"row_screen.init({self.row.table_name}) {self.max_col_name_len=}")

    def activate_field(self, field):
        self.app.trace(f"row_screen.activate_field({field.name=})")
        if self.active_field is not None and self.active_field != field:
            self.active_field.deactivate()
        self.active_field = field

    def process_mouse(self, mouse_event):
        _, x, y, _, bstate = mouse_event
        self.app.trace(f"row_screen.process_mouse({y=}, {x=}, bstate={tui_base.bstate_str(bstate)})")
        if bstate == tui_base.curses.BUTTON1_CLICKED:
            if y == self.button_y:
                # check buttons
                for i, (button_x_first, button_x_last) in enumerate(self.command_buttons_x):
                    if button_x_first <= x <= button_x_last:
                        return self.execute(self.commands[i])
        for field in self.fields:
            if field.enclose(y, x):
                return field.process_mouse(mouse_event)
        return mouse_event

    def process_key(self, key):
       #if self.popup is not None:
       #    key = self.popup.process_key(key)
       #    if key is None or key in ('APP_EXIT', 'APP_ABORT') or isinstance(key, tui_base.screen):
       #        return key
        self.app.trace(f"row_screen.process_key({key=}) {self.active_field=}")
        if self.active_field is not None:
            return self.active_field.process_key(key)
        return key

    def execute(self, command):
        self.app.trace(f"row_screen.execute({command=})")
        match command:
            case 'Cancel':
                self.app.trace(f"Cancel command going back to screen {self.back.title}")
                return self.back
            case 'Submit':
                self.app.trace("Submit command not implemented")
                return self.back

    def draw_body(self):
        self.app.trace(f"draw_body(): {len(self.columns)=}")
        self.begin_x = self.max_col_name_len + 2
        self.width = self.cols - self.begin_x
        self.fields = []
        lineno = 2
        lineno_by_col = []
        for column in self.columns:
            self.app.stdscr.addstr(lineno, 0, f"{column.name}:")
            value = self.row.get(column.name)
            value_len = len(value)
            nlines = max(1, math.ceil(value_len * 1.2 / self.width))
            lineno_by_col.append(lineno)
            self.app.trace(f"{column.name=}, {value_len=}, {nlines=} at {lineno=}, {self.begin_x=}")
            shared = field_shared(column.name, nlines, self.begin_x, self.width, self.app)
            if column.can_edit:
                f_type = editable_field
            else:
                f_type = read_only_field
            self.fields.append(f_type(value, shared, lineno))
            lineno += nlines
        self.active_field = None

        # draw command buttons
        self.button_y = lineno + 3
        assert self.button_y < self.lines, f"{self.button_y=}: too many lines to fit on screen, {self.lines=}"
        button_text_width = sum(len(command) for command in self.commands) + 3 * (len(self.commands) - 1)
        self.button_start_x = (self.cols - button_text_width) // 2
        button_x = self.button_start_x
        self.command_buttons_x = []
        for command in self.commands:
            # 0xf1 is white on red, looks like error
            # 0xf2 is white on green, hard to read
            # 0xf3 is white on yellow, can't read it
            # 0xf4 is white on blue, goofy
            # 0xf5 is white on purple, best out of first 6
            # 0xf6 is white on turquoise, hard to read
            self.app.stdscr.addstr(self.button_y, button_x, command, tui_base.curses.color_pair(0x05))
            self.command_buttons_x.append((button_x, button_x + len(command) - 1))
            button_x += 3 + len(command)



if __name__ == "__main__":
    import database

    database.load_database()
    start(database.Tables)

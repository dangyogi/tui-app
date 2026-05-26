# tui.py

r'''This is a generic TUI front-end for database type applications.

It provides a tables view (list of rows with column headings) and a row view (similar to a form).

It builds on three classes that you must write with the following interfaces:

    table:
        .name
        .columns
        .screen_popup_commands   # list of strings, tui will add Back and Abort/Exit to the end of these.
        .row_popup_commands      # list of strings, or None for row popup in table screen
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

See the tui_base.py module doc string for how the tui library works.
'''

import math

from . import tui_base


def start(tables, top_screen=None):
    app_instance = app(tables, top_screen)
    tui_base.curses.wrapper(app_instance.run)

class app:
    r'''Created and run by `start` fn.
    '''
    screen = None

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
        print(f"app.execute({command=})", file=self.trace_file)
        if command in self.tables:
            print("command is table, returning table_screen", file=self.trace_file)
            return table_screen(self.tables[command], self.screen)
        if command == 'Back':
            return self.screen.back
        if command == 'Exit':
            print(f"command is {command!r}, returning 'APP_EXIT'", file=self.trace_file)
            return 'APP_EXIT'
        if command == 'Abort':
            print(f"command is {command!r}, returning 'APP_ABORT'", file=self.trace_file)
            return 'APP_ABORT'
        if command == 'Change':
            # for testing
            self.set_changed()
            return None
        print(f"app.execute({command=}): forwarding to screen", file=self.trace_file)
        return self.screen.table.execute(self, command)


class table_screen(tui_base.screen):
    scroll_amount = 3

    def __init__(self, table, back=None):
        super().__init__(table.name, back)
        self.table = table
        self.first_row = 0

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
        print(f"table_screen.init({self.table.name=})", file=self.app.trace_file)
        self.rows = self.table.get_rows(self.app)
        self.row_popup_commands = self.table.row_popup_commands
        self.columns = self.table.columns
        self.max_lens = []
        self.column_names = []
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
        self.width = sum(self.max_lens) + len(self.max_lens) - 1
        print(f"table_screen.init({self.table.name=}, {self.width=})", file=self.app.trace_file)
        for col, max_len in zip(self.column_names, self.max_lens):
            print(f"{col=}, {max_len=}", file=self.app.trace_file)

    def process_mouse(self, mouse_event):
        if self.popup is not None:
            mouse_event = self.popup.process_mouse(mouse_event)
            if mouse_event is None or mouse_event in ('APP_EXIT', 'APP_ABORT') \
               or isinstance(mouse_event, tui_base.screen):
                return mouse_event
        _, x, y, _, bstate = mouse_event
        print(f"screen.process_mouse({y=}, {x=}, bstate={tui_base.bstate_str(bstate)})", file=self.app.trace_file)
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
        print(f"row_execute({self.popup_y=}, {command=})", file=self.app.trace_file)
        row = self.rows[self.first_row + self.popup_y]
        match command:
            case "View/Edit":
                return row_screen(row, self)
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
        self.draw_rows(self.first_row)

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
        print(f"row_screen.init({self.row.table_name}) {self.max_col_name_len=}", file=self.app.trace_file)

    def delete(self):
        for field in self.fields:
            field.delete()

    def activate_field(self, field):
        print(f"row_screen.activate_field({field.name=})", file=self.app.trace_file)
        if self.active_field is not None and self.active_field != field:
            self.active_field.deactivate()
        self.active_field = field

    def process_mouse(self, mouse_event):
        _, x, y, _, bstate = mouse_event
        print(f"row_screen.process_mouse({y=}, {x=}, bstate={tui_base.bstate_str(bstate)})",
              file=self.app.trace_file)
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
        print(f"row_screen.process_key({key=}) {self.active_field=}", file=self.app.trace_file)
        if self.active_field is not None:
            return self.active_field.process_key(key)
        return key

    def execute(self, command):
        print(f"row_screen.execute({command=})", file=self.app.trace_file)
        match command:
            case 'Cancel':
                print(f"Cancel command going back to screen {self.back.title}", file=self.app.trace_file)
                return self.back
            case 'Submit':
                print("Submit command not implemented", file=self.app.trace_file)
                return self.back

    def draw_body(self):
        print(f"draw_body(): {len(self.columns)=}", file=self.app.trace_file)
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
            print(f"{column.name=}, {value_len=}, {nlines=} at {lineno=}, {self.begin_x=}", file=self.app.trace_file)
            self.fields.append(field(self, value, column, nlines, lineno))
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

class field:
    r'''These are created each time the screen.draw is called.

    Therefore, they only see one screen size during their lifetime and only need to draw the text once.
    '''
    changed = False
    in_select = False
    pos_attr = tui_base.curses.A_REVERSE
    selection_pair = 0x06  # black on yellow
    no_edit_pair = 0x01    # black on red
    normal_pair = 0x10     # white on black

    def __init__(self, screen, text, column, nlines, lineno):
        self.screen = screen
        self.begin_x = screen.begin_x
        self.width = screen.width
        self.column = column
        self.nlines = nlines
        self.lineno = lineno
        self.subwin = screen.app.stdscr.subwin(self.nlines, self.width, self.lineno, self.begin_x)
        print(f"field({column.name}).__init__: {text=!r}, {column.name=} {column.can_edit=}, {nlines=}, {lineno=}",
              file=screen.app.trace_file)
        if column.can_edit:
            self.subwin.addstr(0, 0, text)
            self.position = 0, 0  # local (subwin) coordinates
            self.selection_len = 0
        else:
            if text:
                self.subwin.addstr(0, 0, text, tui_base.curses.color_pair(self.no_edit_pair))
            else:
                self.subwin.addstr(0, 0, ' ', tui_base.curses.color_pair(self.no_edit_pair))

    @property
    def name(self):
        return self.column.name

    def to_index(self, y, x):
        r'''Converts local (subwin) coordinates to text index.
        '''
        ans = self.width * y + x
        print(f"field({self.name}).to_index({y=}, {x=}) -> {ans}", file=self.screen.app.trace_file)
        return ans

    def to_pos(self, index):
        y, x = divmod(index, self.width)
        print(f"field({self.name}).to_pos({index=}) -> {y=}, {x=}", file=self.screen.app.trace_file)
        if y >= self.nlines:
            # set to lower right corner
            y = self.nlines - 1
            x = self.width - 1
            print(f"field({self.name}).to_pos({index=}): OVERFLOW!, setting to lower right corner {y=}, {x=}",
                  file=self.screen.app.trace_file)
        return y, x

    def pos_offset(self, len):
        y, x = self.position
        new_x = self.position[1] + len
        y_inc, x_inc = divmod(new_x, self.width)
        y_offset, x_offset = y + y_inc, x + x_inc
        print(f"field({self.name}).pos_offset({len=}) -> {y_offset=}, {x_offset=}",
              file=self.screen.app.trace_file)
        return y_offset, x_offset

    def delete(self):
        print(f"field({self.name}).delete()", file=self.screen.app.trace_file)
        del self.subwin

    def enclose(self, y, x):
        ans = self.column.can_edit and self.subwin.enclose(y, x)
        print(f"field({self.name}).enclose({y=}, {x=}) -> {ans}", file=self.screen.app.trace_file)
        return ans

    def get_text(self):
        text = self.subwin.instr(0, 0).decode('utf-8').rstrip()
        print(f"field({self.name}).get_text() -> {text!r}", file=self.screen.app.trace_file)
        return text

    def process_mouse(self, mouse_event):
        r'''Caller ensures self.enclose on mouse_event
        '''
        _, x_mouse, y_mouse, _, bstate = mouse_event

        # convert to local (subwin) coordinates
        y = y_mouse - self.lineno
        x = x_mouse - self.begin_x

        match bstate:
            case tui_base.curses.BUTTON1_CLICKED:
                print(f"field({self.name}).process_mouse({y=}, {x=}): BUTTON1_CLICKED",
                      file=self.screen.app.trace_file)
                self.cancel_selection()
                self.set_position(y, x)
            case tui_base.curses.BUTTON1_DOUBLE_CLICKED:
                print(f"field({self.name}).process_mouse({y=}, {x=}): BUTTON1_DOUBLE_CLICKED",
                      file=self.screen.app.trace_file)
                middle = self.to_index(y, x)
                text = self.get_text()
                start = text.rfind(' ', 0, middle) + 1
                end = text.find(' ', middle)
                if end == -1:
                    end = len(text)
                while text[end] in ',.;':
                    end -= 1
                self.set_selection(start, end)
            case tui_base.curses.BUTTON1_TRIPLE_CLICKED:
                print(f"field({self.name}).process_mouse({y=}, {x=}): BUTTON1_TRIPLE_CLICKED",
                      file=self.screen.app.trace_file)
                self.set_selection(0, len(self.get_text()))
            case tui_base.curses.BUTTON1_PRESSED:
                print(f"field({self.name}).process_mouse({y=}, {x=}): BUTTON1_PRESSED",
                      file=self.screen.app.trace_file)
                self.set_position(y, x)
                self.in_select = True
            case tui_base.curses.REPORT_MOUSE_POSITION if self.in_select:
                print(f"field({self.name}).process_mouse({y=}, {x=}): REPORT_MOUSE_POSITION",
                      file=self.screen.app.trace_file)
                self.extend_selection(y, x)
            case tui_base.curses.BUTTON1_RELEASED:
                print(f"field({self.name}).process_mouse({y=}, {x=}): BUTTON1_RELEASED",
                      file=self.screen.app.trace_file)
                self.extend_selection(y, x)
                self.in_select = False
            case _:
                return mouse_event
        self.subwin.noutrefresh()
        return None

    def process_key(self, key):
        if self.position is None:
            print(f"field({self.name}).process_key({key=}): position not set",
                  file=self.screen.app.trace_file)
            return key
        y, x = self.position
        if len(key) == 1 and tui_base.curses.ascii.isprint(key):
            print(f"field({self.name}).process_key({key=}): position {y=}, {x=}, ascii.is_print",
                  file=self.screen.app.trace_file)
            self.delete_selection()
            self.subwin.insch(y, x, key)
            self.inc_position()
        else:
            match key:
                case 'KEY_DELETE' | 'KEY_DC' | 'KEY_BACKSPACE' if self.selection_len:
                    print(f"field({self.name}).process_key({key=}): position {y=}, {x=}, "
                          f"{self.selection_len=}, delete_selection",
                          file=self.screen.app.trace_file)
                    self.delete_selection()
                case 'KEY_DELETE' | 'KEY_DC' if not self.selection_len:
                    print(f"field({self.name}).process_key({key=}): position {y=}, {x=}, "
                          f"no selection, delch at cursor",
                          file=self.screen.app.trace_file)
                    self.subwin.delch(y, x)
                    self.set_position(y, x)  # to turn cursor on
                case 'KEY_BACKSPACE' if not self.selection_len:
                    if x > 0:
                        del_y = y
                        del_x = x - 1
                        print(f"field({self.name}).process_key({key=}): position {y=}, {x=}, "
                              f"no selection, del prev char at {del_y=}, {del_x=}",
                              file=self.screen.app.trace_file)
                    elif y > 0:
                        del_y = y - 1
                        del_x = 0
                        print(f"field({self.name}).process_key({key=}): position {y=}, {x=}, "
                              f"no selection, del prev char at {del_y=}, {del_x=}",
                              file=self.screen.app.trace_file)
                    self.subwin.delch(del_y, del_x)
                    self.set_position(del_y, del_x)
                case 'KEY_UP' if y > 0:
                    new_y = y - 1
                    print(f"field({self.name}).process_key({key=}): position {y=}, {x=}, "
                          f"no selection, move to {new_y=}, {x=}",
                          file=self.screen.app.trace_file)
                    self.set_position(new_y, x)
                case 'KEY_DOWN' if y + 1 < self.nlines:
                    new_y = y + 1
                    print(f"field({self.name}).process_key({key=}): position {y=}, {x=}, "
                          f"no selection, move to {new_y=}, {x=}",
                          file=self.screen.app.trace_file)
                    self.set_position(new_y, x)
                case 'KEY_LEFT' if x > 0:
                    new_x = x - 1
                    print(f"field({self.name}).process_key({key=}): position {y=}, {x=}, "
                          f"no selection, move to {y=}, {new_x=}",
                          file=self.screen.app.trace_file)
                    self.set_position(y, new_x)
                    self.set_position(y, new_x)
                case 'KEY_RIGHT' if x + 1 < self.width:
                    new_x = x + 1
                    print(f"field({self.name}).process_key({key=}): position {y=}, {x=}, "
                          f"no selection, move to {y=}, {new_x=}",
                          file=self.screen.app.trace_file)
                    self.set_position(y, new_x)
                    self.set_position(y, new_x)
                case _:
                    return key
        self.subwin.noutrefresh()
        return None

    pos_attr = tui_base.curses.A_REVERSE
    selection_pair = 0x06  # black on yellow
    no_edit_pair = 0x01    # black on red
    normal_pair = 0x10     # white on black

    def set_selection(self, start, end):
        y_start, x_start = self.to_pos(start)
        print(f"field({self.name}).set_selection({start=}, {end=}): -> {y_start=}, {x_start=}",
              file=self.screen.app.trace_file)
        self.set_position(y_start, x_start)
        self.selection_len = end - start
        self.subwin.chgat(y_start, x_start, self.selection_len,
                          tui_base.curses.color_pair(self.selection_pair))

    def extend_selection(self, y, x):
        new_len = self.to_index(y, x) - self.to_index(*self.position)
        print(f"field({self.name}).extend_selection({y=}, {x=}) {self.selection_len=}: -> {new_len=}",
              file=self.screen.app.trace_file)
        if self.selection_len > new_len:
            # deselect from new_len to self.selection_len
            y_start, x_start = self.pos_offset(new_len)
            self.subwin.chgat(y_start, x_start, self.selection_len - new_len,
                              tui_base.curses.color_pair(self.normal_pair))
        elif new_len > self.selection_len:
            # select from old_len to new_len
            y_start, x_start = self.pos_offset(self.selection_len)
            self.subwin.chgat(y_start, x_start, new_len - self.selection_len,
                              tui_base.curses.color_pair(self.selection_pair))

    def cancel_selection(self):
        if self.selection_len:
            y, x = self.position
            print(f"field({self.name}).cancel_selection(): {y=}, {x=}, {self.selection_len=}",
                  file=self.screen.app.trace_file)
            self.subwin.chgat(y, x, self.selection_len, tui_base.curses.color_pair(self.normal_pair))
            self.selection_len = 0

    def delete_selection(self):
        if self.selection_len:
            y, x = self.position
            print(f"field({self.name}).delete_selection(): {y=}, {x=}, {self.selection_len=}",
                  file=self.screen.app.trace_file)
            for _ in range(self.selection_len):
                self.subwin.delch(y, x)
            self.selection_len = 0

    def set_position(self, y, x):
        print(f"field({self.name}).set_position({y=}, {x=})", file=self.screen.app.trace_file)
        self.cancel_selection()
        self.position = y, x
        self.subwin.chgat(y, x, 1, self.pos_attr)
        self.screen.activate_field(self)

    def inc_position(self):
        print(f"field({self.name}).inc_position()", file=self.screen.app.trace_file)
        y, x = self.to_pos(self.to_index(*self.position) + 1)
        self.set_position(y, x)

    def deactivate(self):
        if self.selection_len:
            print(f"field({self.name}).deactivate() {self.selection_len=}",
                  file=self.screen.app.trace_file)
            self.cancel_selection()
        else:
            y, x = self.position
            print(f"field({self.name}).deactivate(): no selection, {y=}, {x=}",
                  file=self.screen.app.trace_file)
            self.subwin.chgat(y, x, 1, tui_base.curses.color_pair(self.normal_pair))
        self.subwin.noutrefresh()




if __name__ == "__main__":
    import database

    database.load_database()
    start(database.Tables)

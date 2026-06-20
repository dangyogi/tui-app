# row_screen.py

import math

from . import tui_base
from .field import field_shared, read_only_field, editable_field


class row_screen(tui_base.screen):
    active_field = None
    msg_len = 0
    default_attr = 0x00
    error_attr = 0x10
    error_msg_attr = 0x10
    error_field = None

    def __init__(self, row, back=None, global_validate=None, callback=None):
        r'''
            global_validate is a function that is called on update after individual
            field validates have been done (and all passed).  This function takes
            this row_screen as its single argument, and returns an error message (to be
            displayed), if there was an error; or None if no errors.

            callback is a function that is called after a succesful Submit.  It takes no
            arguments and returns None.
        '''

        super().__init__(f"{row.table_name}: {row.human_key()}", back)
        self.row = row
        self.columns = self.row.columns
        self.row_screen_commands = list(row.row_screen_commands) \
                                 + ['Cancel', 'Update', 'Submit']
        self.fields = ()
        self.global_validate = global_validate
        self.callback = callback

    def init(self):
        self.max_col_name_len = 0
        for column in self.columns:
            if len(column.name) > self.max_col_name_len:
                self.max_col_name_len = len(column.name)
        self.app.trace(f"row_screen.init({self.row.table_name}) {self.max_col_name_len=}")

    def activate_field(self, field_num):
        self.app.trace(f"row_screen.activate_field({field_num=})")
        if self.active_field != field_num:
            if self.active_field is not None:
                self.fields[self.active_field].deactivate()
            self.active_field = field_num
            field = self.fields[field_num]
            if field.position is None:
                field.position = 0
                field.selection_len = 0
            field.set_attrs()

    def process_mouse(self, mouse_event):
        _, x, y, _, bstate = mouse_event
        self.app.trace(f"row_screen.process_mouse({y=}, {x=}, bstate={tui_base.bstate_str(bstate)})")
        if self.error_field is not None:
            self.error_field.highlight()
            self.error_field = None
        self.clear_message()
        # run command
        if bstate == tui_base.curses.BUTTON1_CLICKED:
            if y == self.button_y:
                # check buttons
                for i, (button_x_first, button_x_last) in enumerate(self.command_buttons_x):
                    if button_x_first <= x <= button_x_last:
                        return self.execute(self.row_screen_commands[i])
        # run this past the fields
        for field in self.fields:
            if field.enclose(y, x):
                return field.process_mouse(mouse_event)
        return mouse_event

    def process_key(self, key):
       #if self.popup is not None:
       #    key = self.popup.process_key(key)
       #    if tui_base.event_handled(key):
       #        return key
        self.app.trace(f"row_screen.process_key({key=}) {self.active_field=}")
        if self.error_field is not None:
            self.error_field.highlight()
            self.error_field = None
        self.clear_message()
        if self.active_field is not None:
            key = self.fields[self.active_field].process_key(key)
            if tui_base.event_handled(key):
                return key
        if key == '\t':
            active_field = self.active_field
            if active_field is None:
                offset = 0
            else:
                offset = active_field + 1
            for i in range(len(self.fields)):
                active_field = (offset + i) % len(self.fields)
                if self.fields[active_field].can_edit:
                    self.activate_field(active_field)
                    return None
        elif key == 'KEY_BTAB':
            active_field = self.active_field
            if active_field is None:
                offset = len(self.fields)
            else:
                offset = active_field - 1
            for i in range(len(self.fields)):
                active_field = (offset - i) % len(self.fields)
                if self.fields[active_field].can_edit:
                    self.activate_field(active_field)
                    return None
        return key

    def execute(self, command):
        self.app.trace(f"row_screen.execute({command=})")
        match command:
            case 'Cancel':
                self.app.trace(f"Cancel command going back to screen {self.back.title}")
                return self.back
            case 'Update':
                if self.update():
                    return 'REFRESH'
            case 'Submit':
                if self.update():
                    if self.callback is not None:
                        self.callback()
                    return self.back

    def update(self):
        r'''Returns True if all validation passes.

        Else dislays error message.

        Also updates self.row if all validation passes.
        '''
        for field in self.fields:
            if field.changed:
                try:
                    field.validate()
                except ValueError as exc:
                    field.highlight(tui_base.curses.color_pair(self.error_attr))
                    self.message(str(exc), tui_base.curses.color_pair(self.error_msg_attr))
                    self.error_field = field
                    return False
        if self.global_validate is not None:
            msg = self.global_validate(self)
            if msg:
                self.message(msg, tui_base.curses.color_pair(self.error_msg_attr))
                return False
        for field in self.fields:
            if field.changed:
                self.row.set(field.name, field.text)
                field.changed = False
        self.app.set_changed()
        return True

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
            shared = field_shared(column.name, nlines, self.begin_x, self.width, self.app, column.validate)
            if column.can_edit:
                f_type = editable_field
            else:
                f_type = read_only_field
            self.fields.append(f_type(len(self.fields), value, shared, lineno,
                                      attr_pair=column.column_attr_pair(self.row)))
            lineno += nlines
        self.active_field = None

        # draw command buttons
        self.button_y = lineno + 3
        assert self.button_y < self.lines, f"{self.button_y=}: too many lines to fit on screen, {self.lines=}"
        button_text_width = sum(len(command) for command in self.row_screen_commands) \
                          + 3 * (len(self.row_screen_commands) - 1)
        self.button_start_x = (self.cols - button_text_width) // 2
        button_x = self.button_start_x
        self.command_buttons_x = []
        for command in self.row_screen_commands:
            # 0xf1 is white on red, looks like error
            # 0xf2 is white on green, hard to read
            # 0xf3 is white on yellow, can't read it
            # 0xf4 is white on blue, goofy
            # 0xf5 is white on purple, best out of first 6
            # 0xf6 is white on turquoise, hard to read
            self.app.stdscr.addstr(self.button_y, button_x, command, tui_base.curses.color_pair(0x05))
            self.command_buttons_x.append((button_x, button_x + len(command) - 1))
            button_x += 3 + len(command)

    def message(self, msg, attr):
        x = (self.cols - len(msg)) // 2  # center message
        self.app.stdscr.addstr(self.button_y + 2, x, msg, attr)
        self.msg_len = len(msg)

    def clear_message(self):
        if self.msg_len:
            x = (self.cols - self.msg_len) // 2  # center message
            if self.error_field is not None:
                attr_pair = self.error_field.default_attr_pair
            else:
                attr_pair = self.default_attr
            self.app.stdscr.addstr(self.button_y + 2, x, ' ' * self.msg_len,
                                   tui_base.curses.color_pair(attr_pair))
            self.msg_len = 0


# menu_screen.py

import math

from . import tui_base
from .field import field_shared, read_only_field


class menu_screen(tui_base.screen):
    active_field = None
    msg_len = 0
    error_attr = 0x10
    error_msg_attr = 0x10
    error_field = None

    task_pair     = 0x0   # standard white on black
    cant_run_pair = 0x10  # red text
    may_run_pair  = 0x30  # yellow text
    must_run_pair = 0x20  # green text

    def __init__(self, actions, title="Menu", back=None):
        super().__init__(title, back)
        self.actions = actions
        self.widths = [[0, 0, 0]]   # list of [max_task_number_len, max_step_number_len, max_name_len], one per column
        self.num_columns = 1
        for a in self.actions.values():
            if a.column_break:
                self.num_columns += 1
                self.widths.append([0, 0, 0])
            if a.task is None:
                if len(a.number) > self.widths[self.num_columns - 1][0]:
                    self.widths[self.num_columns - 1][0] = len(a.number)
            else:
                if len(a.number) > self.widths[self.num_columns - 1][1]:
                    self.widths[self.num_columns - 1][1] = len(a.number)
            if len(a.name) > self.widths[self.num_columns - 1][2]:
                self.widths[self.num_columns - 1][2] = len(a.name)
        self.col_widths = [task_num_width + step_num_width + name_width + 2
                           for task_num_width, step_num_width, name_width in self.widths]

    def init(self):
        self.app.trace(f"menu_screen.init({self.title}) {self.num_columns=}, {self.widths=}, {self.col_widths=}")

    def process_mouse(self, mouse_event):
        _, x, y, _, bstate = mouse_event
        self.app.trace(f"menu_screen.process_mouse({y=}, {x=}, bstate={tui_base.bstate_str(bstate)})")
        if self.error_field is not None:
            self.error_field.highlight()
            self.clear_message()
            self.error_field = None
        # run command
        if bstate == tui_base.curses.BUTTON1_CLICKED:
            if y == self.button_y:
                # check buttons
                for i, (button_x_first, button_x_last) in enumerate(self.command_buttons_x):
                    if button_x_first <= x <= button_x_last:
                        return self.execute(self.menu_screen_commands[i])
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
        self.app.trace(f"menu_screen.process_key({key=}) {self.active_field=}")
        if self.error_field is not None:
            self.error_field.highlight()
            self.clear_message()
            self.error_field = None
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
        self.app.trace(f"menu_screen.execute({command=})")
        match command:
            case 'Cancel':
                self.app.trace(f"Cancel command going back to screen {self.back.title}")
                return self.back
            case 'Submit':
                for field in self.fields:
                    if field.changed:
                        try:
                            field.validate()
                        except ValueError as exc:
                            field.highlight(tui_base.curses.color_pair(self.error_attr))
                            self.message(str(exc), tui_base.curses.color_pair(self.error_attr))
                            self.error_field = field
                            return None
                for field in self.fields:
                    if field.changed:
                        self.row.set(field.name, field.text)
                        field.changed = False
                self.app.set_changed()
                return self.back

    def draw_body(self):
        self.app.trace(f"draw_body(): {self.num_columns=}, {self.col_widths=}, {self.widths=}")
        fill = self.cols - sum(self.col_widths)
        gap = fill // ((self.num_columns - 1) + 4)
        self.begin_x = [gap * 2]
        for width in self.col_widths[:-1]:
            self.begin_x.append(self.begin_x[-1] + width + gap)
        self.app.trace(f"draw_body(): {fill=}, {gap=}, {self.begin_x=}")
        self.fields = []
        column = 1
        x = self.begin_x[column - 1]
        begin_y = 2
        lineno = begin_y
        self.max_y = 0
        widths = self.widths[column - 1]
        for action in self.actions.values():
            if action.column_break:
                if lineno > self.max_y:
                    self.max_y = lineno
                column += 1
                lineno = begin_y
                x = self.begin_x[column - 1]
                widths = self.widths[column - 1]
            nlines = 1
            self.app.trace(f"{action.number=}, {action.committed=}, {action.can_run()=}, {action.has_run()=}, "
                           f"{action.step.state=}, {nlines=} at {lineno=}, {x=}, {widths=}")
            w = widths[0]
            if action.task is not None:
                w += 1 + widths[1]
            self.app.stdscr.addstr(lineno, x + w - len(action.number), f"{action.number}")
            shared = field_shared(action.number, nlines, x + w + 1, widths[2], self.app)
            if action.is_task:
                attr_pair = self.task_pair
            elif not action.can_run():
                attr_pair = self.cant_run_pair
            elif action.has_run():
                attr_pair = self.may_run_pair
            else:
                attr_pair = self.must_run_pair
            self.fields.append(read_only_field(len(self.fields), action.name, shared, lineno, attr_pair=attr_pair))
            lineno += nlines
        if lineno > self.max_y:
            self.max_y = lineno
        self.app.trace(f"{self.max_y=}")
        self.active_field = None  # FIX: Still needed??

    def message(self, msg, attr):
        x = (self.cols - len(msg)) // 2  # center message
        self.app.stdscr.addstr(self.max_y + 2, x, msg, attr)
        self.msg_len = len(msg)

    def clear_message(self):
        if self.msg_len:
            x = (self.cols - self.msg_len) // 2  # center message
            self.app.stdscr.addstr(self.max_y + 2, x, ' ' * self.msg_len,
                                   tui_base.curses.color_pair(self.error_field.default_attr_pair))
            self.msg_len = 0


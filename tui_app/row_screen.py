# row_screen.py

import math

from csv_app.trace import trace
from . import tui_base
from .field import multi_line_shared


class row_screen(tui_base.screen):
    active_field = None
    _refocus = None        # screen_key to re-focus after a grow-REFRESH (None -> drop focus)
    msg_len = 0
    default_attr = 0x00
    error_attr = 0x10
    error_msg_attr = 0x10
    error_field = None

    master_row = None
    table = None

    def __init__(self, title, back=None, global_validate=None, callback=None):
        r'''
            global_validate is a function that is called on update after individual
            field validates have been done (and all passed).  This function takes
            this row_screen as its single argument, and returns an error message (to be
            displayed), if there was an error; or None if no errors.

            callback is a function that is called after a succesful Submit.  It takes no
            arguments and returns None.
        '''
        super().__init__(title, back)
        self.fields = ()
        self.global_validate = global_validate
        self.callback = callback
        self.attrs_changed = set()

    @classmethod
    def for_update(cls, row, back=None, global_validate=None, callback=None):
        ans = cls(f"{row.table_name}: {row.human_key()}", back,
                  global_validate=global_validate, callback=callback)
        ans.init_row(row)
        return ans

    @classmethod
    def for_create(cls, table, back=None, global_validate=None, callback=None):
        ans = cls(f"{table.name}: Create", back,
                  global_validate=global_validate, callback=callback)
        ans.init_table(table)
        return ans

    def init_row(self, row):
        self.master_row = row
        self.row = row.copy()
        self.columns = self.row.columns
        self.row_screen_commands = list(row.row_screen_commands) + ['Cancel', 'Apply']

    def init_table(self, table):
        self.table = table
        self.row = table.row_class(create=True)
        self.columns = self.table.columns
        self.row_screen_commands = ['Cancel', 'Create']

    def init(self):
        self.max_col_name_len = 0
        for column in self.columns:
            if len(column.name) > self.max_col_name_len:
                self.max_col_name_len = len(column.name)
        trace(f"row_screen.init({self.row.table_name}) {self.max_col_name_len=}")

    def process_mouse(self, mouse_event):
        _, x, y, _, bstate = mouse_event
        trace(f"row_screen.process_mouse({y=}, {x=}, bstate={tui_base.bstate_str(bstate)})")
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
        trace(f"row_screen.process_key({key=}) {self.active_field=}")
        if self.error_field is not None:
            self.error_field.highlight()
            self.error_field = None
        self.clear_message()
        if self.active_field is not None:
            key = self.active_field.process_key(key)
            if key == 'REFRESH':
                # the active (multi-line) field grew -> re-focus it after the redraw so the cursor
                # (which from_field restores) keeps typing where it left off
                self._refocus = self.active_field.screen_key
            if tui_base.event_handled(key):
                return key
        if key == '\x1B':                       # Esc: abort the active field edit (never leaves)
            if self.active_field is not None:
                self.abort_field(self.active_field)
                self.activate_field(None)
            return None
        if key == 'KEY_F(8)':                   # Back
            if self.attrs_changed or any(field.changed for field in self.fields):
                self.message("Unapplied changes: use Cancel or Apply to leave",
                             tui_base.curses.color_pair(self.error_msg_attr))
                return None                     # don't leave with unapplied changes
            return self.back
        if key == '\t' or key == 'KEY_ENTER' or key == '\n':   # accept, then next editable field
            if self.active_field is not None and not self.accept_field(self.active_field):
                return None                     # validation failed -> stay in the field
            offset = 0 if self.active_field is None else self.active_field.screen_key + 1
            for i in range(len(self.fields)):
                idx = (offset + i) % len(self.fields)
                if self.fields[idx].can_edit:
                    self.activate_field(self.fields[idx])
                    return None
        elif key == 'KEY_BTAB':                 # accept, then previous editable field
            if self.active_field is not None and not self.accept_field(self.active_field):
                return None
            offset = len(self.fields) if self.active_field is None else self.active_field.screen_key - 1
            for i in range(len(self.fields)):
                idx = (offset - i) % len(self.fields)
                if self.fields[idx].can_edit:
                    self.activate_field(self.fields[idx])
                    return None
        return key

    def execute(self, command):
        trace(f"row_screen.execute({command=})")
        match command:
            case 'Cancel':
                trace(f"row_screen.execute: Cancel command going back to screen {self.back.title}")
                return self.back
            case 'Apply':  # write the copy to the master row (db) + Back
                trace(f"row_screen.execute: Apply")
                if self.active_field is not None and not self.accept_field(self.active_field):
                    return None                  # active field invalid -> stay
                if not self.validate():
                    return None
                self.copy_to_master()
                if self.callback is not None:
                    self.callback()
                trace(f"row_screen.execute -> {self.back=}")
                return self.back
            case 'Create':  # creating a row
                if self.active_field is not None and not self.accept_field(self.active_field):
                    return None
                if not self.validate():
                    return None
                self.insert()
                if self.callback is not None:
                    self.callback()
                trace(f"row_screen.execute -> {self.back=}")
                return self.back
        trace(f"row_screen.execute: forwarding to base screen class")
        ans = super().execute(command)
        trace(f"row_screen.execute -> {ans}")
        return ans

    def accept_field(self, field):
        r'''Validate `field` and, if valid, write it into self.row and recompute the calculated cells.
        Returns True if accepted (or nothing to accept); False if it failed validation -- in which case
        the field is highlighted and the error message shown, and the caller should stay put.
        '''
        if not field.changed:
            return True
        try:
            field.validate()
        except ValueError as exc:
            field.highlight(tui_base.curses.color_pair(self.error_attr))
            self.message(str(exc), tui_base.curses.color_pair(self.error_msg_attr))
            self.error_field = field
            return False
        self.row.set(field.name, field.text)     # into the copy, NOT the master (that's Apply)
        self.attrs_changed.add(field.name)
        field.changed = False
        self.recompute()
        return True

    def recompute(self):
        r'''Repaint the read-only (calculated) fields from self.row so an accepted edit's effect on
        calculated columns shows immediately.
        '''
        for field in self.fields:
            if not field.can_edit:
                value = self.row.get(field.name)
                if value != field.text:
                    field.text = value
                    field.paint()

    def validate(self):
        r'''Final checks before Apply/Create: required-field check (create mode) then global_validate.
        Per-field validation already happened on accept_field.  Shows a message + returns False on
        failure, else True.
        '''
        if self.table is not None:
            try:
                self.row.check_required(self.attrs_changed)
            except ValueError as exc:
                self.message(str(exc), tui_base.curses.color_pair(self.error_msg_attr))
                return False
        if self.global_validate is not None:
            msg = self.global_validate(self)
            if msg:
                self.message(msg, tui_base.curses.color_pair(self.error_msg_attr))
                return False
        return True

    def abort_field(self, field):
        r'''Esc: discard the field's in-progress edit -- reset its text to self.row's value (the last
        accepted value, or the original if never accepted) and repaint.  self.row is the source of
        truth, so this undoes only the current edit session.
        '''
        if field.changed:
            field.text = self.row.get(field.name)
            field.changed = False
            field.paint()

    def copy_to_master(self):
        r'''Copies the values changed on the screen from self.row to self.master_row.

        Doesn't return anything.
        '''
        for attr in self.attrs_changed:
            self.master_row.set(attr, getattr(self.row, attr))
        self.app.set_changed()

    def insert(self):
        r'''Inserts the values changed on the screen from self.row.

        Doesn't return anything.
        '''
        self.table.insert(**{attr: getattr(self.row, attr) for attr in self.attrs_changed})
        self.app.set_changed()

    def draw_body(self):
        trace(f"draw_body(): {len(self.columns)=}")
        self.begin_x = self.max_col_name_len + 2
        self.width = self.cols - self.begin_x
        prior = {f.screen_key: f for f in self.fields}    # by screen_key (== column index)
        refocus = self._refocus
        self._refocus = None
        if refocus is None and self.active_field is not None:
            # not preserving focus (resize / validate): drop the old cursor so from_field, if it
            # rebuilds that field's in-progress edit, doesn't repaint a stray cursor
            self.active_field.position = None
        self.fields = []
        lineno = 2
        for i, column in enumerate(self.columns):
            self.app.stdscr.addstr(lineno, 0, f"{column.name}:")
            old = prior.get(i)
            preserve = old is not None and old.changed   # in-progress edit lives only in the field
            text = old.text if preserve else self.row.get(column.name)
            shared = multi_line_shared(column, self.begin_x, self.width, self.app,
                                       nlines=1, creating=self.table is not None)
            # size to fit the text (grow handles typing beyond this); honor edit_width as extra room
            nlines = max(1, shared.line_count(text))
            if column.edit_width is not None:
                nlines = max(nlines, math.ceil(column.edit_width / self.width))
            shared.nlines = nlines
            trace(f"{column.name=}, {len(text)=}, {nlines=} at {lineno=}, {self.begin_x=}, {preserve=}")
            if preserve:
                field = shared.from_field(old, begin_y=lineno, screen_key=i)
            else:
                field = shared.field_for(self.row, begin_y=lineno, screen_key=i)
            self.fields.append(field)
            lineno += nlines
        # after a grow-REFRESH, re-focus the field that grew (from_field already restored its cursor)
        self.active_field = None
        if refocus is not None and refocus < len(self.fields):
            self.active_field = self.fields[refocus]

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


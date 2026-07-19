# table_screen.py

from functools import partial

from csv_app.trace import trace
from . import tui_base
from .field import single_line_shared


class table_screen(tui_base.screen):
    scroll_amount = 3
    error_attr = 0x01
    view_edit_command = 'View/Edit'    # row popup command F2 runs to open the focused row

    def __init__(self, table, back=None, validate_fn=None, **select):
        r'''The validate_fn is passed the table and returns an error_message or None.
        '''
        super().__init__(table.name, back)
        self.table = table
        self.first_row = 0         # index into self.rows of top row on screen
        self.validate_fn = validate_fn
        self.select = select
        # Cell focus is the base screen's self.active_field (the focused field object); its cell is
        # active_field.screen_key == (row, col).  self.editable_cols (set in init) drives Left/Right.

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
        # indexes (into self.columns) of columns a user can focus/edit; read-only and calculated
        # columns are never focusable.  Consumed by cell-focus navigation in later batches.
        self.editable_cols = [i for i, column in enumerate(self.columns) if column.can_edit]
        trace(f"table_screen.init: {self.editable_cols=}")

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
                self._open_row_popup(self.first_row + (y - 2), y + 1)   # row popup below the row
            else:
                self._open_screen_popup()                              # table-level popup at the top
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
        trace(f"table_screen.process_key({key=})")
        match key:
            case '\x1B':                        # Esc -> Back
                return self.execute('Back')
            case 'KEY_F(1)':                    # Help
                self.show_help()
            case 'KEY_F(10)':                   # screen menu (table names, Back, Exit/Abort)
                self._open_screen_popup()
            case 'KEY_F(9)':                    # row menu for the focused row
                self._open_row_popup_for_focus()
            case 'KEY_F(2)':                    # open the focused row in row_screen (View/Edit)
                return self._view_edit_focused_row()
            case 'KEY_DOWN':                    # move cell focus down one row (same column)
                self._move_focus_row(1)
            case 'KEY_UP':                      # move cell focus up one row (same column)
                self._move_focus_row(-1)
            case 'KEY_RIGHT' | '\t':            # next editable column (wraps to next row)
                self._move_focus_col(1)
            case 'KEY_LEFT' | 'KEY_BTAB':       # previous editable column (wraps to previous row)
                self._move_focus_col(-1)
            case 'KEY_NPAGE':                   # Page Down: scroll a page (focus may scroll off)
                self.scroll_up(self.lines - 3)
            case 'KEY_PPAGE':                   # Page Up: scroll a page
                self.scroll_down(self.lines - 3)
            case 'KEY_HOME':                    # scroll to the top
                if self.first_row:
                    self.scroll_down(self.first_row)
            case 'KEY_END':                     # scroll to the bottom
                rows_left = len(self.rows) - self.first_row
                if rows_left > self.lines - 2:
                    self.scroll_up(rows_left - (self.lines - 3))
            case _:
                return key

    def _open_row_popup(self, row_index, y):
        r'''Open the per-row popup (row.row_popup_commands) for rows[row_index], drawn at screen line
        y.  Shared by right-click (on a row) and F9.
        '''
        if self.popup is not None:
            self.popup.delete()
        self.popup_y = row_index - self.first_row
        row = self.rows[row_index]
        trace(f"table_screen._open_row_popup({row_index=}, {y=}): {row=}, {row.row_popup_commands=}")
        self.popup = tui_base.popup_menu(row.human_key(), self, row.row_popup_commands,
                                         partial(row.execute, self), y, 4)

    def _open_screen_popup(self):
        r'''Open the screen-level popup (table commands + Back/Exit/Abort).  Shared by right-click
        (top rows) and F10.  If a screen popup is already open, leave it in place.
        '''
        if self.popup is not None and self.popup_y is None:
            return                          # screen popup already open -- keep using it
        if self.popup is not None:
            self.popup.delete()             # replace an open row popup
        self.popup_y = None
        trace(f"table_screen._open_screen_popup(): {self.screen_popup_commands=}")
        self.popup = tui_base.popup_menu("Screen", self, self.screen_popup_commands,
                                         self.execute, 1, 4)

    def _open_row_popup_for_focus(self):
        r'''F9: open the row popup for the focused row.  Focus the top visible row first if nothing is
        focused; no-op when there are no rows.
        '''
        if not self.rows:
            return
        if self.active_field is None:
            self._move_focus_row(1)         # focus the top visible row
        if self.active_field is None:
            return
        row_index = self.active_field.screen_key[0]
        y = (row_index - self.first_row) + 2   # screen line of that row
        self._open_row_popup(row_index, y + 1)

    def _view_edit_focused_row(self):
        r'''F2: open the focused row (runs the row's view_edit_command, e.g. "View/Edit").  Focus the
        top visible row first if nothing is focused.  Returns the screen to switch to (the row's
        execute result, normally a row_screen), or None to stay.
        '''
        if not self.rows:
            return None
        if self.active_field is None:
            self._move_focus_row(1)             # focus the top visible row
        if self.active_field is None:
            return None
        row = self.rows[self.active_field.screen_key[0]]
        if self.view_edit_command not in row.row_popup_commands:
            trace(f"table_screen._view_edit_focused_row: {self.view_edit_command!r} not offered by row")
            return None
        return row.execute(self, self.view_edit_command)

    def scroll_up(self, nlines):
        trace(f"scroll_up({nlines})")
        if len(self.rows) - self.first_row - nlines < self.lines - 3:
            first_row = len(self.rows) - (self.lines - 3)
            nlines = first_row - self.first_row
            trace(f"adjusted {nlines=}")
        if nlines > 0:
            self.first_row += nlines
            self._reindex_row_fields()
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
            self._reindex_row_fields()
            self.app.stdscr.move(2, 0)
            if nlines > self.lines - 2:
                trace(f"scroll_down: {nlines=} too great, clear whole screen insdelln({-(self.lines - 2)})")
                self.app.stdscr.insdelln(-(self.lines - 2))
                self.draw_rows(self.first_row)
            else:
                self.app.stdscr.insdelln(nlines)
                self.draw_rows(self.first_row, 2, nlines)

    def _reindex_row_fields(self):
        r'''Maintain row_fields after a scroll changed first_row (and insdelln shifted the glyphs):
        update each retained field's begin_y to its new screen line, and drop entries for rows that
        scrolled off-screen.  draw_rows then (re)adds the newly-exposed rows.  This is a pure
        dict/attr update (no screen reads), safe to run on the live scroll path.
        '''
        visible = self.lines - 2
        for row_index in list(self.row_fields):
            new_line = 2 + (row_index - self.first_row)
            if 2 <= new_line < 2 + visible:
                for field in self.row_fields[row_index]:
                    field.begin_y = new_line
            else:
                del self.row_fields[row_index]
        # if the focused cell's row scrolled off-screen, drop focus (its row is gone from row_fields)
        if self.active_field is not None and self.active_field.screen_key[0] not in self.row_fields:
            self.active_field = None
        trace(f"_reindex_row_fields: keys now {sorted(self.row_fields)}, {self.first_row=}")

    def _focus_cell(self, row, col):
        r'''Focus the cell at (row, col) -- col is 0 for a read-only table.  The base activate_field
        deactivates the previously focused cell and highlights this one (editable -> select-all,
        read-only -> reverse_attr).  The row must be on screen (present in row_fields).
        '''
        self.activate_field(self.row_fields[row][col])

    def _default_col(self):
        r'''Column to focus when there is no current column: the first editable column, or 0 for a
        read-only table (whole-row focus on the first field).
        '''
        return self.editable_cols[0] if self.editable_cols else 0

    def _ensure_visible(self, row):
        r'''Scroll the viewport minimally so that row index `row` is on screen.'''
        visible = self.lines - 2
        if row < self.first_row:
            self.scroll_down(self.first_row - row)
        elif row > self.first_row + visible - 1:
            self.scroll_up(row - (self.first_row + visible - 1))

    def _move_focus_row(self, delta):
        r'''Move cell focus up/down by delta rows, keeping the same column (auto-scroll to stay
        visible).  With nothing focused yet, the first keypress focuses the top visible row.
        '''
        if not self.rows:
            return
        if self.active_field is None:
            # first keypress: Down starts at the top visible row, Up at the bottom visible row
            if delta > 0:
                row = self.first_row
            else:
                row = min(self.first_row + (self.lines - 2) - 1, len(self.rows) - 1)
            col = self._default_col()
        else:
            row, col = self.active_field.screen_key
            row = max(0, min(row + delta, len(self.rows) - 1))
        self._ensure_visible(row)
        self._focus_cell(row, col)

    def _move_focus_col(self, delta):
        r'''Move cell focus to the previous/next editable column (delta -1/+1), wrapping to the
        adjacent row's last/first editable column at the ends.  No-op when there are no editable
        columns.  With nothing focused yet, the first keypress focuses the top visible row's first
        editable cell.
        '''
        if not self.rows or not self.editable_cols:
            return
        if self.active_field is None:
            # first keypress: Right starts at the first editable col, Left at the last
            col = self.editable_cols[0] if delta > 0 else self.editable_cols[-1]
            self._ensure_visible(self.first_row)
            self._focus_cell(self.first_row, col)
            return
        row, col = self.active_field.screen_key
        ci = self.editable_cols.index(col) + delta
        if ci < 0:
            row, ci = row - 1, len(self.editable_cols) - 1     # wrap to previous row's last col
        elif ci >= len(self.editable_cols):
            row, ci = row + 1, 0                                # wrap to next row's first col
        if not (0 <= row < len(self.rows)):
            return                                             # at the very first/last cell: no move
        self._ensure_visible(row)
        self._focus_cell(row, self.editable_cols[ci])

    def show_help(self):
        r'''F1 help -- grows as more keys (and mouse) are added (F9/F10/F2/DEL, editing).'''
        help_lines = [
            "Arrows ............. move cell selection",
            "Tab / Shift-Tab .... next / prev editable cell",
            "PgUp / PgDn ........ scroll a page",
            "Home / End ......... scroll to top / bottom",
            "F10 / F9 ........... screen menu / row menu",
            "F2 ................. open the focused row",
            "Esc ................ back",
            "F1 ................. this help",
        ]
        self.popup = tui_base.popup_message("Navigation", self, help_lines)

    def execute(self, command):
        trace(f"table_screen.execute({command=})")
       #match command:
       #    case 'Cancel':
        trace(f"table_screen.execute: forwarding to table")
        ans = self.table.execute(self, command)
        if ans == 'Continue':
            trace(f"table_screen.execute: forwarding to base screen class")
            ans = super().execute(command)
        trace(f"table_screen.execute -> {ans}")
        return ans

    def draw_body(self):
        self.rows = self.table.get_rows(self.app, **self.select)
        trace(f"draw_body(): {len(self.rows)=}")
        # remember the focused cell so it survives a full redraw (resize, or returning from a row
        # form / popup); restored after the fields are rebuilt, if that row is still on screen
        focus_key = self.active_field.screen_key if self.active_field is not None else None
        max_lens = []
        column_names = []
        self.row_fields = {}   # {abs_row_index -> [one field per column]}, (re)built by draw_rows
        self.active_field = None   # fields are recreated below; focus is restored from focus_key
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
            column_names.append(name)
            if len(name) > max_len:
                max_len = len(name)
            max_lens.append(max_len)
            self.field_shareds.append(single_line_shared(column, name, begin_x, max_len, self.app))
            begin_x += max_len + 1
        self.width = begin_x - 1
        trace(f"table_screen.draw_body({self.table.name=}, {self.width=})")
        for col, max_len in zip(column_names, max_lens):
            trace(f"{col=}, {max_len=}")
        values = [f"{name:<{max_len}}" if column.alignment == 'left' else f"{name:>{max_len}}"
                  for column, name, max_len
                   in zip(self.columns, column_names, max_lens)]
        self.app.stdscr.addstr(1, 0, ' '.join(values),
                          #tui_base.curses.A_PROTECT)    # no effect
                          #tui_base.curses.A_UNDERLINE)  # not too bad
                          #tui_base.curses.A_LOW)        # no effect
                          #tui_base.curses.A_BOLD)       # just barely...
                           tui_base.curses.A_REVERSE)    # just barely...
                          #tui_base.curses.color_pair(0xF0))       # not seeing a difference between high/low white...
                          #tui_base.curses.color_pair(0xFf))       # solid white...
        self.draw_rows(self.first_row)
        if focus_key is not None and focus_key[0] in self.row_fields:
            self._focus_cell(*focus_key)          # restore focus after a full redraw

    def draw_rows(self, first_row=0, first_line=2, nlines=None):
        if nlines is None:
            nlines = self.lines - first_line
        trace(f"draw_rows({first_row=}, {first_line=}, {nlines=})")
        for lineno, row in enumerate(self.rows[first_row:], first_line):
            if lineno - first_line == nlines:
                break
            row_index = first_row + (lineno - first_line)
            fields = []
            for col, shared in enumerate(self.field_shareds):
                fields.append(shared.field_for(row, begin_y=lineno, screen_key=(row_index, col)))
            self.row_fields[row_index] = fields
        trace(f"draw_rows: row_fields keys now {sorted(self.row_fields)}")


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
                # row popup
                if self.popup is not None:
                    self.popup.delete()
                self.popup_y = y - 2  # selected row#
                row = self.rows[self.first_row + self.popup_y]
                trace(f"screen.process_mouse creating popup for row {self.first_row + self.popup_y}, "
                               f"{row=}, commands={row.row_popup_commands}")
                self.popup = tui_base.popup_menu(row.human_key(), self, row.row_popup_commands,
                                                 partial(row.execute, self), y + 1, 4)
            else:
                # table level popup at top of screen
                if self.popup is not None:
                    if self.popup_y is not None:   # this is a row popup, replace it
                        self.popup.delete()
                    else:
                        return None                # this is a table level popup, just keep using it...
                self.popup_y = None
                self.popup = tui_base.popup_menu("Screen", self, self.screen_popup_commands,
                                                 self.execute, 1, 4)
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
            case 'KEY_DOWN':                    # move cell focus down one row (same column)
                self._move_focus_row(1)
            case 'KEY_UP':                      # move cell focus up one row (same column)
                self._move_focus_row(-1)
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
            row, col = self.first_row, self._default_col()
        else:
            row, col = self.active_field.screen_key
            row = max(0, min(row + delta, len(self.rows) - 1))
        self._ensure_visible(row)
        self._focus_cell(row, col)

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
        max_lens = []
        column_names = []
        self.row_fields = {}   # {abs_row_index -> [one field per column]}, (re)built by draw_rows
        self.active_field = None   # a full (re)draw recreates fields, so focus is dropped (e.g. on resize)
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
            self.field_shareds.append(field_shared(name, 1, begin_x, max_len, self.app, column.validate,
                                                   column.alignment, left_placeholder="<", right_placeholder=">"))
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

    def draw_rows(self, first_row=0, first_line=2, nlines=None):
        if nlines is None:
            nlines = self.lines - first_line
        trace(f"draw_rows({first_row=}, {first_line=}, {nlines=})")
        for lineno, row in enumerate(self.rows[first_row:], first_line):
            if lineno - first_line == nlines:
                break
            row_index = first_row + (lineno - first_line)
            fields = []
            for col, (column, field_shared) in enumerate(zip(self.columns, self.field_shareds)):
                if column.can_edit:
                    f_type = editable_field
                else:
                    f_type = read_only_field
                fields.append(f_type((row_index, col), row.get(column.name), field_shared, lineno,
                                     attr_pair=column.column_attr_pair(row)))
            self.row_fields[row_index] = fields
        trace(f"draw_rows: row_fields keys now {sorted(self.row_fields)}")


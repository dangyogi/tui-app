# table_screen.py

from functools import partial

from csv_app.trace import trace
from . import tui_base
from .field import single_line_shared


class table_screen(tui_base.screen):
    scroll_amount = 3
    error_attr = 0x01
    view_edit_command = 'View/Edit'    # row popup command F2 runs to open the focused row
    delete_command = 'Delete'          # row command F5 runs (after confirm) to delete the focused row
    create_command = 'Create'          # table command INS runs to create a new row
    help_lines = [                     # F1 help (base screen.show_help renders it); grows over time
        "Up / Down .......... move to the previous / next row",
        "Left / Right ....... move the cursor in the cell",
        "Tab / Shift-Tab .... next / prev editable cell",
        "type ............... edit the cell (Enter or Tab commits)",
        "Esc ................ discard the cell edit",
        "PgUp / PgDn ........ scroll a page",
        "Home / End ......... scroll to top / bottom",
        "Ins / F5 ........... create row / delete focused row",
        "F2 ................. open the focused row",
        "F10 / F9 ........... screen menu / row menu",
        "F8 ................. back",
        "F12 ................ exit the app",
        "F1 ................. this help",
    ]

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
        mouse_event = super().process_mouse(mouse_event)   # popup routing first
        if tui_base.event_handled(mouse_event):
            return mouse_event
        _, x, y, _, bstate = mouse_event
        curses = tui_base.curses
        trace(f"table_screen.process_mouse({y=}, {x=}, bstate={tui_base.bstate_str(bstate)})")
        if bstate == curses.BUTTON3_CLICKED:
            if y >= 2:
                self._open_row_popup(self.first_row + (y - 2), y + 1)   # row popup below the row
            else:
                self._open_screen_popup()                              # table-level popup at the top
            return None
        if bstate == curses.BUTTON4_PRESSED:
            self.scroll_down(self.scroll_amount)
            return None
        if bstate == curses.BUTTON5_PRESSED:
            self.scroll_up(self.scroll_amount)
            return None
        if bstate in (curses.BUTTON1_CLICKED, curses.BUTTON1_DOUBLE_CLICKED,
                      curses.BUTTON1_TRIPLE_CLICKED, curses.BUTTON1_PRESSED):
            return self._button1(mouse_event, y, x)
        if bstate in (curses.REPORT_MOUSE_POSITION, curses.BUTTON1_RELEASED):
            # continue an in-progress drag-select, clamping the pointer into the focused cell so a drag
            # that wanders into another row/column just selects out to this cell's edge
            field = self.active_field
            if getattr(field, 'in_select', False):
                cy = min(max(y, field.begin_y), field.begin_y + field.nlines - 1)
                cx = min(max(x, field.begin_x), field.begin_x + field.ncols - 1)
                field.process_mouse((mouse_event[0], cx, cy, mouse_event[3], bstate))
                return None
        return mouse_event

    def _button1(self, mouse_event, y, x):
        r'''LEFT click/press on a data row: focus the cell under the pointer, committing the previously
        focused cell.  Only editable cells are hit-testable (read_only.enclose is always False), so a
        click landing on an editable cell focuses it and routes the event to its field (cursor position
        / word- or all-select / drag start); a click elsewhere on the row (a read-only cell or the gap,
        or any cell of a fully read-only table) focuses the row -- its first editable cell, or column 0.
        '''
        if y < 2:
            return mouse_event                       # header / above the data -> bubble
        row = self.first_row + (y - 2)
        if row not in self.row_fields:
            return mouse_event                       # below the last visible row -> bubble
        for field in self.row_fields[row]:
            if field.enclose(y, x):                  # an editable cell under the pointer
                if self._focus_cell(row, field.screen_key[1]):   # focus (may block on a bad commit)
                    self.active_field.process_mouse(mouse_event)  # position cursor / select / drag
                return None
        self._focus_cell(row, self._default_col())   # not on an editable cell -> focus the row
        return None

    def process_key(self, key):
        key = super().process_key(key)          # popup routing + common keys (F8 Back, F1 help)
        if tui_base.event_handled(key):
            return key
        trace(f"table_screen.process_key({key=})")
        match key:                              # screen navigation (F1/F8 handled by base screen)
            case 'KEY_F(2)':                    # open the focused row in row_screen (View/Edit)
                return self._view_edit_focused_row()
            case 'KEY_F(5)':                    # delete the focused row (with y/n confirm)
                self._confirm_delete_focused_row(); return None
            case 'KEY_F(9)':                    # row menu for the focused row
                self._open_row_popup_for_focus(); return None
            case 'KEY_F(10)':                   # screen menu (table names, Back, Exit/Abort)
                self._open_screen_popup(); return None
            case 'KEY_IC':                      # Insert -> create a new row (if the table offers it)
                return self._create_row()
            case 'KEY_DOWN' | 'KEY_ENTER' | '\n':   # down a row (commits the current cell; Enter too)
                self._move_focus_row(1); return None
            case 'KEY_UP':                      # up a row
                self._move_focus_row(-1); return None
            case '\t':                          # next editable cell (wraps rows)
                self._move_focus_col(1); return None
            case 'KEY_BTAB':                    # previous editable cell
                self._move_focus_col(-1); return None
            case 'KEY_NPAGE':                   # Page Down: scroll a page
                self.scroll_up(self.lines - 3); return None
            case 'KEY_PPAGE':                   # Page Up: scroll a page
                self.scroll_down(self.lines - 3); return None
            case 'KEY_HOME':                    # scroll to the top
                if self.first_row:
                    self.scroll_down(self.first_row)
                return None
            case 'KEY_END':                     # scroll to the bottom
                rows_left = len(self.rows) - self.first_row
                if rows_left > self.lines - 2:
                    self.scroll_up(rows_left - (self.lines - 3))
                return None
        # Left/Right (cursor), typing, Delete, Esc act on the focused cell
        if self.active_field is not None:
            key = self._cell_key(key)
            if tui_base.event_handled(key):
                return key
        return key                              # not handled here -> bubble up

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

    def _confirm_delete_focused_row(self):
        r'''DEL: pop a y/n confirm to delete the focused row.  Focus the top visible row first if
        nothing is focused; no-op if the row doesn't offer delete_command or there are no rows.  The
        actual delete happens in _do_delete (on Yes); focus auto-advances via draw_body restoring the
        same row index (now the next row).
        '''
        if not self.rows:
            return
        if self.active_field is None:
            self._move_focus_row(1)             # focus the top visible row
        if self.active_field is None:
            return
        row_index = self.active_field.screen_key[0]
        row = self.rows[row_index]
        if self.delete_command not in row.row_popup_commands:
            trace(f"table_screen._confirm_delete_focused_row: {self.delete_command!r} not offered")
            return
        if self.popup is not None:
            self.popup.delete()
        self.popup_y = row_index - self.first_row
        y = (row_index - self.first_row) + 2    # screen line of the row
        self.popup = tui_base.popup_confirm(f"Delete {row.human_key()}?", self,
                                            partial(self._do_delete, row_index), y + 1, 4)

    def _do_delete(self, row_index, choice):
        r'''popup_confirm callback: on 'Yes' run the row's delete command (which usually returns
        'REFRESH'); 'No' cancels.
        '''
        if choice != 'Yes':
            return None
        return self.rows[row_index].execute(self, self.delete_command)

    def _create_row(self):
        r'''INS: create a new row if the table offers create_command (advertised in
        screen_popup_commands).  Returns the screen to switch to (normally a row_screen) or None.
        '''
        if self.create_command in self.table.screen_popup_commands:
            return self.execute(self.create_command)
        trace(f"table_screen._create_row: {self.create_command!r} not offered by table")
        return None

    def _cell_key(self, key):
        r'''Route an edit key (Left/Right cursor, typing, Delete, Esc-abort) to the focused cell.  The
        field consumes what it can (Esc aborts the edit + re-selects, staying focused); TAB/BTAB/UP/
        DOWN/Enter are handled as navigation in process_key and never reach here.
        '''
        field = self.active_field
        if not field.can_edit:
            return key                          # read-only focused cell: nothing to edit
        result = field.process_key(key)
        if tui_base.event_handled(result):
            return result                       # field handled it (None) or returned a sentinel
        return key                              # Left/Right at a text edge, etc.: bubble (no-op)

    def _commit_edit(self):
        r'''Write the focused cell through to its row if it changed (marking the app changed) and
        recompute that row's calculated cells.  Returns True on success (or nothing to commit); on a
        validation error (column.validate / to_python raising ValueError) pops an error message and
        returns False so the caller (_focus_cell) leaves focus on the cell to be fixed.  Write-through
        does NOT Save; that stays a separate app command.
        '''
        field = self.active_field
        if field is None or not field.can_edit or not field.changed:
            return True
        row, col = field.screen_key
        name = self.columns[col].name
        try:
            if field.text.strip():           # empty is a required-check concern, not the converter's
                field.validate()             # column.validate may raise ValueError
            self.rows[row].set(name, field.text)   # to_python may also raise ValueError
        except ValueError as exc:
            self._cell_error(str(exc))
            return False
        self.app.set_changed()
        field.changed = False
        field.snapshot = field.text              # new abort baseline: a later Esc undoes to HERE
        self._recompute_row(row)
        return True

    def _cell_error(self, msg):
        r'''Pop an error message for a failed cell commit (replacing any current popup).'''
        if self.popup is not None:
            self.popup.delete()
        self.popup = tui_base.popup_message('Error', self, msg, self.error_attr)

    def _recompute_row(self, row):
        r'''Repaint the read-only (calculated) cells in `row` from self.rows[row] -- in place, no
        rebuild -- so a committed edit's effect on calculated columns shows immediately.  A calculated
        cell that can't compute yet (e.g. a foreign-key lookup on a not-yet-valid key raises) blanks
        instead of crashing.
        '''
        if row not in self.row_fields:
            return
        for j, f in enumerate(self.row_fields[row]):
            if not f.can_edit:
                try:
                    value = self.rows[row].get(self.columns[j].name)
                except Exception as exc:
                    trace(f"table_screen._recompute_row({row=}): {self.columns[j].name}: "
                          f"{type(exc).__name__}: {exc} -> blank")
                    value = ''
                if value != f.text:
                    f.text = value
                    f.paint()

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
        r'''Focus the cell at (row, col) -- col is 0 for a read-only table.  Commits the previously
        focused cell first (moving focus is how an edit is committed); if that commit fails validation
        the move is aborted (an error popup is up and focus stays on the bad cell) and this returns
        False.  An editable cell becomes live: it left-aligns (cursor visible) and select-alls; the
        previous editable cell reverts to its column's display alignment.  Returns True on success.
        The row must be on screen (present in row_fields).
        '''
        field = self.row_fields[row][col]
        if self.active_field is field:
            return True
        old = self.active_field
        if old is not None:
            if not self._commit_edit():          # write-through the old cell's edit (if any)
                return False                     # invalid edit -> stay on the old cell
            old.deactivate()                     # clear its cursor / highlight
            if old.can_edit:
                old.editing = False
                old.paint()                      # re-render at the column's display alignment
        self.active_field = field
        if field.can_edit:
            field.editing = True
            field.paint()                        # re-render left-aligned for the cursor
        field.activate()                         # editable -> select-all; read-only -> reverse
        return True

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

    def _bottom_visible_row(self):
        r'''Absolute index of the bottom row currently on screen.'''
        return min(self.first_row + (self.lines - 2) - 1, len(self.rows) - 1)

    def _move_focus_row(self, delta):
        r'''Move cell focus up/down by delta rows, keeping the same column.  A normal move auto-scrolls
        to stay visible; moving off the top/bottom of the table WRAPS to the bottom/top visible row
        (staying on screen -- no jump to the far end).  With nothing focused yet, the first keypress
        focuses the top (Down) or bottom (Up) visible row.
        '''
        if not self.rows:
            return
        n = len(self.rows)
        if self.active_field is None:
            row = self.first_row if delta > 0 else self._bottom_visible_row()
            col = self._default_col()
        else:
            row, col = self.active_field.screen_key
            target = row + delta
            if target < 0:
                row = self._bottom_visible_row()    # wrapped off the top -> bottom visible row
            elif target >= n:
                row = self.first_row                # wrapped off the bottom -> top visible row
            else:
                row = target
                self._ensure_visible(row)           # normal move: auto-scroll to keep it visible
        self._focus_cell(row, col)

    def _move_focus_col(self, delta):
        r'''Move cell focus to the previous/next editable cell (delta -1/+1), wrapping to the adjacent
        row's last/first editable column at the column ends, and off the top/bottom of the table to
        the bottom/top visible row (staying on screen).  No-op when there are no editable columns.
        With nothing focused yet, the first keypress focuses the top visible row's first (Tab) or last
        (Shift-Tab) editable cell.
        '''
        if not self.rows or not self.editable_cols:
            return
        n = len(self.rows)
        if self.active_field is None:
            col = self.editable_cols[0] if delta > 0 else self.editable_cols[-1]
            self._focus_cell(self.first_row, col)
            return
        row, col = self.active_field.screen_key
        ci = self.editable_cols.index(col) + delta
        if ci < 0:
            row, ci = row - 1, len(self.editable_cols) - 1     # wrap to previous row's last col
        elif ci >= len(self.editable_cols):
            row, ci = row + 1, 0                                # wrap to next row's first col
        if row < 0:
            row = self._bottom_visible_row()                   # wrapped off the top -> bottom visible
        elif row >= n:
            row = self.first_row                               # wrapped off the bottom -> top visible
        else:
            self._ensure_visible(row)
        self._focus_cell(row, self.editable_cols[ci])

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
        if focus_key is not None and self.rows:
            # restore focus after a full redraw; clamp the row so deleting the last row advances to
            # the new last row (auto-advance falls out of keeping the same row index)
            row = min(focus_key[0], len(self.rows) - 1)
            if row in self.row_fields:
                self._focus_cell(row, focus_key[1])

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


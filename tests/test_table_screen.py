# test_table_screen.py

r'''Tests for table_screen navigation state.

Follows the lightweight pattern in test_field_interaction.py: the `app` is a plain Mock (so every
curses drawing call on app.stdscr is silently absorbed), and only the specific curses bits that need a
live terminal are monkeypatched.  These tests assert on navigation *state*, not on what is drawn.
'''

from unittest.mock import Mock

import pytest

from tui_app import tui_base
from tui_app.table_screen import table_screen
from tui_app.field import editable


@pytest.fixture(autouse=True)
def patch_curses(monkeypatch):
    # color_pair needs a live terminal; identity is enough for these state-focused tests.
    monkeypatch.setattr(tui_base.curses, "color_pair", lambda n: n)


class FakeColumn:
    r'''Minimal stand-in for a consuming app's column object.'''
    def __init__(self, name, can_edit=False, min_width=None, abbr=None, alignment="left"):
        self.name = name
        self.can_edit = can_edit
        self.min_width = min_width
        self.abbr = abbr or name   # matches csv_app Column: abbr defaults to the name
        self.alignment = alignment

    def validate(self, s):
        pass

    def column_attr_pair(self, row):
        return None


class FakeTable:
    r'''Minimal stand-in for a consuming app's table object.'''
    screen_popup_commands = ()

    def __init__(self, name, columns, rows=()):
        self.name = name
        self.columns = columns
        self._rows = rows

    def get_rows(self, app, **select):
        return list(self._rows)

    def execute(self, screen, command):
        return 'Continue'


class FakeRow:
    r'''Minimal stand-in for a consuming app's row object.

    get() raises KeyError for an unknown column, like the real row.
    '''
    row_popup_commands = ('View/Edit', 'Delete')

    def __init__(self, **values):
        self._values = values

    def get(self, name):
        return str(self._values[name])

    def set(self, name, value):
        self._values[name] = value

    def human_key(self):
        return self.get("item")

    def execute(self, screen, command):
        return 'Continue'


@pytest.fixture
def columns():
    # mix of read-only and editable columns, like Inv_checklist
    return [
        FakeColumn("item"),                       # 0: read-only
        FakeColumn("num_pkgs", can_edit=True),    # 1: editable
        FakeColumn("unit"),                       # 2: read-only (calculated in the real app)
        FakeColumn("num_units", can_edit=True),   # 3: editable
    ]


@pytest.fixture
def screen(columns):
    scr = table_screen(FakeTable("Inv", columns))
    scr.app = Mock(name="app")
    scr.init()
    return scr


def test_editable_cols(screen):
    assert screen.editable_cols == [1, 3]


def test_focus_starts_unset(screen):
    assert screen.active_field is None


def make_rows(n):
    return [FakeRow(item=f"item{i}", num_pkgs=i, unit="ea", num_units=2 * i) for i in range(n)]


def make_rows_ab(n):
    return [FakeRow(a=f"a{i}", b=f"b{i}") for i in range(n)]


def test_row_fields_built(columns):
    scr = table_screen(FakeTable("Inv", columns, make_rows(3)))
    scr.app = Mock(name="app")
    scr.lines = 24
    scr.cols = 80
    scr.init()
    scr.draw_body()
    # one entry per row, keyed by absolute row index
    assert sorted(scr.row_fields) == [0, 1, 2]
    # each row holds one field per column, in column order
    for fields in scr.row_fields.values():
        assert len(fields) == len(columns)
    # editable columns -> editable behavior mixin; read-only columns -> not
    row0 = scr.row_fields[0]
    assert not isinstance(row0[0], editable)   # item: read-only
    assert isinstance(row0[1], editable)       # num_pkgs: editable
    assert not isinstance(row0[2], editable)   # unit: read-only
    assert isinstance(row0[3], editable)       # num_units: editable


def make_drawn_screen(columns, n_rows, lines=6):
    r'''A table_screen drawn once with n_rows rows; lines=6 -> 4 visible row lines (2..5).'''
    scr = table_screen(FakeTable("Inv", columns, make_rows(n_rows)))
    scr.app = Mock(name="app")
    scr.app.stdscr.inch.return_value = 0         # reverse_attr (read-only focus) reads inch as an int
    scr.lines = lines
    scr.cols = 80
    scr.init()
    scr.draw_body()
    return scr


def test_scroll_up_maintains_row_fields(columns):
    scr = make_drawn_screen(columns, 10)          # visible = 4 rows: indices 0..3
    assert sorted(scr.row_fields) == [0, 1, 2, 3]
    scr.scroll_up(1)                              # first_row -> 1
    assert sorted(scr.row_fields) == [1, 2, 3, 4]
    assert scr.row_fields[1][0].begin_y == 2      # retained row shifted to the top line
    assert scr.row_fields[4][0].begin_y == 5      # newly exposed row at the bottom line
    assert 0 not in scr.row_fields                # scrolled off the top


def test_scroll_down_maintains_row_fields(columns):
    scr = make_drawn_screen(columns, 10)
    scr.scroll_up(2)                              # first_row -> 2, keys {2,3,4,5}
    assert sorted(scr.row_fields) == [2, 3, 4, 5]
    scr.scroll_down(1)                            # first_row -> 1
    assert sorted(scr.row_fields) == [1, 2, 3, 4]
    assert scr.row_fields[1][0].begin_y == 2      # newly exposed row at the top line
    assert 5 not in scr.row_fields                # scrolled off the bottom


def test_screen_key_is_row_col(columns):
    scr = make_drawn_screen(columns, 3)
    assert scr.row_fields[0][1].screen_key == (0, 1)
    assert scr.row_fields[2][3].screen_key == (2, 3)


def test_focus_cell(columns):
    scr = make_drawn_screen(columns, 3)
    scr._focus_cell(0, 1)                         # editable column
    field = scr.row_fields[0][1]
    assert scr.active_field is field
    assert field.position == 0
    assert field.selection_len == len(field.get_text())   # editable activate = select-all
    scr._focus_cell(2, 3)                         # move focus to another cell
    assert scr.active_field is scr.row_fields[2][3]


def test_focus_dropped_when_scrolled_off(columns):
    scr = make_drawn_screen(columns, 10)          # visible rows 0..3
    scr._focus_cell(0, 1)
    assert scr.active_field is not None
    scr.scroll_up(2)                              # rows 0,1 scroll off the top
    assert scr.active_field is None


# --- task 4M: BUTTON1 mouse (focus a cell / route to the field / drag) -----------------------------

def _click(scr, field, bstate):
    return scr.process_mouse((0, field.begin_x, field.begin_y, 0, bstate))


def test_left_click_focuses_editable_cell(columns):
    scr = make_drawn_screen(columns, 3)
    target = scr.row_fields[1][1]                 # row 1, editable num_pkgs
    assert _click(scr, target, tui_base.curses.BUTTON1_CLICKED) is None
    assert scr.active_field is target
    assert target.editing                         # editable focused cell is live (left-aligned)


def test_left_click_read_only_cell_focuses_row(columns):
    scr = make_drawn_screen(columns, 3)
    target = scr.row_fields[2][0]                 # row 2, read-only item
    assert _click(scr, target, tui_base.curses.BUTTON1_CLICKED) is None
    assert scr.active_field is scr.row_fields[2][1]   # focuses the row's first editable column


def test_left_click_commits_previous_cell(columns):
    scr = make_drawn_screen(columns, 3)
    scr._focus_cell(0, 1)
    scr.active_field.text = "9"
    scr.active_field.changed = True
    _click(scr, scr.row_fields[1][3], tui_base.curses.BUTTON1_CLICKED)
    assert scr.rows[0].get("num_pkgs") == "9"     # old cell written through on focus change
    assert scr.active_field is scr.row_fields[1][3]


def test_fully_read_only_table_click_focuses_column_0():
    cols = [FakeColumn("a"), FakeColumn("b")]     # no editable columns
    scr = table_screen(FakeTable("RO", cols, make_rows_ab(3)))
    scr.app = Mock(name="app")
    scr.app.stdscr.inch.return_value = 0
    scr.lines = 6
    scr.cols = 80
    scr.init()
    scr.draw_body()
    _click(scr, scr.row_fields[1][1], tui_base.curses.BUTTON1_CLICKED)
    assert scr.active_field is scr.row_fields[1][0]   # read-only table -> focus the row (col 0)


def test_click_above_data_rows_bubbles(columns):
    scr = make_drawn_screen(columns, 3)
    ev = (0, 5, 1, 0, tui_base.curses.BUTTON1_CLICKED)   # y=1 is the header, not a data row
    assert scr.process_mouse(ev) is ev
    assert scr.active_field is None


def test_drag_routes_to_focused_cell(columns):
    scr = make_drawn_screen(columns, 3)
    target = scr.row_fields[0][1]
    _click(scr, target, tui_base.curses.BUTTON1_PRESSED)   # press -> focus + start drag
    assert scr.active_field is target
    assert target.in_select
    # a motion report continues the drag on the focused cell (handled, not bubbled)
    assert scr.process_mouse((0, target.begin_x + 1, target.begin_y, 0,
                              tui_base.curses.REPORT_MOUSE_POSITION)) is None


def test_drag_outside_cell_is_clamped(columns):
    # dragging into another row/column must not crash (to_index asserts on out-of-bounds coords)
    scr = make_drawn_screen(columns, 3)
    target = scr.row_fields[0][1]
    _click(scr, target, tui_base.curses.BUTTON1_PRESSED)
    # drag well above and to the right of the cell -> clamped to the cell, still handled
    assert scr.process_mouse((0, target.begin_x + 999, target.begin_y - 5, 0,
                              tui_base.curses.REPORT_MOUSE_POSITION)) is None
    assert scr.process_mouse((0, 0, target.begin_y + 5, 0,
                              tui_base.curses.BUTTON1_RELEASED)) is None
    assert not target.in_select                    # release ended the drag


def test_focus_preserved_on_full_redraw(columns):
    scr = make_drawn_screen(columns, 3)
    scr._focus_cell(0, 1)
    assert scr.active_field is not None
    scr.draw_body()                              # full redraw recreates fields, restores focus
    assert scr.active_field is scr.row_fields[0][1]   # same cell re-focused (new field object)


def test_focus_clamped_on_redraw_when_rows_shrink(columns):
    scr = make_drawn_screen(columns, 3)
    scr._focus_cell(2, 1)
    scr.table._rows = scr.table._rows[:1]        # rows 1,2 removed before the redraw
    scr.draw_body()
    assert scr.active_field is scr.row_fields[0][1]   # clamped to the nearest remaining row


def test_focus_dropped_on_redraw_when_no_rows(columns):
    scr = make_drawn_screen(columns, 3)
    scr._focus_cell(2, 1)
    scr.table._rows = []                          # all rows removed
    scr.draw_body()
    assert scr.active_field is None              # nothing to focus


def test_first_keypress_focuses_top_visible_first_editable(columns):
    scr = make_drawn_screen(columns, 5)
    assert scr.active_field is None
    scr.process_key('KEY_DOWN')                  # first keypress -> top visible row, first editable col (1)
    assert scr.active_field is scr.row_fields[0][1]


def test_arrow_down_moves_focus_same_column(columns):
    scr = make_drawn_screen(columns, 5)
    scr.process_key('KEY_DOWN')                  # focus (0, 1)
    scr.process_key('KEY_DOWN')                  # -> (1, 1)
    assert scr.active_field.screen_key == (1, 1)


def test_arrow_up_wraps_to_bottom_visible(columns):
    scr = make_drawn_screen(columns, 5)          # visible rows 0..3
    scr.process_key('KEY_DOWN')                  # focus (0, 1)
    scr.process_key('KEY_UP')                    # off the top -> wraps to the bottom visible row
    assert scr.active_field.screen_key == (3, 1)
    assert scr.first_row == 0                     # stayed on screen (no scroll)


def test_arrow_down_autoscrolls_at_bottom(columns):
    scr = make_drawn_screen(columns, 10)         # visible 4 rows: 0..3
    for _ in range(4):                           # first -> (0,1), then down to (3,1)
        scr.process_key('KEY_DOWN')
    assert scr.active_field.screen_key == (3, 1)
    assert scr.first_row == 0
    scr.process_key('KEY_DOWN')                  # from bottom row -> scroll to reveal row 4
    assert scr.active_field.screen_key == (4, 1)
    assert scr.first_row == 1


def test_up_first_keypress_focuses_bottom_visible(columns):
    scr = make_drawn_screen(columns, 10)         # visible rows 0..3
    assert scr.active_field is None
    scr.process_key('KEY_UP')
    assert scr.active_field.screen_key == (3, 1)  # bottom visible row, first editable col


def test_arrow_down_wraps_to_top_visible(columns):
    scr = make_drawn_screen(columns, 3)          # 3 rows, all visible
    scr._focus_cell(2, 1)                        # last row
    scr.process_key('KEY_DOWN')                  # off the bottom -> wraps to the top visible row
    assert scr.active_field.screen_key == (0, 1)
    assert scr.first_row == 0                     # stayed on screen


def test_tab_wraps_from_last_cell_to_top(columns):
    scr = make_drawn_screen(columns, 3)          # editable_cols [1, 3], all visible
    scr._focus_cell(2, 3)                        # last row, last editable col
    scr.process_key('\t')                        # off the bottom -> wraps to top visible first cell
    assert scr.active_field.screen_key == (0, 1)


def test_btab_first_keypress_focuses_rightmost_col(columns):
    scr = make_drawn_screen(columns, 5)
    assert scr.active_field is None
    scr.process_key('KEY_BTAB')
    assert scr.active_field.screen_key == (0, 3)  # top visible row, right-most editable col


def test_tab_first_keypress_focuses_leftmost_col(columns):
    scr = make_drawn_screen(columns, 5)
    scr.process_key('\t')
    assert scr.active_field.screen_key == (0, 1)  # top visible row, first editable col


def test_tab_moves_to_next_editable_col_then_wraps(columns):
    scr = make_drawn_screen(columns, 5)          # editable_cols == [1, 3]
    scr.process_key('KEY_DOWN')                  # focus (0, 1)
    scr.process_key('\t')                        # -> (0, 3)
    assert scr.active_field.screen_key == (0, 3)
    scr.process_key('\t')                        # last editable col -> wrap to next row's first
    assert scr.active_field.screen_key == (1, 1)


def test_btab_wraps_to_previous_row(columns):
    scr = make_drawn_screen(columns, 5)
    scr.process_key('KEY_DOWN')                  # (0, 1)
    scr.process_key('\t')                        # (0, 3)
    scr.process_key('\t')                        # (1, 1)
    scr.process_key('KEY_BTAB')                  # first editable col -> wrap to prev row's last
    assert scr.active_field.screen_key == (0, 3)


def test_btab_from_first_cell_wraps_to_bottom_visible(columns):
    scr = make_drawn_screen(columns, 5)          # visible rows 0..3, editable_cols [1, 3]
    scr.process_key('KEY_DOWN')                  # (0, 1) -- the very first editable cell
    scr.process_key('KEY_BTAB')                  # off the top -> bottom visible row's last editable
    assert scr.active_field.screen_key == (3, 3)
    assert scr.first_row == 0                     # stayed on screen


def test_tab_and_shift_tab_alias_right_and_left(columns):
    scr = make_drawn_screen(columns, 5)
    scr.process_key('KEY_DOWN')                  # (0, 1)
    scr.process_key('\t')                        # like Right -> (0, 3)
    assert scr.active_field.screen_key == (0, 3)
    scr.process_key('KEY_BTAB')                  # like Left -> (0, 1)
    assert scr.active_field.screen_key == (0, 1)


def test_f8_returns_back(columns):
    scr = make_drawn_screen(columns, 3)
    back = object()
    scr.back = back
    assert scr.process_key('KEY_F(8)') is back   # F8 -> Back returns the back screen


def test_f1_calls_show_help(columns, monkeypatch):
    scr = make_drawn_screen(columns, 3)
    called = []
    monkeypatch.setattr(scr, "show_help", lambda: called.append(True))
    assert scr.process_key('KEY_F(1)') is None
    assert called == [True]


def test_f12_exits_when_clean(columns):
    scr = make_drawn_screen(columns, 3)
    scr.app.changed = False
    assert scr.process_key('KEY_F(12)') == 'APP_EXIT'    # nothing unsaved -> exit cleanly
    assert scr.popup is None


def test_f12_confirms_when_changed(columns):
    scr = make_drawn_screen(columns, 3)
    scr.app.changed = True
    assert scr.process_key('KEY_F(12)') is None          # unsaved changes -> confirm, stay for now
    assert scr.popup is not None
    assert scr.popup.cmd_fn('Yes') == 'APP_ABORT'        # Yes -> abort (discard + quit)
    assert scr.popup.cmd_fn('No') is None                # No -> stay


def test_q_no_longer_quits(columns):
    scr = make_drawn_screen(columns, 3)
    assert scr.process_key('q') == 'q'                    # 'q' is an ordinary key now, just bubbles


def test_left_right_noop_in_read_only_table():
    cols = [FakeColumn("a", min_width=5), FakeColumn("b", min_width=5)]   # no editable columns
    rows = [FakeRow(a=f"a{i}", b=f"b{i}") for i in range(3)]
    scr = table_screen(FakeTable("RO", cols, rows))
    scr.app = Mock(name="app")
    scr.lines = 24
    scr.cols = 80
    scr.init()
    scr.draw_body()
    assert scr.editable_cols == []
    scr.process_key('KEY_RIGHT')
    assert scr.active_field is None


def fake_popup_menu_factory(record):
    def fake_popup_menu(title, screen, commands, execute, y, x):
        record.update(title=title, commands=commands, y=y, x=x)
        return Mock(name="popup")
    return fake_popup_menu


def test_f10_opens_screen_popup(columns, monkeypatch):
    scr = make_drawn_screen(columns, 3)
    rec = {}
    monkeypatch.setattr(tui_base, "popup_menu", fake_popup_menu_factory(rec))
    assert scr.process_key('KEY_F(10)') is None
    assert scr.popup is not None
    assert rec['title'] == "Screen"
    assert scr.popup_y is None


def test_f10_keeps_existing_screen_popup(columns, monkeypatch):
    scr = make_drawn_screen(columns, 3)
    monkeypatch.setattr(tui_base, "popup_menu", fake_popup_menu_factory({}))
    scr.process_key('KEY_F(10)')
    first = scr.popup
    scr.process_key('KEY_F(10)')                 # pressing F10 again keeps the same popup
    assert scr.popup is first


def test_f9_opens_row_popup_for_focused_row(columns, monkeypatch):
    scr = make_drawn_screen(columns, 5)
    rec = {}
    monkeypatch.setattr(tui_base, "popup_menu", fake_popup_menu_factory(rec))
    scr._focus_cell(2, 1)                         # focus row 2
    assert scr.process_key('KEY_F(9)') is None
    assert scr.popup is not None
    assert rec['commands'] == ('View/Edit', 'Delete')  # the row's row_popup_commands
    assert scr.popup_y == 2                       # on-screen offset of the focused row


def test_f9_focuses_top_visible_row_when_nothing_focused(columns, monkeypatch):
    scr = make_drawn_screen(columns, 5)
    rec = {}
    monkeypatch.setattr(tui_base, "popup_menu", fake_popup_menu_factory(rec))
    assert scr.active_field is None
    scr.process_key('KEY_F(9)')
    assert scr.active_field is not None           # focused the top visible row first
    assert scr.active_field.screen_key[0] == scr.first_row
    assert scr.popup is not None


def test_f9_noop_with_no_rows(columns, monkeypatch):
    scr = table_screen(FakeTable("Inv", columns, []))
    scr.app = Mock(name="app")
    scr.lines = 24
    scr.cols = 80
    scr.init()
    scr.draw_body()
    monkeypatch.setattr(tui_base, "popup_menu", fake_popup_menu_factory({}))
    scr.process_key('KEY_F(9)')
    assert scr.popup is None


def test_f2_opens_focused_row(columns, monkeypatch):
    scr = make_drawn_screen(columns, 5)
    scr._focus_cell(2, 1)
    sentinel = Mock(name="row_screen")
    row = scr.rows[2]
    monkeypatch.setattr(row, "execute",
                        lambda screen, cmd: sentinel if cmd == 'View/Edit' else None)
    assert scr.process_key('KEY_F(2)') is sentinel   # returns the row_screen to switch to


def test_f2_focuses_top_visible_row_when_nothing_focused(columns, monkeypatch):
    scr = make_drawn_screen(columns, 5)
    seen = {}
    def fake_execute(screen, cmd):
        seen['row_index'] = scr.active_field.screen_key[0]
        return None
    for r in scr.rows:
        monkeypatch.setattr(r, "execute", fake_execute)
    assert scr.active_field is None
    scr.process_key('KEY_F(2)')
    assert scr.active_field is not None               # focused the top visible row first
    assert seen['row_index'] == scr.first_row


def test_f2_noop_when_view_edit_not_offered(columns, monkeypatch):
    scr = make_drawn_screen(columns, 5)
    scr._focus_cell(1, 1)
    row = scr.rows[1]
    monkeypatch.setattr(type(row), "row_popup_commands", ('Delete',))   # no View/Edit
    called = []
    monkeypatch.setattr(row, "execute", lambda screen, cmd: called.append(cmd))
    assert scr.process_key('KEY_F(2)') is None
    assert called == []                              # execute not called


def test_f2_noop_with_no_rows(columns):
    scr = table_screen(FakeTable("Inv", columns, []))
    scr.app = Mock(name="app")
    scr.lines = 24
    scr.cols = 80
    scr.init()
    scr.draw_body()
    assert scr.process_key('KEY_F(2)') is None


# --- DEL (delete with confirm + auto-advance) and INS (create) ------------------------------------

def test_del_opens_confirm(columns, monkeypatch):
    scr = make_drawn_screen(columns, 3)
    scr._focus_cell(1, 1)
    rec = {}
    def fake_confirm(title, screen, cmd_fn, y, x, outside_space='below'):
        rec.update(title=title, cmd_fn=cmd_fn)
        return Mock(name="popup")
    monkeypatch.setattr(tui_base, "popup_confirm", fake_confirm)
    scr.process_key('KEY_F(5)')
    assert scr.popup is not None
    assert rec['title'] == "Delete item1?"       # human_key of the focused row


def test_do_delete_yes_runs_delete(columns, monkeypatch):
    scr = make_drawn_screen(columns, 3)
    called = []
    monkeypatch.setattr(scr.rows[1], "execute",
                        lambda screen, cmd: called.append(cmd) or 'REFRESH')
    assert scr._do_delete(1, 'Yes') == 'REFRESH'
    assert called == ['Delete']


def test_do_delete_no_is_noop(columns, monkeypatch):
    scr = make_drawn_screen(columns, 3)
    called = []
    monkeypatch.setattr(scr.rows[1], "execute", lambda screen, cmd: called.append(cmd))
    assert scr._do_delete(1, 'No') is None
    assert called == []


def test_del_noop_when_not_offered(columns, monkeypatch):
    scr = make_drawn_screen(columns, 3)
    scr._focus_cell(1, 1)
    monkeypatch.setattr(type(scr.rows[1]), "row_popup_commands", ('View/Edit',))   # no Delete
    scr.process_key('KEY_F(5)')
    assert scr.popup is None


def test_delete_advances_focus_to_next_row(columns):
    scr = make_drawn_screen(columns, 4)          # rows 0..3
    scr._focus_cell(1, 1)
    del scr.table._rows[1]                        # delete row 1 -> rows shift up
    scr.draw_body()                              # REFRESH rebuild
    assert scr.active_field.screen_key == (1, 1)  # same index -> now the next row


def test_delete_last_row_clamps_focus(columns):
    scr = make_drawn_screen(columns, 3)
    scr._focus_cell(2, 1)
    del scr.table._rows[2]                        # delete the last row
    scr.draw_body()
    assert scr.active_field.screen_key == (1, 1)  # clamped to the new last row


def test_ins_creates_row_when_offered(columns, monkeypatch):
    scr = make_drawn_screen(columns, 3)
    scr.table.screen_popup_commands = ('Create',)
    sentinel = Mock(name="create_screen")
    monkeypatch.setattr(scr, "execute", lambda cmd: sentinel if cmd == 'Create' else None)
    assert scr.process_key('KEY_IC') is sentinel


def test_ins_noop_when_not_offered(columns, monkeypatch):
    scr = make_drawn_screen(columns, 3)
    scr.table.screen_popup_commands = ()         # table doesn't offer Create
    monkeypatch.setattr(scr, "execute",
                        lambda cmd: pytest.fail("execute should not be called"))
    assert scr.process_key('KEY_IC') is None


# --- in-place cell editing -----------------------------------------------------------------------

def test_printable_char_edits_focused_cell(columns):
    scr = make_drawn_screen(columns, 3)
    scr._focus_cell(1, 1)                        # num_pkgs (editable), value "1", select-all
    scr.process_key('7')
    assert scr.active_field.text == "7"          # replaced the selected value


def test_space_inserts_like_any_char(columns):
    scr = make_drawn_screen(columns, 3)
    scr._focus_cell(1, 1)
    scr.process_key(' ')                         # Space is a normal insert now (no special role)
    assert scr.active_field.text == " "          # replaced the select-all


def test_printable_on_readonly_cell_bubbles(columns):
    scr = make_drawn_screen(columns, 3)
    scr._focus_cell(0, 0)                        # item (read-only)
    assert scr.process_key('x') == 'x'           # nothing to edit -> bubbles up unhandled


def test_typing_with_no_focus_bubbles(columns):
    scr = make_drawn_screen(columns, 3)
    assert scr.active_field is None
    assert scr.process_key('7') == '7'           # no auto-focus; the key just bubbles


def test_enter_moves_down(columns):
    scr = make_drawn_screen(columns, 3)
    scr._focus_cell(0, 1)
    scr.process_key('\n')
    assert scr.active_field.screen_key == (1, 1)


def test_cell_edit_commit_writes_row_and_advances(columns):
    scr = make_drawn_screen(columns, 3)
    scr._focus_cell(1, 1)
    scr.process_key('7')                         # edit -> "7"
    scr.process_key('\n')                        # Enter: down a row -> commits (1,1) first
    assert scr.rows[1].get("num_pkgs") == "7"    # written through to the row
    scr.app.set_changed.assert_called()
    assert scr.active_field.screen_key == (2, 1)  # advanced to the next row


def test_cell_edit_tab_commits_and_moves_column(columns):
    scr = make_drawn_screen(columns, 3)
    scr._focus_cell(1, 1)
    scr.process_key('9')
    scr.process_key('\t')                        # Tab: next editable cell -> commits (1,1) first
    assert scr.rows[1].get("num_pkgs") == "9"
    assert scr.active_field.screen_key == (1, 3)


def test_cell_edit_abort_restores_row_value(columns):
    scr = make_drawn_screen(columns, 3)
    scr._focus_cell(1, 1)
    orig = scr.rows[1].get("num_pkgs")
    scr.process_key('7')
    assert scr.active_field.text == "7"
    scr.process_key('\x1B')                      # Esc -> abort the cell edit (stay focused)
    assert scr.active_field.text == orig          # restored
    assert scr.active_field.screen_key == (1, 1)  # still focused
    assert scr.rows[1].get("num_pkgs") == orig    # row untouched


def test_del_does_not_delete_row(columns):
    scr = make_drawn_screen(columns, 3)
    scr._focus_cell(1, 1)
    scr.process_key('7')                         # cell now "7"
    scr.process_key('KEY_DC')                    # DEL routes to the field, never delete-row
    assert scr.popup is None                     # no delete-row confirm (that's F5 now)


# --- cell commit validation + calc-field tolerance ------------------------------------------------

def _raise_value_error(s):
    raise ValueError("bad num")


def test_cell_commit_invalid_stays_and_pops_error(columns):
    scr = make_drawn_screen(columns, 3)
    scr._focus_cell(1, 1)                          # editable num_pkgs
    f = scr.active_field
    f.text = "bad"
    f.changed = True
    f.field_shared.convert_fn = _raise_value_error
    assert scr._commit_edit() is False            # validation failed
    assert scr.popup is not None                   # error popup shown
    assert f.changed                               # still dirty (not written through)
    assert scr.rows[1].get("num_pkgs") == "1"      # row keeps its original value


def test_focus_cell_blocked_by_invalid_commit(columns):
    scr = make_drawn_screen(columns, 3)
    scr._focus_cell(1, 1)
    f = scr.active_field
    f.text = "bad"
    f.changed = True
    f.field_shared.convert_fn = _raise_value_error
    assert scr._focus_cell(2, 1) is False          # moving off the bad cell is blocked
    assert scr.active_field is f                     # focus stays on the bad cell


def test_recompute_row_tolerates_calc_error(columns):
    scr = make_drawn_screen(columns, 3)
    orig_get = scr.rows[0].get
    def raising_get(name):
        if name == "unit":                          # calc column can't compute (bad FK)
            raise KeyError("Foobar")
        return orig_get(name)
    scr.rows[0].get = raising_get
    scr._recompute_row(0)                           # must not raise
    assert scr.row_fields[0][2].text == ""          # calc cell blanked

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
from tui_app.field import read_only_field, editable_field


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
    def __init__(self, **values):
        self._values = values

    def get(self, name):
        return str(self._values[name])

    def human_key(self):
        return self.get("item")


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
    # editable columns -> editable_field; read-only columns -> plain read_only_field
    row0 = scr.row_fields[0]
    assert not isinstance(row0[0], editable_field)   # item: read-only
    assert isinstance(row0[1], editable_field)       # num_pkgs: editable
    assert not isinstance(row0[2], editable_field)   # unit: read-only
    assert isinstance(row0[3], editable_field)       # num_units: editable


def make_drawn_screen(columns, n_rows, lines=6):
    r'''A table_screen drawn once with n_rows rows; lines=6 -> 4 visible row lines (2..5).'''
    scr = table_screen(FakeTable("Inv", columns, make_rows(n_rows)))
    scr.app = Mock(name="app")
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


def test_focus_dropped_on_full_redraw(columns):
    scr = make_drawn_screen(columns, 3)
    scr._focus_cell(0, 1)
    assert scr.active_field is not None
    scr.draw_body()                              # full redraw recreates fields -> focus dropped
    assert scr.active_field is None


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


def test_arrow_up_clamps_at_top(columns):
    scr = make_drawn_screen(columns, 5)
    scr.process_key('KEY_DOWN')                  # focus (0, 1)
    scr.process_key('KEY_UP')                    # can't go above row 0
    assert scr.active_field.screen_key == (0, 1)


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


def test_left_first_keypress_focuses_rightmost_col(columns):
    scr = make_drawn_screen(columns, 5)
    assert scr.active_field is None
    scr.process_key('KEY_LEFT')
    assert scr.active_field.screen_key == (0, 3)  # top visible row, right-most editable col


def test_right_first_keypress_focuses_leftmost_col(columns):
    scr = make_drawn_screen(columns, 5)
    scr.process_key('KEY_RIGHT')
    assert scr.active_field.screen_key == (0, 1)  # top visible row, first editable col


def test_right_moves_to_next_editable_col_then_wraps(columns):
    scr = make_drawn_screen(columns, 5)          # editable_cols == [1, 3]
    scr.process_key('KEY_DOWN')                  # focus (0, 1)
    scr.process_key('KEY_RIGHT')                 # -> (0, 3)
    assert scr.active_field.screen_key == (0, 3)
    scr.process_key('KEY_RIGHT')                 # last editable col -> wrap to next row's first
    assert scr.active_field.screen_key == (1, 1)


def test_left_wraps_to_previous_row(columns):
    scr = make_drawn_screen(columns, 5)
    scr.process_key('KEY_DOWN')                  # (0, 1)
    scr.process_key('KEY_RIGHT')                 # (0, 3)
    scr.process_key('KEY_RIGHT')                 # (1, 1)
    scr.process_key('KEY_LEFT')                  # first editable col -> wrap to prev row's last
    assert scr.active_field.screen_key == (0, 3)


def test_left_at_very_first_cell_is_noop(columns):
    scr = make_drawn_screen(columns, 5)
    scr.process_key('KEY_DOWN')                  # (0, 1) -- the very first editable cell
    scr.process_key('KEY_LEFT')                  # nowhere before it -> no move
    assert scr.active_field.screen_key == (0, 1)


def test_tab_and_shift_tab_alias_right_and_left(columns):
    scr = make_drawn_screen(columns, 5)
    scr.process_key('KEY_DOWN')                  # (0, 1)
    scr.process_key('\t')                        # like Right -> (0, 3)
    assert scr.active_field.screen_key == (0, 3)
    scr.process_key('KEY_BTAB')                  # like Left -> (0, 1)
    assert scr.active_field.screen_key == (0, 1)


def test_esc_returns_back(columns):
    back = object()
    scr = table_screen(FakeTable("Inv", columns, make_rows(3)), back=back)
    scr.app = Mock(name="app")
    scr.lines = 24
    scr.cols = 80
    scr.init()
    scr.draw_body()
    assert scr.process_key('\x1B') is back       # Esc -> Back returns the back screen


def test_f1_calls_show_help(columns, monkeypatch):
    scr = make_drawn_screen(columns, 3)
    called = []
    monkeypatch.setattr(scr, "show_help", lambda: called.append(True))
    assert scr.process_key('KEY_F(1)') is None
    assert called == [True]


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

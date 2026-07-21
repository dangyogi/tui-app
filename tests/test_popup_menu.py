# test_popup_menu.py

r'''Tests for popup_menu's column-major multi-column layout + hit-testing + key nav.

Same lightweight pattern as the other screen tests: app.stdscr is a Mock (subwin/addstr/chgat/inch all
absorbed), so we assert layout state (ncols/rows_per_col/_cell/_index_at) and navigation, not pixels.
'''

from unittest.mock import Mock

import pytest

from tui_app import tui_base
from tui_app.tui_base import screen, popup_menu


@pytest.fixture(autouse=True)
def patch_curses(monkeypatch):
    monkeypatch.setattr(tui_base.curses, "color_pair", lambda n: n)


def make_menu(commands, cmd_fn=None, lines=24, cols=80, begin_y=1, begin_x=4):
    s = screen("host")
    s.app = Mock(name="app")
    s.app.stdscr.inch.return_value = 0       # popup captures overlaid chars via inch
    s.lines = lines
    s.cols = cols
    s.popup = popup_menu("Menu", s, commands, cmd_fn or (lambda c: f"ran:{c}"), begin_y, begin_x)
    return s.popup


def test_short_list_is_single_column():
    m = make_menu(['Back', 'Exit', 'Abort'])
    assert m.ncols == 1
    assert m.rows_per_col == 3
    assert m._cell(0) == (1, 2)
    assert m._cell(2) == (3, 2)


def test_long_list_wraps_into_columns():
    # lines=6 -> max_rows=2, so 7 commands wrap into ceil(7/2)=4 columns of 2 rows (last col has 1).
    cmds = [f"cmd{i}" for i in range(7)]      # col_width == 4
    m = make_menu(cmds, lines=6)
    assert m.rows_per_col == 2
    assert m.ncols == 4
    assert m._cell(0) == (1, 2)               # col 0, row 0
    assert m._cell(1) == (2, 2)               # col 0, row 1
    assert m._cell(2) == (1, 8)               # col 1, row 0 (x = 2 + 1*(4+2))
    assert m._cell(6) == (1, 20)              # col 3, row 0 (x = 2 + 3*6)


def test_index_at_maps_screen_coords():
    m = make_menu([f"cmd{i}" for i in range(7)], lines=6)   # 4 cols x 2 rows, begin_y=1 begin_x=4
    assert m._index_at(2, 12) == 2            # col 1 row 0: y=begin_y+1, x=begin_x+8
    assert m._index_at(3, 6) == 1             # col 0 row 1: y=begin_y+2, x=begin_x+2
    assert m._index_at(2, 10) is None         # rel_x=4 -> in the gap between col 0 and col 1
    assert m._index_at(3, 24) is None         # col 3 row 1 -> flat index 7, past the last command


def test_key_nav_moves_within_and_between_columns():
    m = make_menu([f"cmd{i}" for i in range(7)], lines=6)   # 4 cols x 2 rows
    m.select(0)
    m.process_key('KEY_DOWN')
    assert m.selection == 1                   # down a row in col 0
    m.process_key('KEY_DOWN')
    assert m.selection == 1                   # already at the bottom of the column -> no move
    m.process_key('KEY_RIGHT')
    assert m.selection == 3                   # same row, next column (+rows_per_col)
    m.process_key('KEY_UP')
    assert m.selection == 2                   # up a row in col 1
    m.process_key('KEY_LEFT')
    assert m.selection == 0                   # same row, previous column


def test_key_nav_clamps_at_edges():
    m = make_menu([f"cmd{i}" for i in range(7)], lines=6)
    m.select(0)
    m.process_key('KEY_UP')
    assert m.selection == 0                   # top of column -> no move
    m.process_key('KEY_LEFT')
    assert m.selection == 0                   # first column -> no move
    m.select(6)                               # last command (col 3, row 0)
    m.process_key('KEY_RIGHT')
    assert m.selection == 6                   # no column to the right -> no move


def _menu7(ran):
    return make_menu([f"cmd{i}" for i in range(7)],
                     cmd_fn=lambda c: ran.append(c) or f"ran:{c}", lines=6)


def test_press_drag_highlights_and_release_executes():
    ran = []
    m = _menu7(ran)
    curses = tui_base.curses
    assert m.process_mouse((0, 6, 2, 0, curses.BUTTON1_PRESSED)) is None
    assert m.selection == 0 and m.pressing    # press on col 0 row 0
    assert m.process_mouse((0, 12, 2, 0, curses.REPORT_MOUSE_POSITION)) is None
    assert m.selection == 2                   # dragged onto col 1 row 0
    assert not ran                            # nothing runs until release
    assert m.process_mouse((0, 12, 2, 0, curses.BUTTON1_RELEASED)) == "ran:cmd2"
    assert ran == ["cmd2"] and not m.pressing


def test_drag_off_menu_deselects():
    ran = []
    m = _menu7(ran)
    curses = tui_base.curses
    m.process_mouse((0, 6, 2, 0, curses.BUTTON1_PRESSED))
    assert m.selection == 0
    m.process_mouse((0, 10, 2, 0, curses.REPORT_MOUSE_POSITION))   # rel_x=4 -> in the gap (off entries)
    assert m.selection is None                # deselected while off an entry


def test_release_off_menu_dismisses():
    ran = []
    m = _menu7(ran)
    screen_ = m.screen
    curses = tui_base.curses
    m.process_mouse((0, 6, 2, 0, curses.BUTTON1_PRESSED))
    assert m.process_mouse((0, 10, 2, 0, curses.BUTTON1_RELEASED)) is None   # release in the gap
    assert not ran                            # nothing executed
    assert screen_.popup is None              # ...dismissed


def test_single_click_on_entry_executes():
    ran = []
    m = _menu7(ran)
    curses = tui_base.curses
    # a terminal that collapses press+release into one BUTTON1_CLICKED still runs the entry
    assert m.process_mouse((0, 12, 2, 0, curses.BUTTON1_CLICKED)) == "ran:cmd2"
    assert ran == ["cmd2"]

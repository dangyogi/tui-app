# test_field_grow.py

r'''Tests for multi-line grow mechanics (migration step 4): field_shared.line_count, multi_line
grow_if_needed, the process_key -> 'REFRESH' path, and deactivate() clearing the cursor.
'''

from unittest.mock import Mock

import pytest

from tui_app import tui_base
from tui_app.field import (
    field_shared, editable_single_line, editable_multi_line,
)


@pytest.fixture(autouse=True)
def patch_curses(monkeypatch):
    monkeypatch.setattr(tui_base.curses, "color_pair", lambda n: n)


@pytest.fixture
def app():
    return Mock(name="app")


# --- line_count mirrors wrap ----------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "",
    "short",
    "exactlyten",                       # == ncols (10)
    "abcdefghijklmnop",                 # 16 chars, no spaces -> mid-word break
    "one two three four five six",      # word wrapping
    "aaaaaaaaaa bbbbbbbbbb cccccccccc", # each word fills a line
])
def test_line_count_matches_wrap(text):
    fs = field_shared("f", nlines=30, begin_x=0, ncols=10)
    expected = sum(1 for start, pad, line in fs.wrap(text, 0) if start is not None)
    assert fs.line_count(text) == expected


def test_line_count_empty_is_one():
    fs = field_shared("f", nlines=5, begin_x=0, ncols=10)
    assert fs.line_count("") == 1
    assert fs.line_count("   ") == 1     # rstrips to empty


# --- grow_if_needed -------------------------------------------------------------------------------

def test_multi_line_grow_if_needed(app):
    fs = field_shared("m", nlines=1, begin_x=0, ncols=5, app=app,
                      left_placeholder="", right_placeholder="")
    f = editable_multi_line(0, "12345", fs, begin_y=0)   # 5 chars fit one 5-col line
    assert not f.grow_if_needed()
    f.text = "123456"                                    # now needs 2 lines
    assert f.grow_if_needed()


def test_multi_line_no_grow_when_taller(app):
    fs = field_shared("m", nlines=3, begin_x=0, ncols=5, app=app,
                      left_placeholder="", right_placeholder="")
    f = editable_multi_line(0, "123456", fs, begin_y=0)  # needs 2, has 3
    assert not f.grow_if_needed()


def test_single_line_never_grows(app):
    # single_line scrolls instead of growing, so grow_if_needed is always False even when overflowing
    fs = field_shared("s", nlines=1, begin_x=0, ncols=5, app=app,
                      left_placeholder="<", right_placeholder=">")
    sl = editable_single_line(0, "way too long to fit", fs, begin_y=0)
    assert not sl.grow_if_needed()
    # (read_only_multi_line inherits multi_line.grow_if_needed, but it is never called: read-only
    #  cells aren't edited, and draw_body sizes them via line_count so they never truncate.)


# --- process_key returns REFRESH when the edit overflows ------------------------------------------

def test_process_key_grow_returns_refresh(app):
    app.screen = Mock(name="screen")
    fs = field_shared("m", nlines=1, begin_x=0, ncols=5, app=app,
                      left_placeholder="", right_placeholder="")
    f = editable_multi_line(0, "12345", fs, begin_y=0)   # fills the single line
    f.position = 5                                        # append cursor at the end
    result = f.process_key('6')                           # -> "123456", needs a 2nd line
    assert result == 'REFRESH'
    assert f.text == "123456"
    assert f.changed


def test_process_key_no_grow_returns_none(app):
    app.screen = Mock(name="screen")
    fs = field_shared("m", nlines=2, begin_x=0, ncols=5, app=app,
                      left_placeholder="", right_placeholder="")
    f = editable_multi_line(0, "12345", fs, begin_y=0)   # has room for a 2nd line
    f.position = 5
    result = f.process_key('6')                           # -> "123456", still fits 2 lines
    assert result is None
    assert f.text == "123456"


# --- deactivate clears the cursor -----------------------------------------------------------------

def test_delete_selection_puts_cursor_at_deletion_point(app):
    # deleting a selection (e.g. DEL on a select-all) leaves the cursor AT the deletion point,
    # not one past it -- else on an emptied field the cursor would be off the end and not drawn
    app.screen = Mock(name="screen")
    fs = field_shared("f", nlines=1, begin_x=0, ncols=10, app=app,
                      left_placeholder="<", right_placeholder=">")
    f = editable_single_line(0, "abc", fs, begin_y=0)
    f.position = 0
    f.selection_len = 3                          # whole value selected
    f.delete_selection()                         # DEL the selection (insch='')
    assert f.text == ""
    assert f.position == 0                        # cursor at the deletion point


def test_replace_selection_puts_cursor_after_char(app):
    app.screen = Mock(name="screen")
    fs = field_shared("f", nlines=1, begin_x=0, ncols=10, app=app,
                      left_placeholder="<", right_placeholder=">")
    f = editable_single_line(0, "abc", fs, begin_y=0)
    f.position = 0
    f.selection_len = 3
    f.delete_selection("x")                      # type a char over the selection
    assert f.text == "x"
    assert f.position == 1                        # cursor after the inserted char


def test_single_line_edits_left_aligned(app):
    # a right-aligned cell displays right-aligned but edits LEFT-aligned so the cursor stays visible
    fs = field_shared("f", nlines=1, begin_x=0, ncols=10, app=app, alignment="right",
                      left_placeholder="<", right_placeholder=">")
    f = editable_single_line(0, "42", fs, begin_y=0)
    assert f.pads == [8]           # display: "42" right-aligned in 10 cols -> pad 8
    f.editing = True
    f.paint()
    assert f.pads == [0]           # editing: left-aligned (pad 0), cursor after the text is visible


def test_empty_right_aligned_cursor_visible(app):
    # an empty right-aligned cell must keep the position-0 cursor on-screen (pad 0), not pushed off
    # the right edge -- so a focused/emptied right-aligned cell still shows its cursor
    fs = field_shared("f", nlines=1, begin_x=0, ncols=10, app=app, alignment="right",
                      left_placeholder="<", right_placeholder=">")
    f = editable_single_line(0, "", fs, begin_y=0)
    assert f.pads == [0]
    assert list(f.gen_locations(0, 1)) == [(0, 0, 1)]   # cursor cell at column 0 is drawable


def test_deactivate_clears_cursor(app):
    fs = field_shared("s", nlines=1, begin_x=0, ncols=10, app=app,
                      left_placeholder="<", right_placeholder=">")
    f = editable_single_line(0, "hello", fs, begin_y=0)
    f.position = 3
    f.selection_len = 2
    f.deactivate()
    assert f.position is None
    assert f.selection_len == 0

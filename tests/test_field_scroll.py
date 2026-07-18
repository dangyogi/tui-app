# test_field_scroll.py

r'''Tests for single-line horizontal column-scroll (migration step 3).

The `app` is a Mock so draws are absorbed; curses.color_pair is monkeypatched to identity.  These
check the X_single scroll formula, the show_cursor() repaint decision, and that the shared
wrap/get_col/to_index machinery round-trips with a scrolled single-line field ("<"/">" markers).
'''

from unittest.mock import Mock

import pytest

from tui_app import tui_base
from tui_app.field import (
    field_shared, read_only_single_line, editable_single_line,
)


@pytest.fixture(autouse=True)
def patch_curses(monkeypatch):
    monkeypatch.setattr(tui_base.curses, "color_pair", lambda n: n)


@pytest.fixture
def app():
    return Mock(name="app")


def make_editable(app, text, ncols=5, begin_x=0, paint=False):
    fs = field_shared("f", nlines=1, begin_x=begin_x, ncols=ncols, app=app,
                      left_placeholder="<", right_placeholder=">")
    return editable_single_line(0, text, fs, begin_y=10, paint=paint)


# --- the X_single scroll formula ------------------------------------------------------------------

@pytest.mark.parametrize("text, position, expected", [
    # ncols=5, X_single=0.6 -> int(5*0.6)=3
    ("0123456789", 0, 0),    # cursor at start -> no scroll
    ("0123456789", 3, 0),    # position - 3 == 0
    ("0123456789", 4, 1),
    ("0123456789", 5, 2),
    ("0123456789", 9, 5),    # clamped to upper (len-ncols)
    ("0123456789", 10, 6),   # append: upper gains +1 to keep the append cursor visible
    ("abc", 0, 0),           # fits in ncols -> never scrolls
    ("abc", 3, 0),           # even at the append position, a fitting field does not scroll
    ("12345", 4, 0),         # exactly fills ncols -> no scroll until append
    ("12345", 5, 1),         # append past a full field -> scroll 1
])
def test_compute_scroll(app, text, position, expected):
    f = make_editable(app, text)
    f.position = position
    assert f._compute_scroll() == expected


def test_read_only_never_scrolls(app):
    fs = field_shared("f", nlines=1, begin_x=0, ncols=5, app=app,
                      left_placeholder="<", right_placeholder=">")
    f = read_only_single_line(0, "0123456789", fs, begin_y=10, paint=False)
    assert f._compute_scroll() == 0    # no cursor -> no scroll


# --- show_cursor(): repaint only when the scroll window shifts -------------------------------------

def test_show_cursor_repaints_when_scroll_changes(app):
    f = make_editable(app, "0123456789")
    f.position = 9            # wants scroll 5
    f.scroll = 0             # stale
    f.paint = Mock(name="paint")
    f.set_attrs = Mock(name="set_attrs")
    f.show_cursor()
    assert f.paint.called
    assert not f.set_attrs.called


def test_show_cursor_setattrs_when_scroll_unchanged(app):
    f = make_editable(app, "0123456789")
    f.position = 9
    f.scroll = 5             # already correct
    f.paint = Mock(name="paint")
    f.set_attrs = Mock(name="set_attrs")
    f.show_cursor()
    assert f.set_attrs.called
    assert not f.paint.called


# --- paint() drives scroll, and the shared machinery round-trips ----------------------------------

def test_paint_sets_scroll_and_round_trips(app):
    f = make_editable(app, "0123456789", ncols=5, begin_x=0, paint=False)
    f.position = 5
    f.paint()
    assert f.scroll == 2
    # the cursor (index 5) lands on a visible column, and it maps back to index 5
    col = f.get_col(5)
    assert col is not None and 0 <= col < 5
    assert f.to_index(f.begin_y, f.begin_x + col) == 5

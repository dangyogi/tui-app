# test_field_factory.py

r'''Tests for the field_shared factory family (step 1 of the migration).

Same lightweight pattern as test_field_interaction.py: `app` is a plain Mock so every curses draw on
app.stdscr is absorbed, and curses.color_pair is monkeypatched to identity.  These assert which field
gets built and that it carries the right text/attrs -- not what is painted.
'''

from unittest.mock import Mock

import pytest

from tui_app import tui_base
from tui_app.field import (
    read_only, editable,
    read_only_single_line, editable_single_line,
    read_only_multi_line, editable_multi_line,
    read_only_single_shared, editable_single_shared,
    read_only_multi_shared, editable_multi_shared,
    single_line_shared, multi_line_shared,
)


@pytest.fixture(autouse=True)
def patch_curses(monkeypatch):
    # color_pair needs a live terminal; identity is enough here.
    monkeypatch.setattr(tui_base.curses, "color_pair", lambda n: n)


@pytest.fixture
def app():
    return Mock(name="app")


class FakeColumn:
    r'''Minimal column stand-in; adds `calculated` (the multi picker needs it).'''
    def __init__(self, name, can_edit=False, calculated=False, alignment="left", attr_pair=0x70):
        self.name = name
        self.can_edit = can_edit
        self.calculated = calculated
        self.alignment = alignment
        self._attr_pair = attr_pair

    def validate(self, s):
        pass

    def column_attr_pair(self, row):
        return self._attr_pair


class FakeRow:
    def __init__(self, **values):
        self._values = values

    def get(self, name):
        return str(self._values[name])


# --- single_line_shared (table convention) --------------------------------------------------------

def test_single_line_shared_read_only(app):
    col = FakeColumn("item", can_edit=False, alignment="left")
    shared = single_line_shared(col, "item", begin_x=5, ncols=8, app=app)
    assert isinstance(shared, read_only_single_shared)
    assert shared.field_class is read_only_single_line
    assert shared.nlines == 1
    assert shared.left_placeholder == "<" and shared.right_placeholder == ">"
    assert shared.alignment == "left"
    assert shared.column is col
    assert shared.convert_fn == col.validate


def test_single_line_shared_editable_keeps_alignment(app):
    col = FakeColumn("qty", can_edit=True, alignment="right")
    shared = single_line_shared(col, "qty", begin_x=0, ncols=4, app=app)
    assert isinstance(shared, editable_single_shared)
    assert shared.field_class is editable_single_line
    assert shared.alignment == "right"


# --- multi_line_shared (row_screen convention) ----------------------------------------------------

@pytest.mark.parametrize("can_edit, calculated, creating, expect_editable", [
    (False, False, True,  True),    # create: plain column is editable
    (False, True,  True,  False),   # create: calculated (not can_edit) is read-only
    (True,  True,  True,  True),    # create: calculated but can_edit -> editable (matches :239)
    (False, False, False, False),   # update: not can_edit -> read-only
    (True,  False, False, True),    # update: can_edit -> editable
    (True,  True,  False, True),    # update: can_edit wins regardless of calculated
])
def test_multi_line_shared_editable_predicate(app, can_edit, calculated, creating, expect_editable):
    col = FakeColumn("c", can_edit=can_edit, calculated=calculated)
    shared = multi_line_shared(col, begin_x=2, ncols=30, app=app, nlines=3, creating=creating)
    if expect_editable:
        assert isinstance(shared, editable_multi_shared)
        assert shared.field_class is editable_multi_line
    else:
        assert isinstance(shared, read_only_multi_shared)
        assert shared.field_class is read_only_multi_line
    assert shared.nlines == 3
    assert shared.name == "c"                 # multi uses the column name
    assert shared.alignment == "left"         # row_screen default
    assert shared.left_placeholder == ""      # multi_line grows -> no placeholders
    assert shared.right_placeholder == ""
    assert shared.column is col


# --- field_for / edit_text / from_field -----------------------------------------------------------

def test_field_for_pulls_text_and_attr(app):
    col = FakeColumn("qty", can_edit=True, attr_pair=0x06)
    shared = single_line_shared(col, "qty", begin_x=5, ncols=8, app=app)
    row = FakeRow(qty=42)
    f = shared.field_for(row, begin_y=10, screen_key=(2, 3))
    assert isinstance(f, editable) and isinstance(f, editable_single_line)
    assert f.text == "42"
    assert f.attr_pair == 0x06
    assert f.begin_y == 10
    assert f.screen_key == (2, 3)


def test_field_for_read_only(app):
    col = FakeColumn("item", can_edit=False)
    shared = single_line_shared(col, "item", begin_x=0, ncols=10, app=app)
    f = shared.field_for(FakeRow(item="eggs"), begin_y=4, screen_key=(0, 0))
    assert isinstance(f, read_only) and not isinstance(f, editable)
    assert f.text == "eggs"


def test_edit_text_seeds_editable_with_callback(app):
    shared = editable_single_shared("answer", 1, begin_x=3, ncols=5, app=app, convert_fn=int)
    cb = lambda s: "CB"
    f = shared.edit_text("hi", begin_y=7, screen_key=1, callback=cb)
    assert isinstance(f, editable)
    assert f.text == "hi"
    assert f.callback is cb
    assert f.begin_y == 7 and f.screen_key == 1


def test_from_field_preserves_edit_state(app):
    shared = editable_single_shared("x", 1, begin_x=0, ncols=20, app=app)
    old = editable_single_line(1, "hello world", shared, begin_y=5)
    old.changed = True
    old.position = 3
    old.selection_len = 2
    old.snapshot = "hello"               # the edit-session baseline (differs from the grown text)
    old.attr_pair = 0x06                 # a column_attr_pair(row) highlight
    new = shared.from_field(old, begin_y=9, screen_key=1)
    assert isinstance(new, editable)
    assert new.text == "hello world"
    assert new.changed is True
    assert new.position == 3
    assert new.selection_len == 2
    assert new.snapshot == "hello"       # carried across the grow-REFRESH (abort undoes the whole visit)
    assert new.begin_y == 9
    assert new.attr_pair == 0x06         # highlight preserved, not reset to default


def test_abort_restores_snapshot_and_clears_changed(app):
    shared = editable_single_shared("x", 1, begin_x=0, ncols=20, app=app)
    f = editable_single_line(1, "orig", shared, begin_y=5)
    assert f.snapshot == "orig"          # construction seeds the abort baseline
    f.activate()
    f.position = 4                       # cursor left past where the shorter snapshot ends
    f.insert("Z")                        # simulate an edit
    assert f.changed is True
    f.abort()
    assert f.text == "orig"              # restored to the snapshot
    assert f.changed is False            # snapshot IS the accepted baseline -> clean afterwards
    assert f.position is None            # cursor dropped (so paint() draws no stale reverse block)
    assert f.selection_len == 0


def test_to_index_empty_field_is_zero(app):
    # a click anywhere in an empty cell maps to index 0 (the sole cursor position), never -1
    shared = editable_single_shared("x", 1, begin_x=10, ncols=8, app=app)
    f = editable_single_line(1, "", shared, begin_y=5)
    assert f.to_index(5, 10) == 0                    # left edge
    assert f.to_index(5, 15) == 0                    # middle of the empty cell -> still 0, not -1


def test_click_empty_field_shows_cursor(app):
    # regression: to_index returned -1 for an empty field -> set_position(-1) -> no cursor drawn
    shared = editable_single_shared("x", 1, begin_x=10, ncols=8, app=app)
    f = editable_single_line(1, "", shared, begin_y=5)
    assert f.process_mouse((0, 15, 5, 0, tui_base.curses.BUTTON1_CLICKED)) is None
    assert f.position == 0                           # cursor at 0 (was -1)
    assert f.selection_len == 0


def test_double_click_empty_field_does_not_crash(app):
    # regression: BUTTON1_DOUBLE_CLICKED did self.text[-1] on an empty field -> IndexError
    shared = editable_single_shared("x", 1, begin_x=10, ncols=8, app=app)
    f = editable_single_line(1, "", shared, begin_y=5)
    assert f.process_mouse((0, 15, 5, 0, tui_base.curses.BUTTON1_DOUBLE_CLICKED)) is None
    assert f.position == 0                           # no word to select; cursor set, no IndexError


def test_esc_aborts_and_reselects(app):
    shared = editable_single_shared("x", 1, begin_x=0, ncols=20, app=app)
    f = editable_single_line(1, "orig", shared, begin_y=5)
    f.activate()
    f.process_key('a')                   # typing replaces the select-all
    assert f.text == "a" and f.changed is True
    assert f.process_key('\x1B') is None  # Esc is handled by the field itself
    assert f.text == "orig"              # aborted to the snapshot
    assert f.changed is False
    assert f.position == 0 and f.selection_len == len("orig")   # re-selected: stays focused

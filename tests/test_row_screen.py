# test_row_screen.py

r'''Tests for row_screen field navigation, which now uses the base (object-based) activate_field.

State-focused: fields are Mocks carrying just screen_key/can_edit/process_key, so we assert which field
becomes active and that activate/deactivate fire, without a real terminal.
'''

from unittest.mock import Mock

import pytest

from tui_app import tui_base
from tui_app.row_screen import row_screen


@pytest.fixture(autouse=True)
def patch_curses(monkeypatch):
    monkeypatch.setattr(tui_base.curses, "color_pair", lambda n: n)


def fake_field(screen_key, can_edit, handled=False):
    r'''A stand-in field.  process_key returns None (handled) or the key (not handled).'''
    f = Mock(name=f"field{screen_key}")
    f.screen_key = screen_key
    f.can_edit = can_edit
    f.process_key.side_effect = (lambda key: None) if handled else (lambda key: key)
    return f


def make_screen(fields):
    s = row_screen("test")
    s.app = Mock(name="app")
    s.fields = fields
    return s


def test_tab_navigation_skips_readonly_and_wraps():
    s = make_screen([fake_field(0, False), fake_field(1, True),
                     fake_field(2, False), fake_field(3, True)])
    # Tab from nothing -> first editable (index 1)
    assert s.process_key('\t') is None
    assert s.active_field is s.fields[1]
    s.fields[1].activate.assert_called_once()
    # Tab -> next editable (index 3): deactivate old, activate new
    assert s.process_key('\t') is None
    assert s.active_field is s.fields[3]
    s.fields[1].deactivate.assert_called_once()
    s.fields[3].activate.assert_called_once()
    # Tab -> wraps back to index 1
    assert s.process_key('\t') is None
    assert s.active_field is s.fields[1]


def test_shift_tab_goes_backward():
    s = make_screen([fake_field(0, False), fake_field(1, True),
                     fake_field(2, False), fake_field(3, True)])
    s.process_key('\t')                     # -> index 1
    assert s.process_key('KEY_BTAB') is None
    assert s.active_field is s.fields[3]     # previous editable, wrapping upward


def test_key_routed_to_active_field():
    f = fake_field(0, True, handled=True)
    s = make_screen([f])
    s.active_field = f
    assert s.process_key('x') is None        # active field handled it
    f.process_key.assert_called_once_with('x')


def test_grow_refresh_records_refocus():
    f = fake_field(0, True)
    f.process_key.side_effect = lambda key: 'REFRESH'   # the field grew
    s = make_screen([f])
    s.active_field = f
    assert s.process_key('x') == 'REFRESH'
    assert s._refocus == 0                    # remembered which field to re-focus after the redraw


# --- draw_body: multi-line grow rebuild (real fields) ---------------------------------------------

class FakeColumn:
    def __init__(self, name, can_edit=False, calculated=False, edit_width=None, alignment="left"):
        self.name = name
        self.can_edit = can_edit
        self.calculated = calculated
        self.edit_width = edit_width
        self.alignment = alignment

    def validate(self, s):
        pass

    def column_attr_pair(self, row):
        return 0x70


class FakeRow:
    row_screen_commands = ()
    table_name = "T"

    def __init__(self, columns, values):
        self.columns = columns
        self._values = dict(values)

    def copy(self):
        return FakeRow(self.columns, self._values)

    def get(self, name):
        return str(self._values.get(name, ""))

    def set(self, name, val):
        self._values[name] = val

    def human_key(self):
        return "k"


def make_row_screen(columns, values, cols=25, lines=40):
    s = row_screen.for_update(FakeRow(columns, values))
    s.app = Mock(name="app")
    s.cols = cols
    s.lines = lines
    s.init()
    return s


def test_draw_body_sizes_by_line_count():
    cols = [FakeColumn("a"), FakeColumn("b", can_edit=True)]
    s = make_row_screen(cols, {"a": "short", "b": "x"})
    s.draw_body()
    assert len(s.fields) == 2
    assert s.fields[0].nlines == 1           # short values fit one line (no *1.2 slack)
    assert s.fields[1].nlines == 1


def test_draw_body_grow_refresh_preserves_edit_and_refocuses():
    cols = [FakeColumn("a", can_edit=True)]
    s = make_row_screen(cols, {"a": "x"})
    s.draw_body()
    f = s.fields[0]
    # simulate typing a long value into the field: the edit lives in the field, not self.row
    f.text = "a much longer edited value that wraps"
    f.changed = True
    f.position = len(f.text)
    s.active_field = f
    s._refocus = 0                           # as process_key would set on a grow
    s.draw_body()
    new = s.fields[0]
    assert new is not f                       # rebuilt
    assert new.text == "a much longer edited value that wraps"   # from_field, not the stale row "x"
    assert new.changed                        # preserved -> still submits
    assert new.nlines >= 2                    # grew to fit
    assert s.active_field is new              # re-focused
    assert s.row.get("a") == "x"             # row NOT updated until submit

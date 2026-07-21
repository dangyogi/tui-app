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
    f.changed = False
    f.process_key.side_effect = (lambda key: None) if handled else (lambda key: key)
    return f


def make_screen(fields):
    s = row_screen("test")
    s.app = Mock(name="app")
    s.fields = fields
    s.row_screen_commands = ['Cancel', 'Apply']   # buttons are part of the Tab cycle
    s.button_y = 20
    s.command_buttons_x = [(0, 5), (9, 13)]
    return s


def test_tab_cycles_fields_then_buttons():
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
    # Tab off the last field -> first button (Cancel), field deactivated
    assert s.process_key('\t') is None
    assert s.active_field is None
    assert s.focused_button == 0
    s.fields[3].deactivate.assert_called_once()
    # Tab -> second button (Apply)
    assert s.process_key('\t') is None
    assert s.focused_button == 1
    # Tab -> wraps back to the first editable field
    assert s.process_key('\t') is None
    assert s.active_field is s.fields[1]
    assert s.focused_button is None


def test_shift_tab_goes_backward():
    s = make_screen([fake_field(0, False), fake_field(1, True),
                     fake_field(2, False), fake_field(3, True)])
    s.process_key('\t')                     # -> field 1
    assert s.process_key('KEY_BTAB') is None
    assert s.active_field is None
    assert s.focused_button == 1             # BTab off the first field wraps to the last button (Apply)


def test_enter_runs_focused_button():
    back = Mock(name="back")
    s = make_screen([fake_field(0, True)])
    s.back = back
    s.focused_button = 0                     # 'Cancel' -> Back
    assert s.process_key('\n') is back
    # Space runs it too
    s.focused_button = 0
    assert s.process_key(' ') is back


def test_esc_drops_button_focus_and_stays():
    s = make_screen([fake_field(0, True)])
    s.focused_button = 1
    assert s.process_key('\x1B') is None
    assert s.focused_button is None


def test_active_popup_gets_keys_first():
    # base screen.process_key routes to the popup before field/button handling (Esc closes it)
    f = fake_field(0, True)
    s = make_screen([f])
    s.active_field = f
    popup = Mock(name="popup")
    popup.process_key.return_value = None            # popup consumed the key (closed itself)
    s.popup = popup
    assert s.process_key('\x1B') is None
    popup.process_key.assert_called_once_with('\x1B')
    f.process_key.assert_not_called()                # popup won -> field never saw the Esc


def test_key_routed_to_active_field():
    f = fake_field(0, True, handled=True)
    s = make_screen([f])
    s.active_field = f
    assert s.process_key('x') is None        # active field handled it
    f.process_key.assert_called_once_with('x')


def test_f8_backs_when_unchanged():
    back = object()
    s = make_screen([fake_field(0, False), fake_field(1, True)])
    s.back = back
    assert s.process_key('KEY_F(8)') is back    # F8 = Back; view-only -> back


def test_esc_routed_to_active_field_and_stays():
    f = fake_field(0, True, handled=True)       # the field owns Esc-abort now (consumes it)
    s = make_screen([f])
    s.back = object()
    s.active_field = f
    assert s.process_key('\x1B') is None        # Esc never leaves
    f.process_key.assert_called_once_with('\x1B')   # forwarded to the field (which aborts + re-selects)
    assert s.active_field is f                   # stays focused (no screen-level deselect)


def test_f8_blocked_with_unapplied_changes():
    f = fake_field(0, True)
    f.changed = True
    s = make_screen([f])
    s.back = object()
    s.cols = 80
    s.button_y = 10
    assert s.process_key('KEY_F(8)') is None    # unapplied changes -> stay
    assert s.msg_len > 0                        # a message was shown


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

    def __getattr__(self, name):        # copy_to_master reads getattr(self.row, attr)
        try:
            return self._values[name]
        except KeyError:
            raise AttributeError(name)

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


# --- task 5b: accept-field / recompute / Apply ----------------------------------------------------

def test_accept_field_writes_to_row():
    cols = [FakeColumn("qty", can_edit=True)]
    s = make_row_screen(cols, {"qty": "1"})
    s.draw_body()
    f = s.fields[0]
    f.text = "5"
    f.changed = True
    assert s.accept_field(f) is True
    assert s.row.get("qty") == "5"           # written into the copy
    assert "qty" in s.attrs_changed
    assert not f.changed


def test_accept_field_invalid_stays_and_messages():
    cols = [FakeColumn("qty", can_edit=True)]
    s = make_row_screen(cols, {"qty": "1"})
    s.draw_body()
    s.cols = 80
    s.button_y = 20
    f = s.fields[0]
    def bad(text):
        raise ValueError("bad value")
    f.field_shared.convert_fn = bad          # accept_field validates via field.convert() (convert_fn)
    f.text = "x"
    f.changed = True
    assert s.accept_field(f) is False
    assert s.error_field is f
    assert s.msg_len > 0
    assert s.row.get("qty") == "1"           # NOT written
    assert "qty" not in s.attrs_changed


def test_recompute_updates_readonly_fields():
    cols = [FakeColumn("qty", can_edit=True), FakeColumn("total")]   # total is read-only
    s = make_row_screen(cols, {"qty": "1", "total": "2"})
    s.draw_body()
    total_field = s.fields[1]
    assert total_field.text == "2"
    s.row.set("total", "8")                   # a recomputed value in the copy
    s.recompute()
    assert total_field.text == "8"            # read-only field repainted from self.row


def test_tab_accepts_then_moves():
    cols = [FakeColumn("a", can_edit=True), FakeColumn("b", can_edit=True)]
    s = make_row_screen(cols, {"a": "1", "b": "2"})
    s.draw_body()
    s.activate_field(s.fields[0])
    s.fields[0].text = "9"
    s.fields[0].changed = True
    s.process_key('\t')                       # accept a, then move to b
    assert s.row.get("a") == "9"
    assert s.active_field is s.fields[1]


def test_apply_copies_to_master():
    cols = [FakeColumn("a", can_edit=True)]
    master = FakeRow(cols, {"a": "1"})
    s = row_screen.for_update(master)
    s.app = Mock(name="app")
    s.cols = 25
    s.lines = 40
    s.init()
    s.draw_body()
    back = object()
    s.back = back
    s.activate_field(s.fields[0])
    s.fields[0].text = "7"
    s.fields[0].changed = True
    assert s.execute('Apply') is back
    assert master.get("a") == "7"             # accepted edit written through to the master row


def test_accept_blanked_field_skips_type_check():
    cols = [FakeColumn("qty", can_edit=True)]
    s = make_row_screen(cols, {"qty": "5"})
    s.draw_body()
    f = s.fields[0]
    f.field_shared.convert_fn = float          # float("") would raise -- must not be called
    f.text = ""                                 # blanked (optional field)
    f.changed = True
    assert s.accept_field(f) is True            # empty -> skip type-check, accept
    assert s.row.get("qty") == ""               # written as blank (required-check handles required)


def test_apply_after_blanking_optional_field():
    # blanking an optional field then Apply must not choke (copy_to_master uses the csv string)
    cols = [FakeColumn("a", can_edit=True)]
    master = FakeRow(cols, {"a": "5"})
    s = row_screen.for_update(master)
    s.app = Mock(name="app")
    s.cols = 25
    s.lines = 40
    s.init()
    s.draw_body()
    s.back = object()
    s.activate_field(s.fields[0])
    s.fields[0].text = ""                    # blank it
    s.fields[0].changed = True
    assert s.execute('Apply') is s.back
    assert master.get("a") == ""             # blank written through (via get() -> "")


def test_accept_all_accepts_every_changed_field():
    # a field edited but never Tab-accepted (e.g. entered then Apply clicked) must still be captured
    cols = [FakeColumn("a", can_edit=True), FakeColumn("b", can_edit=True)]
    s = make_row_screen(cols, {"a": "1", "b": "2"})
    s.draw_body()
    s.fields[0].text = "9"; s.fields[0].changed = True
    s.fields[1].text = "8"; s.fields[1].changed = True
    assert s.accept_all() is True
    assert s.row.get("a") == "9" and s.row.get("b") == "8"
    assert s.attrs_changed == {"a", "b"}


def test_mouse_click_field_accepts_previous():
    cols = [FakeColumn("a", can_edit=True), FakeColumn("b", can_edit=True)]
    s = make_row_screen(cols, {"a": "1", "b": "2"})
    s.app.screen = s                         # so a field's set_position reaches the real activate_field
    s.draw_body()
    s.activate_field(s.fields[0])
    s.fields[0].text = "9"; s.fields[0].changed = True
    fb = s.fields[1]
    s.process_mouse((0, fb.begin_x, fb.begin_y, 0, tui_base.curses.BUTTON1_CLICKED))
    assert s.row.get("a") == "9"             # field a accepted when the click switched fields
    assert "a" in s.attrs_changed
    assert s.active_field is fb


def test_has_unsaved_includes_unapplied_field_edits():
    f = fake_field(0, True)
    s = make_screen([f])
    s.app.changed = False
    assert s.has_unsaved() is False              # app clean + no field edits
    f.changed = True
    assert s.has_unsaved() is True               # an unapplied field edit counts as unsaved


def test_f12_confirms_with_unapplied_field_edits(monkeypatch):
    f = fake_field(0, True)
    f.changed = True
    s = make_screen([f])
    s.app.changed = False                        # app itself is clean; only the field is edited
    s.cols = 80
    s.lines = 24
    rec = {}
    def fake_confirm(title, screen, cmd_fn, y, x, outside_space='below'):
        rec.update(title=title, cmd_fn=cmd_fn)
        return Mock(name="popup")
    monkeypatch.setattr(tui_base, "popup_confirm", fake_confirm)
    assert s.process_key('KEY_F(12)') is None    # F12 -> confirm, don't silently discard the edit
    assert s.popup is not None
    assert rec['cmd_fn']('Yes') == 'APP_ABORT'


def test_f12_exits_clean_row():
    s = make_screen([fake_field(0, True)])
    s.app.changed = False
    assert s.process_key('KEY_F(12)') == 'APP_EXIT'   # nothing unapplied -> exit cleanly


def test_create_duplicate_key_shows_message_and_stays():
    # table.insert raising ValueError (dup key / bad FK) must not crash: show a message, stay on form
    cols = [FakeColumn("item", can_edit=True)]

    class CreateRow(FakeRow):
        row_screen_commands = ()
        def check_required(self, attrs_in):
            pass                                  # nothing missing -> validate() passes

    class DupTable:
        name = "T"
        columns = cols
        def row_class(self, create=False):
            return CreateRow(cols, {})
        def insert(self, **attrs):
            raise ValueError("T: duplicate key 'dup'")

    s = row_screen.for_create(DupTable())
    s.app = Mock(name="app")
    s.cols = 40
    s.lines = 24
    s.init()
    s.draw_body()
    s.fields[0].text = "dup"
    s.fields[0].changed = True
    assert s.execute('Create') is None            # dup -> stays on the form (not self.back)
    assert s.msg_len > 0                            # error message was shown


def test_create_missing_required_shows_message_and_stays():
    # check_required raising ValueError must be caught by validate(): show a message, stay on form
    cols = [FakeColumn("item", can_edit=True)]

    class ReqRow(FakeRow):
        row_screen_commands = ()
        def check_required(self, attrs_in):
            raise ValueError("T.check_required: missing attrs=['unit']")

    class ReqTable:
        name = "T"
        columns = cols
        def row_class(self, create=False):
            return ReqRow(cols, {})
        def insert(self, **attrs):
            raise AssertionError("insert must not be reached when required check fails")

    s = row_screen.for_create(ReqTable())
    s.app = Mock(name="app")
    s.cols = 40
    s.lines = 24
    s.init()
    s.draw_body()
    s.fields[0].text = "x"
    s.fields[0].changed = True
    assert s.execute('Create') is None            # required check failed -> stay
    assert s.msg_len > 0


def test_recompute_tolerates_calc_field_error():
    # a calculated field whose get() raises (FK lookup on a not-yet-valid key) must not crash recompute
    cols = [FakeColumn("qty", can_edit=True), FakeColumn("unit")]   # unit read-only/calculated
    s = make_row_screen(cols, {"qty": "1", "unit": "ea"})
    s.draw_body()
    assert s.fields[1].text == "ea"
    orig_get = s.row.get
    def raising_get(name):
        if name == "unit":
            raise KeyError("Foobar")           # calc can't compute for an invalid item
        return orig_get(name)
    s.row.get = raising_get
    s.recompute()                              # must not raise
    assert s.fields[1].text == ""              # calc field blanked until inputs are valid

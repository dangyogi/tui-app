# test_menu_screen.py

r'''Tests for menu_screen action navigation, which now uses the base (object-based) activate_field.

State-focused: menu_screen is built with minimal FakeActions (enough for __init__), then self.fields is
replaced with Mock action fields so we can assert which becomes active without a real terminal.
'''

from unittest.mock import Mock

from tui_app.menu_screen import menu_screen


class FakeAction:
    def __init__(self, name, can_run=True, number="1", task=None, column_break=False):
        self.name = name
        self.can_run = can_run
        self.number = number
        self.task = task
        self.column_break = column_break


def fake_action_field(screen_key, can_run):
    f = Mock(name=f"af{screen_key}")
    f.screen_key = screen_key
    f.action.can_run = can_run
    return f


def make_menu():
    actions = {1: FakeAction("a1"), 2: FakeAction("a2"), 3: FakeAction("a3")}
    m = menu_screen(actions, title="M")
    m.app = Mock(name="app")
    # index 1's action can't run -> navigation should skip it
    m.fields = [fake_action_field(0, True), fake_action_field(1, False), fake_action_field(2, True)]
    return m


def test_key_down_selects_first_runnable_then_skips_unrunnable():
    m = make_menu()
    assert m.process_key('KEY_DOWN') is None      # nothing active -> first runnable (index 0)
    assert m.active_field is m.fields[0]
    m.fields[0].activate.assert_called_once()

    assert m.process_key('KEY_DOWN') is None      # skip non-runnable index 1 -> index 2
    assert m.active_field is m.fields[2]
    m.fields[0].deactivate.assert_called_once()
    m.fields[2].activate.assert_called_once()


def test_key_up_wraps_to_last_runnable():
    m = make_menu()
    m.process_key('KEY_DOWN')                      # -> index 0
    assert m.process_key('KEY_UP') is None         # up from 0 wraps to last runnable (index 2)
    assert m.active_field is m.fields[2]


def test_f8_backs():
    back = object()
    m = make_menu()
    m.back = back
    assert m.process_key('KEY_F(8)') is back       # F8 = Back, via the base screen + execute('Back')


def test_f8_on_top_menu_is_noop():
    m = make_menu()                                # back defaults to None (top menu)
    assert m.process_key('KEY_F(8)') is None       # nowhere to go -> harmless no-op (keeps looping)


def test_f1_shows_help(monkeypatch):
    m = make_menu()
    called = []
    monkeypatch.setattr(m, "show_help", lambda: called.append(True))
    assert m.process_key('KEY_F(1)') is None       # F1 -> base screen.show_help
    assert called and m.help_lines                 # menu_screen defines help_lines


def test_active_popup_gets_keys_first():
    m = make_menu()
    popup = Mock(name="popup")
    popup.process_key.return_value = None           # popup consumed the key (e.g. Esc closes help)
    m.popup = popup
    assert m.process_key('\x1B') is None
    popup.process_key.assert_called_once_with('\x1B')

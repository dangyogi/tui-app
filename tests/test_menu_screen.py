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

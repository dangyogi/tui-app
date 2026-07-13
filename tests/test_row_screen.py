# test_row_screen.py

r'''Tests for row_screen field navigation, which now uses the base (object-based) activate_field.

State-focused: fields are Mocks carrying just screen_key/can_edit/process_key, so we assert which field
becomes active and that activate/deactivate fire, without a real terminal.
'''

from unittest.mock import Mock

from tui_app.row_screen import row_screen


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

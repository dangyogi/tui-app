# test_screen.py

r'''Tests for the base tui_base.screen behavior shared by all screens.'''

from unittest.mock import Mock

from tui_app.tui_base import screen


def test_activate_field():
    s = screen("title")
    f1, f2 = Mock(name="f1"), Mock(name="f2")

    s.activate_field(f1)                 # nothing active -> just highlight f1
    assert s.active_field is f1
    f1.activate.assert_called_once()
    f1.deactivate.assert_not_called()

    s.activate_field(f2)                 # switch: un-highlight f1, highlight f2
    assert s.active_field is f2
    f1.deactivate.assert_called_once()
    f2.activate.assert_called_once()

    s.activate_field(f2)                 # same field -> no-op
    assert f2.activate.call_count == 1
    assert f2.deactivate.call_count == 0

    s.activate_field(None)               # clear focus: un-highlight f2, nothing new
    assert s.active_field is None
    f2.deactivate.assert_called_once()

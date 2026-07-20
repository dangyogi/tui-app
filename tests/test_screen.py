# test_screen.py

r'''Tests for the base tui_base.screen behavior shared by all screens.'''

from unittest.mock import Mock

import pytest

from tui_app import tui_base
from tui_app.tui_base import screen, popup_message


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


@pytest.fixture(autouse=True)
def patch_curses(monkeypatch):
    monkeypatch.setattr(tui_base.curses, "color_pair", lambda n: n)


def make_message():
    s = screen("host")
    s.app = Mock(name="app")
    s.app.stdscr.inch.return_value = 0       # popup captures overlaid chars via inch
    s.lines = 24
    s.cols = 80
    s.popup = popup_message("Note", s, ["hello"])
    return s


@pytest.mark.parametrize("key", ['\x1B', 'KEY_DC', 'KEY_ENTER', '\n', ' '])
def test_popup_message_dismisses_on_key(key):
    s = make_message()
    assert s.popup.process_key(key) is None
    assert s.popup is None                   # delete() cleared the screen's popup


def test_popup_message_ignores_other_keys():
    s = make_message()
    popup = s.popup
    assert popup.process_key('x') is None     # consumed (ignored), not bubbled
    assert s.popup is popup                    # still up


def test_popup_message_dismisses_on_left_click():
    s = make_message()
    assert s.popup.process_mouse((0, 5, 5, 0, tui_base.curses.BUTTON1_CLICKED)) is None
    assert s.popup is None


def test_popup_message_ignores_other_mouse():
    s = make_message()
    popup = s.popup
    assert popup.process_mouse((0, 5, 5, 0, tui_base.curses.BUTTON4_PRESSED)) is None
    assert s.popup is popup                    # scroll doesn't dismiss

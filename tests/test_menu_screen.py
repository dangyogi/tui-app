# test_menu_screen.py

r'''Tests for menu_screen action navigation, which now uses the base (object-based) activate_field.

State-focused: menu_screen is built with minimal FakeActions (enough for __init__), then self.fields is
replaced with Mock action fields so we can assert which becomes active without a real terminal.
'''

from unittest.mock import Mock

import pytest

from tui_app import tui_base
from tui_app.menu_screen import menu_screen


@pytest.fixture(autouse=True)
def patch_curses(monkeypatch):
    # color_pair needs a live terminal; identity is enough (real fields in the ask_question tests paint).
    monkeypatch.setattr(tui_base.curses, "color_pair", lambda n: n)


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


def test_tab_and_btab_mirror_down_and_up():
    m = make_menu()
    assert m.process_key('\t') is None             # Tab == Down: nothing active -> first runnable
    assert m.active_field is m.fields[0]
    assert m.process_key('\t') is None             # Tab: skip non-runnable index 1 -> index 2
    assert m.active_field is m.fields[2]
    assert m.process_key('KEY_BTAB') is None       # BTab == Up: back to index 0
    assert m.active_field is m.fields[0]


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


def test_left_click_runs_action():
    m = make_menu()
    for i, f in enumerate(m.fields):
        f.enclose.return_value = (i == 0)         # pointer over field 0 (runnable)
        f.action.execute.return_value = f"ran{i}"
    result = m.process_mouse((0, 5, 5, 0, tui_base.curses.BUTTON1_CLICKED))
    assert result == "ran0"                       # a single click runs the action (UI line 45)
    m.fields[0].activate.assert_called_once()     # ...selecting it first
    assert m.active_field is m.fields[0]


def test_left_click_ignores_unrunnable_action():
    m = make_menu()
    event = (0, 5, 5, 0, tui_base.curses.BUTTON1_CLICKED)
    for i, f in enumerate(m.fields):
        f.enclose.return_value = (i == 1)         # pointer over field 1 (can't run)
    assert m.process_mouse(event) == event        # bubbled, not executed
    m.fields[1].activate.assert_not_called()


def test_esc_dismisses_question():
    m = make_menu()
    m.max_y, m.cols = 5, 80
    m.question = "How many?"
    m.answer = Mock(name="answer")                  # the isolated ask_question field
    callback = m.callback = Mock(name="callback")   # keep a ref: clear_question nulls m.callback
    assert m.process_key('\x1B') is None            # Esc dismisses the whole question (never leaves)
    assert m.answer is None                         # clear_question tore it down...
    assert m.question is None
    callback.assert_not_called()                    # ...without running the callback


# --- ask_question validation protocol -------------------------------------------------------------

def make_menu_q(convert_fn=int, callback=None):
    m = make_menu()
    m.app.screen = m                                # so the answer field's activate_field routes to m
    m.max_y, m.cols = 5, 80
    m.ask_question("Q", callback or (lambda v: f"ok{v}"), "0", convert_fn=convert_fn)
    return m


def test_answer_is_never_active_field():
    m = make_menu_q(convert_fn=int)
    cmd = m.fields[0]
    m.activate_field(cmd)                           # the running command is highlighted
    m.activate_field(m.answer)                       # the answer must not steal it
    assert m.active_field is cmd


def test_answer_arrow_moves_on_first_press_and_keeps_command():
    m = make_menu_q(convert_fn=int)                 # default "0": answer fully selected (pos 0, len 1)
    cmd = m.fields[0]
    m.activate_field(cmd)                           # running the command highlights it
    m.answer.process_key('KEY_RIGHT')               # FIRST press
    assert m.answer.position == 1                    # cursor moved immediately (not re-selected)
    assert m.answer.selection_len == 0
    assert m.active_field is cmd                     # command stays highlighted while answering


def test_ask_question_selects_default_for_replace():
    m = make_menu_q(convert_fn=int)                 # default "0"
    assert m.answer.position == 0
    assert m.answer.selection_len == len("0")       # whole default selected -> first keystroke replaces


def test_answer_bad_type_shows_error_and_keeps_question():
    ran = []
    m = make_menu_q(convert_fn=int, callback=lambda v: ran.append(v))
    m.answer.text = "abc"                           # not an int
    assert m.run_callback("abc") is None
    assert m.question == "Q"                        # prompt stays up (not torn down)
    assert m.answer is not None
    assert not ran                                  # app callback never called
    assert m.error_message is not None                    # error is displayed


def test_answer_business_error_reasks_with_entry():
    def cb(v):
        raise ValueError("too big")                 # type-valid but business-invalid
    m = make_menu_q(convert_fn=int, callback=cb)
    m.answer.text = "99"
    assert m.run_callback("99") is None
    assert m.question == "Q"                        # re-asked
    assert m.answer.text == "99"                    # ...with the rejected entry as the default
    assert m.error_message is not None                    # error shown


def test_esc_two_stage_error_then_bail():
    m = make_menu_q(convert_fn=int, callback=lambda v: (_ for _ in ()).throw(ValueError("nope")))
    m.answer.text = "99"
    m.run_callback("99")                            # business error -> re-asks + shows error below
    assert m.error_message is not None and m.question == "Q"
    assert m.process_key('\x1B') is None            # FIRST Esc: dismiss the error only
    assert m.error_message is None
    assert m.question == "Q" and m.answer is not None   # ...question stays up
    assert m.process_key('\x1B') is None            # SECOND Esc: bail out of the question
    assert m.question is None and m.answer is None


def test_show_error_clips_long_message():
    m = make_menu()
    m.max_y, m.cols = 5, 40
    m.show_error("x" * 200)                         # far wider than cols -> must clip, not overflow
    assert m.error_message is not None
    assert len(m.error_message) <= m.cols           # clipped to fit the line


def test_answer_success_converts_clears_and_returns():
    got = []
    m = make_menu_q(convert_fn=int, callback=lambda v: got.append(v) or "next")
    m.answer.text = "7"
    assert m.run_callback("7") == "next"            # returns the callback's result
    assert got == [7]                               # callback got the CONVERTED int, not "7"
    assert m.question is None                        # prompt torn down
    assert m.answer is None


def test_answer_chaining_leaves_next_question_up():
    m = make_menu_q(convert_fn=int, callback=None)
    def cb(v):
        m.ask_question("Q2", lambda v2: "done", "1", convert_fn=int)   # chain to another question
        return None
    m.callback = cb
    m.answer.text = "5"
    assert m.run_callback("5") is None
    assert m.question == "Q2"                        # the chained question is the one left up
    assert m.answer is not None

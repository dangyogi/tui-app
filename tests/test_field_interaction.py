# test_field_interaction.py

import curses
import pytest
from unittest.mock import Mock, call

from tui_app import field
from tui_app.field import field_shared, read_only_single_line, editable_single_line


@pytest.fixture(autouse=True)
def something(monkeypatch):
    monkeypatch.setattr(field.curses, 'color_pair', lambda x: x)
    monkeypatch.setattr(field.curses, 'ascii',
                        lambda x: x in " abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")


@pytest.fixture
def share_1_line():
    return field_shared("share_1_line", nlines=1, begin_x=30, ncols=20, app=Mock(name="app"))

@pytest.fixture
def text():
      # x   3
      #     0123456789012345
    return "but are created"

@pytest.fixture
def e_field(share_1_line, text):
    e_field =  editable_single_line(1, text, share_1_line, begin_y=10)
    e_field.pos_attr = 'REVERSE'
    e_field.attr_pair = 'NORMAL'
    e_field.selection_pair = 'YELLOW'
    e_field.chgat = Mock(name="chgat")
    return e_field

def check_calls(mock, *args):
    if mock.call_count != len(args):
        print("got:")
        for call in mock.call_args_list:
            print(" ", call.args)
        print("expected:")
        for call in args:
            print(" ", call)
    assert mock.call_count == len(args)
    for i in range(len(args)):
        assert mock.call_args_list[i].args == args[i]
    mock.reset_mock()
    assert mock.call_count == 0


def start_select(e_field, index):
    assert not e_field.in_select
    assert e_field.process_mouse((1, 30 + index, 10, 1, curses.BUTTON1_PRESSED)) is None
    assert e_field.position == index
    assert e_field.selection_len == 0
    assert e_field.in_select
    check_calls(e_field.chgat, (index, 1, e_field.pos_attr))

def test_start_select(e_field):
    start_select(e_field, 5)


def select_end(e_field, index):
    assert e_field.process_mouse((1, 30 + index, 10, 1, curses.BUTTON1_RELEASED)) is None
    assert not e_field.chgat.called
    assert not e_field.in_select


def select_forward(e_field, pos, index):
    assert e_field.position == pos
    assert e_field.in_select
    assert e_field.process_mouse((1, 30 + index, 10, 1, curses.REPORT_MOUSE_POSITION)) is None
    assert e_field.position == pos
    assert e_field.selection_len == index - pos + 1
    assert e_field.in_select
    check_calls(e_field.chgat, (pos, 1, e_field.attr_pair), (pos, index - pos + 1, e_field.selection_pair))
    select_end(e_field, index)

def test_select_forward(e_field):
    start_select(e_field, 5)
    select_forward(e_field, 5, 7)


def select_backward(e_field, pos, index):
    assert e_field.position == pos
    assert e_field.in_select
    assert e_field.process_mouse((1, 30 + index, 10, 1, curses.REPORT_MOUSE_POSITION)) is None
    assert e_field.position == pos
    assert e_field.selection_len == index - pos
    assert e_field.in_select
    check_calls(e_field.chgat, (pos, 1, e_field.attr_pair), (index, pos - index, e_field.selection_pair))
    select_end(e_field, index)

def test_select_backward(e_field):
    start_select(e_field, 5)
    select_backward(e_field, 5, 2)


def test_editable_activate_selects_all(e_field):
    e_field.activate()
    assert e_field.position == 0
    assert e_field.selection_len == len(e_field.get_text())
    check_calls(e_field.chgat, (0, len(e_field.get_text()), e_field.selection_pair))


def test_read_only_activate_deactivate_toggle(share_1_line):
    f = read_only_single_line(0, "hello", share_1_line, begin_y=10, paint=False)
    f.reverse_attr = Mock(name="reverse_attr")
    f.activate()
    f.deactivate()
    assert f.reverse_attr.call_count == 2


def test_gen_locations_right_align_offsets_by_pad():
    fs = field_shared("f", nlines=1, begin_x=30, ncols=20, app=Mock(name="app"), alignment="right")
    f = read_only_single_line(0, "42", fs, begin_y=10)    # "42" right-aligned in 20 cols -> pad 18
    assert f.pads == [18]
    # highlighting text indices 0..2 must land on the digits (begin_x + pad), not the left padding
    assert list(f.gen_locations(0, 2)) == [(10, 30 + 18, 2)]


def test_gen_locations_left_align_no_offset():
    fs = field_shared("f", nlines=1, begin_x=30, ncols=20, app=Mock(name="app"), alignment="left")
    f = read_only_single_line(0, "42", fs, begin_y=10)
    assert f.pads == [0]
    assert list(f.gen_locations(0, 2)) == [(10, 30, 2)]


def test_to_index_and_get_col_right_align():
    fs = field_shared("f", nlines=1, begin_x=30, ncols=20, app=Mock(name="app"), alignment="right")
    f = editable_single_line(0, "42", fs, begin_y=10)    # painted -> starts=[0], pads=[18]
    # clicking on the digits maps to the right text index
    assert f.to_index(10, 30 + 18) == 0                  # '4'
    assert f.to_index(10, 30 + 19) == 1                  # '2'
    assert f.to_index(10, 30) == 0                       # click on the left padding -> start of text
    # get_col maps an index back to its padded column
    assert f.get_col(0) == 18
    assert f.get_col(1) == 19


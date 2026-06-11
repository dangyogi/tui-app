# test_field_interaction.py

import curses
import pytest
from unittest.mock import Mock, call

from tui_app import field
from tui_app.field import field_shared, read_only_field, editable_field


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
    e_field =  editable_field(1, text, share_1_line, begin_y=10)
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


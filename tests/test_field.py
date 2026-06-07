# test_read_only_field.py

import pytest
from tui_app.field import wrapper, read_only_field


@pytest.fixture
def wrap_3_lines():
    return wrapper("wrap_3_lines", nlines=3, ncols=20)

@pytest.fixture
def text():
           #         1         2         3         4         5         6         7         8
           #12345678901234567890123456789012345678901234567890123456789012345678901234567890
    return "but are created automatically when test functions request them as parameters."

    # scroll 0:
    #       12345678901234567890
    # ( 0, "but are created     ")
    # (16, "automatically when  ")
    # (35, "test functions [...]")

    # scroll 29:
    #       12345678901234567890
    # (29, "[...] test functions")
    # (50, "request them as     ")
    # (66, "parameters.         ")

@pytest.fixture
def ro_field(text, wrap_3_lines):
    return read_only_field(text, wrap_3_lines, begin_y=10, begin_x=30, paint=False)


def test_gen_locations(ro_field):
    ro_field.starts = [0, 16, 35]
    locations = list(ro_field.gen_locations(8, 57))
    assert len(locations) == 3
    assert locations[0] == (10, 38, 8)
    assert locations[1] == (11, 30, 19)
    assert locations[2] == (12, 30, 14)


def test_gen_locations2(ro_field):
    ro_field.scroll = 29
    ro_field.starts = [29, 50, 66]
    locations = list(ro_field.gen_locations(8, 77))
    assert len(locations) == 3
    assert locations[0] == (10, 36, 14)
    assert locations[1] == (11, 30, 16)
    assert locations[2] == (12, 30, 11)


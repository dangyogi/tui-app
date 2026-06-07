# test_field.py

import pytest
from tui_app.field import wrapper, read_only_field, editable_field


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

    # scroll 19:
    #       12345678901234567890
    # (19, "[...] ally when test")
    # (40, "functions request   ")
    # (58, "them as parameters. ")

    # scroll 52:
    #         12345678901234567890
    # (52,   "[...] them as       ")
    # (66,   "parameters.         ")
    # (None, "                    ")

@pytest.fixture
def ro_field(text, wrap_3_lines):
    return read_only_field(text, wrap_3_lines, begin_y=10, begin_x=30, paint=False)

@pytest.fixture
def e_field(text, wrap_3_lines):
    return editable_field(text, wrap_3_lines, begin_y=10, begin_x=30, paint=False)


def test_gen_locations(ro_field):
    ro_field.starts = [0, 16, 35]
    locations = list(ro_field.gen_locations(8, 57))
    assert len(locations) == 3
    assert locations[0] == (10, 38, 8)
    assert locations[1] == (11, 30, 19)
    assert locations[2] == (12, 30, 14)


def test_gen_locations2(ro_field):
    ro_field.scroll = 19
    ro_field.starts = [19, 40, 58]
    locations = list(ro_field.gen_locations(8, 77))
    assert len(locations) == 3
    assert locations[0] == (10, 36, 14)
    assert locations[1] == (11, 30, 18)
    assert locations[2] == (12, 30, 19)


def test_gen_locations3(ro_field):
    ro_field.scroll = 52
    ro_field.starts = [52, 66, None]
    locations = list(ro_field.gen_locations(8, 77))
    assert len(locations) == 2
    assert locations[0] == (10, 36, 8)
    assert locations[1] == (11, 30, 11)


@pytest.mark.parametrize("y, ans_y", [
    (9, False),
    (10, True),
    (11, True),
    (12, True),
    (13, False),
])
@pytest.mark.parametrize("x, ans_x", [
    (29, False),
    (30, True),
    (31, True),
    (48, True),
    (49, True),
    (50, False),
])
def test_enclose(e_field, y, x, ans_y, ans_x):
    assert e_field.enclose(y, x) == (ans_y and ans_x)


@pytest.mark.parametrize("y, x, ans", [
    (10, 30, 0),
    (10, 44, 14),
    (10, 45, 15),
    (10, 46, 15),
    (10, 49, 15),
    (12, 30, 35),
    (12, 43, 48),
    (12, 44, 48),
    (12, 45, 48),
    (12, 46, 48),
    (12, 49, 48),
])
def test_to_index(e_field, y, x, ans):
    # scroll 0:
    #       12345678901234567890
    # ( 0, "but are created     ")
    # (16, "automatically when  ")
    # (35, "test functions [...]")

    e_field.starts = [0, 16, 35]
    assert e_field.to_index(y, x) == ans


@pytest.mark.parametrize("y, x, ans", [
    (10, 30, 25),
    (10, 31, 25),
    (10, 35, 25),
    (10, 36, 25),
    (10, 37, 26),
    (10, 48, 37),
    (10, 49, 38),
    (12, 30, 58),
    (12, 47, 75),
    (12, 48, 76),
    (12, 49, 76),
])
def test_to_index2(e_field, y, x, ans):
    # scroll 19:
    #       12345678901234567890
    # (19, "[...] ally when test")
    # (40, "functions request   ")
    # (58, "them as parameters. ")

    e_field.scroll = 19
    e_field.starts = [19, 40, 58]
    assert e_field.to_index(y, x) == ans


@pytest.mark.parametrize("y, x, ans", [
    (11, 30, 66),
    (11, 40, 76),
    (11, 41, 76),
    (11, 48, 76),
    (11, 49, 76),
    (12, 30, 76),
    (12, 31, 76),
    (12, 48, 76),
    (12, 49, 76),
])
def test_to_index3(e_field, y, x, ans):
    # scroll 52:
    #         12345678901234567890
    # (52,   "[...] them as       ")
    # (66,   "parameters.         ")
    # (None, "                    ")

    e_field.scroll = 52
    e_field.starts = [52, 66, None]
    assert e_field.to_index(y, x) == ans

# test_field.py

import pytest
from tui_app.field import field_shared, read_only_field, editable_field


@pytest.fixture
def share_3_lines():
    return field_shared("share_3_lines", nlines=3, begin_x=30, ncols=20)

@pytest.fixture
def text():
           #         1         2         3         4         5         6         7         8
           #1234567890123456789012345678901234567890123456789012345678901234567890123456789012345
   #return "but are created automatically when test functions request them as parameters."
    return "but are created         automatically when test functions request them as parameters."

    # scroll 0:
    #       12345678901234567890
    # ( 0, "but are created     ")
    # (24, "automatically when  ")
    # (43, "test functions [...]")

    # scroll 27:
    #       12345678901234567890
    # (27, "[...] ally when test")
    # (48, "functions request   ")
    # (66, "them as parameters. ")

    # scroll 60:
    #         12345678901234567890
    # (60,   "[...] them as       ")
    # (74,   "parameters.         ")
    # (None, "                    ")

@pytest.fixture
def ro_field(text, share_3_lines):
    return read_only_field(0, text, share_3_lines, begin_y=10, paint=False)

@pytest.fixture
def ro_field_empty(share_3_lines):
    return read_only_field(0, "", share_3_lines, begin_y=10, paint=False)

@pytest.fixture
def e_field(text, share_3_lines):
    return editable_field(0, text, share_3_lines, begin_y=10, paint=False)


def test_gen_locations(ro_field):
    # scroll 0:
    #       12345678901234567890
    # ( 0, "but are created     ")
    # (24, "automatically when  ")
    # (43, "test functions [...]")

    ro_field.starts = [0, 24, 43]
    locations = list(ro_field.gen_locations(8, 65))  # 8 is 'c' in created, 65 is space before them
    assert len(locations) == 3
    assert locations[0] == (10, 38, 12)
    assert locations[1] == (11, 30, 19)
    assert locations[2] == (12, 30, 14)


def test_gen_locations2(ro_field):
    # scroll 27:
    #       12345678901234567890
    # (27, "[...] ally when test")
    # (48, "functions request   ")
    # (66, "them as parameters. ")

    ro_field.scroll = 27
    ro_field.starts = [27, 48, 66]
    locations = list(ro_field.gen_locations(8, 85))  # 8 is 'c' in created, 85 is after end of text
    assert len(locations) == 3
    assert locations[0] == (10, 36, 14)
    assert locations[1] == (11, 30, 18)
    assert locations[2] == (12, 30, 19)


def test_gen_locations3A(ro_field):
    # scroll 60:
    #         12345678901234567890
    # (60,   "[...] them as       ")
    # (74,   "parameters.         ")
    # (None, "                    ")

    ro_field.scroll = 60
    ro_field.starts = [60, 74, None]
    locations = list(ro_field.gen_locations(8, 85))
    assert len(locations) == 2
    assert locations[0] == (10, 36, 8)
    assert locations[1] == (11, 30, 11)


def test_gen_locations3B(ro_field):
    # scroll 60:
    #         12345678901234567890
    # (60,   "[...] them as       ")
    # (74,   "parameters.         ")
    # (None, "                    ")

    ro_field.scroll = 60
    ro_field.starts = [60, 74, None]
    locations = list(ro_field.gen_locations(74, 78))   # 74 is 'p' in parameters, 78 is 'm' in parameters
    assert len(locations) == 1
    assert locations[0] == (11, 30, 4)


def test_gen_locations3C(ro_field):
    # scroll 60:
    #         3         4
    #  x      01234567890123456789
    #         12345678901234567890
    # (60,   "[...] them as       ")
    # (74,   "parameters.         ")
    # (None, "                    ")

    ro_field.scroll = 60
    ro_field.starts = [60, 74, None]
    locations = list(ro_field.gen_locations(85, 86))    # 84 is '.'
    assert len(locations) == 1
    assert locations[0] == (11, 41, 1)


@pytest.mark.parametrize("index, lineno", [
    (0, 0),      # 'b' in but
    (15, 0),     # space between "created" and "automatically"
    (24, 1),     # first 'a' in "automatically"
    (42, 1),     # space between "when" and "test"
    (43, 2),     # first 't' in test
    (56, 2),     # 's' in functions
    (57, 2),     # overlapped by right_placeholder
    (62, 2),     # overlapped by right_placeholder
    (63, None),  # past 3rd line
    (64, None),  # past 3rd line
    (65, None),  # past 3rd line
])
def test_get_lineno(ro_field, index, lineno):
    # scroll 0:
    #       12345678901234567890
    # ( 0, "but are created     ")
    # (24, "automatically when  ")
    # (43, "test functions [...]")

    ro_field.starts = [0, 24, 43]
    assert ro_field.get_lineno(index) == lineno


@pytest.mark.parametrize("index, lineno", [
    (0, None),  # 'b' in but
    (26, None), # first 't' in automatically
    (27, 0),    # overlapped by left_placeholder
    (32, 0),    # overlapped by left_placeholder
    (33, 0),    # last 'a' in automatically
    (46, 0),    # end of "test"
    (47, 0),    # space between "test" and "functions"
    (48, 1),    # 'f' in "functions"
    (64, 1),    # 't' in "request"
    (65, 1),    # space between "request" and "them"
    (66, 2),    # 't' in "them"
    (84, 2),    # '.'
])
def test_get_lineno2(ro_field, index, lineno):
    # scroll 27:
    #       12345678901234567890
    # (27, "[...] ally when test")
    # (48, "functions request   ")
    # (66, "them as parameters. ")

    ro_field.scroll = 27
    ro_field.starts = [27, 48, 66]
    assert ro_field.get_lineno(index) == lineno


@pytest.mark.parametrize("index, lineno", [
    (0, None),
    (59, None),
    (60, 0),    # overlapped by left_placeholder
    (65, 0),    # overlapped by left_placeholder
    (66, 0),    # 't' in them
    (74, 1),    # 'p' in parameters
    (84, 1),    # '.'
])
def test_get_lineno3(ro_field, index, lineno):
    # scroll 60:
    #         12345678901234567890
    # (60,   "[...] them as       ")
    # (74,   "parameters.         ")
    # (None, "                    ")

    ro_field.scroll = 60
    ro_field.starts = [60, 74, None]
    assert ro_field.get_lineno(index) == lineno


@pytest.mark.parametrize("index, col", [
    (0, 0),      # 'b' in but
    (15, 15),    # space between "created" and "automatically"
    (24, 0),     # first 'a' in "automatically"
    (42, 18),    # space between "when" and "test"
    (43, 0),     # first 't' in test
    (56, 13),    # 's' in functions
    (57, 14),    # overlapped by right_placeholder
    (62, 19),    # overlapped by right_placeholder
    (63, None),  # past 3rd line
    (64, None),  # past 3rd line
    (65, None),  # past 3rd line
])
def test_get_col(ro_field, index, col):
    # scroll 0:
    #       12345678901234567890
    # ( 0, "but are created     ")
    # (24, "automatically when  ")
    # (43, "test functions [...]")

    ro_field.starts = [0, 24, 43]
    assert ro_field.get_col(index) == col


@pytest.mark.parametrize("index, col", [
    (0, None),  # 'b' in but 
    (26, None), # first 't' in automatically
    (27, 0),    # overlapped by left_placeholder
    (32, 5),    # overlapped by left_placeholder
    (33, 6),    # last 'a' in automatically
    (46, 19),   # end of "test"
    (47, 19),   # space between "test" and "functions"
    (48, 0),    # 'f' in "functions"
    (64, 16),   # 't' in "request"
    (65, 17),   # space between "request" and "them"
    (66, 0),    # 't' in "them"
    (84, 18),   # '.'
])
def test_get_col2(ro_field, index, col):
    # scroll 27:
    #       12345678901234567890
    # (27, "[...] ally when test")
    # (48, "functions request   ")
    # (66, "them as parameters. ")

    ro_field.scroll = 27
    ro_field.starts = [27, 48, 66]
    assert ro_field.get_col(index) == col


@pytest.mark.parametrize("index, col", [
    (0, None),
    (59, None),
    (60, 0),    # overlapped by left_placeholder
    (65, 5),    # overlapped by left_placeholder
    (66, 6),    # 't' in them
    (74, 0),    # 'p' in parameters
    (84, 10),   # '.'
])
def test_get_col3(ro_field, index, col):

    # scroll 60:
    #         12345678901234567890
    # (60,   "[...] them as       ")
    # (74,   "parameters.         ")
    # (None, "                    ")

    ro_field.scroll = 60
    ro_field.starts = [60, 74, None]
    assert ro_field.get_col(index) == col


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
    (10, 30, 0),   # 'b' in but
    (10, 44, 14),  # 'd' in created
    (10, 45, 15),
    (10, 46, 16),
    (10, 47, 17),
    (10, 48, 18),
    (10, 49, 19),
    (12, 30, 43),  # 't' in test
    (12, 43, 56),  # 's' in functions
    (12, 44, 56),
    (12, 45, 56),
    (12, 46, 56),
    (12, 49, 56),
])
def test_to_index(e_field, y, x, ans):
    # scroll 0:
    #       3         4
    #       01234567890123456789
    #       12345678901234567890
    # ( 0, "but are created     ")
    # (24, "automatically when  ")
    # (43, "test functions [...]")

    e_field.starts = [0, 24, 43]
    assert e_field.to_index(y, x) == ans


@pytest.mark.parametrize("y, x, ans", [
    (10, 30, 33),
    (10, 31, 33),
    (10, 35, 33),
    (10, 36, 33),   # last 'a' in automatically
    (10, 37, 34),
    (10, 48, 45),   # 's' in test
    (10, 49, 46),
    (11, 30, 48),   # 'f' in functions
    (12, 30, 66),   # 't' in them
    (12, 47, 83),   # 's' in parameters
    (12, 48, 84),
    (12, 49, 84),
])
def test_to_index2(e_field, y, x, ans):
    # scroll 27:
    #       3         4
    #       01234567890123456789
    #       12345678901234567890
    # (27, "[...] ally when test")
    # (48, "functions request   ")
    # (66, "them as parameters. ")

    e_field.scroll = 27
    e_field.starts = [27, 48, 66]
    assert e_field.to_index(y, x) == ans


@pytest.mark.parametrize("y, x, ans", [
    (11, 30, 74),   # 'p' in parameters
    (11, 40, 84),   # '.'
    (11, 41, 84),
    (11, 48, 84),
    (11, 49, 84),
    (12, 30, 84),
    (12, 31, 84),
    (12, 48, 84),
    (12, 49, 84),
])
def test_to_index3(e_field, y, x, ans):
    # scroll 60:
    #         3         4
    #         01234567890123456789
    #         12345678901234567890
    # (60,   "[...] them as       ")
    # (74,   "parameters.         ")
    # (None, "                    ")

    e_field.scroll = 60
    e_field.starts = [60, 74, None]
    assert e_field.to_index(y, x) == ans

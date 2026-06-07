# test_wrapper.py

import pytest
from tui_app.field import wrapper


def mk_wrap_1_line(alignment):
    """Returns a standard 1-line high wrapper for evaluating table cells."""
    return wrapper("wrap_1_line", nlines=1, ncols=20, alignment=alignment)

@pytest.fixture
def wrap_1_line():
    return mk_wrap_1_line("left")

@pytest.fixture
def wrap_1_line_right():
    return mk_wrap_1_line("right")

@pytest.fixture
def wrap_3_lines():
    return wrapper("wrap_3_lines", nlines=3, ncols=20, alignment="left")


@pytest.mark.parametrize("end, ans", [
    (0, -1),
    (8, 7),
    (12, 9),
    (30, 28),
])
def test_first_non_blank_left(wrap_1_line, end, ans):
           #          1         2         3
           #0123456789012345678901234567890
    text = " Returns a    standard 1-line  "
    assert wrap_1_line.first_non_blank_left(text, end) == ans


@pytest.mark.parametrize("start, ans", [
    (0, 1),
    (8, 9),
    (11, 14),
    (29, 31),
])
def test_first_non_blank(wrap_1_line, start, ans):
           #          1         2         3
           #0123456789012345678901234567890
    text = " Returns a    standard 1-line  "
    assert wrap_1_line.first_non_blank(text, start) == ans


@pytest.mark.parametrize("text_in, text_out", [
    #          1         2
    #012345678901234567890
    ("asdfasdfasdf sdf sadf asd", "asdfasdfasdf sdf sadf asd"),
    ("asdfasdfasdf sdf", "asdfasdfasdf sdf    "),
])
def test_align(wrap_1_line, text_in, text_out):
    assert wrap_1_line.align(text_in) == text_out


def test_wrap0(wrap_1_line):
    """Verifies layout text behavior when scroll is zero (no shifting)."""
    text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    scroll = 0

    # Extract the yielded lines from the generator
    lines = list(wrap_1_line.wrap(text, scroll))
    assert len(lines) == 1

    start_offset, rendered_line = lines[0]
    assert len(rendered_line) == 20

    # When scroll == 0, the start offset should be exactly 0
    assert start_offset == 0
    # Should completely fit the column width (20 chars) without a left placeholder
    assert rendered_line.startswith("A")
    assert rendered_line.endswith(" [...]")

@pytest.mark.parametrize("scroll", (1, 2, 3, 4, 5))
def test_cut_at_both_ends(wrap_1_line, scroll):
    """Validates that under the unified index formula (index = x + scroll),

    the correct first visible character lands at screen column x=6 when scroll > 0.
    """
    text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    # Screen column x=6 must map to text index: 6 + scroll

    lines = list(wrap_1_line.wrap(text, scroll))
    assert len(lines) == 1
    start_index, rendered_line = lines[0]
    assert len(rendered_line) == 20
    assert start_index == scroll

    assert rendered_line.startswith("[...] ")
    assert rendered_line.endswith(" [...]")
    # The character at physical screen column 6 must match text index 7
    assert rendered_line[6] == text[6 + scroll]


@pytest.mark.parametrize("scroll", (6, 7, 8, 19))
def test_right_fits(wrap_1_line, scroll):
    """Parametrized check evaluating text slice points across varying shift levels."""
    text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    lines = list(wrap_1_line.wrap(text, scroll))
    assert len(lines) == 1
    start_index, rendered_line = lines[0]
    assert len(rendered_line) == 20
    assert start_index == scroll
    assert rendered_line.startswith("[...] ")

    # Check last character
    assert rendered_line[len(text) - 1 - scroll] == text[-1]


@pytest.mark.parametrize("wrapper, result", [
    (mk_wrap_1_line("left"),  "Hello World!        "),
    (mk_wrap_1_line("right"), "        Hello World!"),
])
def test_short_text_blank_padding(wrapper, result):
    """Ensures short lines fill the layout matrix cleanly with empty trailing whitespace."""
                 #          1         2         3
                 #0123456789012345678901234567890
    short_text = "Hello World!"

    lines = list(wrapper.wrap(short_text))
    assert len(lines) == 1
    start_index, rendered_line = lines[0]
    assert len(rendered_line) == 20
    assert start_index == 0

    assert rendered_line == result


@pytest.fixture
def text():
           #         1         2         3         4         5         6         7         8
           #12345678901234567890123456789012345678901234567890123456789012345678901234567890
    return "but are created automatically when test functions request them as parameters."

def test_multi_line(wrap_3_lines, text):
    lines = list(wrap_3_lines.wrap(text))
    assert len(lines) == 3
                            #12345678901234567890
    assert lines[0] == ( 0, "but are created     ")
    assert lines[1] == (16, "automatically when  ")
    assert lines[2] == (35, "test functions [...]")


def test_multi_line2(wrap_3_lines, text):
    lines = list(wrap_3_lines.wrap(text, scroll=29))
    assert len(lines) == 3
                            #12345678901234567890
    assert lines[0] == (29, "[...] test functions")
    assert lines[1] == (50, "request them as     ")
    assert lines[2] == (66, "parameters.         ")


def test_multi_line3(wrap_3_lines, text):
    lines = list(wrap_3_lines.wrap(text, scroll=52))
    assert len(lines) == 3
                              #12345678901234567890
    assert lines[0] == (52,   "[...] them as       ")
    assert lines[1] == (66,   "parameters.         ")
    assert lines[2] == (None, "                    ")

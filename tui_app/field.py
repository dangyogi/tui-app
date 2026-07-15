# field.py

r'''This handles user input fields.  Each field is a simple rectangle.  It will scroll long lines to fit.

These are created each time the screen.draw is called.

Therefore, they only see one screen size during their lifetime and only need to draw the text once.
'''

from .tui_base import curses, bstate_str, trace


class field_shared:
    max_waste = 10

    def __init__(self, name, nlines, begin_x, ncols, app=None, validate_fn=None, alignment="left",
                 left_placeholder='[...] ', right_placeholder=' [...]'):
        self.name = name
        self.nlines = nlines
        self.begin_x = begin_x
        self.ncols = ncols
        self.app = app     # only used (shared) by field classes below
        self.validate_fn = validate_fn
        self.alignment = alignment
        self.left_placeholder = left_placeholder
        self.right_placeholder = right_placeholder

    def wrap(self, text, scroll=0):
        r'''Generates (index, pad, line) triples: index is the text offset of the line's first char
        (None for a blank line), pad is the left x-offset of the text within the ncols-wide line
        (0 for left alignment; the leading-pad width for right alignment), and line is the padded text.
        '''
        text = text.rstrip()
        if scroll:
            wtext = self.left_placeholder + text[scroll + len(self.left_placeholder):]
            trace(f"{self.name}.wrap: {self.left_placeholder=!r}, {wtext=!r}")
        else:
            wtext = text
        offset = 0
        start_offset = scroll  # add to offset to get scroll
        for lineno in range(self.nlines):
            if offset >= len(wtext):
                if lineno == 0:  # then offset == 0 and len(wtext) == 0
                    yield 0, 0, ' ' * self.ncols
                    lineno += 1
                if lineno < self.nlines:
                    yield from self.blank_lines(self.nlines - lineno)
                break
            next = offset + self.ncols
            if next >= len(wtext):
                # next past end of wtext
                yield start_offset + offset, *self.align(wtext[offset:])
                yield from self.blank_lines(self.nlines - lineno - 1)
                break
            elif lineno + 1 == self.nlines:
                # last line and next < len(wtext), so more text than will fit on last line.
                # add self.right_placeholder
                final_line = wtext[offset: next - len(self.right_placeholder)] + self.right_placeholder
                trace(f"{self.name}.wrap: {offset=}, {next=}, {final_line=!r}")
                yield start_offset + offset, *self.align(final_line)
            elif wtext[next] == ' ':
                # next hit in between words.
                # find last non-blank char on line
                first_non_blank_left = self.first_non_blank_left(wtext, next)
                yield start_offset + offset, *self.align(wtext[offset: first_non_blank_left + 1])
                offset = self.first_non_blank(wtext, next + 1)
            else:
                # next hit in the middle of a word.
                i = wtext.rfind(' ', next - self.max_waste, next)
                if i != -1:
                    next = i + 1
                yield start_offset + offset, *self.align(wtext[offset: next])
                offset = next

    def first_non_blank_left(self, text, end):
        r'''Scans back from end to find the index to the last non-blank char in text.

        Assumes end points to a blank char in text.  Thus, end is one past the end of the text to consider.

        Returns -1 if all text before end is blank.
        '''
        while end > 0 and text[end - 1] == ' ':
            end -= 1
        return end - 1

    def first_non_blank(self, text, start):
        r'''Scans forward from start to find the first non-blank char in text.

        Generally start points to a blank char in text.

        Returns len(text) if all remaining text is blank.
        '''
        while start < len(text) and text[start] == ' ':
            start += 1
        return start

    def start_of_word(self, text, index):
        r'''Scans backward from index for the start of the word.

        index should point to a non-space character.
        '''
        while index > 0 and text[index - 1] != ' ':
            index -= 1
        return index

    def end_of_word(self, text, index):
        r'''Scans forward from index for the end of the word.

        index should point to a non-space character.
        '''
        while index + 1 < len(text) and text[index + 1] != ' ':
            index += 1
        return index

    def align(self, line):
        r'''Pad `line` out to ncols.  Returns (pad, padded_line), where pad is the left x-offset of
        the text within the padded line: 0 for left alignment (padding added on the right), and
        ncols-len(line) for right alignment (padding added on the left).
        '''
        pad = self.ncols - len(line)
        if pad <= 0:
            return 0, line
        match self.alignment:
            case "left":
                return 0, line + ' ' * pad
            case "right":
                return pad, ' ' * pad + line
            case _:
                raise ValueError(f'field_shared.align: illegal {self.alignment=!r}, '
                                 f'expected "left" or "right"')

    def blank_lines(self, nlines):
        for _ in range(nlines):
            yield None, 0, ' ' * self.ncols


class read_only_field:
    default_attr_pair = 0x01    # attr_pair 0x01 is black on red
    can_edit = False
    changed = False

    def __init__(self, screen_key, text, field_shared, begin_y, paint=True, attr_pair=None, attr=0):
        self.screen_key = screen_key   # screen-assigned id: an index, or (row, col) for table_screen
        self.text = text
        self.field_shared = field_shared
        self.begin_y = begin_y
        self.scroll = 0
        self.pads = [0] * self.nlines   # per-line left text-offset; paint() overrides (right-align)
        if attr_pair is None:
            self.attr_pair = self.default_attr_pair
        else:
            self.attr_pair = attr_pair
        self.attr = attr
        trace(f"{self.__class__.__name__}({self.name}).__init__: "
              f"{text=!r}, {begin_y=}, {self.nlines=}, {self.begin_x=}, {self.ncols=}")
        if paint:
            self.paint()

    @property
    def name(self):
        return self.field_shared.name

    @property
    def nlines(self):
        return self.field_shared.nlines

    @property
    def begin_x(self):
        return self.field_shared.begin_x

    @property
    def ncols(self):
        return self.field_shared.ncols

    @property
    def app(self):
        return self.field_shared.app

    def validate(self):
        return self.field_shared.validate_fn(self.text)

    def enclose(self, y, x):
        return False

    def paint(self):
        r'''Completely replaces everything visible on the screen (ie, curses attrs).

        Recalculates self.scroll position.
        '''
        # FIX: Recalculate scroll position
       #trace(f"{self.name}.paint({self.text=!r})")
        self.starts = []
        self.pads = []     # per-line left x-offset of the text (0 for left-aligned)
        stdscr = self.app.stdscr
        attr = curses.color_pair(self.attr_pair) + self.attr
        for y, (start, pad, line) in zip(range(self.begin_y, self.begin_y + self.nlines),
                                         self.field_shared.wrap(self.text, self.scroll)):
            self.starts.append(start)
            self.pads.append(pad)
            stdscr.addstr(y, self.begin_x, line, attr)
        self.set_attrs()

    def set_attrs(self, reset=False):
        pass

    def activate(self):
        r'''Highlight this (read-only) field as the active/selected one.'''
        self.reverse_attr()

    def deactivate(self):
        r'''Un-highlight; reverse_attr toggles, so this is the same call as activate().'''
        self.reverse_attr()

    def chgat(self, start, length, attr):
        r'''This takes indexes into self.text.
        '''
        stdscr = self.app.stdscr
        for y, x, num in self.gen_locations(start, start + max(1, length)):
            stdscr.chgat(y, x, num, attr)

    def reverse_attr(self, start=0, length=None):
        r'''This takes indexes into self.text.

        Toggles curses.A_REVERSE
        '''
        stdscr = self.app.stdscr
        attr = None
        if length is None:
            length = len(self.text)
        for y, x, num in self.gen_locations(start, start + max(1, length)):
            if attr is None:
                current_attr = stdscr.inch(y, x)
                new_attr = current_attr ^ curses.A_REVERSE
               #trace(f"{self.name}.reverse_attr({start=}, {length=}): {hex(current_attr)=}, "
               #      f"{hex(new_attr)=}, {hex(curses.A_REVERSE)=}")
            stdscr.chgat(y, x, num, new_attr)

    def gen_locations(self, start, end):
        r'''This takes indexes into self.text and generates all y, x, num values that are visible.
        '''
        def gen_line(lineno):
            this_start = self.starts[lineno]
            if this_start is not None:
                if lineno + 1 < self.nlines and self.starts[lineno + 1] is not None:
                    # not the last line with text
                    next_start = min(self.starts[lineno + 1], this_start + self.ncols)
                elif len(self.text) > this_start + self.ncols:
                    # last line has placeholder
                    next_start = this_start + self.ncols - len(self.field_shared.right_placeholder)
                else:
                    # last line has no placeholder
                    next_start = len(self.text) + 1  # + 1 to allow settings attr on the char after end of text
               #trace(f"{self.name}.gen_locations.gen_line({start=}, {end=}, {lineno=}): "
               #      f"{this_start=}, {next_start=}")
                if this_start < end and next_start > start:
                    skip = 0 if lineno or not self.scroll else len(self.field_shared.left_placeholder)
                    start_x = max(skip, start - this_start)
                    end_x = min(end, next_start) - this_start
                   #trace(f"{self.name}.gen_locations.gen_line: {skip=}, {start_x=}, {end_x=}")
                    if end_x > skip and end_x > start_x:
                        yield self.begin_y + lineno, self.begin_x + self.pads[lineno] + start_x, \
                              end_x - start_x

        trace(f"{self.name}.gen_locations({start=}, {end=})")
        for lineno in range(self.nlines):
           #trace(f"{self.name}.gen_locations: calling gen_line({lineno=})")
            yield from gen_line(lineno)

    def get_lineno(self, index):
        r'''Returns None if index not visible.
        '''
        if index < self.starts[0]:
            return None
        for lineno in range(1, self.nlines):
            start = self.starts[lineno]
            if start is None:
                if index < self.starts[lineno - 1] + self.ncols:
                    return lineno - 1
                return None
            if index < start:
                return lineno - 1
        if index < self.starts[-1] + self.ncols:
            return self.nlines - 1
        return None

    def get_col(self, index):
        r'''Returns None if index not visible.  Includes the line's left pad (for right alignment).
        '''
        if index < self.starts[0]:
            return None
        for lineno in range(1, self.nlines):
            start = self.starts[lineno]
            if start is None:
                if index < self.starts[lineno - 1] + self.ncols:
                    return min(self.ncols - 1, self.pads[lineno - 1] + index - self.starts[lineno - 1])
                return None
            if index < start:
                return min(self.ncols - 1, self.pads[lineno - 1] + index - self.starts[lineno - 1])
        if index < self.starts[-1] + self.ncols:
            return min(self.ncols - 1, self.pads[-1] + index - self.starts[-1])
        return None


class editable_field(read_only_field):
    pos_attr = curses.A_REVERSE
    selection_pair = 0x06        # black on yellow
    default_attr_pair = 0x70     # white on black
    can_edit = True

    position = None              # text index
    selection_len = 0
    in_select = False

    def __init__(self, screen_key, text, field_shared, begin_y, paint=True, attr_pair=None, callback=None):
        super().__init__(screen_key, text, field_shared, begin_y, paint=paint, attr_pair=attr_pair)
        self.callback = callback

    def get_text(self):
       #trace(f"{self.name}.get_text() -> {self.text!r}")
        return self.text

    def enclose(self, y, x):
        ans = self.begin_y <= y < self.begin_y + self.nlines and \
              self.begin_x <= x < self.begin_x + self.ncols
       #trace(f"{self.name}.enclose({y=}, {x=}) -> {ans}")
        return ans

    def to_index(self, y, x):
        r'''Converts screen coordinates to text index.
        '''
        assert y >= self.begin_y and y < self.begin_y + self.nlines, \
               f"editable_field({self.name}).to_index({y=}, {x=}): y out of bounds {self.begin_y=}, {self.nlines=}"
        assert x >= self.begin_x and x < self.begin_x + self.ncols, \
               f"editable_field({self.name}).to_index({y=}, {x=}): x out of bounds {self.begin_x=}, {self.ncols=}"
        y -= self.begin_y
        x -= self.begin_x
        start_x = self.starts[y]
        if start_x is None:
            ans = len(self.text) - 1
        else:
            skip = 0
            if y == 0 and self.scroll:
                skip = len(self.field_shared.left_placeholder)
                if x <= skip:
                    ans = start_x + skip
                   #trace(f"{self.name}.to_index({y=}, {x=}) -> {ans}")
                    return ans
            if y + 1 < self.nlines:
                if self.starts[y + 1] is not None:
                    end_x = min(self.starts[y + 1], start_x + self.ncols)
                else:
                    end_x = min(start_x + self.ncols, len(self.text))
            elif len(self.text) > start_x + self.ncols:
                end_x = start_x + self.ncols - len(self.field_shared.right_placeholder)
            else:
                end_x = len(self.text)
            ans = start_x + max(0, x - self.pads[y])
            if ans >= end_x:
                ans = end_x - 1
       #trace(f"{self.name}.to_index({y=}, {x=}) -> {ans}")
        return ans

    def set_attrs(self, reset=False):
        if self.position is not None:
            if self.selection_len == 0:
                if reset:
                    attr = curses.color_pair(self.attr_pair)
                else:
                    attr = self.pos_attr
                self.chgat(self.position, 1, attr)
            else:
                if reset:
                    attr = curses.color_pair(self.attr_pair)
                else:
                    attr = curses.color_pair(self.selection_pair)
                if self.selection_len > 0:
                    self.chgat(self.position, self.selection_len, attr)
                else:
                    self.chgat(self.position + self.selection_len, abs(self.selection_len), attr)

    def set_position(self, index):
       #trace(f"{self.name}.set_position({index=})")
        self.set_attrs(reset=True)
        self.position = index
        self.selection_len = 0
        self.set_attrs()
        self.app.screen.activate_field(self)

    def set_selection(self, start, end):
        r'''if positive selection (end >= start):
              start is leftmost selected char and end is one past rightmost selected char.
              self.selection_len ends up >= 0
           otherwise 
              start is one past rightmost selected char and end is leftmost selected char.
              self.selection_len ends up < 0, which essentially reverses start and end.
        '''
        length = end - start   # negative, if selecting to the left
        if start == self.position and length == self.selection_len:
           #trace(f"{self.name}.set_selection({start=}, {end=}): no change!")
           pass
        else:
           #trace(f"{self.name}.set_selection({start=}, {end=})")
            self.set_attrs(reset=True)
            self.position = start
            self.selection_len = length
            self.set_attrs()
            self.app.screen.activate_field(self)

    def process_mouse(self, mouse_event):
        r'''Caller ensures self.enclose on mouse_event
        '''
        _, x, y, _, bstate = mouse_event

        index = self.to_index(y, x)

        match bstate:
            case curses.BUTTON1_CLICKED:
                trace(f"{self.name}.process_mouse({y=}, {x=}): BUTTON1_CLICKED")
                self.set_position(index)
            case curses.BUTTON1_DOUBLE_CLICKED:
                if self.text[index] == ' ':
                    trace(f"{self.name}.process_mouse({y=}, {x=}): "
                          f"BUTTON1_DOUBLE_CLICKED on space: ignored")
                else:
                    trace(f"{self.name}.process_mouse({y=}, {x=}): BUTTON1_DOUBLE_CLICKED")
                    start = self.field_shared.start_of_word(self.text, index)
                    end = self.field_shared.end_of_word(self.text, index)
                    while self.text[end] in ',.;':
                        end -= 1
                    self.set_selection(start, end + 1)
            case curses.BUTTON1_TRIPLE_CLICKED:
                trace(f"{self.name}.process_mouse({y=}, {x=}): BUTTON1_TRIPLE_CLICKED")
                self.set_selection(0, len(self.text))
            case curses.BUTTON1_PRESSED:
                trace(f"{self.name}.process_mouse({y=}, {x=}): {self.in_select=} BUTTON1_PRESSED")
                self.set_position(index)
                self.in_select = True
            case curses.REPORT_MOUSE_POSITION if self.in_select:
                trace(f"{self.name}.process_mouse({y=}, {x=}): {self.in_select=} REPORT_MOUSE_POSITION")
                self.extend_selection(index)
            case curses.BUTTON1_RELEASED if self.in_select:
                trace(f"{self.name}.process_mouse({y=}, {x=}): {self.in_select=} BUTTON1_RELEASED")
                self.extend_selection(index)
                self.in_select = False
            case _:
                trace(f"{self.name}.process_mouse({y=}, {x=}): {self.in_select=} "
                      f"unknown bstate={bstate_str(bstate)}")
                return mouse_event
        return None

    def process_key(self, key):
        trace(f"{self.name}.process_key({key=}): {self.callback=}")
        if (key == 'KEY_ENTER' or key == '\n') and self.callback is not None:
            return self.callback(self.get_text())
        if self.position is None:
            trace(f"{self.name}.process_key({key=}): position not set")
            return key
        if len(key) == 1 and curses.ascii.isprint(key):
            trace(f"{self.name}.process_key({key=}): {self.position=}, ascii.is_print")
            self.delete_selection(key)
        else:
            match key:
                case 'KEY_DELETE' | 'KEY_DC' | 'KEY_BACKSPACE' if self.selection_len:
                    trace(f"{self.name}.process_key({key=}): {self.position=}, "
                          f"{self.selection_len=}, delete_selection")
                    self.delete_selection()
                case 'KEY_DELETE' | 'KEY_DC' if not self.selection_len:
                    # delete char at self.position
                    trace(f"{self.name}.process_key({key=}): {self.position=}, "
                          f"no selection, delch at cursor")
                    self.delete(1, self.position)  # erases all attrs
                    self.set_attrs()
                case 'KEY_BACKSPACE' if not self.selection_len and self.position > 0:
                    # delete char to left of self.position
                    self.position -= 1
                    self.delete(1, self.position)
                    self.set_attrs()
                case 'KEY_UP' if self.get_lineno(self.position) > 0:
                    new_y = self.get_lineno(self.position) - 1
                    x = self.get_col(self.position)
                    trace(f"{self.name}.process_key({key=}): "
                          f"{self.position=}, move to {new_y=}, {x=}")
                    self.set_position(self.to_index(new_y + self.begin_y, x + self.begin_x))
                case 'KEY_DOWN' if self.get_lineno(self.position) + 1 < self.nlines:
                    new_y = self.get_lineno(self.position) + 1
                    x = self.get_col(self.position)
                    trace(f"{self.name}.process_key({key=}): "
                          f"{self.position=}, move to {new_y=}, {x=}")
                    self.set_position(self.to_index(new_y + self.begin_y, x + self.begin_x))
                case 'KEY_LEFT' if self.position > 0:
                    trace(f"{self.name}.process_key({key=}): {self.position=}")
                    self.set_position(self.position - 1)
                case 'KEY_RIGHT' if self.position < len(self.text):
                    trace(f"{self.name}.process_key({key=}): "
                          f"{self.position=}, {len(self.text)=}")
                    self.set_position(self.position + 1)
                case _:
                    trace(f"{self.name}.process_key({key=}): unknown key")
                    return key
        return None

    def insert(self, text, offset=0):
        self.text = self.text[: offset] + text + self.text[offset:]
        self.changed = True
        self.paint()

   #def replace(self, text, offset=0):
   #    self.text = self.text[: offset] + text + self.text[offset + len(text):]
   #    self.paint()

    def delete(self, nchars, offset=0, insch=''):
        self.text = self.text[: offset] + insch + self.text[offset + nchars:]
        self.changed = True
        self.paint()

    def extend_selection(self, last):
        if last >= self.position:
            last += 1
        self.set_selection(self.position, last)
        trace(f"{self.name}.extend_selection({last=}): {self.position=}, {self.selection_len=}")

    def delete_selection(self, insch=''):
        if not self.selection_len:
            if insch:
                self.insert(insch, self.position)
                self.set_position(self.position + 1)
        else:
            if self.selection_len > 0:
                pos = self.position
            else:
                pos = self.position + self.selection_len
            trace(f"{self.name}.delete_selection(): {pos=}, {self.selection_len=}")
            self.delete(abs(self.selection_len), pos, insch)
            if insch is not None:
                self.set_position(pos + 1)
            else:
                self.set_position(pos)

    def activate(self):
        r'''Select the whole value so the first typed char replaces it.'''
        self.position = 0
        self.selection_len = len(self.get_text())
        self.set_attrs()

    def deactivate(self):
        self.set_attrs(reset=True)


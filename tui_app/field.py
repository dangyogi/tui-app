# field.py

r'''This handles user input fields.  Each field is a simple rectangle.  It will scroll long lines to fit.

These are created each time the screen.draw is called.

Therefore, they only see one screen size during their lifetime and only need to draw the text once.
'''

import curses


class wrapper:
    left_placeholder = '[...] '
    right_placeholder = ' [...]'
    max_waste = 10

    def __init__(self, name, nlines, ncols, app=None, alignment="left"):
        self.name = name
        self.nlines = nlines
        self.ncols = ncols
        self.alignment = alignment
        self.app = app     # only used (shared) by field classes below

    def wrap(self, text, scroll=0):
        r'''Generates (index, line) pairs.
        '''
        text = text.rstrip()
        if scroll:
            wtext = self.left_placeholder + text[scroll + len(self.left_placeholder):]
            print(f"wrap: {self.left_placeholder=!r}, {wtext=!r}")
        else:
            wtext = text
        offset = 0
        start_offset = scroll  # add to offset to get scroll
        for lineno in range(self.nlines):
            if offset >= len(wtext):
                yield from self.blank_lines(self.nlines - lineno)
                break
            next = offset + self.ncols
            if next >= len(wtext):
                # next past end of wtext
                yield start_offset + offset, self.align(wtext[offset:])
                yield from self.blank_lines(self.nlines - lineno - 1)
                break
            elif lineno + 1 == self.nlines:
                # last line and next < len(wtext), so more text than will fit on last line.
                # add self.right_placeholder
                final_line = wtext[offset: next - len(self.right_placeholder)] + self.right_placeholder
                print(f"wrap: {offset=}, {next=}, {final_line=!r}")
                yield start_offset + offset, self.align(final_line)
            elif wtext[next] == ' ':
                # next hit in between words.
                # find last non-blank char on line
                last_non_blank = self.last_non_blank(wtext, next)
                yield start_offset + offset, self.align(wtext[offset: last_non_blank + 1])
                offset = self.first_non_blank(wtext, next + 1)
            else:
                # next hit in the middle of a word.
                i = wtext.rfind(' ', next - self.max_waste, next)
                if i != -1:
                    next = i + 1
                yield start_offset + offset, self.align(wtext[offset: next])
                offset = next

    def last_non_blank(self, text, end):
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

    def align(self, line):
        pad = ' ' * (self.ncols - len(line))
        if not pad:
            return line
        match self.alignment:
            case "left":
                return line + pad
            case "right":
                return pad + line
            case _:
                raise ValueError(f'wrapper.align: illegal {self.alignment=!r}, '
                                 f'expected "left" or "right"')

    def blank_lines(self, nlines):
        for _ in range(nlines):
            yield None, ' ' * self.ncols


class read_only_field:
    attr_pair = 0x01    # black on red

    def __init__(self, text, wrapper, begin_y, begin_x, paint=True):
        self.text = text
        self.wrapper = wrapper
        self.begin_y = begin_y
        self.begin_x = begin_x
        self.scroll = 0
        self.trace(f"field({self.name}).__init__: {text=!r}, {begin_y=}, {begin_x=}")
        if paint:
            self.paint()

    @property
    def name(self):
        return self.wrapper.name

    def enclose(self, y, x):
        return False

    def trace(self, *objects, sep=' ', end='\n', flush=False):
        if self.wrapper.app is not None and self.wrapper.app.trace_file is not None:
            print(*objects, sep=sep, end=end, file=self.wrapper.app.trace_file, flush=flush)

    def paint(self):
        r'''Completely replaces everything visible on the screen (ie, curses attrs).

        Recalculates self.scroll position.
        '''
        self.trace(f"field({self.name}).paint({self.text=!r})")
        self.starts = []
        stdscr = self.wrapper.app.stdscr
        attr = curses.color_pair(self.attr_pair)
        for y, (start, line) in zip(range(self.begin_y, self.begin_y + self.wrapper.nlines),
                                    self.wrapper.wrap(self.text, self.scroll)):
            self.starts.append(start)
            stdscr.addstr(y, self.begin_x, line, attr)
        self.set_attrs()

    def set_attrs(self, reset=False):
        pass

    def chgat(self, start, end, attr):
        r'''This takes indexes into self.text.
        '''
        stdscr = self.wrapper.app.stdscr
        for y, x, num in self.gen_locations(start, end):
            stdscr.chgat(y, x, num, attr)

    def gen_locations(self, start, end):
        r'''This takes indexes into self.text and generates all y, x, num values that are visible.
        '''
        def gen_line(lineno):
            this_start = self.starts[lineno]
            if lineno + 1 < self.wrapper.nlines:
                next_start = min(self.starts[lineno + 1], this_start + self.wrapper.ncols)
            else:
                next_start = min(this_start + self.wrapper.ncols - len(self.wrapper.right_placeholder),
                                 len(self.text))
            print(f"{self.name}.gen_locations.gen_line({start=}, {end=}, {lineno=}): {this_start=}, {next_start=}")
            if this_start < start + end and next_start > start:
                skip = 0 if lineno or not self.scroll else len(self.wrapper.left_placeholder)
                start_x = max(skip, start - this_start)
                end_x = min(end, next_start) - this_start
                print(f"{self.name}.gen_locations.gen_line: {skip=}, {start_x=}, {end_x=}")
                if end_x > skip and end_x > start_x:
                    yield self.begin_y + lineno, self.begin_x + start_x, end_x - start_x
        print(f"{self.name}.gen_locations({start=}, {end=})")
        for lineno in range(self.wrapper.nlines):
            print(f"{self.name}.gen_locations: calling gen_line({lineno=})")
            yield from gen_line(lineno)


class editable_field(read_only_field):
    pos_attr = curses.A_REVERSE
    selection_pair = 0x06  # black on yellow
    attr_pair = 0x70       # white on black

    position = 0           # text index
    selection_len = 0
    changed = False
    in_select = False

    def insert(self, text, offset=0):
        self.paint(self.text[: offset] + text + self.text[offset:])

    def replace(self, text, offset=0):
        self.paint(self.text[: offset] + text + self.text[offset + len(text):])

    def delete(self, nchars, offset=0, insch=''):
        self.paint(self.text[: offset] + insch + self.text[offset + nchars:])

    def enclose(self, y, x):
        ans = self.begin_y <= y < self.begin_y + self.wrapper.nlines and \
              self.begin_x <= x < self.begin_x + self.wrapper.ncols
        self.trace(f"field({self.name}).enclose({y=}, {x=}) -> {ans}")
        return ans

    def do_chgat(self, start, nchars, attr=None):
        self.trace(f"field({self.name}).do_chgat({start=}, {nchars=}")
        for lineno in range(self.wrapper.nlines):
            offset = offsets[lineno]
            if offset <= start:
                # starts at or after beg of line
                x = start - offset
                if start < offsets[lineno + 1] <= start + nchars:
                    # spills over to next line
                    self.chgat(lineno, x, self.wrapper.ncols - x, attr)
                else:
                    # does not spill over to next line
                    self.chgat(lineno, x, nchars, attr)
                    break
            else:
                if start + nchars > offset:
                    # starts before beg of line, continues to this line
                    self.chgat(lineno, 0, nchars - (offset - start), attr)
                else:
                    break
        else:
            self.trace(f"field({self.name}).do_chgat fell off end of lines")

    def set_attrs(self, reset=False):
        if self.selection_len == 0:
            if reset:
                attr = curses.color_pair(self.attr_pair)
            else:
                attr = self.pos_attr
            self.do_chgat(self.position, 1, attr)
        else:
            if reset:
                attr = curses.color_pair(self.attr_pair)
            else:
                attr = curses.color_pair(self.selection_pair)
            if self.selection_len > 0:
                self.do_chgat(self.position, self.selection_len, attr)
            else:
                self.do_chgat(self.position + self.selection_len, abs(self.selection_len), attr)

    def to_index(self, y, x):
        r'''Converts local (subwin) coordinates to text index.
        '''
        ans = self.width * y + x
        self.trace(f"field({self.name}).to_index({y=}, {x=}) -> {ans}")
        return ans

    def to_pos(self, index):
        y, x = divmod(index, self.width)
        self.trace(f"field({self.name}).to_pos({index=}) -> {y=}, {x=}")
        if y >= self.wrapper.nlines:
            # set to lower right corner
            y = self.wrapper.nlines - 1
            x = self.width - 1
            self.trace(f"field({self.name}).to_pos({index=}): "
                       f"OVERFLOW!, setting to lower right corner {y=}, {x=}")
        return y, x

    def get_text(self):
        self.trace(f"field({self.name}).get_text() -> {self.text!r}")
        return self.text

    def process_mouse(self, mouse_event):
        r'''Caller ensures self.enclose on mouse_event
        '''
        _, x, y, _, bstate = mouse_event

        index = self.to_index(y, x)

        match bstate:
            case tui_base.curses.BUTTON1_CLICKED:
                self.trace(f"field({self.name}).process_mouse({y=}, {x=}): BUTTON1_CLICKED")
                self.set_attr(reset=True)
                self.selection_len = 0
                self.position = index
                self.set_attr()
            case tui_base.curses.BUTTON1_DOUBLE_CLICKED:
                self.trace(f"field({self.name}).process_mouse({y=}, {x=}): BUTTON1_DOUBLE_CLICKED")
                text = self.get_text()
                start = text.rfind(' ', 0, index) + 1
                end = text.find(' ', index)
                if end == -1:
                    end = len(text)
                while text[end - 1] in ',.;':
                    end -= 1
                self.set_selection(start, end)
            case tui_base.curses.BUTTON1_TRIPLE_CLICKED:
                self.trace(f"field({self.name}).process_mouse({y=}, {x=}): BUTTON1_TRIPLE_CLICKED")
                self.set_selection(0, len(self.get_text()))
            case tui_base.curses.BUTTON1_PRESSED:
                self.trace(f"field({self.name}).process_mouse({y=}, {x=}): "
                           f"{self.in_select=} BUTTON1_PRESSED")
                self.set_attr(reset=True)
                self.set_position(index)
                self.in_select = True
            case tui_base.curses.REPORT_MOUSE_POSITION if self.in_select:
                self.trace(f"field({self.name}).process_mouse({y=}, {x=}): "
                           f"{self.in_select=} REPORT_MOUSE_POSITION")
                self.extend_selection(index)
            case tui_base.curses.BUTTON1_RELEASED if self.in_select:
                self.trace(f"field({self.name}).process_mouse({y=}, {x=}): "
                           f"{self.in_select=} BUTTON1_RELEASED")
                self.extend_selection(index)
                self.in_select = False
            case _:
                self.trace(f"field({self.name}).process_mouse({y=}, {x=}): {self.in_select=} "
                           f"unknown bstate={tui_base.bstate_str(bstate)}")
                return mouse_event
        return None

    def process_key(self, key):
        if self.position is None:
            self.trace(f"field({self.name}).process_key({key=}): position not set")
            return key
        if len(key) == 1 and tui_base.curses.ascii.isprint(key):
            self.trace(f"field({self.name}).process_key({key=}): {self.position=}, ascii.is_print")
            self.delete_selection(key)
            self.position += 1
        else:
            match key:
                case 'KEY_DELETE' | 'KEY_DC' | 'KEY_BACKSPACE' if self.selection_len:
                    self.trace(f"field({self.name}).process_key({key=}): {self.position=}, "
                               f"{self.selection_len=}, delete_selection")
                    self.delete_selection()
                case 'KEY_DELETE' | 'KEY_DC' if not self.selection_len:
                    # delete char at self.position
                    self.trace(f"field({self.name}).process_key({key=}): {self.position=}, "
                               f"no selection, delch at cursor")
                    self.delete(1, self.position)
                case 'KEY_BACKSPACE' if not self.selection_len and self.position > 0:
                    # delete char to left of self.position
                    self.position -= 1
                    self.delete(1, self.position)
                case 'KEY_UP' if y > 0:
                    new_y = y - 1
                    self.trace(f"field({self.name}).process_key({key=}): {self.position=}, "
                               f"no selection, move to {new_y=}, {x=}")
                    self.set_position(new_y, x)
                case 'KEY_DOWN' if y + 1 < self.wrapper.nlines:
                    new_y = y + 1
                    self.trace(f"field({self.name}).process_key({key=}): {self.position=}, "
                               f"no selection, move to {new_y=}, {x=}")
                    self.set_position(new_y, x)
                case 'KEY_LEFT' if x > 0:
                    self.trace(f"field({self.name}).process_key({key=}): {self.position=}, "
                               f"no selection, move to {y=}, {new_x=}")
                    self.set_position(y, new_x)
                case 'KEY_RIGHT' if x + 1 < self.width:
                    new_x = x + 1
                    self.trace(f"field({self.name}).process_key({key=}): {self.position=}, "
                               f"no selection, move to {y=}, {new_x=}")
                    self.set_position(y, new_x)
                case _:
                    self.trace(f"field({self.name}).process_key({key=}): unknown key")
                    return key
        self.subwin.noutrefresh()
        return None

    def set_selection(self, start, end):
        r'''end is one past last selected char.
        '''
        assert end > start, f"field({self.name}).set_selection: {end=} not greater than {start=}"
        self.trace(f"field({self.name}).set_selection({start=}, {end=})")
        self.set_attr(reset=True)
        self.set_position(start)
        self.selection_len = end - start
        self.set_attr()

    def extend_selection(self, y, x):
        cur_index = self.to_index(*self.position)
        new_index = self.to_index(y, x)
        if new_index >= cur_index:
            new_len = new_index - cur_index + 1
        else:
            new_len = new_index - cur_index
        self.trace(f"field({self.name}).extend_selection({y=}, {x=}) {self.position=}, "
                   f"{self.selection_len=}: -> {new_len=}")
        if self.selection_len != new_len:
            if self.selection_len >= 0:
                if new_len > self.selection_len:
                    # select from old_len to new_len
                    y_start, x_start = self.pos_offset(self.selection_len)
                    self.subwin.chgat(y_start, x_start, new_len - self.selection_len,
                                      tui_base.curses.color_pair(self.selection_pair))
                else: # self.selection_len > new_len:
                    # deselect from new_len to self.selection_len
                    y_start, x_start = self.pos_offset(new_len)
                    # do max here to also clear pos_attr in case we're starting out moving left
                    self.subwin.chgat(y_start, x_start, max(1, self.selection_len) - new_len,
                                      tui_base.curses.color_pair(self.normal_pair))
                    if new_len < 0:
                        self.subwin.chgat(y_start, x_start, -new_len,
                                          tui_base.curses.color_pair(self.selection_pair))
            else: # self.selection_len < 0
                if new_len < self.selection_len:
                    # select from new_len to old_len
                    y_start, x_start = self.pos_offset(new_len)
                    self.subwin.chgat(y_start, x_start, self.selection_len - new_len,
                                      tui_base.curses.color_pair(self.selection_pair))
                else: # new_len > self.selection_len
                    # deselect from self.selection_len to new_len
                    y_start, x_start = self.pos_offset(self.selection_len)
                    self.subwin.chgat(y_start, x_start, new_len - self.selection_len,
                                      tui_base.curses.color_pair(self.normal_pair))
                    if new_len > 0:
                        y, x = self.position
                        self.subwin.chgat(y, x, new_len,
                                          tui_base.curses.color_pair(self.selection_pair))
            self.selection_len = new_len

    def delete_selection(self, insch=None):
        if not self.selection_len:
            if insch is not None:
                self.insert(insch, self.position)
        else:
            if self.selection_len > 0:
                pos = self.position
            else:
                pos = self.position + self.selection_len
            self.trace(f"field({self.name}).delete_selection(): {pos=}, {self.selection_len=}")
            self.delete(abs(self.selection_len), pos, insch)
            self.selection_len = 0
            self.set_position(pos)

    def set_position(self, index):
        self.trace(f"field({self.name}).set_position({index=})")
        self.set_attr(reset=True)
        self.position = index
        self.selection_len = 0
        self.set_attr()
        self.screen.activate_field(self)

    def deactivate(self):
        self.set_attr(reset=True)
        self.selection_len = 0




if __name__ == "__main__":
   pass 

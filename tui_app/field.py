# field.py

r'''This handles user input fields.  Each field is a simple rectangle.  It will scroll long lines to fit.

These are created each time the screen.draw is called.

Therefore, they only see one screen size during their lifetime and only need to draw the text once.

Class structure (full-mixin, decided 2026-07-18):

  field       -- base: shared per-cell state, the single __init__, and (for now) the layout/index math
                 shared by single_line and multi_line.
  single_line -- LAYOUT mixin (specializes in step 3: horizontal column-scroll, no wrap).
  multi_line  -- LAYOUT mixin (specializes in step 4: line-grow via REFRESH).
  read_only   -- BEHAVIOR mixin: activate/deactivate = reverse_attr; set_attrs = no-op.
  editable    -- BEHAVIOR mixin: activate = select-all; text editing, selection, cursor.

Concrete cells = one BEHAVIOR + one LAYOUT + the base, e.g.:

  read_only_single_line(read_only, single_line, field)
  editable_single_line (editable,  single_line, field)
  read_only_multi_line (read_only, multi_line,  field)
  editable_multi_line  (editable,  multi_line,  field)

Screens never name a concrete class -- they configure a field_shared (a factory) and ask it for fields.

MIGRATION NOTE (step 2, 2026-07-18): the single/multi LAYOUT mixins are still empty; the layout/index
math (paint, gen_locations, get_lineno, get_col, to_index) and wrap() currently live on `field` /
field_shared and are shared by both, so single_line and multi_line behave identically for now.  They
diverge in step 3 (single-line scroll) and step 4 (multi-line grow), at which point wrap() moves onto
multi_line.
'''

from .tui_base import curses, bstate_str, trace


class field_shared:
    max_waste = 10

    # Concrete field class this shared builds.  None on the base; set by the thin subclasses at the
    # bottom of this file (read_only_single_shared, editable_multi_shared, ...).  The screens never
    # name a field class -- they configure a field_shared (usually via the pickers below) and ask it
    # for fields with field_for()/edit_text()/from_field().
    field_class = None

    def __init__(self, name, nlines, begin_x, ncols, app=None, validate_fn=None, alignment="left",
                 left_placeholder='[...] ', right_placeholder=' [...]', column=None):
        self.name = name
        self.nlines = nlines
        self.begin_x = begin_x
        self.ncols = ncols
        self.app = app     # only used (shared) by field classes below
        self.validate_fn = validate_fn
        self.alignment = alignment
        self.left_placeholder = left_placeholder
        self.right_placeholder = right_placeholder
        self.column = column   # the consuming-app column; used by field_for() to pull row values

    def field_for(self, row, begin_y, screen_key):
        r'''Build a field whose text is row's value for this column (self.column).'''
        text = row.get(self.column.name)
        attr_pair = self.column.column_attr_pair(row)
        return self.field_class(screen_key, text, self, begin_y, attr_pair=attr_pair)

    def edit_text(self, text, begin_y, screen_key, callback=None):
        r'''Build an editable field seeded with an exact string (no backing row).'''
        return self.field_class(screen_key, text, self, begin_y, callback=callback)

    def from_field(self, old, begin_y, screen_key):
        r'''Rebuild a field at new geometry (grown nlines / shifted begin_y), preserving the
        in-progress edit state so it is not lost across a REFRESH (and still submits: `changed`
        must ride along, else the column drops out of the screen's attrs_changed set).

        The row is not committed mid-edit, so the old field's attr_pair (the column_attr_pair(row)
        highlight) is exactly what should carry over -- pass it through rather than falling back to
        default_attr_pair (which would drop the row's highlight after a grow).
        '''
        f = self.field_class(screen_key, old.text, self, begin_y, paint=False,
                             attr_pair=old.attr_pair, attr=old.attr)
        f.changed = old.changed
        f.position = getattr(old, 'position', None)
        f.selection_len = getattr(old, 'selection_len', 0)
        f.paint()
        return f

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

    def line_count(self, text):
        r'''How many wrapped lines `text` needs at ncols, with NO line limit and no placeholders.

        Mirrors wrap()'s word-breaking (space breaks; mid-word break with max_waste lookback), so
        multi_line can tell when an edited field must grow.  Empty text needs 1 line.
        '''
        text = text.rstrip()
        if not text:
            return 1
        offset = 0
        lines = 0
        while offset < len(text):
            lines += 1
            next = offset + self.ncols
            if next >= len(text):
                break
            if text[next] == ' ':
                offset = self.first_non_blank(text, next + 1)
            else:
                i = text.rfind(' ', next - self.max_waste, next)
                if i != -1:
                    next = i + 1
                offset = next
        return lines


class field:
    r'''Base for all on-screen field cells: shared per-cell state, the single __init__, and (for now)
    the layout/index math shared by single_line and multi_line.  Concrete cells combine a BEHAVIOR
    mixin + a LAYOUT mixin + this base (see the module docstring).
    '''
    changed = False

    def __init__(self, screen_key, text, field_shared, begin_y, paint=True, attr_pair=None,
                 attr=0, callback=None):
        self.screen_key = screen_key   # screen-assigned id: an index, or (row, col) for table_screen
        self.text = text
        self.field_shared = field_shared
        self.begin_y = begin_y
        self.scroll = 0
        self.callback = callback        # used by editable cells (harmless on read-only)
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

    def paint(self):
        r'''Completely replaces everything visible on the screen (ie, curses attrs).

        Renders self.text (wrapped, from self.scroll) plus the cursor/selection.  single_line drives
        self.scroll from the cursor before delegating here; multi_line does not scroll yet (step 4).
        '''
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

    def show_cursor(self):
        r'''Redraw the cursor/selection after self.position changed.  Base (and multi_line): no
        horizontal scroll, so just set the attrs.  single_line overrides to scroll the cursor into
        view (repainting only when that shifts the scroll window).
        '''
        self.set_attrs()

    def grow_if_needed(self):
        r'''Does the current text overflow nlines?  Base (and single_line, which scrolls instead):
        never.  multi_line overrides to return True when the text needs more wrapped lines, so the
        editing code can trigger a REFRESH that re-lays-out the (taller) field.
        '''
        return False

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
                    # never run past the field's own width: the append cursor (next_start = len+1) on
                    # an exactly-full line would otherwise land one column past ncols (curses ERR).
                    end_x = min(end_x, self.ncols - self.pads[lineno])
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

    def to_index(self, y, x):
        r'''Converts screen coordinates to text index.
        '''
        assert y >= self.begin_y and y < self.begin_y + self.nlines, \
               f"{self.__class__.__name__}({self.name}).to_index({y=}, {x=}): y out of bounds " \
               f"{self.begin_y=}, {self.nlines=}"
        assert x >= self.begin_x and x < self.begin_x + self.ncols, \
               f"{self.__class__.__name__}({self.name}).to_index({y=}, {x=}): x out of bounds " \
               f"{self.begin_x=}, {self.ncols=}"
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


class single_line:
    r'''LAYOUT mixin: single-line cell with horizontal (character) scroll.

    self.scroll is a character offset into the text.  paint() recomputes it from the cursor
    (self.position) so the cursor stays visible; the [<]/[>] placeholders (from field_shared) mark
    scrolled-off text.  Read-only single-line cells have no cursor, so they never scroll (scroll 0).

    NOTE: this still reuses field.paint / gen_locations / to_index (which already understand a scroll
    offset + placeholders); only the driving of self.scroll is added here.  A full no-wrap rewrite of
    the single-line layout can follow if needed, but the shared machinery renders one line correctly.
    '''
    X_single = 0.6   # keep the cursor ~60% of the way across the field when it scrolls

    def _compute_scroll(self):
        r'''The character offset that keeps self.position visible: 0 when the text fits or there is
        no cursor (read-only).
        '''
        position = getattr(self, 'position', None)
        if position is None:
            return 0
        # the +1 in `upper` (only at the append position) keeps the cursor-past-last-char visible
        upper = max(0, len(self.text) - self.ncols + (1 if position >= len(self.text) else 0))
        return min(max(position - int(self.ncols * self.X_single), 0), upper)

    def paint(self):
        self.scroll = self._compute_scroll()
        super().paint()

    def show_cursor(self):
        if self._compute_scroll() != self.scroll:
            self.paint()          # scroll window shifted -> re-render text (also redraws the cursor)
        else:
            self.set_attrs()      # cursor moved within the window -> just move the highlight


class multi_line:
    r'''LAYOUT mixin: multi-line cell that grows (never scrolls).

    Reuses the shared wrap-based layout on `field` (wrap() still lives on field_shared).  When an edit
    makes the text need more than nlines wrapped lines, grow_if_needed() reports it; the editing code
    returns 'REFRESH' and the screen re-lays-out the field one (or more) lines taller.  No horizontal
    scroll and no [<]/[>] placeholders (multi_line_shared uses empty markers).
    '''

    def grow_if_needed(self):
        return self.field_shared.line_count(self.text) > self.nlines


class read_only:
    r'''BEHAVIOR mixin: a non-editable cell.'''
    default_attr_pair = 0x01    # attr_pair 0x01 is black on red
    can_edit = False

    def enclose(self, y, x):
        return False

    def set_attrs(self, reset=False):
        pass

    def activate(self):
        r'''Highlight this (read-only) field as the active/selected one.'''
        self.reverse_attr()

    def deactivate(self):
        r'''Un-highlight; reverse_attr toggles, so this is the same call as activate().'''
        self.reverse_attr()


class editable:
    r'''BEHAVIOR mixin: an editable cell (text entry, selection, cursor).'''
    pos_attr = curses.A_REVERSE
    selection_pair = 0x06        # black on yellow
    default_attr_pair = 0x70     # white on black
    can_edit = True

    position = None              # text index
    selection_len = 0
    in_select = False

    def get_text(self):
       #trace(f"{self.name}.get_text() -> {self.text!r}")
        return self.text

    def enclose(self, y, x):
        ans = self.begin_y <= y < self.begin_y + self.nlines and \
              self.begin_x <= x < self.begin_x + self.ncols
       #trace(f"{self.name}.enclose({y=}, {x=}) -> {ans}")
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
        self.show_cursor()
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
            self.show_cursor()
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
                case 'KEY_DELETE' | 'KEY_DC' if not self.selection_len and self.position < len(self.text):
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
        if self.grow_if_needed():
            # the edit needs another line -> let the screen re-lay-out this (taller) field
            trace(f"{self.name}.process_key({key=}): grow -> REFRESH")
            return 'REFRESH'
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
            if insch:
                self.set_position(pos + 1)    # a char replaced the selection -> cursor after it
            else:
                self.set_position(pos)        # selection just deleted -> cursor at the deletion point

    def activate(self):
        r'''Select the whole value so the first typed char replaces it.'''
        self.position = 0
        self.selection_len = len(self.get_text())
        self.set_attrs()

    def deactivate(self):
        r'''Clear the highlight AND the cursor state: a deactivated field has no cursor, so when it
        is later repainted (e.g. from_field on a grow-REFRESH) it shows no stray cursor.  Re-entering
        the field select-alls anyway (activate), so nothing depends on the old position.
        '''
        self.set_attrs(reset=True)
        self.position = None
        self.selection_len = 0


# --- concrete field cells (one BEHAVIOR + one LAYOUT + the base) -----------------------------------

class read_only_single_line(read_only, single_line, field):
    pass

class editable_single_line(editable, single_line, field):
    pass

class read_only_multi_line(read_only, multi_line, field):
    pass

class editable_multi_line(editable, multi_line, field):
    pass


# --- field_shared factory family -------------------------------------------------------------------
#
# Thin subclasses that parallel the field classes: each just names the concrete field_class it builds.
# The base field_shared holds all the factory machinery.  Adding a field kind is adding a subclass --
# no central switch to edit -- and apps can define their own (e.g. menu_screen's action_shared).

class read_only_single_shared(field_shared):
    field_class = read_only_single_line

class editable_single_shared(field_shared):
    field_class = editable_single_line

class read_only_multi_shared(field_shared):
    field_class = read_only_multi_line

class editable_multi_shared(field_shared):
    field_class = editable_multi_line


def single_line_shared(column, name, begin_x, ncols, app):
    r'''Column-backed single-line field_shared (table_screen convention: 1 line, "<"/">" markers,
    the column's alignment).  Picks editable vs read-only from column.can_edit.
    '''
    cls = editable_single_shared if column.can_edit else read_only_single_shared
    return cls(name, 1, begin_x, ncols, app, column.validate, column.alignment,
               left_placeholder="<", right_placeholder=">", column=column)


def multi_line_shared(column, begin_x, ncols, app, *, nlines, creating):
    r'''Column-backed multi-line field_shared (row_screen convention: left-aligned, no placeholders --
    multi_line grows instead of truncating).  Editable when creating unless calculated-and-not-editable;
    when updating only if column.can_edit.  (Matches the predicate at row_screen.py:239.)
    '''
    editable = ((not column.calculated) or column.can_edit) if creating else column.can_edit
    cls = editable_multi_shared if editable else read_only_multi_shared
    return cls(column.name, nlines, begin_x, ncols, app, column.validate,
               left_placeholder="", right_placeholder="", column=column)

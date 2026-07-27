# tui_base.py

r'''
Life of a tui app:
    - tui.start is called by the user app that is using the tui library.
    - tui.start creates a tui.app instance and has curses.wrapper call its run method (which is passed stdscr)
    - curses is now initialized and available as tui_base.curses
    - app.run stores stdscr as self.stdscr and goes from one screen to the next by
      saving it in self.screen, then calling calling screen.run, which returns the next screen (or None to exit
      the app).
    - screen.run saves app as self.app, call screen.init and then calls screen.draw and processes input, repeating
      screen.draw when the screen is resized.

Where to find things:
    - app          is screen.app
    - curses       is tui_base.curses
    - stdscr       is app.stdscr
    - screen       is app.screen
    - changed flag is app.changed, set with app.set_changed()

How input in processed:
    - input is read in screen.run
    - this calls screen.process_mouse or screen.process_key.  If either of these return a special value:
      - an instance of screen, screen.run returns this to app.run to start that screen.
      - 'APP_EXIT', screen.run returns None to app.run to exit the app
      - 'APP_ABORT', screen.run calls sys.exit(1) to exit the app
        (F12 = exit: 'APP_EXIT' when clean, else a Yes/No confirm whose Yes returns 'APP_ABORT')
      - None, screen.run assumes the event was handled and just loops to read more input
    - table_screen(screen):
      - process_mouse
          - screen.process_mouse
          - on BUTTON3_CLICKED, it creates a new popup.  Table level popup if y < 2, else row popup.
          - on BUTTON4_PRESSED (middle mouse wheel scrolled), scroll_down
          - on BUTTON5_PRESSED (middle mouse wheel scrolled), scroll_up
          - on LEFT_N_CLICK, LEFT_PRESSED, deactivate active field, activate selected field and field.process_mouse
          - on DRAG, DRAG-RELEASE, active field.process_mouse, x, y clamped to field boundaries
          - else return the mouse_event for somebody else to handle
      - process_key
          - screen.process_key
          - on F2, select first row no active field, active row.execute('View/Edit')
          - on F5, popup Delete confirm, on "Yes", row.execute('Delete')
          - on F9, open row popup
          - on F10, open screen popup
          - on INS, self.execute('Create')
          - on UP, DOWN/ENTER, commit field edit, move_focus_row
          - on TAB, BTAB, commit field edit, move_focus_col
          - on NPAGE, PPAGE, scroll_up/down a whole screen
          - on HOME, scroll to first row
          - on END, scroll to last row
          - else if active field, field.process_key
    - screen
      - process_mouse
        - routes to popup
      - process_key
        - routes to popup
        - on F8, execute('Back')
        - on F1, show help
        - on F12, self.exit_app (defined in screen)
    - popup
      - process_mouse
        (nothing)
      - process_key
        - on ESC, DEL, BACKSPACE, dismiss popup
    - popup_message(popup)
      - process_mouse
        - no enclose test
        - on LEFT_CLICK, dismiss popup
      - process_key
        - on ESC, DEL, BACKSPACE, ENTER, SPACE, dismiss popup
    - popup_menu(popup)
      - process_mouse
        - no enclose test
        - on CLICK-DRAG, select item, unselect if not on item
        - on DRAG-RELEASE, LEFT_CLICK, select and self.execute(), if not on command dismiss popup
        - forward to popup.process_mouse
      - process_key
        - on UP, DOWN, move the selected menu item up/down one
        - on LEFT, RIGHT, move the selected menu item left/right one (multi-column)
        - on ENTER or SPACE, return self.execute()
        - else popup.process_key
    - popup_confirm(popup_menu)
      - process_key
        - on 'y' or 'Y', select Yes and self.execute
        - on 'n' or 'N', select No and self.execute
        - else popup_menu.process_key
    - row_screen(screen):
      - process_mouse
        - screen.process_mouse
        - clear message
        - on LEFT_CLICK inside a button, return self.execute(button name)
        - if any field encloses the mouse position
          - if another field is active, accept it
          - return field.process_mouse
        - else return the mouse_event for somebody else to handle
      - process_key
        - on ESC with message up, clear_message, return None
        - clear_message
        - on F8, if unapplied changes display message; else back
        - try screen.process_key
        - if active_field, try active_field.process_key
        - on ENTER, SPACE, when button focused, self.execute(button name)
        - on ESC when button focused, unfocus button == no field or button selected
        - on TAB/ENTER, RTAB, select next/prior field/button
        - else return the key for somebody else to handle
    - menu_screen(screen):
      - process_mouse
        - screen.process_mouse
        - in answer, answer.process_mouse
        - on LEFT_CLICK, LEFT_DBL_CLICK on command, execute command
      - process_key
        - screen.process_key
        - on ESC, clears error_message or question
        - if answer, try answer.process_key
        - on DOWN/TAB, UP/BTAB, move to next/prior command
        - on ENTER, SPACE execute selected command
    - field.editable:
      - process_mouse
        - on LEFT_CLICKED, cancel selection, set position in text
        - on LEFT_DOUBLE_CLICKED, select the current word
        - on LEFT_TRIPLE_CLICKED, select the whole text
        - on LEFT-DRAG, make selection for deleting
        - else return the mouse_event for somebody else to handle
      - process_key
        - on ENTER with callback, return callback(text)
        - if position not set, return key for somebody else to handle
        - on curses.ascii.isprint, delete selection (if any), insert char before position, skip following keys
        - on DEL or BACKSPACE with selection, delete selection
        - on DEL without selection, delete char at position
        - on BACKSPACE without selection, delete char before position
        - on arrow keys, cancel selection, move position
        - on ESC, abort edits, select all, return None
        - else return the key for somebody else to handle
        - if grow_if_needed(), return 'REFRESH'; else return None

colors:
    COLOR 0 r=0, g=0, b=0           # black
    COLOR 1 r=680, g=0, b=0         # red
    COLOR 2 r=0, g=680, b=0         # green
    COLOR 3 r=680, g=680, b=0       # yellow
    COLOR 4 r=0, g=0, b=680         # blue
    COLOR 5 r=680, g=0, b=680       # magenta
    COLOR 6 r=0, g=680, b=680       # cyan
    COLOR 7 r=680, g=680, b=680     # white
   #COLOR 8 is the same as COLOR 0
    COLOR 9 r=1000, g=0, b=0
    COLOR 10 r=0, g=1000, b=0
    COLOR 11 r=1000, g=1000, b=0
    COLOR 12 r=0, g=0, b=1000
    COLOR 13 r=1000, g=0, b=1000
    COLOR 14 r=0, g=1000, b=1000
    COLOR 15 r=1000, g=1000, b=1000
'''

import sys
import curses
import curses.ascii
from csv_app.trace import trace


__all__ = "curses init_screen bstate_str screen popup trace".split()

def init_colors():
    r'''Loads colors as follows:

    Pair is 0bFfff Bbbb:
        F is high fg
        fff is fg color as bgr
        B is high bg
        bbb is bg color as bgr

    Convert to attr with curses.color_pair(pair_number)
    '''

    # color pair 0 is wired white (COLOR 7) on black
    pair = 0
    for fg in range(16):
        for bg in range(16):
            if pair:
                curses.init_pair(pair, fg, bg)
            pair += 1

def init_screen(stdscr):
   #stdscr.leaveok(True)        # cursor moved to new position on update
    stdscr.leaveok(False)       # cursor not moved to new position on update
    curses.curs_set(0)          # 0 - invisible, 1 - normal (typ underline), 2 - very visible (typ block)
   #curses.curs_set(1)          # 0 - invisible, 1 - normal (typ underline), 2 - very visible (typ block)
   #curses.curs_set(2)          # 0 - invisible, 1 - normal (typ underline), 2 - very visible (typ block)
    curses.mousemask(0xFFFFFFFF)
    stdscr.idlok(True)          # not needed
    stdscr.scrollok(True)       # needed for scroll to work.
   #stdscr.setscrreg(10, 30)    # doesn't affect insdelln, but causes addstr to fail at line 30
    init_colors()

def bstate_str(bstate):
    pre = ''
    if bstate & curses.BUTTON_SHIFT:
        pre += 'BUTTON_SHIFT '
        bstate &= ~curses.BUTTON_SHIFT
    if bstate & curses.BUTTON_CTRL:
        pre += 'BUTTON_CTRL '
        bstate &= ~curses.BUTTON_CTRL
    if bstate & curses.BUTTON_ALT:
        pre += 'BUTTON_ALT '
        bstate &= ~curses.BUTTON_ALT
    for num in range(1, 6):
        for event in ["PRESSED", "RELEASED", "CLICKED", "DOUBLE_CLICKED", "TRIPLE_CLICKED"]:
            name = f"BUTTON{num}_{event}"
            value = getattr(curses, name)
            if bstate & value:
                other = bstate & ~value
                if other:
                    pre += f"{hex(other)} "
                return pre + name
    if bstate & curses.REPORT_MOUSE_POSITION:
        other = bstate & ~curses.REPORT_MOUSE_POSITION
        if other:
            pre += f"{hex(other)} "
        return pre + 'REPORT_MOUSE_POSITION'
    return f"<unknown {hex(bstate)}>"

def event_handled(event):
    r'''Used by both process_mouse and process_key.
    '''
    return event is None or event in ('REFRESH', 'APP_EXIT', 'APP_ABORT') or isinstance(event, screen)


class screen:
    r'''Represents a full screen to tui.

    '''

    width = None
    popup = None
    active_field = None   # the currently active field object (see activate_field), or None
    help_title = "Navigation"
    help_lines = ()       # subclasses set their key/mouse help; empty -> F1 does nothing
    help_hint = "F1=Help" # drawn top-right on row 0 when help_lines is non-empty (UI line 10)

    def __init__(self, title, back=None, note=None):
        r'''self.app is set by run.

        note is for caller's use.  screen doesn't use it.
        '''
        self.title = title
        self.back = back     # screen to go back to
        self.note = note

    def init(self):
        r'''Run each time run is called, but _not_ each time the screen is resized.
        '''
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.title}>"

    def run(self, app):
        r'''This is called once to handle all of the screen processing, until the app switches to a new screen.

        It stores app on self.app, calls self.init (once), then each time the screen is resized calls self.draw
        and processes key and mouse events.  Finally, it returns the next screen to run (or None to exit the app).
        '''
        self.app = app
        self.init()
        while True:
            self.draw()
            while True:
                key = self.app.stdscr.getkey()   # not echoed
                if key == 'KEY_MOUSE':
                    mouse_event = self.process_mouse(curses.getmouse())
                    if isinstance(mouse_event, screen):
                        return mouse_event
                    if mouse_event == 'REFRESH':
                        break   # back to self.draw
                    if mouse_event == 'APP_EXIT':
                        return None
                    if mouse_event == 'APP_ABORT':
                        sys.exit(1)
                elif key == 'KEY_RESIZE':
                    curses.update_lines_cols()
                    break  # from inner while loop ==> redraw screen
                else:
                    key = self.process_key(key)
                    if isinstance(key, screen):
                        return key
                    if key == 'REFRESH':
                        break   # back to self.draw
                    if key == 'APP_EXIT':
                        return None
                    if key == 'APP_ABORT':
                        sys.exit(1)
                    # (no 'q' quit: exit is F12, or Exit/Abort from the F10 screen menu)
                self.app.stdscr.refresh() # does not refresh subwin the first time its called, but gets it the
                                          # second time(??)
                                          # fixed by calling noutrefresh() on subwin

    def delete(self):
        r'''Delete subwins.
        '''
        if self.popup is not None:
            self.popup.delete()   # doesn't get redrawn
            self.popup = None

    def process_mouse(self, mouse_event):
        r'''Route to the active popup first (a click/drag it doesn't consume falls through as the
        event, unchanged).  A subclass calls `super().process_mouse(...)` at the TOP of its own, then
        handles anything the popup left over.  No popup -> a harmless pass-through.
        '''
        if self.popup is not None:
            mouse_event = self.popup.process_mouse(mouse_event)
        return mouse_event

    def process_key(self, key):
        r'''Route to the active popup first (Esc/Del there closes it), then handle the keys common to
        every screen.  A subclass handles its own specific keys, calls `super().process_key(key)` near
        the TOP (so a popup wins over field/cell handling), then handles the rest.  A screen with
        special Back behavior (e.g. row_screen's unapplied-changes guard) handles F8 before delegating.
        '''
        if self.popup is not None:
            key = self.popup.process_key(key)
            if event_handled(key):
                return key
        match key:
            case 'KEY_F(8)':          # Back (validates via execute; None on a top screen -> no-op)
                return self.execute('Back')
            case 'KEY_F(1)':          # Help
                self.show_help()
                return None
            case 'KEY_F(12)':         # Exit the app (confirm first if there are unsaved changes)
                return self.exit_app()
        return key

    def show_help(self):
        r'''F1 help: pop up the screen's help_lines (a class variable).  No help_lines -> nothing.'''
        if self.help_lines:
            self.popup = popup_message(self.help_title, self, list(self.help_lines))

    def has_unsaved(self):
        r'''True when exiting now would lose work, so exit_app confirms first.  Base = the app's
        changed flag; a screen with its own uncommitted state (e.g. row_screen's unapplied field
        edits) extends this.'''
        return self.app.changed

    def exit_app(self):
        r'''F12: exit the app.  With nothing unsaved, exit cleanly (APP_EXIT).  With unsaved changes,
        pop a Yes/No confirm -- Yes aborts (APP_ABORT, discarding the changes), No stays.  The
        popup_confirm callback returns the leaving sentinel, which propagates back out to screen.run.
        '''
        if not self.has_unsaved():
            return 'APP_EXIT'
        title = "Discard changes and exit?"
        width = 4 + len(title)
        begin_x = max(1, (self.cols - width) // 2)
        begin_y = max(1, (self.lines - 4) // 2)
        if self.popup is not None:
            self.popup.delete()
        self.popup = popup_confirm(title, self,
                                   lambda choice: 'APP_ABORT' if choice == 'Yes' else None,
                                   begin_y, begin_x, outside_space=None)
        return None

    def validate(self):
        return True

    def activate_field(self, field):
        r'''Make `field` the active field: un-highlight the previously active one and highlight this one.

        Each field knows how to (un)highlight itself via activate()/deactivate(), so this one method serves
        every screen.  Pass None to just clear the active field.  Re-activating the same field is a no-op, so
        the redundant calls a field makes while editing don't disturb its cursor.
        '''
        if self.active_field is field:
            return
        if self.active_field is not None:
            self.active_field.deactivate()
        self.active_field = field
        if field is not None:
            field.activate()

    def execute(self, command):
        trace(f"screen.execute({command=})")
        match command:
            case 'Back':
                trace("screen.execute: Back validating table")
                if self.validate():
                    trace(f"screen.execute: passed validate -> {self.back=}")
                    return self.back
                trace(f"screen.execute: failed validate -> None")
                return None
        return self.app.execute(command)

    def draw(self):
        r'''Run each time the screen is resized.
        '''
        self.lines = curses.LINES
        self.cols = curses.COLS
        trace(f"draw(): {self.lines=}, {self.cols=}")
        if self.width is None:
            title_x = (self.cols - len(self.title)) // 2   # center title
        else:
            assert self.width < self.cols, \
                   f"ERROR: Screen not wide enough, must be at least {self.width + 1} columns"
            title_x = (self.width - len(self.title)) // 2   # center title
        self.delete()
        self.app.stdscr.erase()
        self.app.stdscr.addstr(0, title_x, self.title, curses.A_REVERSE)   # center title
        self.app.draw_changed(title_x)
        if self.help_lines:                                     # advertise F1 help, centered between
            title_right = title_x + len(self.title)             # the title and the right screen edge
            hint_x = title_right + (self.cols - title_right - len(self.help_hint)) // 2
            self.app.stdscr.addstr(0, hint_x, self.help_hint)
        self.draw_body()

    def draw_body(self):
        pass


class popup:
    r'''Popup window

    Blank space is added on the inside sides (but not top and bottom).
    Blank space is added on the outside sides and top or bottom depending on outside_space.
    '''

    def __init__(self, name, screen, begin_y, begin_x, text_height, text_width, outside_space=None,
                 name_attr_pair=0):
        r'''To understand what's going on here:

        - A subwin is created with self.height/width/begin_y/begin_x.
          - with a box that occupies the top and bottom rows, and the left and right columns.
          - In addition a blank column is left inside the left and right box sides.
          - The subwin has its own coordinate system, but this includes the box and extra spacing.
            - Thus, the first char of text goes at y=1, x=2 in subwin coordinates.
        - The saved/restored area extends outside of the subwin.
          - It is defined by self.saved_height/saved_width/saved_y/saved_x.
          - This includes a blank column outside the left and right box sides, and a blank row outside
            the top or bottom box side depending on outer_space.
          - Thus, begin_y and begin_x must be at least 1.
        '''
        self.border_at = curses.color_pair(0xF1)
        self.name = name
        self.screen = screen
        self.text_height = text_height
        self.text_width = text_width
        self.height = 2 + text_height
        self.width = 4 + max(len(name), text_width)  # includes box and inside spacing

        trace(f"popup.__init__({name=}, {begin_y=}, {begin_x=}, {text_height=}, {text_width=}): "
              f"{self.height=}, {self.width=}")

        assert 1 <= begin_y, f"popup.__init__({name=}) {begin_y=} < 1"
        assert 1 <= begin_x <= screen.cols - self.width, \
               f"popup.__init__({name=}) {begin_x=} outside 1 to {screen.cols - self.width}"

        # begin_y, begin_x is upper left corner of box
        # saved_y, saved_x is upper left corner of area to save and restore (includes blank space around the box)
        if begin_y <= screen.lines - self.height:
            self.begin_y = begin_y
        else:
            self.begin_y = begin_y - (self.height + 1)
            outside_space = 'above'

        if outside_space is None:
            self.saved_height = self.height
        else:
            self.saved_height = self.height + 1

        match outside_space:
            case 'below' | None:
                self.saved_y = self.begin_y
            case 'above':
                self.saved_y = self.begin_y - 1

        self.begin_x = begin_x
        self.saved_x = self.begin_x - 1
        if self.begin_x == screen.cols - self.width:
            # right side of box at rigth edge of screen.  Only outside space on left.
            self.saved_width = self.width + 1
        else:
            self.saved_width = self.width + 2

        trace(f"popup.__init__: {self.begin_y=}, {self.begin_x=}, "
              f"{self.saved_y=}, {self.saved_x=}, {self.saved_height=}, {self.saved_width=})")

        self.saved_chars = [[screen.app.stdscr.inch(line, col)
                             for col in range(self.saved_x, self.saved_x + self.saved_width)]
                            for line in range(self.saved_y, self.saved_y + self.saved_height)]
        # blank popup area, including space outside of subwin
        for y in range(self.saved_y, self.saved_y + self.saved_height):
            screen.app.stdscr.addstr(y, self.saved_x, ' ' * self.saved_width)
        self.subwin = screen.app.stdscr.subwin(self.height, self.width, self.begin_y, self.begin_x)
       #ch = 0x20 + curses.color_pair(6)
       #self.subwin.border(ch, ch, ch, ch, ch, ch, ch, ch)
       #chars = [0x20 + curses.color_pair(p) for p in range(3, 7)]
       #self.subwin.border(chars[0], chars[1], chars[2], chars[3], chars[2], chars[2], chars[3], chars[3])
        self.subwin.box()   # does not change window coords, so addstr can overwrite the box chars,
                            # including wrapping
        self.subwin.addstr(0, 2, self.name, curses.color_pair(name_attr_pair))
       #self.subwin.chgat(0, 0, self.width, self.border_at)

    def process_key(self, key):
        trace(f"popup.process_key({key=})")
        if key == "\x1B" or key == 'KEY_DELETE' or key == 'KEY_DC':
            self.delete()
        else:
            return key

    def process_mouse(self, mouse_event):
        return mouse_event

    def enclose(self, y, x):
        return self.subwin.enclose(y, x)

    def delete(self):
        trace(f"popup.delete()")
        if self.subwin is not None:
            del self.subwin
            self.subwin = None
        # restore overlain image
        for lineno, chars in enumerate(self.saved_chars, self.saved_y):
            for col, char in enumerate(chars, self.saved_x):
                self.screen.app.stdscr.addch(lineno, col, char)
        self.screen.popup = None

class popup_message(popup):
    def __init__(self, name, screen, lines, text_attr_pair=0):
        if isinstance(lines, str):
            lines = [lines]
        lines = [line[:max(1, screen.cols - 6)] for line in lines]   # clip so the box fits the screen
        text_width = max(len(line) for line in lines)
        begin_y = (screen.lines - len(lines) - 2) // 2
        begin_x = (screen.cols - text_width - 4) // 2
        super().__init__(name, screen, begin_y, begin_x, len(lines), text_width)
        for lineno, line in enumerate(lines, 1):
            self.subwin.addstr(lineno, 2, f"{line:{self.width - 4}}", curses.color_pair(text_attr_pair))

    def process_key(self, key):
        r'''A message box has no selection: Esc/Del/Enter/Space (and a click, see process_mouse)
        dismiss it; every other key is ignored (consumed) while it is up.'''
        if key in ('\x1B', 'KEY_DELETE', 'KEY_DC', 'KEY_ENTER', '\n', ' '):
            self.delete()
        return None

    def process_mouse(self, mouse_event):
        r'''A left click dismisses the message; other mouse events are ignored while it is up.'''
        _, x, y, _, bstate = mouse_event
        if bstate == curses.BUTTON1_CLICKED:
            self.delete()
        return None

class popup_menu(popup):
    r'''A command menu.  A long list wraps into several columns (column-major: fill a column top-down,
    then the next), sized to fit the screen height; a short list stays one column.  self.selection is a
    flat index into self.commands; _cell() maps it to a subwin (y, x) and _index_at() maps a screen
    (y, x) back to an index.
    '''
    col_gap = 2   # blank columns between menu columns when the list wraps into several
    pressing = False   # True while a left-button drag-select is in progress

    def __init__(self, name, screen, commands, cmd_fn, begin_y, begin_x, outside_space='below'):
        self.commands = commands
        self.cmd_fn = cmd_fn
        self.n = len(commands)
        self.col_width = max(len(command) for command in commands)
        # Column-major layout: wrap into as few columns as fit the screen height, capped by width.
        max_rows = max(1, screen.lines - 4)                  # popup box needs 2 rows + a margin
        avail_width = screen.cols - begin_x - 4              # inside the box (2 spacing each side)
        max_cols = max(1, (avail_width + self.col_gap) // (self.col_width + self.col_gap))
        ncols = min(max_cols, -(-self.n // max_rows))        # ceil(n / max_rows), capped by width
        self.rows_per_col = -(-self.n // ncols)              # balance the columns: ceil(n / ncols)
        self.ncols = -(-self.n // self.rows_per_col)         # drop any now-empty trailing column
        text_height = self.rows_per_col
        text_width = self.ncols * self.col_width + (self.ncols - 1) * self.col_gap
        super().__init__(name, screen, begin_y, begin_x, text_height, text_width, outside_space)
        for i, command in enumerate(commands):
            y, x = self._cell(i)
            self.subwin.addstr(y, x, f"{command:{self.col_width}}")
        self.selection = None   # flat index into self.commands
        self.select(0)

    def _cell(self, index):
        r'''(subwin y, x) of command `index` (column-major).'''
        col, row = divmod(index, self.rows_per_col)
        return row + 1, 2 + col * (self.col_width + self.col_gap)

    def _index_at(self, y, x):
        r'''Command index under screen (y, x); None if outside the menu, in a column gap, or past the
        last command.'''
        if not self.enclose(y, x):
            return None
        row = y - self.begin_y - 1
        rel_x = x - self.begin_x - 2
        if not (0 <= row < self.rows_per_col) or rel_x < 0:
            return None
        col, within = divmod(rel_x, self.col_width + self.col_gap)
        if within >= self.col_width or col >= self.ncols:    # in the gap / past the last column
            return None
        index = col * self.rows_per_col + row
        return index if index < self.n else None

    def process_key(self, key):
        trace(f"popup_menu.process_key({key=})")
        if self.selection is None and key in ('KEY_DOWN', 'KEY_UP', 'KEY_LEFT', 'KEY_RIGHT',
                                              'KEY_ENTER', '\n', ' '):
            self.select(0)                                   # re-anchor after a mouse deselect
            return None
        if key == 'KEY_DOWN':                                # next row in this column
            if self.selection % self.rows_per_col + 1 < self.rows_per_col \
                    and self.selection + 1 < self.n:
                self.select(self.selection + 1)
        elif key == 'KEY_UP':                                # previous row in this column
            if self.selection % self.rows_per_col > 0:
                self.select(self.selection - 1)
        elif key == 'KEY_RIGHT':                             # same row, next column
            if self.selection + self.rows_per_col < self.n:
                self.select(self.selection + self.rows_per_col)
        elif key == 'KEY_LEFT':                              # same row, previous column
            if self.selection - self.rows_per_col >= 0:
                self.select(self.selection - self.rows_per_col)
        elif key == 'KEY_ENTER' or key == '\n' or key == ' ':
            return self.execute()
        else:
            return super().process_key(key)

    def process_mouse(self, mouse_event):
        r'''UI gesture (lines 3-5): LEFT PRESS + DRAG highlights the entry under the pointer (off the
        menu deselects); LEFT RELEASE on an entry executes it, RELEASE off the menu dismisses.  A quick
        click a terminal collapses to BUTTON1_CLICKED is treated as press+release at one spot.  Other
        buttons (wheel, etc.) bubble.
        '''
        _, x, y, _, bstate = mouse_event
        trace(f"popup_menu.process_mouse({y=}, {x=}, bstate={bstate_str(bstate)})")
        # NOTE on the `self.pressing` guards below: ncurses' default mouseinterval (~166 ms) HOLDS a
        # BUTTON1_PRESSED for that long, hoping to combine it with a following event into a
        # CLICKED/DOUBLE/TRIPLE.  If the first drag motion arrives inside that window, the press gets
        # merged away and we never see a standalone BUTTON1_PRESSED -- so we can get REPORT_MOUSE_POSITION
        # (or the RELEASE) with no preceding press.  It's a race against that timer, hence intermittent.
        # We guard REPORT and RELEASE on `pressing` so a press we never saw can't drive a phantom
        # drag/execute (fail-safe: that gesture just does nothing -> re-press).  Empirically, pressing
        # then pausing briefly before dragging makes the press reliable (the interval elapses, ncurses
        # emits the standalone PRESSED).  mouseinterval(0) would deliver raw press/release reliably but
        # KILLS CLICKED/DOUBLE/TRIPLE synthesis, which field.py/table_screen depend on -- so we live
        # with it.  Refs: https://invisible-island.net/ncurses/man/curs_mouse.3x.html
        #   https://manpages.debian.org/buster/ncurses-doc/mouseinterval.3ncurses.en.html
        if bstate == curses.BUTTON1_PRESSED:
            self.pressing = True
            self._highlight_or_deselect(self._index_at(y, x))
            return None
        if bstate == curses.REPORT_MOUSE_POSITION and self.pressing:
            self._highlight_or_deselect(self._index_at(y, x))
            return None
        if bstate == curses.BUTTON1_RELEASED and self.pressing:  # only finish a press WE started
            self.pressing = False
            return self._release_at(y, x)
        if bstate == curses.BUTTON1_CLICKED:                 # self-contained press+release
            return self._release_at(y, x)
        return super().process_mouse(mouse_event)            # wheel / stray release / etc. -> bubble

    def _release_at(self, y, x):
        r'''Finish the gesture: on an entry -> execute it; off the menu -> dismiss.'''
        index = self._index_at(y, x)
        if index is None:
            self.delete()                                    # off the menu -> dismiss
            return None
        self.select(index)
        return self.execute()                                # on an entry -> run it

    def _highlight_or_deselect(self, index):
        r'''During a drag: highlight `index` if on an entry, else clear the highlight (off the menu).'''
        if index is None:
            if self.selection is not None:
                y, x = self._cell(self.selection)
                self.subwin.chgat(y, x, self.col_width, 0)
                self.subwin.noutrefresh()
                self.selection = None
        else:
            self.select(index)

    def execute(self):
        trace(f"popup_menu.execute(): {self.selection=}")
        command = self.commands[self.selection]
        trace(f"popup_menu.execute(): {command=}")
        self.delete()
        ans = self.cmd_fn(command)
        trace(f"popup_menu.execute() -> {ans}")
        return ans

    def select(self, index):
        r'''Highlight command `index` (a flat index into self.commands), un-highlighting the old one.'''
        trace(f"popup_menu.select({index=})")
        assert 0 <= index < self.n, \
           f"popup_menu.select: {index=} out of range 0-{self.n - 1}"
        if self.selection is not None:
            y, x = self._cell(self.selection)
            self.subwin.chgat(y, x, self.col_width, 0)
        self.selection = index
        y, x = self._cell(index)
        self.subwin.chgat(y, x, self.col_width, curses.A_REVERSE)
        self.subwin.noutrefresh()


class popup_confirm(popup_menu):
    r'''A Yes/No confirmation popup.  Enter/Space runs the highlighted choice (default No); 'y'/'Y'
    answer Yes and 'n'/'N' answer No directly; Esc dismisses (== No).  cmd_fn is called with the
    chosen command string ('Yes' or 'No').
    '''
    def __init__(self, name, screen, cmd_fn, begin_y, begin_x, outside_space='below'):
        super().__init__(name, screen, ('No', 'Yes'), cmd_fn, begin_y, begin_x, outside_space)

    def process_key(self, key):
        if key in ('y', 'Y'):
            self.select(1)                 # Yes
            return self.execute()
        if key in ('n', 'N'):
            self.select(0)                 # No
            return self.execute()
        return super().process_key(key)

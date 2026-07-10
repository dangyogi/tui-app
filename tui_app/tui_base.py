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
      - 'q' from screen.process_key, returns None to app.run to exit the app (this may go away in the future)
      - None, screen.run assumes the event was handled and just loops to read more input
    - table_screen:
      - process_mouse
          - if a popup is active, call its process_mouse.  If it returns any of the special values above,
            the value is simply returned to screen.process_mouse, otherwise it proceeds on:
          - on BUTTON3_CLICKED, it creates a new popup.  Table level popup if y < 2, else row popup.
          - on BUTTON4_PRESSED (middle mouse wheel scrolled), scroll_down
          - on BUTTON5_PRESSED (middle mouse wheel scrolled), scroll_up
          - else return the mouse_event for somebody else to handle
      - process_key
          - if a popup is active, call its process_key.  If it returns any of the special values above,
            the value is simply returned to screen.process_key, otherwise it proceeds on:
          - on KEY_UP, scroll_down
          - on KEY_DOWN, scroll_up
          - on KEY_PPAGE, scroll_down a whole screen
          - on KEY_NPAGE, scroll_up a whole screen
          - on KEY_HOME, scroll to first row
          - on KEY_END, scroll to last row
          - else return the key for somebody else to handle
    - popup
      - process_mouse
          - if the mouse position is outside of the popup, simply return the mouse_event for somebody else to handle
          - on BUTTON1_CLICKED, select the indicated menu entry
          - on BUTTON1_DOUBLE_CLICKED, select the indicated menu entry, then return self.execute()
          - else return the mouse_event for somebody else to handle
      - process_key
          - on KEY_UP, move the selected menu item up one
          - on KEY_DOWN, move the selected menu item down one
          - on KEY_ENTER or '\n' or ' ', return self.execute()
          - on "\x1B" or 'KEY_DELETE' or 'KEY_DC', call self.delete() and return None
          - else return the key for somebody else to handle
    - row_screen:
      - process_mouse
          - on BUTTON1_CLICKED inside a button, return self.execute(button command)
          - if any field encloses the mouse position, return field.process_mouse
          - else return the mouse_event for somebody else to handle
      - process_key
          - if there is an active_field, return active.process_key
          - else return the key for somebody else to handle
    - field:
      - process_mouse
          - on BUTTON1_CLICKED, cancel selection, set position in text
          - on BUTTON1_DOUBLE_CLICKED, select the current word
          - on BUTTON1_TRIPLE_CLICKED, select the whole text
          - on BUTTON1_PRESSED, set self.in_select, return None
          - on REPORT_MOUSE_POSITION while self.in_select, extend selection
          - on BUTTON1_RELEASED, unset self.in_select, return None
          - else return the mouse_event for somebody else to handle
      - process_key
          - on 'KEY_DELETE' or 'KEY_DC' or 'KEY_BACKSPACE' with selection, delete selection
          - on 'KEY_DELETE' or 'KEY_DC' without selection, delete char at position
          - on 'KEY_BACKSPACE' without selection, delete char before position
          - on curses.ascii.isprint, delete selection (if any), insert char before position
          - on arrow keys, cancel selection, move position
          - else return the key for somebody else to handle

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

    def __init__(self, title, back=None):
        r'''self.app is set by run.
        '''
        self.title = title
        self.back = back     # screen to go back to

    def init(self):
        r'''Run each time run is called, but _not_ each time the screen is resized.
        '''
        pass

    def __str__(self):
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
                    if key == 'q':
                        return None  # quit
                app.stdscr.refresh() # does not refresh subwin the first time its called, but gets it the second time(??)
                                     # fixed by calling noutrefresh() on subwin

    def delete(self):
        r'''Delete subwins.
        '''
        if self.popup is not None:
            self.popup.delete()   # doesn't get redrawn
            self.popup = None

    def process_mouse(self, mouse_event):
        return mouse_event

    def process_key(self, key):
        return key

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
        text_width = max(len(line) for line in lines)
        begin_y = (screen.lines - len(lines) - 2) // 2
        begin_x = (screen.cols - text_width - 4) // 2
        super().__init__(name, screen, begin_y, begin_x, len(lines), text_width)
        for lineno, line in enumerate(lines, 1):
            self.subwin.addstr(lineno, 2, f"{line:{self.width - 4}}", curses.color_pair(text_attr_pair))

class popup_menu(popup):
    def __init__(self, name, screen, commands, cmd_fn, begin_y, begin_x, outside_space='below'):
        super().__init__(name, screen, begin_y, begin_x,
                         len(commands), max(len(command) for command in commands),
                         outside_space)
        self.commands = commands
        self.cmd_fn = cmd_fn
        for lineno, command in enumerate(commands, 1):
            self.subwin.addstr(lineno, 2, f"{command:{self.width - 4}}")
        self.selection = None   # index into self.commands
        self.select(0)

    def process_key(self, key):
        trace(f"popup_menu.process_key({key=})")
        if key == 'KEY_DOWN':
            if self.selection + 1 < self.text_height:
                self.select(self.selection + 1)
        elif key == 'KEY_UP':
            if self.selection - 1 >= 0:
                self.select(self.selection - 1)
        elif key == 'KEY_ENTER' or key == '\n' or key == ' ':
            return self.execute()
        else:
            return super().process_key(key)

    def process_mouse(self, mouse_event):
        _, x, y, _, bstate = mouse_event
        trace(f"popup_menu.process_mouse({y=}, {x=}, bstate={bstate_str(bstate)})")
        if not self.enclose(y, x) or not (self.begin_y < y < self.begin_y + self.height - 1):
            return mouse_event
        if bstate == curses.BUTTON1_CLICKED:
            self.select(y - self.begin_y - 1)
        if bstate == curses.BUTTON1_DOUBLE_CLICKED:
            self.select(y - self.begin_y - 1)
            return self.execute()
        else:
            return super().process_mouse(mouse_event)

    def execute(self):
        trace(f"popup_menu.execute(): {self.selection=}")
        command = self.commands[self.selection]
        trace(f"popup_menu.execute(): {command=}")
        self.delete()
        ans = self.cmd_fn(command)
        trace(f"popup_menu.execute() -> {ans}")
        return ans

    def select(self, index):
        r'''index into self.commands

        So first command is 0, last command is self.text_height - 1
        '''
        trace(f"popup_menu.select({index=})")
        assert 0 <= index < self.text_height, \
           f"popup_menu.select: {index=} out of range {0}-{self.text_height - 1}"
        if self.selection is not None:
            self.subwin.chgat(self.selection + 1, 2, self.width - 4, 0)
        self.selection = index
        self.subwin.chgat(self.selection + 1, 2, self.width - 4, curses.A_REVERSE)
        self.subwin.noutrefresh()

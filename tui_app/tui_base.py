# tui_base.py

r'''
Life of a tui app:
    - tui.start is called by the user app that is using the tui library.
    - tui.start creates a tui.app instance and has curses.wrapper call its run method (which is passed stdscr)
    - curses is now initialized and available as tui_base.curses
    - app.run stores stdscr as self.stdscr, opens its self.trace_file and goes from one screen to the next by
      saving it in self.screen, then calling calling screen.run, which returns the next screen (or None to exit
      the app).
    - screen.run saves app as self.app, call screen.init and then calls screen.draw and processes input, repeating
      screen.draw when the screen is resized.

Where to find things:
    - app          is screen.app
    - curses       is tui_base.curses
    - stdscr       is app.stdscr
    - trace_file   is app.trace_file
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
                    if mouse_event == 'APP_EXIT':
                        return None
                    if mouse_event == 'APP_ABORT':
                        sys.exit(1)
                    if mouse_event is not None:
                        id, x, y, z, bstate = mouse_event
                        # FIX: anything else to do here besides ignore it?
                elif key == 'KEY_RESIZE':
                    curses.update_lines_cols()
                    break  # from inner while loop ==> redraw screen
                else:
                    key = self.process_key(key)
                    if isinstance(key, screen):
                        return key
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
        print(f"draw(): {self.lines=}, {self.cols=}", file=self.app.trace_file)
        if self.width is None:
            self.width = self.cols
        self.delete()
        self.app.stdscr.erase()
        title_x = (self.width - len(self.title)) // 2   # center title
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

    def __init__(self, name, screen, commands, cmd_fn, begin_y, begin_x, outside_space='below'):
        self.border_at = curses.color_pair(0xF1)
        self.name = name
        self.screen = screen
        self.commands = commands
        self.cmd_fn = cmd_fn
        self.height = 2 + len(commands)                                             # includes box
        self.width = 4 + max(len(name), max(len(command) for command in commands))  # includes box and inside spacing

        print(f"popup.__init__({name=}, {commands=}, {begin_y=}, {begin_x=})", file=screen.app.trace_file)

        assert 1 <= begin_y, f"popup.__init__({name=}) {begin_y=} < 1"
        self.saved_height = self.height + 1
        assert 1 <= begin_x <= screen.cols - self.width, \
               f"popup.__init__({name=}) {begin_x=} outside 1 to {screen.cols - self.width}"

        # begin_y, begin_x is upper left corner of box
        # saved_y, saved_x is upper left corner of area to save and restore (includes blank space around the box)
        if begin_y <= screen.lines - self.height:
            self.begin_y = begin_y
        else:
            self.begin_y = begin_y - (self.height + 1)
            outside_space = 'above'

        match outside_space:
            case 'below':
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

        print(f"popup.__init__: {self.begin_y=}, {self.begin_x=}, "
              f"{self.saved_y=}, {self.saved_x=}, {self.height=}, {self.width=})",
              file=screen.app.trace_file)

        self.saved_chars = [[screen.app.stdscr.inch(line, col)
                             for col in range(self.saved_x, self.saved_x + self.saved_width)]
                            for line in range(self.saved_y, self.saved_y + self.saved_height)]
        for y in range(self.saved_y, self.saved_y + self.saved_height):
            screen.app.stdscr.addstr(y, self.saved_x, ' ' * self.saved_width)
        self.subwin = screen.app.stdscr.subwin(self.height, self.width, self.begin_y, self.begin_x)
       #ch = 0x20 + curses.color_pair(6)
       #self.subwin.border(ch, ch, ch, ch, ch, ch, ch, ch)
       #chars = [0x20 + curses.color_pair(p) for p in range(3, 7)]
       #self.subwin.border(chars[0], chars[1], chars[2], chars[3], chars[2], chars[2], chars[3], chars[3])
        self.subwin.box()   # does not change window coords, so addstr can overwrite the box chars,
                            # including wrapping
        self.subwin.addstr(0, 2, self.name)
       #self.subwin.chgat(0, 0, self.width, self.border_at)
        for lineno, command in enumerate(commands, 1):
            self.subwin.addstr(lineno, 2, f"{command:{self.width - 4}}")
        self.selection = None
        self.select(1)

    def process_key(self, key):
        print(f"popup.process_key({key=})", file=self.screen.app.trace_file)
        if key == 'KEY_DOWN':
            if self.selection + 1 < self.height - 1:
                self.select(self.selection + 1)
        elif key == 'KEY_UP':
            if self.selection - 1 > 0:
                self.select(self.selection - 1)
        elif key == 'KEY_ENTER' or key == '\n' or key == ' ':
            return self.execute()
        elif key == "\x1B" or key == 'KEY_DELETE' or key == 'KEY_DC':
            self.delete()
        else:
            return key

    def process_mouse(self, mouse_event):
        _, x, y, _, bstate = mouse_event
        print(f"popup.process_mouse({y=}, {x=}, bstate={bstate_str(bstate)})", file=self.screen.app.trace_file)
        if not self.enclose(y, x) or not (self.begin_y < y < self.begin_y + self.height - 1):
            return mouse_event
        if bstate == curses.BUTTON1_CLICKED:
            self.select(y - self.begin_y)
        if bstate == curses.BUTTON1_DOUBLE_CLICKED:
            self.select(y - self.begin_y)
            return self.execute()
        else:
            return mouse_event

    def execute(self):
        print(f"popup.execute(): {self.selection=}", file=self.screen.app.trace_file)
        command = self.commands[self.selection - 1]
        print(f"popup.execute(): {command=}", file=self.screen.app.trace_file)
        self.delete()
        return self.cmd_fn(command)

    def enclose(self, y, x):
        return self.subwin.enclose(y, x)

    def select(self, y):
        r'''y in subwin coord.

        So first command is 1, last command is self.height - 2
        '''
        print(f"popup.select({y=})", file=self.screen.app.trace_file)
        assert 0 < y < self.height - 1, \
           f"popup.select: {y=} out of range {1}-{self.height - 2}"
        if self.selection is not None:
            self.subwin.chgat(self.selection, 2, self.width - 4, 0)
        self.selection = y
        self.subwin.chgat(self.selection, 2, self.width - 4, curses.A_REVERSE)
        self.subwin.noutrefresh()

    def delete(self):
        print(f"popup.delete()", file=self.screen.app.trace_file)
        if self.subwin is not None:
            del self.subwin
            self.subwin = None
        # restore overlain image
        for lineno, chars in enumerate(self.saved_chars, self.saved_y):
            for col, char in enumerate(chars, self.saved_x):
                self.screen.app.stdscr.addch(lineno, col, char)
        self.screen.popup = None


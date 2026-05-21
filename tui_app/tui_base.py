# tui_base.py

r'''
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

import curses


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
    curses.mousemask(0xFFFFFFFF)
    stdscr.idlok(True)          # not needed
    stdscr.scrollok(True)       # needed for scroll to work.
   #stdscr.setscrreg(10, 30)    # doesn't affect insdelln, but causes addstr to fail at line 30
    init_colors()

def bstate_str(bstate):
    pre = ''
    if bstate & curses.BUTTON_SHIFT:
        pre = 'BUTTON_SHIFT '
        bstate &= ~curses.BUTTON_SHIFT
    if bstate & curses.BUTTON_CTRL:
        pre = 'BUTTON_CTRL '
        bstate &= ~curses.BUTTON_CTRL
    if bstate & curses.BUTTON_ALT:
        pre = 'BUTTON_ALT '
        bstate &= ~curses.BUTTON_ALT
    for num in range(1, 6):
        for event in ["PRESSED", "RELEASED", "CLICKED", "DOUBLE_CLICKED", "TRIPLE_CLICKED"]:
            name = f"BUTTON{num}_{event}"
            if bstate & getattr(curses, name):
                return name
    return f"<unknown {hex(bstate)}>"


class screen:
    width = None
    popup = None

    def __init__(self, title):
        self.title = title

    def init(self):
        r'''Run each time run is called, but _not_ each time the screen is resized.
        '''
        pass

    def run(self, app):
        r'''This draws the screen, processes inputs, and returns the next screen to run (or None to exit).
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
                    if key == 'q':
                        return None  # quit
                app.stdscr.refresh() # does not refresh subwin the first time its called, but gets it the second time(??)
                                     # fixed by calling noutrefresh() on subwin

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
        if self.popup is not None:
            self.popup.delete()   # doesn't get redrawn
        self.app.stdscr.erase()
        self.app.stdscr.addstr(0, (self.width - len(self.title)) // 2, self.title, curses.A_REVERSE)   # center title
        self.draw_body()

    def draw_body(self):
        pass


class popup:
    def __init__(self, name, screen, commands, cmd_fn, begin_y, begin_x):
        self.border_at = curses.color_pair(0xF1)
        self.name = name
        self.screen = screen
        self.commands = commands
        self.cmd_fn = cmd_fn
        self.height = 2 + len(commands)                                 # includes box
        self.width = 4 + max(len(command) for command in commands)      # includes box and inside spacing

        if begin_y <= 0:
            self.begin_y = self.saved_y = 0
            self.saved_height = self.height + 1
        elif begin_y + self.height > screen.lines:
            self.begin_y = screen.lines + 1 - begin_y
            self.saved_y = self.begin_y - 1
            self.saved_height = self.height + 1
        else:
            self.begin_y = begin_y
            self.saved_y = self.begin_y - 1
            self.saved_height = self.height + 2

        if begin_x <= 0:
            self.begin_x = self.saved_x = 0
            self.saved_width = self.width + 1
        elif begin_x + self.width > screen.cols:
            self.begin_x = screen.cols + 1 - begin_x
            self.saved_x = self.begin_x - 1
            self.saved_width = self.width + 1
        else:
            self.begin_x = begin_x
            self.saved_x = self.begin_x - 1
            self.saved_width = self.width + 2

        print(f"popup.__init__({name=}, {commands=}, {begin_y=}, {begin_x=})", file=screen.app.trace_file)
        self.saved_chars = [[screen.app.stdscr.inch(line, col)
                             for col in range(self.saved_x, self.saved_x + self.saved_width)]
                            for line in range(self.saved_y, self.saved_y + self.saved_height)]
        for y in range(self.saved_y, self.saved_y + self.saved_height):
            screen.app.stdscr.addstr(y, self.saved_x, ' ' * self.saved_width)
        self.subwin = screen.app.stdscr.subwin(self.height, self.width, begin_y, begin_x)
       #ch = 0x20 + curses.color_pair(6)
       #self.subwin.border(ch, ch, ch, ch, ch, ch, ch, ch)
       #chars = [0x20 + curses.color_pair(p) for p in range(3, 7)]
       #self.subwin.border(chars[0], chars[1], chars[2], chars[3], chars[2], chars[2], chars[3], chars[3])
        self.subwin.box()   # does not change window coords, so addstr can overwrite the box chars, including wrapping
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
        if not self.enclose(y, x) or not (self.begin_y < y < self.begin_y + self.height):
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
        del self.subwin
        self.subwin = None
        for lineno, chars in enumerate(self.saved_chars, self.saved_y):
            for col, char in enumerate(chars, self.saved_x):
                self.screen.app.stdscr.addch(lineno, col, char)
        self.screen.popup = None


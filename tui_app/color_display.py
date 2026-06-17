# color_display.py

r'''Shows the 256 different color pair colors.
'''

import time
import curses
from . import tui_base

def doit(stdscr):
    tui_base.init_screen(stdscr)
    stdscr.erase()
    print(f"{curses.LINES=}, {curses.COLS=}", file=Trace_file)
    print(f"need {2 + 2*15} lines, {3 + 7*15 + 4} cols", file=Trace_file)
    paint(stdscr)
    print(f"doing refresh", file=Trace_file)
    stdscr.refresh()
    print(f"doing getkey", file=Trace_file)
    key = stdscr.getkey()
    print(f"getkey returned {key=}", file=Trace_file)

def paint(stdscr=None):
    for bg in range(16):
        for fg in range(16):
            pair = (fg << 4) | bg
            if stdscr is None:
                color = pair
            else:
                color = curses.color_pair(pair)
            if stdscr is None:
                print(2 + 2*bg, 3 + 7*fg, hex(pair), '  ', end='')
            else:
                print(f"{fg=}, {bg=}, y={2 + 2*bg}, x={3 + 7*fg}, pair={hex(pair)}", file=Trace_file)
                stdscr.addstr(2 + 2*bg, 3 + 7*fg, hex(pair), color)
        if stdscr is None:
            print()

def run():
    global Trace_file
    with open('color_display.txt', 'wt') as Trace_file:
        curses.wrapper(doit)
        #paint()


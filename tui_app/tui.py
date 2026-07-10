# tui.py

r'''This is a generic TUI front-end for database type applications.

It provides a tables view (list of rows with column headings) and a row view (similar to a form).

It builds on three classes that you must write with the following interfaces:

    table:
        .name
        .columns
        .screen_popup_commands   # list of strings, tui will add Back and Abort/Exit to the end of these.
        .get_rows(app, **select) # returns a list of selected row objects.
                                 # select keys are column_name (__eq assumed), or column_name__<lt|le|eq|ne|ge|gt>
                                 # results of select keys are and-ed.
                                 # This library does not support paging to the data.
        .execute(app, command)   # for anything on screen popup other than table_names or Back/Abort/Exit

    column:
        .name
        .abbr                    # abbr name to save space on the screen.  May be None.
        .min_width               # may be None, used for table view to fit all of the columns on the screen
        .alignment               # "left" or "right"
        .can_edit                # True/False
        .validate(s)             # raises ValueError if s not valid
        .column_attr_pair(row)   # returns attr_pair for column, or None for default attr

    row:
        .table_name
        .columns
        .human_key()            # may be row_num
        .get(column_name)       # returns string to display
        .set(column_name, str)  # sets column_name to converted str
        .delete()
        .row_popup_commands
        .row_screen_commands
        .execute(app, command)  # for commands on row popup

See the tui_base.py module doc string for how the tui library works.
'''

from csv_app.trace import trace
from . import tui_base
from .table_screen import table_screen


def start(tables, top_screen=None):
    app_instance = app(tables, top_screen)
    tui_base.curses.wrapper(app_instance.run)

class app:
    r'''Created and run by `start` fn.
    '''
    screen = None

    def __init__(self, tables, top_screen=None):
        self.tables = tables
        if top_screen is None:
            self.top_screen = table_screen(self.tables[list(tables.keys())[0]])
        else:
            self.top_screen = top_screen
        self.changed = False

    def run(self, stdscr):   # called by curses.wrapper in start fn
        self.stdscr = stdscr
        tui_base.init_screen(stdscr)
        self.screen = self.top_screen
        while self.screen is not None:
            next_screen = self.screen.run(self)
            self.screen.delete()
            self.screen = next_screen

    def draw_changed(self, title_x):
        self.title_x = title_x
        if self.changed:
            self.draw_changed_banner()

    def set_changed(self):
        if not self.changed:
            self.changed = True
            self.draw_changed_banner()

    def reset_changed(self):
        if self.changed:
            self.changed = False
            self.draw_changed_banner(clear=True)

    def draw_changed_banner(self, clear=False):
        if clear:
            attr = tui_base.curses.A_INVIS
        else:
            attr = tui_base.curses.color_pair(0xb1)  # was 0xf1
        self.stdscr.addstr(0, 6, "Changed", attr)

    def execute(self, command):
        r'''Called for table_screen popup.

        Calls self.screen.table.execute if it does not recognize the command.
        '''
        trace(f"app.execute({command=})")
        if command in self.tables:
            trace("command is table, returning table_screen")
            return table_screen(self.tables[command], self.screen)
        match command:
            case 'Back':
                trace("app.execute: Back validating table")
                if self.screen.validate():
                    trace(f"app.execute: passed validate -> {self.screen.back=}")
                    return self.screen.back
                trace(f"app.execute: failed validate -> None")
                return None
            case 'Exit':
                trace(f"app.execute: Exit command -> 'APP_EXIT'")
                return 'APP_EXIT'
            case 'Abort':
                trace(f"app.execute: Abort command -> 'APP_ABORT'")
                return 'APP_ABORT'
        trace(f"app.execute({command=}): forwarding to screen")
        ans = self.screen.table.execute(self, command)
        trace(f"app.execute -> {ans}")
        return ans



if __name__ == "__main__":
    import database

    database.load_database()
    start(database.Tables)

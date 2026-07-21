# menu_screen.py

import math

from csv_app import action
from csv_app.trace import trace
from . import tui_base
from .field import field_shared, read_only_single_line, editable_single_shared


class action_field(read_only_single_line):
    def __init__(self, screen_key, action, field_shared, begin_y, attr_pair):
        super().__init__(screen_key, action.name, field_shared, begin_y, attr_pair=attr_pair)
        self.action = action

    def enclose(self, y, x):
        return y == self.begin_y and self.begin_x <= x < self.begin_x + len(self.text)


class action_shared(field_shared):
    r'''An app-defined member of the field_shared family: builds action_fields (action-backed, not
    column- or row-backed), so field_for takes an action + its runnability attr_pair.
    '''
    field_class = action_field

    def field_for(self, action, begin_y, screen_key, attr_pair):
        return self.field_class(screen_key, action, self, begin_y, attr_pair)


class menu_screen(tui_base.screen):
    active_field = None
    message = None          # general message, 2 lines ABOVE the question (show_message; unused for now)
    error_message = None    # validation error, 2 lines BELOW the question/answer (show_error)
    question = None
    answer = None
    answer_width = 12     # width of the ask_question answer field (it scrolls if the value is longer)
    error_pair = 0x01
    default_pair = 0x00

    task_pair     = 0x0   # standard white on black
    cant_run_pair = 0x10  # red text
    may_run_pair  = 0x30  # yellow text
    must_run_pair = 0x20  # green text
    help_lines = [        # F1 help (base screen.show_help renders it)
        "Up/Down, BTab/Tab .. select the previous / next action",
        "Enter / Space ...... run the selected action",
        "click .............. run an action",
        "r .................. reset all actions",
        "Esc ................ dismiss a question prompt",
        "F8 ................. back",
        "F12 ................ exit the app",
        "F1 ................. this help",
    ]

    def __init__(self, actions, title="Menu", back=None):
        super().__init__(title, back)
        self.actions = actions
        self.widths = [[0, 0, 0]]   # list of [max_task_number_len, max_step_number_len, max_name_len], one per column
        self.num_columns = 1
        for a in self.actions.values():
            if a.column_break:
                self.num_columns += 1
                self.widths.append([0, 0, 0])
            if a.task is None:
                if len(a.number) > self.widths[self.num_columns - 1][0]:
                    self.widths[self.num_columns - 1][0] = len(a.number)
            else:
                if len(a.number) > self.widths[self.num_columns - 1][1]:
                    self.widths[self.num_columns - 1][1] = len(a.number)
            if len(a.name) > self.widths[self.num_columns - 1][2]:
                self.widths[self.num_columns - 1][2] = len(a.name)
        self.col_widths = [task_num_width + step_num_width + name_width + 2
                           for task_num_width, step_num_width, name_width in self.widths]

    def init(self):
        curses = tui_base.curses
        trace(f"menu_screen.init({self.title}) {self.num_columns=}, {self.widths=}, {self.col_widths=}")
        trace(f"    {hex(curses.color_pair(0x01))=}, {hex(curses.A_REVERSE)=}")
        for a in self.actions.values():
            a.app_is(self.app)

    def process_mouse(self, mouse_event):
        result = super().process_mouse(mouse_event)   # popup routing first
        if tui_base.event_handled(result):
            return result
        _, x, y, _, bstate = mouse_event
        trace(f"menu_screen.process_mouse({y=}, {x=}, bstate={tui_base.bstate_str(bstate)})")

        if self.answer is not None and self.answer.enclose(y, x):
            return self.answer.process_mouse(mouse_event)

        # where am I?
        for index in range(len(self.fields)):
            field = self.fields[index]
            if field.enclose(y, x):
                break
        else:
            return mouse_event

        trace(f"menu_screen.process_mouse({y=}, {x=}) in field {index=}, {field.name=}")
        match bstate:
            # UI line 45: a single LEFT CLICK runs the action (== keyboard Enter); accept a
            # click-resolution DOUBLE_CLICK the same way so a fast double still runs it once.
            case tui_base.curses.BUTTON1_CLICKED | tui_base.curses.BUTTON1_DOUBLE_CLICKED \
                    if field.action.can_run:
                self.activate_field(field)
                self.clear_message()
                return self.execute(field.action)
        return mouse_event

    def process_key(self, key):
        trace(f"menu_screen.process_key({key=}) {self.active_field=}")
        key = super().process_key(key)          # popup routing (Esc closes a popup first) + F8/F1
        if tui_base.event_handled(key):
            return key
        if key == '\x1B' and self.answer is not None:   # Esc: two-stage (matches table/row)
            if self.error_message is not None:
                trace("menu_screen.process_key: Esc -> dismiss error (keep question)")
                self.clear_error()              # first Esc: dismiss the error, keep the prompt + entry
            else:
                trace("menu_screen.process_key: Esc -> dismiss question")
                self.clear_question()           # second Esc (no error): bail out of the question
            return None
        if self.answer is not None:
            ans = self.answer.process_key(key)
            if tui_base.event_handled(ans):
                return ans
        if key == 'KEY_DOWN' or key == '\t':    # Tab moves to the next action (like Down)
            if self.active_field is None:
                offset = 0
            else:
                offset = self.active_field.screen_key + 1
            for i in range(len(self.fields)):
                field_index = (offset + i) % len(self.fields)
                if self.fields[field_index].action.can_run:
                    self.activate_field(self.fields[field_index])
                    self.clear_message()
                    return None
        elif key == 'KEY_UP' or key == 'KEY_BTAB':   # Shift-Tab moves to the previous action (like Up)
            if self.active_field is None:
                offset = len(self.fields) - 1
            else:
                offset = self.active_field.screen_key - 1
            for i in range(len(self.fields)):
                field_index = (offset - i) % len(self.fields)
                if self.fields[field_index].action.can_run:
                    self.activate_field(self.fields[field_index])
                    self.clear_message()
                    return None
        elif key == 'KEY_ENTER' or key == '\n' or key == ' ':
            if self.active_field is not None:
                self.clear_message()
                return self.execute(self.active_field.action)
        elif key == 'r':
            self.clear_message()
            action.reset()
            return 'REFRESH'
        return key                              # not handled here -> bubble up

    def execute(self, action):
        if action == 'Back':                    # F8 from the base screen (execute is otherwise
            return self.back                    # action-based, so it can't go through the command chain)
        trace(f"menu_screen.execute({action.name=})")
        ans = action.execute(self)
        trace(f"menu_screen.execute -> {ans}")
        return ans

    def draw_body(self):
        trace(f"draw_body(): {self.num_columns=}, {self.col_widths=}, {self.widths=}")
        fill = self.cols - sum(self.col_widths)
        gap = fill // ((self.num_columns - 1) + 4)
        self.begin_x = [gap * 2]
        for width in self.col_widths[:-1]:
            self.begin_x.append(self.begin_x[-1] + width + gap)
        trace(f"draw_body(): {fill=}, {gap=}, {self.begin_x=}")
        self.fields = []
        column = 1
        x = self.begin_x[column - 1]
        begin_y = 2
        lineno = begin_y
        self.max_y = 0
        last_y = []   # per column
        widths = self.widths[column - 1]
        for action in self.actions.values():
            if action.column_break:
                if lineno > self.max_y:
                    self.max_y = lineno
                last_y.append(lineno)
                column += 1
                lineno = begin_y
                x = self.begin_x[column - 1]
                widths = self.widths[column - 1]
            nlines = 1
           #trace(f"{action.name=}, {action.number=}, {action.can_run=}, {action.step.state=}, "
           #      f"{nlines=} at {lineno=}, {x=}, {widths=}")
            w = widths[0]
            if action.task is not None:
                w += 1 + widths[1]
            self.app.stdscr.addstr(lineno, x + w - len(action.number), f"{action.number}")
            shared = action_shared(action.name, nlines, x + w + 1, widths[2], self.app)
            if action.is_task:
                attr_pair = self.task_pair
            elif not action.can_run:
                attr_pair = self.cant_run_pair
            elif action.has_run:
                attr_pair = self.may_run_pair
            else:
                attr_pair = self.must_run_pair
            self.fields.append(shared.field_for(action, begin_y=lineno,
                                                screen_key=len(self.fields), attr_pair=attr_pair))
            lineno += nlines
        if lineno > self.max_y:
            self.max_y = lineno
        last_y.append(lineno)
        trace(f"{self.max_y=}, {last_y=}")
        self.active_field = None

        # write legend:
        if column == 1:
            # place legend to the lower right of column
            x += self.col_widths[0]
            x += (self.cols - x - 9) // 3
            y = self.max_y - 5
        else:
            # place legend under last column
            x += widths[0] + 1 + widths[1] + 1
            if last_y[-1] + 7 <= self.max_y:
                y = self.max_y - 5
            else:
                y = last_y[-1] + 1
                self.max_y = y + 5
        curses = tui_base.curses
        self.app.stdscr.addstr(y, x, "Legend:", curses.A_UNDERLINE)
        self.app.stdscr.addstr(y + 1, x, "task", curses.color_pair(self.task_pair))
        self.app.stdscr.addstr(y + 2, x, "must run", curses.color_pair(self.must_run_pair))
        self.app.stdscr.addstr(y + 3, x, "may rerun", curses.color_pair(self.may_run_pair))
        self.app.stdscr.addstr(y + 4, x, "can't run", curses.color_pair(self.cant_run_pair))

        # write message:
        if self.message is not None:
            self.show_message(self.message, self.message_attr)

        # write question:
        if self.question is not None:
            self._draw_question()
        if self.error_message is not None:      # validation error, 2 lines below the question/answer
            self.show_error(self.error_message)
        trace("draw_body done")
       #trace()

    def show_message(self, msg, attr):
        msg = msg[:self.cols - 1]            # clip to the line so a long message can't overflow
        x = max(0, (self.cols - len(msg)) // 2)  # center; never negative
        self.app.stdscr.addstr(self.max_y + 2, x, msg, attr)
        self.message = msg
        self.message_attr = attr

    def show_error(self, msg):
        r'''A validation error, drawn 2 lines BELOW the question/answer (show_message's slot is 2
        ABOVE, reserved for other messages).'''
        msg = msg[:self.cols - 1]               # clip to the line so a long error can't overflow
        x = max(0, (self.cols - len(msg)) // 2)  # center; never negative
        self.app.stdscr.addstr(self.max_y + 6, x, msg, tui_base.curses.color_pair(self.error_pair))
        self.error_message = msg

    def clear_error(self):
        if self.error_message is not None:
            x = max(0, (self.cols - len(self.error_message)) // 2)
            self.app.stdscr.addstr(self.max_y + 6, x, self.error_message, tui_base.curses.A_INVIS)
            self.error_message = None

    def clear_message(self):
        if self.message is not None:
            x = (self.cols - len(self.message)) // 2  # center message
            self.app.stdscr.addstr(self.max_y + 2, x, self.message, tui_base.curses.A_INVIS)
            self.message = None

    def activate_field(self, field):
        r'''The ask_question answer is NOT a menu action -- it manages its own cursor/selection and must
        never become self.active_field.  If it did, the FIRST arrow press would (through
        field.set_position -> activate_field) drop the running command's highlight AND re-select the
        answer, undoing the move -- so arrows only "took" on the second press.  Ignore the answer here;
        the running command stays highlighted while you answer.  Menu actions use the base behavior.
        '''
        if field is not self.answer:
            super().activate_field(field)

    def _question_xy(self):
        r'''(y, x) of the question label; the answer field sits at x + len(question) + 1.'''
        x = (self.cols - len(self.question) - self.answer_width - 1) // 2   # center question/response
        return self.max_y + 4, x

    def _draw_question(self):
        y, x = self._question_xy()
        self.app.stdscr.addstr(y, x, self.question)
        self.answer.paint()

    def ask_question(self, question, callback, default='', convert_fn=str):
        r'''Prompt for a value.  convert_fn turns the typed string into the value passed to `callback`
        (int, a date parser, ... ; str = free text), raising ValueError if the input is not valid.  The
        callback receives the CONVERTED value and may itself raise ValueError to reject it (a business
        rule); either way run_callback shows the message and keeps the prompt up for another try.
        '''
        trace(f"menu_screen.ask_question({question=!r}, {default=!r})")
        self.clear_question()
        self.question = question
        self.callback = callback
        y, x = self._question_xy()
        shared = editable_single_shared("answer", 1, x + len(question) + 1, self.answer_width, self.app,
                                        convert_fn=convert_fn,
                                       #alignment="right",
                                        left_placeholder="<", right_placeholder=">")
        self.answer = shared.edit_text(default, begin_y=y, screen_key=1, callback=self.run_callback)
        self._draw_question()
        self.answer.activate()          # select the whole default so the first keystroke replaces it

    def run_callback(self, s):
        trace(f"menu_screen.run_callback({s=!r})")
        self.clear_error()                      # clear any prior error before this attempt
        # 1) type/format check.  A bad value keeps THIS prompt up (not yet torn down).
        try:
            value = self.answer.convert()
        except ValueError as exc:
            trace(f"menu_screen.run_callback: convert failed: {exc}")
            self.show_error(str(exc))
            return None
        # 2) type-valid.  Tear down BEFORE the callback so a callback that chains to another question
        #    (its ask_question) leaves that one up.  Capture what we need to re-ask on a business error.
        question, callback = self.question, self.callback
        convert_fn = self.answer.field_shared.convert_fn
        self.clear_question()
        try:
            ans = callback(value)
        except ValueError as exc:
            trace(f"menu_screen.run_callback: callback rejected: {exc}")
            self.show_error(str(exc))
            self.ask_question(question, callback, s, convert_fn=convert_fn)   # re-ask with the entry
            return None
        trace(f"menu_screen.run_callback -> {ans}")
        return ans

    def clear_question(self):
        if self.question is not None:
            y, x = self._question_xy()
            self.app.stdscr.addstr(y, x, self.question, tui_base.curses.A_INVIS)
            self.app.stdscr.addstr(y, x + len(self.question) + 1, ' ' * self.answer_width)
            self.question = None
            self.answer = None
            self.callback = None


# CLAUDE-tasks.md

### purpose of this file ###

- This file is only intended to be read and responded to by claude.  If I say "you" here, it means claude.
  If you see anthing here that is incorrect, please let me know.  If I say "we" that means claude and myself.

- It is my understanding that each time I launch claude, it starts from scratch, as if that's the first time I've
  called it.  Hence the CLAUDE.md file containing your notes.  This file is similarly motivated as a place for
  my notes to you.  This may evolve somewhat over time.

- While this file may last for several months, I currently don't expect it to become a permanent part of the repo,
  and that it will eventually be deleted once it has served its purpose.

- You are invited to add your own comments here.  For example, to mark tasks as done so they don't need to be
  considered each time claude is started.  Also to record answers to my questions, both for you to know you
  don't need to research them again, and for me to be able to refer back to.

  - Perhaps you could add your comments, indented under what I said that prompted them, starting with "claude:".

- A question mark indicates a question that I would like you to answer.  Please include your answer in this file.

- Does this seem reasonable?  Do you have any suggestions, other than what I've said here, for how we should
  do this?

  - claude: Yes, very reasonable, and it matches how I actually work: I start each session from scratch, so the
    split of "CLAUDE.md = durable facts about how the code works" and "this file = your intent, decisions, open
    questions, and task state" is exactly right.  Suggestions:
    - When something here becomes a settled, durable fact (e.g. a finalized navigation scheme), promote a short
      summary into CLAUDE.md and mark the item done here.  That keeps this file about *intent/status* and CLAUDE.md
      about *how things are*, so neither grows stale.
    - I'll prefix my additions with "claude:" and indent under the point that prompted them, as you asked.  For
      substantive answers I may write a small block so it reads cleanly.
    - Consider a tiny "open questions" / "decisions" list at the top later, if prose starts hiding the live items.
    - FYI this file is currently untracked in git, so it only exists in this machine's working tree.  That's fine
      given it's temporary, but it won't be backed up by commits until (if) you add it.

### development overview ###

- There are 4 repos under rpi-zero-home.  Anything else there should be ignored.

  - csv-app:

    - a .csv based data storage library.  Stores multiple tables in one .csv file to achieve atomic updates.
    
    - it is OK to add code to csv-app to play nicely with tui-app, but would be nice not to require all apps
      using csv-app to use tui-app.

    - this library is largely done with a broad test suite.  But as tui-app evolves, it may place additional
      requirements on csv-app to continue to play nicely with tui-app.
   
  - tui-app:

    - a library for a generic TUI app with table/row/menu screens.  Designed to play nicely with csv-app, but would
      nice not to require it (see below).

    - the comments in CLAUDE.md describe this pretty well.

    - this still has work to be done, and what I will have claude primarily focus on.

  - csv-inv-order:

    - an app built on both tui-app and csv-app to handle inventory/ordering for our monthly Men's Club
      breakfasts.  These only run Nov-Apr, and not during the summer time.  So now is a good time for
      development on all of these libraries.

    - this started out as a CLI app, with different CLI commands for each step in the inventory/ordering
      process.  There was no tui-app library.

    - during this summer, I'm developing the tui-app and adding it to this app.

    - I plan to run this app on a rpi zero 2 W running in my house.  Users from the Men's Club will ssh into
      this computer from their homes to run it.  This lets me keep the code up to date, and also have access to the
      app in case problems are reported.  It also allows more than one user to use the same code (i.e. the same
      database).

    - I started with the table and row screens, thinking that would be enough.  But it seemed like it would 
      nice to have a menu screen that guides the user through the several steps during each monthly cycle.  So I've
      been working to add the menu screen to tui-app.

  - csv-beans:
   
    - a second app for the Men's Club treasurer.  This was initially set up in the same way as csv-inv-order, on top
      of csv-app with CLI commands for the various steps.  The primary activity in the Men's Club is the monthly
      breakfast, so the steps for the treasurer interleave with the steps for csv-inv-order, though run by different
      people.

    - Since I'm the treasurer, this doesn't need to be as polished.  I plan to eventually add a TUI interface to it,
      but that work hasn't started yet, and won't start until the csv-inv-order move to TUI is completed.

- Simple.  I'm the only developer on all of this.  I'm retired, so have extra time; but don't want this being a
  full-time permanent job.  So I'm trying to keep everything as simple as possible.  Also trying to build libraries
  that can be reused for other apps, possibly for other clubs in the park (Mobile Home Park).  Each user probably
  uses their app about 6 times per month during the 6 month active period.  So it's OK if it takes a few more
  keystrokes to get something done.

- I'd like to get these stable where they require very little maintenance.  The very little maintenance goal is
  higher priority than user friendliness, or "sex appeal".

- I don't see any slow-down leaving the trace on all of the time, so plan to do that to help debug reported
  problems.  But I have a concern that the user will have a problem; then re-run the app, thus destroying the
  trace.txt file before reporting the problem.  So it might be nice to keep a few generations of the file.

- FYI: I'm pretty sure that popup_menus are only currently used on the table_screen.  I don't have any plans
  use them anywhere else.

  - claude: Confirmed -- popup_menu is instantiated only in table_screen.py (the row popup and the screen popup);
    popup_message is also only used there (the Error box).  Nowhere else across tui-app, csv-inv-order, or csv-app.

### testing ###

- I am curious how testing would work with your involvement in the project.

  - Do you have the ability to spot errors, thus rendering a test harness obsolete?  Or do you make mistakes that
    are only exposed through running the code (testing)?

    - claude: Honest answer: both, but I do NOT make a test harness obsolete.  By reading code I catch a lot
      (type mismatches, off-by-one, contract violations, dead branches, wrong sentinels), which reduces how many
      bugs reach testing.  But I regularly make mistakes that only surface at runtime -- especially here, where the
      subtle parts are curses screen state, the wrap()/index math in field.py, and event dispatch that a static
      read can't fully verify.  So my plan:
      - Keep the pytest suite; it's cheap (1.78s) and pins exactly the field/wrap logic that's easiest to break.
      - When I change that logic I'll add/extend tests and run them on the Pi
        (ssh rpi-zero-2-w 'source ~/csv-venv/bin/activate && cd ~/tui-app && pytest -q') before claiming done.
      - For curses-interactive behavior that's hard to unit-test, trace.txt is the substitute for a harness -- I
        read it to confirm what actually happened at runtime rather than assuming.
      Treat me as a fast but fallible collaborator: I lower the bug count, I don't remove the need to test.

### first task: table_screen navigation ###

- I'm not happy with the current navigation on the screens.  This doesn't have to be excellent, but it's pretty
  klunky right now.  The performance is great, just what keys/mouse events are needed for the user to get his
  job done.

- I would like claude to start with the navigation on table_screen. I've been going back and forth on whether to
  support direct editing of individual row/columns (cells) on this screen.  It is currently creating 
  editable_fields, but not forwarding key/mouse events to them.  Also need a plan on how these updates would take
  place.

  - Currently draw_rows creates a list of self.fields for each row, and then abandons it.

    - claude: Confirmed, and slightly worse than "abandons": `self.fields = []` is reset *inside* the per-row loop,
      so after draw_rows returns, self.fields holds only the LAST drawn row's fields.  The only current use is
      `self.fields[0].reverse_attr()` for the selected-row highlight.  Also confirmed: table_screen creates
      editable_fields for can_edit columns but never forwards key/mouse events to them.  Your proposed shape -- a
      list (per visible row) of lists of editable_fields, updated (not wholesale replaced) by draw_rows -- is the
      right structure for in-place cell editing.

    - It is sometimes called just to redraw a few rows for scrolling.

    - To support simple editing on the table_screen (without creating a row_screen), the fields for all visible
      rows would have to be kept, and process_mouse/process_key would have to forward events to the current field.

    - draw_rows would then update this, but not replace it since it doesn't always draw all of the rows.

  - One thing to consider is that the rows generally have some "calculated" columns.  These are displayed (as
    read-only) by the current table_screen.  But when the user updates column A, that may cause a change in
    calculated column C.  This change won't be seen until the row gets updated and re-drawn.

    - Does this update/redraw happen for each field that is changed?  I think so, because I don't think there will
      be many cases where the user would update multiple columns for the same row.  Also, the curses performance has
      been very good.
    
    - But this shouldn't happen for every key-stroke.  How does the system know that the user is done editing that
      field?  User hits Enter.  User tabs to next/prior column/row.  Anything else?

    - I think it would be too confusing to allow a change on screen to be scrolled off screen without applying
      it.
      
      - Thus fields only need to be kept for visible rows.
        
        - We really only need to keep editable_fields.
          
          - the mouse event forwarding could key initially on y to the list of fields for that row, then go down
            that list to see which field (if any) encloses the mouse position.

            - Thus, the field list would be a list (one per row) of lists of fields.

  - I'd like the navigation to match, as much as practical, the other screens.

  - I'd like to add a "help" function (F1 key?) to each screen that describes the navigation (but not context
    dependent to, e.g., describe the current table being displayed).

    - Should be able to use the popup_message for this.

  - I'd like all screens to be usable without a mouse.  But also support a mouse to make it easier/faster.
    
    - So we need to develop two plans:

      - How the user accomplishes each task without a mouse.

      - How the user accomplishes each task with a mouse.

  - Steps:
    
    1.  Figure out navigation

    2.  Code/test navigation

    3.  Develop help menus

  - claude: proposed navigation design (2026-07-12) -- PENDING YOUR REVIEW

    - Two findings first:

      - table_screen.py does NOT currently compile: `case KET_BTAB:` (line 99) is a typo for `case 'KEY_BTAB':`
        (missing quotes AND KET->KEY).  As written it's an undefined-name capture pattern, which is an illegal
        irrefutable pattern before `case _:` -> SyntaxError, so the module can't import.  The nav rework replaces
        this method, so it gets fixed then.

      - Decision taken: table_screen WILL support in-place cell editing (driven by your note: Inv_checklist and
        similar are 6-8 rows where you update 1-2 columns down the whole table; a form-per-row is too tedious).
        Full-row editing via row_screen is ALSO kept for big tables (Products, Items).

    - Unifying principle across all three screens:

      - Arrow keys move *focus* in the natural direction.

      - Tab / Shift-Tab move to the next / previous *editable/focusable* element (skips read-only/calculated).

      - Enter activates the focused element (drill-in / run / commit-and-advance).

      - Esc = Back (go to self.back), or close an open popup/question if one is up.

      - F1 = Help popup (popup_message listing that screen's keys).  Non-context (doesn't describe current data).

      - Mouse always optional: click = focus, double-click = activate, right-click = command popup, wheel = scroll.

      - "apply-on-done": leaving an editable cell/field by ANY means commits it first, so nothing dirty can be
        navigated (or scrolled) away unapplied.  This removes the "changed field scrolled off screen" problem.

    - menu_screen (closest to done -- use as the reference feel):

      - Keeps: Up/Down move among runnable actions (wrap); Enter/Space runs focused action; click/double-click.

      - ADD: Esc = Back; F1 = Help.  (Optional later: Left/Right to jump between menu columns.)

      - 'r' (reset) stays for now; per the dependencies section it should later move out of tui-app.

    - row_screen (the form):

      - Keeps: Tab/Shift-Tab between editable fields (wrap); arrows + editing keys operate within the active
        field; click field = focus/position; click button = run.

      - GAP being fixed: the command buttons (Cancel/Validate/Submit/Create) are currently MOUSE-ONLY.  Plan: put
        the buttons in the Tab order after the last field; Enter/Space runs the focused button.  Esc = Cancel (=
        Back).

      - ADD: F1 = Help.

      - R1 RESOLVED (2026-07-12): no data-entry column is multi-line (long lines wrap, but Enter is never entered
        as data), so Enter is free for navigation.  Decision: Enter = advance to next field.

    - table_screen (the big one):

      - Focus model: focus only ever lands on an EDITABLE cell.  Read-only and `calculated` columns are never
        focusable -- Tab/Shift-Tab skip them and Left/Right visit only editable cells.  So in a table with
        editable columns, focus = (focused row, focused editable column).  In a table with NO editable columns,
        focus is at the ROW level (a whole-row highlight); there is no cell focus.

      - Up/Down move the focused row (auto-scroll when focus reaches the top/bottom edge).  This REPLACES the
        current behavior where bare arrows scroll the viewport.  Left/Right move among editable cells in the row.

      - PgUp/PgDn/Home/End: scroll by page / jump to first/last (moving focus).  Mouse wheel: scroll viewport.

      - Editing: typing a printable char on an editable cell enters edit mode.  Commit happens on Enter,
        Tab/Shift-Tab, or an arrow that leaves the cell; Esc cancels the in-progress edit.  On commit: write to
        the row, recompute, and redraw that one row (so calculated columns like unit/pkg_size/totals refresh).

      - Enter semantics -- DECISION NEEDED (choose Model A or Model B):

        - Model A (my first proposal; you flagged it as confusing): Enter is dual-mode on a focused cell --
          NOT editing -> opens the whole row in row_screen; EDITING -> commits the cell and moves down.  The
          confusing part is that idle-Enter jumps to a different screen.

        - Model B (cleaner, recommended): Enter is ONLY about the focused cell -- it begins editing an editable
          cell, and while editing it commits + advances like TAB (to the next editable cell).  Opening the full
          row form is a SEPARATE gesture: double-click, or the row-menu key -> View/Edit.  So Enter never changes
          screens; it just enters/leaves cell-edit.  A read-only cell never has focus, so Enter is never pressed
          on one; in a fully read-only table (row-level focus, no editable cells) Enter acts like TAB and selects
          the next row (so you can then open the row-menu -> View to see fields that don't fit on table_screen).

      - T1 REVISED (2026-07-12): keyboard needs TWO menu-opening keys, mirroring the two right-click popups
        (you can't select the top 2 lines, so the screen menu can't just be "the menu for the focused row"):
        - screen menu (global: table names, Back, Exit/Abort -- today's right-click above row 2): F10.
        - row menu (context for the focused row: View/Edit, Delete, app row commands): F9.
        - T1b RESOLVED (2026-07-12): F10 = screen menu, F9 = row menu (confirmed).
        (Esc is taken by Back.)

      - Data structure: keep a per-visible-row list of that row's fields (a list-of-lists, `self.row_fields`), so
        process_key/process_mouse can route to the focused cell.  draw_rows UPDATES the affected entries on scroll
        rather than discarding the whole thing (today it resets self.fields inside the loop, so only the last
        row's fields survive).  Keeping all cells per row (not just editable) simplifies mouse hit-testing.

      - T2 (read-only tables): resolved by Model B above.  A read-only table gets row-level focus; Enter/Tab and
        arrows move the selection; you open a row via double-click, the View/Edit shortcut, or F9 -> View.

      - keyboard shortcuts (S1) -- RESOLVED (2026-07-12):
        - S1a: F2 = open the focused row in row_screen (the View/Edit command); same as double-click.  (F9's row
          menu also reaches View/Edit.)
        - DEL (KEY_DC) = Delete the focused row, WITH a per-row confirmation (two keystrokes per delete is
          accepted).  DEL pops a confirm ("Delete <human_key>? y/n"); y (or Enter/Yes) deletes the row and
          auto-advances the selection to the next row; n (or Esc) cancels.  So a bulk delete of adjacent rows is
          DEL,y,DEL,y,...  DEL is only active when NOT mid-edit (during a cell edit DEL deletes a character), and
          only fires if 'Delete' is in that row's commands.
          - impl note: reuse a popup for the confirm (popup_menu Yes/No, or a small y/n popup_message variant);
            decide during coding.

    - Suggested build order for Step 2 (code/test):

      1. Fix compile + switch table_screen to row-focus arrows (no editing yet); Esc=Back, F1 stub.  Verify on Pi.

      2. Add per-row field retention + mouse/key routing to the focused cell (still read-only).

      3. Add in-place editing + apply-on-done + calculated-column redraw.

      4. Bring row_screen buttons into the keyboard Tab order; add Esc=Cancel.

      5. Add Esc=Back + F1 to menu_screen.

      6. Step 3: write the per-screen help text and wire F1 -> popup_message.

    - Open decisions blocking coding: NONE remaining.  All resolved (2026-07-12): R1 (Enter=next field on
      row_screen), T1b (F10=screen menu, F9=row menu), T2 (read-only tables get row-level focus), Enter=Model B
      unified, S1a (F2=open row in row_screen), S1b (DEL=delete with y/n confirm + auto-advance).  Step 1 (figure
      out navigation) is DONE; next session starts on Step 2 build order (item 1: fix compile + row-focus arrows).

    - Step 2 implementation notes (from Bruce's Step 1 review, 2026-07-12):

      - Focus lifetime across redraws (refines point 3 -- Bruce's model, cleaner than claude's first take):

        - Retain field objects across scrolls; do NOT recreate the ones that stay on screen.  On scroll, shift
          begin_y on each retained field and create fresh fields ONLY for the newly-exposed rows.  insdelln
          already moved the existing glyphs AND their attributes, so still-visible rows need no re-paint.

        - Because the focused field object persists, it keeps its own position/selection, so its highlight is
          preserved (moved by insdelln; or re-applied by paint()->set_attrs() if we re-paint after setting
          begin_y).  So the screen does NOT need to store the edit position/selection -- the field owns it.

        - The screen DOES need to track which field currently has focus, purely to route keys to it.

        - If the focused field scrolls OFF-screen: first COMMIT its in-progress edit to the underlying row
          (apply-on-done), THEN drop focus -> revert to "no cell selected".

        - On a full draw() (resize): PREFER to retain focus.  The per-column geometry (begin_x, ncols, nlines) is
          data-driven, not screen-width-driven, so a pure resize does NOT change it -- if we redraw at the same
          scroll position we can re-paint the retained fields (paint()->set_attrs re-applies the highlight) and
          keep the in-progress edit UNCOMMITTED (postpone the row update).  Caveat: if a column's width or begin_x
          actually changed (because the underlying DATA changed between draws), the field object would need to be
          resized/repositioned, which it has no clean way to do today.  Bruce: if that proves hard, OK to PUNT
          (commit the edit, drop focus, recreate).

      - begin_y reassignment (point 4): begin_y is a plain attribute, read live by enclose/to_index/
        gen_locations/paint.  On scroll or row-delete, update begin_y on retained fields (rows below a deleted row
        shift up by 1).  Either assign begin_y directly or add a small field.move(new_y) helper.

      - Editable-cell width + overflow (point 5) -- two options, decide during coding:

        - (a) simplest / punt: NO horizontal scroll-during-edit on table_screen.  When a keystroke would push the
          text past the cell's room, IGNORE the char (optional terminal bell); for longer values use F2 ->
          row_screen.  Max editable length = ncols - 1 (the extra slot is the append cursor).

        - (b) better if cheap: implement the field.py paint() "# FIX: Recalculate scroll position" so the
          single-line cell scrolls horizontally during edit (the left/right [...] placeholders already exist for
          this).  Bruce: probably not much code, just needs thought -- if it cleanly solves the width limit,
          prefer (b) over (a).

        - Either way reserve ncols = (editable column width) + 1 so the append cursor is visible.

        - SUB-DECISION (W1), coding-time, not blocking (and less critical if (b) is done, since the cell can
          scroll): what sets an editable column's width?  It must be the max EXPECTED input width, NOT the current
          data width (else you can't type a value wider than existing data, e.g. the first 3-digit count when
          existing are 2-digit).  Proposal: ncols = max(data_width, column.edit_width) + 1; for columns with
          edit_width=None (num_pkgs/num_units) fall back to a sensible default (min_width, or data_width + a few).
          Note: row_screen also sizes from edit_width, so editable numeric columns probably ought to get an
          edit_width set in the app (csv-inv-order).

    - Step 2 coding progress -- cell-focus navigation for table_screen (started 2026-07-13):

      - Working rhythm: SMALL edits.  Each batch is either "foundational" (later batches build on it, so it
        is safe to accept even when partial) or a "stub to be replaced" (avoid writing those).  claude labels
        each batch as one or the other.  Accept a correct partial step (it gets extended later); reject only
        genuinely wrong edits.  (See the earlier discussion: the axis is build-on vs replace, not
        complete vs incomplete.)

      - Testing approach (decided 2026-07-13): reuse the test_field_interaction.py pattern -- `app` is a
        unittest.mock.Mock (so app.stdscr absorbs every draw call), monkeypatch only curses bits that need a
        live terminal (curses.color_pair -> identity; A_REVERSE etc. import fine cold), and mock any
        screen-reading method (the inch/chgat-based highlight) to assert its call args.  NO full curses-module
        mock is needed.  Tests live in tests/test_table_screen.py with FakeColumn/FakeTable fixtures and
        assert navigation STATE (cur_row/cur_col/first_row/row_fields), not pixels.  Tests are folded into
        each batch (can't write them all up front).  Run on the Pi:
          ssh rpi-zero-2-w 'source ~/csv-venv/bin/activate && cd ~/tui-app && pytest -q'

      - Data model the batches implement:
        - focus is a CELL = (cur_row, cur_col).  cur_col indexes self.columns, constrained to
          self.editable_cols; read-only/calculated columns are never focused.
        - row_fields: dict {abs_row_index -> [one field per column, in column order]} for on-screen rows.
          Column-parallel (includes read-only fields), so the focused field is row_fields[cur_row][cur_col],
          and the same structure serves mouse hit-testing.  draw_rows must redraw read-only fields too on
          scroll.
        - movement (wired in a later batch): Up/Down = same column, adjacent row (clamp, auto-scroll);
          Left/Right and Tab/Shift-Tab = prev/next editable column, wrapping to the adjacent row at the ends;
          PgUp/PgDn/Home/End = scroll the viewport (if focus scrolls off -> deselect; finalize-on-off comes
          with editing).  Esc = Back.  F1 = help (getkey returns 'KEY_F(1)', verified on the Pi).

      - Batches:
        - Batch 0 DONE (2026-07-13): fixed the compile break (case 'KEY_BTAB': -- was a bad `KET_BTAB`
          capture pattern that made table_screen.py fail to import).
        - Batch 1 DONE (2026-07-13, foundational): added focus state (cur_row/cur_col) in __init__ and
          self.editable_cols in init(); created tests/test_table_screen.py (fixtures + editable_cols test).
          Nothing consumes the new state yet.  Verified on the Pi: 161 passed.
        - Batch 2 DONE (2026-07-13, foundational): draw_rows builds self.row_fields
          ({abs_row_index -> [field per column]}, column-parallel), reset in draw_body, replacing the throwaway
          self.fields; removed dead begin_x; trace logs the keys.  Added test_row_fields_built (mirrors the real
          Column: FakeColumn.abbr defaults to name; FakeRow.get raises KeyError on unknown column).  Still
          behavior-neutral.  Verified on the Pi: 162 passed.
        - Batch 3 DONE (2026-07-13, foundational): scroll_up/scroll_down call _reindex_row_fields(), which
          shifts begin_y on retained fields to their new screen line and drops scrolled-off entries (a pure
          dict/attr update -- no screen reads -- safe on the live path); draw_rows adds newly-exposed rows.
          Added test_scroll_up_maintains_row_fields / test_scroll_down_maintains_row_fields (assert keys and
          begin_y).  Still behavior-neutral (nothing reads row_fields yet).  Verified on the Pi: 164 passed.
        - Batch 4a (cell-focus movement) STARTED then SET ASIDE (2026-07-13): while wiring the cell highlight
          it became clear the field/screen activate_field relationship should be refactored first, so the field
          stays uniform across ALL screens (table_screen now needs field editing too).  NO 4a code is in the tree
          (both attempts were rejected).  Resume 4a as FR-5 below.

    - Field / activate_field refactor (design 2026-07-13) -- do BEFORE resuming 4a:

      - Goal: one root activate_field usable by every screen; each field knows how to (un)highlight itself.

      - Decisions (all confirmed with Bruce):
        - Rename field.field_num -> field.screen_key: a screen-assigned identifier stored on the field (an int
          index for row_screen/menu_screen; a (row, col) tuple for table_screen).  Screens use it for navigation
          arithmetic.  Callers pass it positionally, so the rename is localized to field.py.
        - screen.activate_field(field) takes the FIELD OBJECT and stores it (self.active_field = field, the
          object, not a key).  set_position/set_selection call self.app.screen.activate_field(self).
          activate_field(None) just clears focus.  Guard `if self.active_field is field: return`, so the
          redundant calls the field makes while editing are no-ops and preserve the cursor.
        - activate/deactivate live on the FIELDS:
            read_only_field.activate() = self.reverse_attr();  deactivate() = self.reverse_attr()  (toggle)
            editable_field.activate()  = select-all (position=0, selection_len=len(get_text()), set_attrs());
              ALWAYS select-all on activate (re-entering a field re-selects the whole value -- deliberate uniform
              "focus selects all"); deactivate unchanged (set_attrs(reset=True)).
        - Root activate_field (tui_base.screen): guard; old.deactivate(); active_field=field; field.activate().
        - Because the fields own the highlight, BOTH row_screen and menu_screen DELETE their activate_field
          overrides and inherit the root one.
        - active_field is now the OBJECT, so row_screen/menu_screen navigation switches from index-based
          (self.fields[self.active_field]) to object-based (self.active_field.process_key / .action), and derives
          the index for Tab/Up/Down arithmetic from self.active_field.screen_key.  menu action fields must be
          given screen_key = their index (today created with screen_key=None).

      - Ripples / risk: row_screen Tab now select-alls the value (was cursor-at-start).  row_screen and
        menu_screen have NO unit tests and this changes their guts -- add tests AND drive csv-inv-order on the Pi.

      - Not fixing now: the menu question/answer editable field routes through the unified path too; that feature
        is already rough and gets its own cleanup later.

      - Batches:
        - FR-1: field.py -- rename field_num->screen_key; add activate/deactivate to read_only_field and
          editable_field; set_position/set_selection -> activate_field(self).
        - FR-2: tui_base.screen -- unified activate_field(field) (+ active_field=None class attr).
        - FR-3: row_screen -- delete its activate_field; nav/routing -> object + screen_key; add test_row_screen.py.
        - FR-4: menu_screen -- delete its activate_field; action fields get screen_key; nav/routing -> object.
        - FR-5: resume Batch 4a -- table_screen cell focus via activate_field(field), screen_key=(row, col),
          read-only-table row focus = activate_field(row_fields[row][0]).  Then 4b (Left/Right, Tab), 4c (Esc,
          F1), then F9/F10/F2/DEL, then in-place editing (item 3).

### dependencies ###

- it would nice, though not absolutely necessary, to remove tui-app's dependencies on csv-app.

  - perhaps use python's logging library, rather than trace?
    
    - I'm not that fond of this library.  It used to be the only option available.  Is that still true?  Or is there
      some other logging library/tool that could be used?

      - claude: stdlib `logging` is no longer the only option -- `loguru` and `structlog` are popular -- but both
        would ADD a third-party dependency, which is the opposite of your goal, so I wouldn't use them here.  Two
        clean ways to drop the csv_app.trace dependency without adding one:
          1. Give tui-app its own tiny trace module (~10 lines, identical `trace(*objects, ...)` API to
             csv_app.trace).  Zero ceremony, and none of the existing `trace(...)` call sites change.
          2. Use stdlib `logging` with a `RotatingFileHandler`.  Slightly more setup, but it directly solves your
             "keep a few generations of trace.txt" concern above (so a user re-running the app doesn't destroy the
             evidence before reporting): it auto-rotates trace.txt -> trace.txt.1 -> ... on size or on each run.
        Recommendation: option 2, precisely because one stdlib tool solves BOTH the decoupling and the generations
        problem.  Keep a thin `trace(*args)` wrapper over the logger so the call sites stay unchanged.  If you'd
        rather stay dead-simple, option 1 plus a few lines of "rename trace.txt.N on startup" also works.

  - I'm not sure why menu_screen imports csv-app.action.  Does some of the code in csv-app.action need to lifted to
    tui-app?

    - claude: I checked.  menu_screen has exactly ONE hard dependency on csv_app.action: the module-level call
      `action.reset()` in the 'r' key handler (menu_screen.py:123), which resets all actions when a new month
      starts.  Everything else it touches on actions (.name, .number, .can_run, .is_task, .has_run, .task,
      .column_break, .execute(screen), .app_is(app)) is duck-typed on the action objects YOU pass in via
      menu_screen(action.Actions, ...), so it needs no import.
      So the fix is the reverse of "lifting code into tui-app" -- push that one call OUT.  Options:
        - give the actions collection a duck-typed .reset() method and call self.actions.reset(); or
        - pass a reset callback into menu_screen; or
        - let 'r' bubble up as a command for the app/consumer to handle.
      No csv_app code needs to move into tui-app; deleting that single coupling line removes the dependency.  The
      broader Action/Task/Step model in csv_app.action is app-specific and rightly stays in csv-app / the consumer.

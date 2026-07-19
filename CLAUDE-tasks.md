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
        - FR-1 DONE (2026-07-13): field.py -- renamed field_num->screen_key; added activate/deactivate to
          read_only_field (reverse_attr) and editable_field (select-all); set_position/set_selection now call
          activate_field(self).  Added test_editable_activate_selects_all / test_read_only_activate_deactivate_
          toggle.  Full suite 166 on the Pi.
          CAVEAT: field->screen contract is now mid-change -- the field passes the OBJECT to activate_field, but
          row_screen/menu_screen still expect an index until FR-3/FR-4.  Unit tests pass (Mock app), but DO NOT
          run csv-inv-order until FR-4 is done, or row/menu editing will break.
        - FR-2 DONE (2026-07-13): tui_base.screen -- added active_field=None class attr and the unified
          activate_field(field) (guard same-field; deactivate old; activate new; accepts None to clear).  Added
          tests/test_screen.py (Mock fields).  Full suite 167 on the Pi.
        - FR-3 DONE (2026-07-13): row_screen -- deleted its activate_field (inherits base); routing now
          self.active_field.process_key(...); Tab/Shift-Tab use self.active_field.screen_key for the index and
          pass the field object to activate_field.  Added tests/test_row_screen.py (Mock fields).  Full suite 170
          on the Pi.  (row_screen Tab now select-alls the value -- confirm feel when running on the Pi post-FR-4.)
        - FR-4 DONE (2026-07-13): menu_screen -- deleted its activate_field (inherits base); action_field takes a
          screen_key and draw_body passes the index; process_mouse/process_key use the field object and
          self.active_field.screen_key for arithmetic.  Added tests/test_menu_screen.py.  Full suite 172 on Pi.
          NOTE: field_num is now fully gone (renamed screen_key everywhere).  The FR-1..FR-4 refactor is COMPLETE
          and the field->screen contract is consistent again.  VALIDATED: Bruce ran csv-inv-order on the Pi
          after FR-4 -- menu nav and the row form looked OK (no re-verify needed before FR-5).  The menu
          question/answer editable field still routes through the unified path and remains rough (cleanup later).
        - FR-5 = resume Batch 4a (table_screen cell focus, using the refactored activate_field).  DECISION:
          retired cur_row/cur_col; focus is the base self.active_field, and the focused cell is
          active_field.screen_key == (row, col).  Sub-batches:
          - 4a-1 DONE (2026-07-15): draw_rows gives each cell screen_key=(row,col); _focus_cell(row,col) ->
            activate_field(row_fields[row][col]) (read-only table uses col 0); draw_body drops focus on a full
            redraw; _reindex_row_fields drops focus when the focused row scrolls off; removed cur_row/cur_col.
            Tests added (screen_key, _focus_cell, focus-drop on scroll-off/redraw).  Full suite 176 on the Pi.
            NOTE: selected_row still present (dormant); retired in 4a-2 with the process_key rewrite.
          - 4a-2 DONE (2026-07-15): rewrote process_key -- Up/Down call _move_focus_row (same column,
            auto-scroll via _ensure_visible); first keypress focuses the top visible row's first editable column
            (read-only table -> col 0, via _default_col).  PgUp/PgDn/Home/End still scroll.  Retired selected_row
            entirely (removed from __init__, draw_rows highlight, and scroll null logic).  Tests added; full suite
            180.  FIRST VISIBLE BEHAVIOR CHANGE -- worth running csv-inv-order on the Pi (arrows now move a
            highlighted cell; Left/Right not wired until 4a-3, so you can only move within one column so far).
          - 4a-2b DONE (2026-07-15): RIGHT-ALIGN HIGHLIGHT BUG (field.py) -- found on the Pi after 4a-2.
            Symptom: focusing a right-aligned cell highlights the LEFT padding, not the text.
            Root cause: field.py's index->screen-x mapping (gen_locations, and also get_col/to_index) computes
            x = begin_x + (index - start), which assumes text starts at begin_x -- true for left alignment.  But
            align() right-justifies by PREPENDING pad = ncols - len(content) spaces, so the text actually starts
            at begin_x + pad; the mapping omits pad.  Pre-existing bug, exposed by 4a-2 (right-aligned columns are
            now focus-highlighted; row_screen fields are all left-aligned, so it never showed before).
            Fix approach = (b) EXACT (Bruce's choice): align()/wrap() expose the per-line pad; the field records
            self.pads[] and adds it in gen_locations/get_col/to_index.  (NOT the (a) leading-space heuristic.)
            Sub-steps:
              - Step 1: align() returns (pad, padded_line); wrap() yields (start, pad, line) triples;
                blank_lines() yields (None, 0, spaces); update the test_field_shared wrap tests to 3-tuples.
                Pure logic -- verify wrap tests green.
              - Step 2: paint() records self.pads[] parallel to self.starts[]; gen_locations adds self.pads[lineno]
                to x (fixes the visible highlight).  Add a right-align highlight test; verify on the Pi.
              - Step 3: get_col()/to_index() add the pad too, so right-aligned click-to-position and
                up/down-in-field stay consistent (not exercised until editing, but keeps the core correct).
            Edge case noted: empty right-aligned cell -> pad recorded as 0 (cursor shows at the left edge); rare,
            refine later if it matters.
            STATUS: all 3 steps done -- align()/wrap() yield pad; field records self.pads[]; gen_locations,
            get_col, and to_index add it; read_only_field.__init__ defaults pads=[0]*nlines so paint=False tests
            work.  Tests updated (wrap 3-tuples, align tuple) and added (right-align gen_locations/to_index/
            get_col).  Full suite 183 on the Pi.  VERIFIED on the Pi: right-aligned highlight now lands on the
            text.

          - 4a-3 DONE (2026-07-15): _move_focus_col(delta) + process_key Left/Right and Tab/Shift-Tab move among
            editable columns (via editable_cols), wrapping to the adjacent row's last/first editable col at the
            ends; no-op in read-only tables; no move at the very first/last editable cell.  Tests added; full
            suite 188.  Behavioral -- worth a Pi run (Left/Right/Tab now reach all editable columns).
            Refinement (2026-07-15): direction-aware first keypress when nothing is selected --
            Down -> top visible row, Up -> bottom visible row; Right -> first editable col, Left -> right-most
            editable col.  (bottom = bottom VISIBLE row.)  Full suite 191.  VERIFIED on the Pi.
          - 4a-4 DONE (2026-07-15): process_key Esc -> Back (self.execute('Back')); F1 -> show_help(), a
            popup_message titled "Navigation" listing the implemented keys (arrows, Tab/Shift-Tab, PgUp/PgDn,
            Home/End, Esc, F1).  (Esc closes an open popup first, via the existing popup.process_key path.)
            Tests added; full suite 193.
          BATCH 4a COMPLETE (cell-focus navigation): 4a-1..4a-4 + the 4a-2b field right-align fix.  Mouse events
          for the help/nav to be added later.

          - NEXT (per Bruce, start here next session): F9/F10 MENUS.  These open, from the keyboard, the SAME two
            popups that right-click already builds in table_screen.process_mouse:
              F10 = screen menu (screen_popup_commands: table names, Back, Exit/Abort) -- the popup made at y<2.
              F9  = row menu for the FOCUSED row (row.row_popup_commands: View/Edit, Delete, app cmds) -- the
                    per-row popup.  Needs a focused row: use self.active_field.screen_key[0]; if nothing focused,
                    either no-op or focus first visible row first (decide then).
            So this is mostly wiring two process_key cases to the existing popup_menu construction (factor the
            popup-building out of process_mouse so key + mouse share it).  Then F2 open row / DEL delete, then
            in-place editing (item 3).

### field_shared-factory + field-class refactor (COMPLETE + Pi-verified 2026-07-18) ###

- STATUS: migration steps 1-4 all done and Pi-verified.  NEXT TASK = F9/F10 menus (see the table_screen
  navigation section above: "NEXT (per Bruce, start here next session): F9/F10 MENUS").  The design below is
  retained as the record of what was built.

- Origin: the paint() "# FIX: Recalculate scroll position" (self.scroll is set to 0 and NEVER recalculated, so
  "scroll long lines to fit" is unimplemented -- the wrap/gen_locations/to_index plumbing exists but nothing
  drives self.scroll).  Fixing it grew into a field.py refactor, which grew (2026-07-18) into a redesign of the
  field_shared vs field split.  claude: this section supersedes the old "field scroll + field-class refactor
  (DESIGN IN PROGRESS 2026-07-17)" section.

- OVERARCHING DECISION (2026-07-18): field_shared becomes a FAMILY of small FACTORY classes.  It, not the screen,
  owns the decision of which concrete field class to build.  A screen configures one field_shared per column and
  then just asks it for fields; it never names a field class.  This is the frame into which the MI/method-placement
  question plugs (see "field-class internals" below) -- and that internals question is now DEFERRED because it is
  fully hidden behind the factory.

  - Why a FAMILY (not one field_shared with a `_make` switch on flags): Bruce's call.  A family of thin subclasses
    that parallel the field classes is closed-to-modification / open-to-extension -- adding a field kind = adding a
    subclass, no central switch to edit.  It also lets apps define their OWN weird field kinds (menu_screen's
    action field) as first-class members instead of core hacks.  The `layout=` and `editable=` flags dissolve into
    the class choice.

  - The family:
      field_shared                 # base: geometry (begin_x, ncols, nlines, alignment), app, trace_name,
                                   #   validate_fn, AND the factory methods.  field_class = None.
      read_only_single_shared      # field_class = read_only_single_line
      editable_single_shared       # field_class = editable_single_line
      read_only_multi_shared       # field_class = read_only_multi_line
      editable_multi_shared        # field_class = editable_multi_line
    Each subclass is ~one line (just sets field_class); the base news up self.field_class(...).  App-defined kinds
    (menu action) subclass field_shared in the APP module (see below), so core never learns about them.

  - Three ways a field_shared makes a field (all new up self.field_class):
      field_for(row, begin_y, screen_key)          -> text = row.get(column.name); attr_pair from
                                                       column.column_attr_pair(row).  Column-backed (table, row).
      edit_text(text, begin_y, screen_key, cb=None)-> seed from an exact string; isolated (menu ask_question).
                                                       validate comes from field_shared.validate_fn (no column).
      from_field(old, begin_y, screen_key)         -> rebuild at new geometry PRESERVING the in-progress edit
                                                       (see REFRESH below).  Distinct intent from edit_text.

  - Caller's choice lives in TWO convenience pickers (written ONCE, not duplicated per screen); weird kinds skip
    them and instantiate their subclass directly:
      single_line_shared(column, begin_x, ncols, app):
          editable_single_shared if column.can_edit else read_only_single_shared
      multi_line_shared(column, begin_x, ncols, app, *, creating):
          editable = (not column.calculated) if creating else column.can_edit   # == today's row_screen.py:239
          editable_multi_shared if editable else read_only_multi_shared
    The per-column editable branch thus runs ONCE PER COLUMN at draw_body time (was per-cell in draw_rows).

  - Per-screen usage after:
      table_screen: single_line_shared(column, ...) per column in draw_body; draw_rows just does
                    shared.field_for(row, begin_y=lineno, screen_key=(row_index, col)) -- the can_edit branch is
                    GONE from draw_rows.
      row_screen:   multi_line_shared(column, ..., creating=self.table is not None) per column;
                    shared.field_for(self.row, ...).  (self.table is not None IS the create-vs-update flag:
                    init_table sets it, init_row does not.)
      menu_screen:  defines its OWN action_shared(field_shared) in menu_screen.py with field_class = action_field
                    and an overridden field_for(action, ...) (action-backed, not row-backed).  action_field stops
                    being an odd-one-out; it is an app-defined family member.
      ask_question: an editable_single_shared with column=None and an explicit validate_fn + trace_name="answer";
                    self.answer = shared.edit_text(default, ..., cb=self.run_callback).

  - display_name is NOT needed on the field: field.name is used ONLY for trace strings; the screen draws the
    column header row itself (table_screen.py:300-308).  So field.name derives from a trace_name (= column.name,
    or "answer" for the isolated case).  No display_name plumbing.

- SCROLL / MULTI-LINE-GROWTH design (2026-07-18, replaces the old "two scroll techniques" plan):
  - SINGLE-LINE (table_screen) KEEPS horizontal column (char) scroll.  Settled formula:
      scroll = clamp(position - int(ncols * X_single), 0, upper)
      upper  = max(0, len(text) - ncols + (1 if position >= len(text) else 0))   # +1 only for append cursor
    X_single ~= 0.6, a class variable.  Upper clamp gives "don't scroll if it fits" (upper 0) and no right-gap;
    the +1 keeps the append position visible.  [<]/[>] horizontal placeholders stay for single-line only.
  - MULTI-LINE (row_screen) DOES NOT SCROLL.  Instead it GROWS line count: when a keystroke needs more than
    nlines wrapped lines, the field bumps its field_shared.nlines += 1 and returns 'REFRESH'; draw() re-lays-out
    the column stack (grown field pushes fields/buttons below it down) and repaints.  Consequences:
      - drops the `* 1.2` over-allocation (row_screen.py:235) and the multi-line placeholder question (none).
      - RETIRES the old MULTI-LINE line-scroll plan AND the W1 "+1 reserved column" hack.
      - nlines is LEFT TALL until you leave the field (no shrink-REFRESH; fewer redraws / no flicker).
    (Single-line scroll still RETIRES W1 for table via horizontal scroll.)
  - REFRESH text-source problem + fix (the crux):
      In row_screen, in-progress edits live ONLY in the field (field.text / field.changed); they reach self.row
      only via update() (row_screen.py:195-202) at validate/submit, and update() CLEARS field.changed (which
      validate() relies on to build attrs_changed).  So we canNOT call update() before REFRESH, and a naive
      field_for(self.row) on REFRESH would pull the STALE row value and lose the edit.
      FIX = from_field(old, begin_y, screen_key): rebuild the edited field carrying over text, changed (CRUCIAL --
      else the column drops out of the submit set), position, selection_len; paint() with the grown nlines.
      draw_body on REFRESH: for each column, if a prior field exists AND is .changed -> shared.from_field(prior,...)
      else shared.field_for(self.row, ...); then re-activate the field whose screen_key matches the old active
      field.  Because changed+text+name are preserved, the EXISTING validate()/update() submit path is unchanged
      (it never learns a REFRESH happened).  This preserves EVERY in-progress edit, not just the active one.
      Alternative held in reserve (Bruce agnostic): RETAIN the field objects and shift begin_y (the
      _reindex_row_fields trick), repainting from the grown field down -- fewer redraws, no state copy, but a more
      surgical draw_body.  Growth is rare, so start with from_field (keeps draw_body's simple rebuild).

- FIELD-CLASS INTERNALS (how field_class is implemented) -- DECISION DEFERRED, now hidden behind the factory:
  - Composition (a field holding separate layout+behavior instances) was considered and REJECTED for the per-cell
    field: the axes share one blob of per-cell MUTABLE state (text/position/selection_len/in_select/scroll/starts/
    pads/begin_y) and call each other BOTH ways (editing mutates text then calls layout to_index/get_col/paint;
    paint() calls behavior set_attrs).  Composition would force back-refs + ~15-20 forwarding stubs + 3x per-cell
    object churn (fields are created/destroyed on every table scroll and on every row_screen REFRESH) to buy a
    runtime-swap capability that never happens (a cell's layout+behavior is fixed at construction).  The churn
    argument specifically KILLS 3-object composition; it does NOT distinguish the two survivors below (both make
    exactly ONE field object per cell and keep field_shared as the shared per-column object).
  - DECIDED (2026-07-18): FULL-MIXIN (not hybrid).  Rationale below.
      full-mixin: field base + single_line/multi_line LAYOUT mixins + read_only/editable BEHAVIOR mixins ->
                  4 concrete classes (read_only_single_line, editable_single_line, read_only_multi_line,
                  editable_multi_line).  read_only & editable are SIBLING mixins on field, NOT editable(read_only).
      hybrid:     keep editable(read_only) single inheritance (as today) + only single/multi as a layout mixin.
    rationale for full-mixin: once LAYOUT (paint/gen_locations/get_col/get_lineno/to_index) is extracted into a
    mixin, the editable(read_only) link carries almost nothing (editable already overrides set_attrs/activate/
    deactivate/enclose), so making them siblings is marginally CLEANER, not more complex.  Both survivors still use
    MI to bring in the layout mixin, so hybrid does not buy "no MRO".  NOTE: this MI decision is for the FIELD
    family ONLY; the field_shared FACTORY family stays plain thin subclasses (no MI) -- see the two-hierarchies
    note at the end of this section.  Method partition (rough):
      field base : __init__, chgat, name/nlines/begin_x/ncols/app props, validate, reverse_attr (shared utils).
      LAYOUT     : paint, gen_locations, get_lineno, get_col, to_index; single_line adds column-scroll + [<>]
                   placeholders (NO wrap); multi_line adds wrap + line-grow (NO scroll, NO placeholders).
      BEHAVIOR   : read_only -> set_attrs(pass), activate/deactivate(reverse_attr), enclose(False);
                   editable  -> set_attrs(cursor/selection), activate(select-all), deactivate, enclose(compute),
                                get_text, process_mouse, process_key, insert, delete, delete_selection,
                                extend_selection, set_position, set_selection.  (Editing methods are
                                layout-agnostic -- KEY_UP/DOWN already no-op on single-line via the get_lineno
                                guards -- so written once.)
    field_shared (base) becomes geometry-only per the family design above; wrap() moves onto the multi_line layout
    (single_line never wraps).

- MIGRATION / TEST PLAN (write tests folded into each step; run on the Pi:
  ssh rpi-zero-2-w 'source ~/csv-venv/bin/activate && cd ~/tui-app && pytest -q'):
  1. Introduce the field_shared FAMILY behind the CURRENT field classes (field_class = read_only_field /
     editable_field for now).  Add field_for/edit_text/from_field + the two pickers.  Port table_screen,
     row_screen, menu_screen, ask_question to construct via the family.  BEHAVIOR-NEUTRAL (no scroll/grow yet).
     This lands the biggest consumer change first, cheaply, with today's field internals.
     - STEP 1 DONE + VERIFIED (2026-07-18), all sub-batches behavior-neutral, suite 205 on the Pi, and Bruce
       drove csv-inv-order on the Pi (menu + row form + ask_question) with no visible change:
       - 1a: field.py -- field_shared gains field_class + field_for/edit_text/from_field + a column= param;
         4 thin subclasses (read_only/editable x single/multi, all pointing at the current field classes);
         pickers single_line_shared / multi_line_shared.  New tests/test_field_factory.py (own fakes with
         `calculated`).  Nothing consumes it yet.
       - 1b: table_screen -- draw_body uses single_line_shared; draw_rows uses shared.field_for() (dropped the
         per-cell can_edit branch).
       - 1c: row_screen -- draw_body uses multi_line_shared(creating=self.table is not None) + field_for();
         the create-vs-update editable predicate moved into the picker (matches old row_screen.py:239).
       - 1d: menu_screen -- added action_shared (app-defined family member, action-backed field_for); action
         fields + ask_question (editable_single_shared.edit_text) build via the family.
  2. Split field internals into the chosen shape (full-mixin vs hybrid) -> the 4 concrete classes.  Pure internal;
     the factory's field_class attrs now point at the new classes.  No consumer change.  wrap() moves to
     multi_line.  Keep behavior identical (single-line still no scroll yet; multi-line still fixed nlines).
     - STEP 2 DONE (2026-07-18), full-mixin, behavior-neutral, suite 205 on the Pi:
       - field.py restructured: `field` base (shared per-cell state + single __init__ + layout/index math:
         paint, chgat, reverse_attr, gen_locations, get_lineno, get_col, to_index); single_line / multi_line
         LAYOUT mixins (EMPTY for now); read_only / editable BEHAVIOR mixins; 4 concrete cells
         read_only_single_line / editable_single_line / read_only_multi_line / editable_multi_line
         (behavior, layout, field).  __init__ unified to take both attr and callback.
       - Factory family field_class attrs repointed to the concrete cells; menu action_field subclasses
         read_only_single_line.
       - DEVIATION from the plan (intentional, lower-risk): wrap() did NOT move to multi_line yet -- it stays
         on field_shared and both layouts still share the wrap-based paint/index math on `field`.  Moving wrap
         only matters once single_line gets its own scroll paint (step 3) and multi_line gets grow (step 4);
         splitting identical code in step 2 just to move it again would be churn.  So single_line/multi_line are
         still empty; they gain methods when they actually diverge.  (test_field_shared.py still tests
         field_shared.wrap, unchanged.)
       - Tests updated: test_field.py (3-line) -> *_multi_line; test_field_interaction.py (1-line) ->
         *_single_line; test_table_screen.py / test_field_factory.py isinstance checks -> the `editable` /
         `read_only` behavior mixins.
       - VERIFIED on the Pi (Bruce drove csv-inv-order): menu/row/table cells render + edit unchanged.
  3. Implement SINGLE-LINE horizontal column-scroll (the X_single formula); drives self.scroll in paint().
     Update the paint() "# FIX: Recalculate scroll position" comment (this IS the fix).  Verify on the Pi.
     - STEP 3 DONE (2026-07-18), suite 219 on the Pi:
       - single_line gains X_single=0.6, _compute_scroll() (the settled formula), a paint() override that sets
         self.scroll before rendering, and a show_cursor() override.  It REUSES the existing shared
         wrap/gen_locations/to_index scroll machinery (which already handles a scroll offset + placeholders) --
         only the driving of self.scroll is new.  (So wrap() still lives on field_shared; a full no-wrap
         single-line rewrite is deferred as unnecessary -- the shared machinery renders one line correctly with
         the "<"/">" markers.)
       - New show_cursor() hook bridges behavior->layout: editable.set_position/set_selection now call
         self.show_cursor() instead of set_attrs().  Base/multi_line show_cursor = set_attrs() (BEHAVIOR-NEUTRAL
         for row_screen).  single_line show_cursor repaints only when the scroll window shifts, else set_attrs.
       - Read-only single-line cells have no cursor -> _compute_scroll returns 0 -> never scroll (unchanged).
       - ask_question now passes left/right_placeholder "<"/">" so its answer field scrolls with short markers
         (was the default 6-char "[...]" markers, too wide for the 5-col field).
       - NOT behavior-neutral (by design): single-line editable fields now scroll.  Live effect today is mostly
         ask_question (table in-place cell editing isn't wired yet, so table cells keep position None/0 ->
         scroll 0 -> no visible change).  New tests/test_field_scroll.py (formula, show_cursor decision, a
         paint->get_col->to_index round-trip).
       - VERIFIED on the Pi (Bruce): typing a long value into a menu ask_question prompt scrolls correctly.
       - PRE-EXISTING BUG spotted during this verify (NOT caused by step 3, defer): validation errors are not
         displayed properly (e.g. an ask_question / validate failure).  Old bug; fix later.  See KNOWN BUGS below.
  4. Implement MULTI-LINE grow-via-REFRESH + from_field; drop the *1.2 (row_screen.py:235) and multi placeholders;
     wire row_screen draw_body's REFRESH rebuild (from_field for changed fields).  Verify edits survive REFRESH
     and still submit correctly.  Update/retire the W1 note (obsoleted).
     - STEP 4 DONE + VERIFIED on the Pi (2026-07-18).  NOT behavior-neutral (row editing now grows):
       - field_shared.line_count(text) mirrors wrap()'s word-breaking; multi_line.grow_if_needed() =
         line_count(text) > nlines; editable.process_key returns 'REFRESH' after an edit that overflows.
         multi_line uses EMPTY placeholders (grows, never truncates).
       - from_field carries the in-progress edit (text + changed + position/selection + attr_pair/attr) so the
         edit AND the row's column_attr_pair highlight survive the redraw.  editable.deactivate() now clears
         position/selection so non-active changed fields paint no stray cursor.
       - row_screen: _refocus (set by process_key on a grow) -> draw_body rebuilds via from_field for changed
         fields / field_for otherwise, sizes nlines via line_count (dropped *1.2, honors edit_width), re-focuses
         the grown field.  Resize/validate still drop focus.
       - TWO bugs found + fixed on the Pi during verify (both committed):
         (a) crash typing a field full -- the append cursor on an exactly-full line made gen_locations emit a
             column past ncols -> chgat curses ERR.  Fixed by capping end_x to ncols-pad in gen_locations (it
             must never yield a location outside the field's rectangle).  [Bruce's steer: fix the source, not
             trap the error.]
         (b) row highlight lost after a grow -- from_field wasn't carrying attr_pair, so it fell back to
             default_attr_pair.  Fixed by passing old.attr_pair/attr through from_field.
       - MINOR known edge (acceptable, not a bug): the append cursor sitting at an exactly-full multi-line last
         line is not drawn until the next char is typed (which grows the field) -- gen_locations caps it away
         rather than showing it past the field.  Retires the W1 "+1 reserved column" hack.
       - Tests: test_field_grow.py + row_screen draw_body tests + from_field attr_pair assertion; suite 235 Pi.
  ---- FIELD-SCROLL MIGRATION (steps 1-4) COMPLETE + Pi-verified 2026-07-18. ----
  5. THEN resume the F9/F10 menus (next feature after this refactor).  <-- START HERE NEXT.
  - Blast radius: field.py + field_shared + all three screens (they construct fields) + the field tests +
    row/menu screen tests.  row_screen & menu_screen still have thin tests -- ALSO drive csv-inv-order on the Pi
    after steps 1 and 4.

- TWO SEPARATE HIERARCHIES, DIFFERENT ANSWERS (both DECIDED 2026-07-18) -- do not conflate:
  - FIELD family (the concrete cells, step 2 internals) = FULL-MIXIN (MI): field base + single_line/multi_line
    LAYOUT mixins + read_only/editable BEHAVIOR mixins -> 4 concrete classes.  (This is what "full-mixin over
    hybrid" decided.  See "FIELD-CLASS INTERNALS" above.)
  - field_shared family (the factories) = PLAIN THIN SUBCLASSES, NO MI: each just sets field_class (one line);
    the base holds all the factory machinery.  The two hierarchies are NOT coupled.
- No open items remain blocking; step 1 of the migration plan can start.

### interaction spec implementation (2026-07-19) ###

- Authoritative spec = `tui_app/USER_INTERACTION` (Bruce's keyboard+mouse table + the RESOLVED
  appendix from the 2026-07-19 review).  This section is the WORK CHECKLIST derived from it.  Keep the
  per-screen help text (F1) in sync with the spec as each piece lands.

- Ordered tasks (each = small batch, tests folded in, verify on the Pi):
  1. F9/F10 keyboard menus -- DONE + Pi-verified 2026-07-19.  Factored _open_row_popup /
     _open_screen_popup out of process_mouse; F10 -> screen popup, F9 -> row popup for the focused row
     (focuses top visible row first if none).  [mouse right-press-drag-select refinement DEFERRED.]
  2. table_screen F2 = open focused row in row_screen -- DONE + Pi-verified 2026-07-19.
     Runs the row's view_edit_command ('View/Edit', a table_screen class attr) and returns the
     row_screen; focuses top visible row first if none; no-op if not offered / no rows.
     - FOLLOW-UP (found during F2 verify): row_screen had NO Esc handling, so Esc couldn't leave the
       row form.  Added (partial task 5, pulled early): Esc deselects the active field then Backs, but
       only when nothing changed; with unapplied changes it shows a message and stays (leave via
       Cancel/Apply).  Buttons are still mouse-only + named Cancel/Validate/Submit until task 5.
       NEEDS Pi verify (Esc returns to table on a clean row; Esc shows the message on a changed row).
  3. table_screen DEL = delete focused row with y/n confirm (+ auto-advance); INS = create row.
     (DEL only when NOT editing; during a cell edit DEL = delete char.)
     - DONE + Pi-verified 2026-07-19 (suite 257).  Added tui_base.popup_confirm (Yes/No, default No,
       y/n shortcuts [y=Yes/delete, n=No/cancel], Up/Down+Enter, Esc=dismiss).  DEL confirms then runs
       the row's delete_command; focus auto-advances via draw_body restoring the same row index
       (clamped to the new last row when the last row goes).  DEL is a silent no-op if the row doesn't
       offer Delete (confirmed acceptable).  INS runs create_command only if the table advertises it
       in screen_popup_commands.  ALSO fixed csv-app table.execute('Create') to RETURN the row_screen
       (was falling through to None) -- committed in csv-app (c77773a).
     - DEFERRED to task 4: "DEL only when NOT editing" -- table cell editing isn't wired yet, so DEL
       always = delete row for now; gate it on edit-mode when task 4 lands.
  4. table_screen in-place cell EDITING: SPACE / printable char (NOT space-insert) / double-click
     starts edit; ENTER/UP/DOWN and TAB/BTAB commit + move; ESC aborts.  On commit: write cell ->
     row, recompute, redraw the row (calculated columns refresh).  This is the big one.
     - KEYBOARD DONE 2026-07-19 (suite 265), NEEDS Pi verify.  `editing` flag gates edit-mode; SPACE /
       printable char start it (char inserts, replacing select-all; space doesn't); _edit_key routes
       to the field (event_handled/return key), field consumes text + Left/Right; Enter/Down/Up/Tab/
       BTab commit+move; Esc aborts.  Commit = row.set(col, text) + app.set_changed() + redraw that
       row (calc cols refresh) + move (write-through, NOT Save).  Esc-abort re-reads from the row.
       Enter (not editing) now moves down.  DEL gating falls out (editing routes to field first).
     - KEYBOARD editing Pi-verified 2026-07-19 (left- AND right-aligned).  Right-aligned cells edit
       LEFT-aligned / display right-aligned (single_line owns its no-wrap paint now; field.editing flag).
       Fixed along the way: delete_selection cursor off-by-one; empty right-aligned cursor visibility.
     - REMAINING: mouse double-click to start edit (deferred to a follow-up batch).
     - NOTE: emptying a REQUIRED field crashes (uncaught ValueError) -- logged under KNOWN BUGS as part
       of the validation-error-display cleanup.
  5. row_screen redesign per spec: remove Validate button; rename Submit->Apply (create keeps
     'Create'); Cancel + Apply both Back (Cancel discards, Apply writes to master/db); accept-field
     (ENTER/TAB/BTAB) always validates + recomputes calculated cols into self.row (copy) WITHOUT
     writing master; ESC only Backs when unchanged (else no-op, no message).  Buttons in the Tab
     sequence.  Careful with `changed` / attrs_changed bookkeeping across per-field accepts.
  6. field ESC abort-reset (NEEDS DESIGN FIRST, then implement): snapshot text on activate; ESC
     restores the snapshot (only undoes the current edit session).  DESIGN QUESTION: after abort the
     `changed` flag must reflect text-vs-ORIGINAL-construction-value, not just "was edited" -- likely
     capture the original value at construction and compute changed, OR store both original + session
     snapshot.  Resolve before coding (Bruce flagged this as needing thought).
  7. app exit/abort keys + popup_message callback (the double-key confirm); revisit AFTER F10 (may be
     unnecessary if the F10 menu's Exit/Abort suffices).  Remove 'q' quit from screen.run when done.
  8. Cross-cutting: ESC precedence chain (popup -> field abort -> Back) applied uniformly;
     popup_message dismiss on ESC/ENTER/SPACE/click (ignore other keys).

- DEFERRED refinements (not blocking): popup mouse right-press-drag-select (open under mouse);
  menu_screen Left/Right between columns (UP/DOWN wrap already works); row_screen scroll (widest table
  ~1/3 screen, not needed yet).

### KNOWN BUGS (deferred) ###

- Creating a row with a DUPLICATE key raises an uncaught exception (csv_app/table.py:158 --
  `assert key not in self, "...Duplicate key..."`), crashing the app.  PRE-EXISTING (not from the
  interaction work); surfaced 2026-07-19 testing INS (create).  Fix later: validate/catch the dup key
  in the create path (row_screen Create / add_row) and show an error message instead of asserting.

- Emptying/deleting a REQUIRED field raises ValueError (Bruce's universal validation error) that is
  UNCAUGHT -> no message (crash).  PRE-EXISTING; surfaced 2026-07-19 testing left-aligned cell editing.
  Part of the broader validation-error-display cleanup: the app raises ValueError for all validation
  problems, but the display paths don't catch/show it.  Fix together with:
    * the existing "validation errors not displayed properly" bug (field.highlight missing / row_screen
      error path),
    * the dup-key assertion above,
    * table cell _commit_edit and INS/Create: catch ValueError on write and show a message (keep
      editing / stay) instead of crashing.
  i.e. one cleanup pass makes validation failures show a message everywhere instead of raising.

- Validation errors not displayed properly (PRE-EXISTING; spotted 2026-07-18 while verifying step 3 on the Pi;
  NOT introduced by the field refactor).  Repro: trigger a validation failure (e.g. an ask_question / a
  row_screen Validate/Submit with a bad value) -- the error message doesn't show as it should.  Bruce: old bug,
  fix later.  claude: not yet investigated; likely in menu_screen.clear_question / the popup_message error path or
  row_screen.validate's error highlight.  Pick up after the field-scroll migration (step 4) / F9-F10 menus.

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

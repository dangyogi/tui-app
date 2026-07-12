# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Start here: active tasks

At the start of a session, read **`CLAUDE-tasks.md`** in this directory if it exists. It holds Bruce's notes to
Claude — current tasks, design decisions, and open questions — and is where in-progress work (e.g. the
table_screen navigation redesign) is tracked. It is a temporary, working file (not intended to be permanent), so
treat it as the source of truth for what to work on next. Add your own notes there prefixed with `claude:`.

## What this is

`tui_app` is a small `curses`-based TUI framework for database-style apps: a scrollable **table view** (list of rows with column headings) and a **row view** (a form for viewing/editing one row), plus an action **menu view**. It is tuned to run acceptably on a Raspberry Pi Zero 2 W, where the `textual` library is too slow — so the code favors minimal redraws (e.g. `curses` `insdelln` scrolling, painting fields once per resize) over convenience.

The framework does not know about any concrete data model. Consuming apps pass in `table` / `column` / `row` objects that satisfy the duck-typed interfaces documented in `tui_app/tui.py` (authoritative) and `README.md`.

## Cross-repo dependency (important)

`pyproject.toml` declares `dependencies = []`, but the code has a hard runtime dependency on the sibling package **`csv_app`** (repo `../csv-app`):

- `from csv_app.trace import trace` — used pervasively for logging (see below). Re-exported from `tui_base` as `tui_base.trace`, so most modules import it via `from .tui_base import trace`.
- `from csv_app import action` — used by `menu_screen.py`.

Both `csv_app` and `tui_app` are installed as **editable** packages into a shared virtualenv. The canonical consumer app lives in `../csv-inv-order` (`csv_inv_order/tui.py` shows how to launch: `tui.start(database.Tables, menu_screen(...))`). When changing a public interface here, check `../csv-app` and `../csv-inv-order` for callers.

## Running tests

Tests use `pytest` (`testpaths = ["tests"]`) and only exercise the pure-logic `field_shared` text-wrapping/alignment code plus `field` interaction — none of it touches a real terminal.

```bash
pytest                              # all tests, from repo root
pytest tests/test_field_shared.py   # one file
pytest tests/test_field_shared.py::test_multi_line   # one test
pytest -k wrap                      # tests matching a name
```

### sshfs / path mapping caveat

This tree is normally edited from a Linux **desktop** that sshfs-mounts the Raspberry Pi's home dir: the Pi's `/home/bruce/xyz` appears on the desktop as `/home/bruce/rpi-zero-home/xyz`. The real venv (sibling `csv-venv`, with `tui_app`/`csv_app`/`pytest` installed editable) is a **Pi venv** and cannot be run from the desktop, for two reasons:

- Its console-script shebangs are absolute Pi paths (`#!/home/bruce/csv-venv/bin/python3`), which don't exist on the desktop → `cannot execute: required file not found`.
- Its `bin/python3` symlinks to `/usr/bin/python3`, which on the desktop is a *different* Python (e.g. 3.12) than the venv was built with (3.11), so its `lib/python3.11/site-packages` is invisible → `No module named pytest`.

The venv is not broken — it just belongs to the Pi. To run tests, either:

```bash
# Option A: run on the Pi over ssh (paths drop the rpi-zero-home/ prefix there).
# The csv-venv must be activated before running tui-app code. (verified: 159 passed)
ssh rpi-zero-2-w 'source ~/csv-venv/bin/activate && cd ~/tui-app && pytest -q'

# Option B: make a desktop-local venv (all packages are pure Python, so x86/3.12 is fine)
cd /home/bruce/rpi-zero-home
python3 -m venv .desktop-venv
.desktop-venv/bin/pip install -e csv-app -e tui-app pytest
cd tui-app && ../.desktop-venv/bin/pytest
```

## Running the app / debugging

There is no runnable app in this repo except the color reference tool:

```bash
color-display   # console script -> tui_app.color_display:run; dumps the 256 color pairs, writes color_display.txt
```

To run a real TUI you launch a consumer app (e.g. `csv_inv_order.tui:run`). Since curses takes over the terminal, `print` debugging is useless — **use `trace(...)` instead**. Every `trace()` call appends to `trace.txt` in the current working directory (line-buffered). Reading `trace.txt` after a run is the primary way to debug screen/field/popup behavior. The code is already heavily instrumented with `trace()`.

## Architecture

### Screen lifecycle (see the module docstring at the top of `tui_base.py`)

`tui.start(tables, top_screen)` builds an `app` (in `tui.py`) and hands it to `curses.wrapper`. The app is a **stack-less screen loop**:

```
app.run: while self.screen is not None: self.screen = self.screen.run(self)
```

Each `screen.run(app)` fully owns the terminal until it returns the **next screen** (or `None` to exit). Inside, it calls `self.init()` once, then loops: `self.draw()` → read keys/mouse → dispatch. `draw()` re-runs on every `KEY_RESIZE`; `init()` does not.

Navigation is by return value, not a call stack. `process_key` / `process_mouse` / `execute` return one of these sentinels, which `screen.run` interprets:

- an instance of `screen` → switch to that screen
- `None` → event handled, keep looping (also: exit app when returned at top level)
- `'REFRESH'` → break out to re-run `draw()`
- `'APP_EXIT'` → exit cleanly; `'APP_ABORT'` → `sys.exit(1)`
- returning the raw key/mouse_event unchanged → "not handled here", bubble up to the next handler

`screen.back` holds the screen to return to; the framework-level `Back` command validates then returns `self.back`. `event_handled()` centralizes the "is this a terminal sentinel" check used when delegating to popups.

### The `execute` command hierarchy

Commands are plain strings resolved through a chain, each level handling what it can and forwarding the rest upward:

`row/table/menu screen.execute` → `screen.execute` (handles `Back`) → `app.execute` (handles table-name commands → new `table_screen`, plus `Save`/`Exit`/`Abort`; raises `ValueError` on unknown). `table_screen` forwards to `table.execute(...)`, and the app-defined table returns `'Continue'` to signal "not mine, keep going up the chain".

### Screens (subclasses of `tui_base.screen`)

- **`table_screen`** — list of rows. Column widths auto-fit from data (`min_width`/`abbr` control this). Right-click above row 2 → screen-level popup menu (`screen_popup_commands`, with `Back`/`Exit`/`Abort` appended dynamically); right-click on a row → per-row popup (`row_popup_commands`). Scrolling uses `insdelln` and only redraws the newly exposed rows.
- **`row_screen`** — one-row form. Built via `for_update(row)` (edits a `row.copy()`, commits to `master_row` on Submit) or `for_create(table)`. Command buttons (`Cancel`/`Validate`/`Submit` or `Create`) render at the bottom. `validate()` runs per-field `validate()`, then `table.check_required`, then an optional `global_validate(self)` callback; failures highlight the offending field and show a centered message.
- **`menu_screen`** — multi-column action menu (used by `csv-inv-order`). Color-codes each action by runnability (task / must-run / may-rerun / can't-run) and draws a legend. Supports an inline question/answer prompt (`ask_question`).

### Popups (`tui_base.popup` and subclasses)

Popups draw into a `curses` subwin and, on `delete()`, **restore the exact characters they overwrote** (captured with `inch()` at construction) — there is no full-screen redraw on dismiss. `popup_menu` is the right-click command menu; `popup_message` is a centered message box (used for errors). A screen holds at most one `self.popup` at a time.

### Fields: `field_shared` vs field instances (`field.py`)

This split is a deliberate performance optimization and is easy to get wrong:

- **`field_shared`** holds per-column *geometry and layout logic* (position, width, `nlines`, alignment, validate fn, and the `wrap()` text-flow algorithm). It is created **once per column per `draw()`** and shared across every cell in that column. It is pure/testable — the test suite targets it directly.
- **`read_only_field` / `editable_field`** are the actual on-screen cells, created **per row on each (re)draw**. Because a field only lives for one screen size, it computes its wrapped `starts` once and just manages attrs (cursor position, selection, `A_REVERSE`) thereafter. `editable_field` handles the full text-editing surface (insert/delete, word/line selection, mouse drag-select, arrow navigation across wrapped lines).

`wrap()` reflows text into `nlines` of `ncols`, breaking on spaces when possible and inserting `left_placeholder`/`right_placeholder` (`[...]`) markers when horizontally scrolled or truncated. The index math between text offsets and screen (y, x) — `to_index`, `get_lineno`, `get_col`, `gen_locations` — is the subtle core; the `test_field_shared.py` / `test_field*.py` cases pin down its expected behavior with worked examples, so consult them before changing wrapping/scrolling.

### Colors

Color pairs are pre-initialized for every fg/bg combination. A pair number is `(fg << 4) | bg`, where each nibble is a 4-bit color: bit 3 = "high/bright", bits 0-2 = color as **BGR** (see the color table in `tui_base.py`). So e.g. `0x01` = black on red, `0x70` = white on black. Run `color-display` to see them all rendered.

## Conventions

- Keep the `trace(...)` instrumentation dense and in the existing `f"func_name(args=...)"` style when adding code paths — it is the only debugging channel once curses is active.
- `# module.py` header comment on each file; module-level `r'''...'''` docstrings carry the real design documentation (especially `tui_base.py` and `field.py`).
- Screen subclasses set behavior-tuning knobs as class attributes (e.g. `scroll_amount`, `error_attr`, the `*_pair` color constants) rather than constructor args.

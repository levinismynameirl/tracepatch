# CLI Guide

The `tph` (or `tracepatch`) command provides tools for viewing, analysing,
and managing traces from the terminal.

## Commands at a Glance

| Command | Purpose |
|---|---|
| `tph logs` | List saved trace files |
| `tph view <file>` | Show trace metadata |
| `tph tree <file>` | Display the call tree |
| `tph stats <file>` | Detailed statistics report |
| `tph diff <a> <b>` | Compare two traces |
| `tph export <file>` | Export to CSV or HTML |
| `tph config` | Show current configuration |
| `tph init` | Create a starter config file |
| `tph run` | Run traced test environment |
| `tph clean` | Clean up generated files |

---

## `tph logs`

List recently saved trace files from `.tracepatch/traces/`.

```bash
tph logs                    # list recent traces
tph logs --limit 10         # show only 10 most recent
tph logs --cache-dir /path  # search a custom directory
tph logs --label "checkout*"  # filter by label (glob)
tph logs --limited          # only show traces that hit a limit
```

### Options

| Flag | Description |
|---|---|
| `--cache-dir DIR` | Parent directory containing `.tracepatch/` |
| `--limit N` | Maximum number of logs (default: 50) |
| `--label PATTERN` | Glob pattern to match trace labels |
| `--limited` | Only show traces that were limited |

---

## `tph view <file>`

Show metadata and summary for a trace file without rendering the tree.

```bash
tph view trace.json
tph view trace.json --json   # include raw JSON dump
```

---

## `tph tree <file>`

Display a trace as a readable call tree. This is the primary command
for exploring what happened during a traced execution.

```bash
tph tree trace.json
tph tree trace.json --color --style unicode
tph tree trace.json --filter 'myapp.*'
tph tree trace.json --filter '!logging'
tph tree trace.json --depth 3
tph tree trace.json --no-args --self-time
tph tree trace.json --format html -o report.html
```

### Options

| Flag | Description |
|---|---|
| `--filter PATTERN` | Module glob (`app.*`) or exclusion (`!stdlib`) |
| `--depth N` | Limit tree to N levels deep |
| `--format F` | `text` (default), `json`, or `html` |
| `--output FILE` | Output file (for HTML format) |
| `--color` | Colorise by duration (green/yellow/red) |
| `--style S` | `ascii` (default), `unicode`, or `ansi` |
| `--no-args` | Hide function arguments |
| `--no-return` | Hide return values |
| `--show-source` | Show source file and line number |
| `--self-time` | Show self-time alongside total time |
| `--no-stats` | Hide the summary statistics header |
| `--no-fold` | Disable folding of repeated sibling calls |
| `--fold-threshold N` | Minimum run to fold (default: 3) |
| `--collapse N` | Auto-collapse subtrees at depth N |

### Call Folding

When a function is called many times consecutively (e.g. in a loop),
the tree automatically folds them into a single line:

```
└── myapp.process(...  [×500]  [avg: 0.12ms, min: 0.08ms, max: 0.31ms])  [60.00ms]
```

Use `--no-fold` to see every individual call, or `--fold-threshold 10`
to only fold runs of 10+ identical calls.

### Auto-Collapse

Traces with more than 200 nodes are automatically collapsed to depth 4.
Use `--collapse N` to choose a different depth, or `--no-fold` plus
`--depth N` for manual control.

---

## `tph stats <file>`

Print a detailed statistics report including top slowest functions,
most-called functions, and a module breakdown.

```bash
tph stats trace.json
```

Example output:

```
Trace: checkout-flow
======================================================================

Top 10 slowest functions:
   1.  db.query                             12.30ms  (×3,  avg 4.10ms,  max 8.20ms)
   2.  http.request                          8.10ms  (×1,  avg 8.10ms,  max 8.10ms)

Top 10 most called functions:
   1.  app.validate                          ×1482   (avg 0.02ms,  total 29.60ms)

Module breakdown:
  myapp                              72 calls ( 48%)   total: 22.10ms
  db                                 18 calls ( 12%)   total: 15.30ms
```

---

## `tph diff <file1> <file2>`

Compare two trace files and show what changed.

```bash
tph diff before.json after.json
```

Output shows:

- `+` — functions present only in the second trace
- `-` — functions present only in the first trace
- `~` — functions whose timing or call count changed significantly

```
+ myapp.new_validator()      added      [3.20ms]
- myapp.old_check()          removed
~ db.query()                 slower     [0.80ms -> 4.20ms  +425%]
~ app.process()              calls      [×3 -> ×12]
```

---

## `tph export <file>`

Export a trace to a different format.

```bash
tph export trace.json --format csv -o trace.csv
tph export trace.json --format html -o report.html
```

### Formats

| Format | Description |
|---|---|
| `csv` | Flat CSV with columns: module, function, args, return_value, elapsed_ms, depth, parent |
| `html` | Interactive HTML tree (same as `tph tree --format html`) |

---

## `tph config`

Show the active configuration, including where it was loaded from and
all effective values.

```bash
tph config                        # show current config
tph config --file custom.toml     # load a specific file
tph config --validate             # validate and exit (for CI)
```

`--validate` exits with code 0 if valid, 1 if invalid.

---

## `tph init`

Create a starter `tracepatch.toml`. Interactive by default — asks for
your source directory, trace mode, and modules to ignore.

```bash
tph init              # interactive setup
tph init --yes        # skip prompts, use defaults
tph init --force      # overwrite existing file
```

---

## `tph run`

Set up and run the traced test environment using `[[test.files]]` from
your configuration. Generates `.tracepatch/trace_runner.py` and executes
the configured functions with tracing enabled.

```bash
tph run
```

This is the replacement for the old `tph setup` command. The backward
compatible alias `tph setup` still works.

---

## `tph clean`

Clean up generated files and trace data.

```bash
tph clean                     # remove setup state (state.json)
tph clean --traces            # remove all trace JSON files
tph clean --older-than 7d     # remove traces older than 7 days
tph clean --all               # remove entire .tracepatch/ directory
```

The backward-compatible alias `tph disable` still works for the basic
cleanup mode.

### Duration Format

For `--older-than`, use a number followed by a unit:

- `7d` — 7 days
- `24h` — 24 hours
- `30m` — 30 minutes

---

## Exit Codes

All commands exit with `0` on success and `1` on any error. Error
messages are written to stderr.

---

## Common Workflows

### Trace a function and view immediately

```python
from tracepatch import trace

with trace(label="debug-checkout") as t:
    checkout(cart)
print(t.tree())
```

### Save traces and review later

```bash
# In your code: traces are auto-saved when cache=true (the default)
# Then from the terminal:
tph logs
tph tree .tracepatch/traces/debug-checkout_20260219_143022_a1b2c3.json --color
```

### Compare before and after a refactor

```bash
# Run your code before the change, save trace
# Run your code after the change, save trace
tph diff before.json after.json
```

### Validate config in CI

```bash
tph config --validate || exit 1
```

# Reading the Call Tree

The call tree is the primary output of tracepatch. This guide explains
how to read it, what the numbers mean, and how to use the various
display options.

## Basic Structure

```
└── __main__.handle_request(user_id=42) -> {'status': 'ok'}  [1.23ms]
    ├── myapp.auth.validate(token='abc...') -> True  [0.45ms]
    │   └── myapp.db.query(sql='SELECT...') -> <Row>  [0.32ms]
    └── myapp.core.process(data={...}) -> {'result': 42}  [0.78ms]
        ├── myapp.core.transform(x=42)  [0.12ms]
        └── myapp.core.save(result=42) -> None  [0.55ms]
```

Each line represents one function call and contains:

| Part | Meaning |
|---|---|
| `myapp.auth` | The Python module where the function is defined |
| `.validate` | The function name |
| `(token='abc...')` | Captured argument values |
| `-> True` | Return value (or `!! Exception` for exceptions) |
| `[0.45ms]` | Wall-clock elapsed time including children |

### Tree Connectors

- `├──` — this node has more siblings below it
- `└──` — this is the last child of its parent
- `│` — vertical line connecting siblings

## Timing

The `[elapsed]` value is **total time** — it includes the function's
own execution plus all its children. Units adapt automatically:

| Display | Meaning |
|---|---|
| `42us` | 42 microseconds |
| `1.23ms` | 1.23 milliseconds |
| `2.500s` | 2.5 seconds |

### Self-Time

Use `--self-time` to see how much time the function itself spent,
excluding its children:

```
└── myapp.process(...)  [1.23ms / self: 0.05ms]
    └── myapp.db.query(...)  [1.18ms / self: 1.18ms]
```

Here `process` took 1.23ms total, but only 0.05ms of its own work.
The remaining 1.18ms was spent in `db.query`.

Self-time reveals the **actual bottleneck** — a function with high
total time but low self-time is just a passthrough.

## Summary Header

By default, a statistics header appears above the tree:

```
Trace: checkout-flow
────────────────────────────────────────────────────────────────────────
Recorded:     150 calls across 5 modules  | Duration: 42.30ms
Max depth:    8 levels                    | Unique functions: 23
Slowest:      db.query [12.30ms]          | Most called: app.validate [×48]
────────────────────────────────────────────────────────────────────────
```

Use `--no-stats` to hide it.

## Call Folding

When a function is called repeatedly in a loop, tracepatch folds
consecutive identical calls into one line:

```
└── myapp.process(...  [×500]  [avg: 0.12ms, min: 0.08ms, max: 0.31ms])  [60.00ms]
```

This tells you:
- The function was called 500 times consecutively
- Average time per call was 0.12ms
- The fastest call took 0.08ms, the slowest 0.31ms
- Total time across all 500 calls was 60ms

Use `--no-fold` to see every individual call, or `--fold-threshold 10`
to only fold runs of 10 or more.

## Filtering

### Include by Pattern

```bash
tph tree trace.json --filter 'myapp.*'
```

Shows only calls whose module matches the glob pattern.

### Exclude by Pattern

```bash
tph tree trace.json --filter '!logging'
```

Hides calls whose module matches, showing everything else.

### Depth Limiting

```bash
tph tree trace.json --depth 3
```

Shows only the top 3 levels of the tree. Deeper calls are replaced
with a `[N nested calls...]` placeholder.

## Source Locations

Use `--show-source` to add the source file and line number:

```
└── myapp.process(data={...})  [1.23ms]  (myapp/core.py:45)
```

This helps distinguish functions with the same name in different files.

## Display Styles

### ASCII (default)

```
├── myapp.process()  [1.23ms]
│   └── myapp.save()  [0.55ms]
└── myapp.cleanup()  [0.12ms]
```

### Unicode (`--style unicode`)

```
├─ myapp.process()  [1.23ms]
│  └─ myapp.save()  [0.55ms]
└─ myapp.cleanup()  [0.12ms]
```

### ANSI (`--style ansi`)

Same as Unicode, but connector characters are dim-coloured for visual
clarity in terminals that support ANSI escape sequences.

### Colour (`--color`)

Calls are colour-coded by elapsed time:
- **Green** — fast (&lt; 10ms)
- **Yellow** — moderate (10–100ms)
- **Red** — slow (&gt; 100ms)

## Common Patterns

### Deep Nesting

If the tree is very deep (>10 levels), it usually indicates:
- Recursive algorithms
- Deeply nested middleware/decorator chains
- Framework internals leaking in

**Fix:** Use `ignore_modules` to filter out framework code, or
`include_modules` to trace only your code.

### Wide Fan-Out

A single function with many children usually means:
- A loop calling different functions
- An orchestrator dispatching to many handlers

**Fix:** Use `--depth` to limit the view, or `--fold-threshold` to
fold the repeated calls.

### Repeated Calls (Folded)

A function shown with `[×N]` was called many times consecutively.
Check whether:
- The call count is expected (processing N items)
- The per-call time is reasonable
- The total time is a bottleneck

### Exceptions

```
└── myapp.process() !! ValueError('invalid input')  [0.03ms]
```

The `!!` marker shows the function raised an exception instead of
returning a value.


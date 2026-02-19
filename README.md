# tracepatch

**See exactly what your code did — every call, argument, return value, and timing — in one readable tree.**

tracepatch records function calls for a single execution scope (a request, a CLI command, a background task) and produces a call tree you can actually read. It's not OpenTelemetry. It's not cProfile. It's a scalpel: point it at the code path that's misbehaving and it tells you exactly what happened.

Zero runtime dependencies. Zero overhead when inactive. Leave it installed in production.

## When to Use / When NOT to Use

**Use tracepatch when you need to:**
- Debug why a specific request is slow or returning wrong results
- Understand the call flow through unfamiliar code
- Compare execution patterns before and after a refactor
- Trace exactly what happens inside a failing test

**Don't use tracepatch for:**
- Distributed tracing across services → use OpenTelemetry
- Statistical profiling of hot paths → use cProfile or py-spy
- Audit logging for compliance → use structured logging

## Quick Start

```python
from tracepatch import trace

def load_user(uid):
    return {"id": uid, "name": "Alice"}

def validate(user):
    return user["name"] != ""

def handle_request(uid):
    user = load_user(uid)
    validate(user)
    return user

with trace(label="debug-request") as t:
    handle_request(42)

print(t.tree())
```

```
Trace: debug-request
────────────────────────────────────────────────────────────────────────
Recorded:     3 calls across 1 modules    | Duration: 0.05ms
Max depth:    1 levels                    | Unique functions: 3
Slowest:      __main__.handle_request [0.05ms]| Most called: __main__.load_user [×1]
────────────────────────────────────────────────────────────────────────

└── __main__.handle_request(uid=42) -> {'id': 42, 'name': 'Alice'}  [0.05ms]
    ├── __main__.load_user(uid=42) -> {'id': 42, 'name': 'Alice'}  [0.01ms]
    └── __main__.validate(user={'id': 42, ...}) -> True  [0.01ms]
```

## Features

- **Zero overhead when inactive** — `sys.settrace` hook only installed inside `trace()` blocks
- **Pure Python** — no runtime dependencies (optional `tomli` on Python <3.11)
- **Async + sync** — works with `async/await`, generators, and async generators via `contextvars`
- **Thread-safe** — each trace is isolated with a unique ID
- **Built-in safety** — `max_depth`, `max_calls`, `max_time` auto-disable before damage
- **Call folding** — repeated calls in loops fold into `[×500]` with min/avg/max timing
- **Self-time** — see where time is actually spent vs. passed through to children
- **Statistics** — summary header with call count, slowest function, module breakdown
- **Multiple outputs** — ASCII tree, Unicode tree, coloured ANSI, JSON, HTML, CSV
- **Source locations** — optional file:line annotation for each call
- **Trace comparison** — `tph diff before.json after.json`
- **CLI** (`tph`) — logs, tree, stats, diff, export, config, init, run, clean
- **TOML config** — `tracepatch.toml` or `pyproject.toml [tool.tracepatch]`
- **Environment overrides** — `TRACEPATCH_ENABLED=0` to disable globally

## Installation

```bash
pip install tracepatch
```

From source:
```bash
pip install .
```

## Quick Start

### Context Manager (Sync)

```python
from tracepatch import trace

def fetch_user(user_id):
    return {"id": user_id, "name": "Alice"}

def handle_request():
    user = fetch_user(42)
    return user

with trace() as t:
    handle_request()

print(t.tree())
```

**Output:**
```
└── __main__.handle_request()  [0.03ms]
    └── __main__.fetch_user(user_id=42) -> {'id': 42, 'name': 'Alice'}  [0.01ms]
```

### Context Manager (Async)

```python
import asyncio
from tracepatch import trace

async def fetch_user(user_id):
    return {"id": user_id, "name": "Alice"}

async def handle_request():
    user = await fetch_user(42)
    return user

async def main():
    async with trace() as t:
        await handle_request()
    print(t.tree())

asyncio.run(main())
```

### Decorator Usage

```python
from tracepatch import trace

# Simple decorator
@trace(label="api-handler")
def handle_api_request():
    process_data()
    return {"status": "OK"}

result = handle_api_request()

# Works with async functions
@trace(label="async-task")
async def background_job():
    await fetch_data()
    await process_data()

await background_job()

# Works with generators
@trace()
def data_generator():
    for i in range(10):
        yield process_item(i)

# Works with async generators
@trace()
async def async_stream():
    for i in range(10):
        yield await fetch_item(i)
```

**Note:** For `@staticmethod` or `@classmethod`, apply `@trace` **after** the decorator:
```python
class MyClass:
    @staticmethod
    @trace()
    def my_static_method():
        pass
```

### Production Safety

```python
from tracepatch import trace

# Auto-stop after 5 seconds (prevent runaway traces)
with trace(max_time=5.0) as t:
    long_running_operation()

# Limit depth and calls
with trace(max_depth=10, max_calls=1000) as t:
    recursive_function()
    
print(f"Limited: {t.was_limited}") # True if stopped early
```

### Filtering and Focus

```python
from tracepatch import trace

# Ignore noisy modules
with trace(ignore_modules=["logging", "urllib"]) as t:
    make_api_call()  # Won't see internal logging/urllib calls

# Environment variable override (set once, affects all traces)
# export TRACEPATCH_ENABLED=0  # Disable all tracing globally
# export TRACEPATCH_MAX_DEPTH=5
```

## Configuration

Create `tracepatch.toml` or add `[tool.tracepatch]` to `pyproject.toml`:

```toml
# Tracing behavior
ignore_modules = ["unittest.mock", "logging"]  # Module prefixes to exclude
# include_modules = ["myapp"]  # Allowlist: only trace these modules
max_depth = 30          # Maximum call nesting depth
max_calls = 10000       # Stop after this many calls
max_repr = 120          # Max length for repr() of args/returns
max_time = 60.0         # Stop after this many seconds

# Cache settings
cache = true            # Auto-save traces
# cache_dir = ".custom_cache"
auto_save = true

# Display settings
show_args = true
show_return = true
tree_style = "ascii"    # "ascii" or "unicode"

# Test setup (for `tph setup`)
[[test.files]]
path = "myapp/core.py"
functions = ["process", "validate"]

[test.custom]
enabled = false         # Use custom test script
script = ""
```

Generate starter config:
```bash
tph init
```

## CLI Usage

```bash
tph logs                           # list saved traces
tph tree trace.json --color        # coloured call tree
tph tree trace.json --self-time    # show self-time
tph tree trace.json --style unicode --no-args   # compact view
tph tree trace.json --filter 'myapp.*'          # only myapp calls
tph tree trace.json --filter '!logging'         # exclude logging
tph tree trace.json --depth 3                   # limit depth
tph stats trace.json               # detailed statistics
tph diff before.json after.json    # compare two traces
tph export trace.json --format csv -o trace.csv
tph config --validate              # validate config (CI)
tph init                           # create tracepatch.toml
tph clean --older-than 7d          # remove old traces
```

## Advanced Usage

### Circular Reference Handling

```python
class Node:
    def __init__(self, value):
        self.value = value
        self.next = None

# Create circular reference
a = Node(1)
b = Node(2)
a.next = b
b.next = a  # Circular!

with trace() as t:
    process(a)  # Won't crash - shows "<circular reference>"
```

### Error Handling

Tracing machinery catches and logs exceptions without affecting traced code:

```python
class BadRepr:
    def __repr__(self):
        raise RuntimeError("broken repr")

with trace() as t:
    use_object(BadRepr())  # Shows "<unprintable>", doesn't crash

# Exception info logged to stderr:
# [tracepatch] repr failed: RuntimeError
```

### Thread Safety

Each trace gets a unique ID for correlation:

```python
import threading

def worker(task_id):
    with trace(label=f"worker-{task_id}") as t:
        do_work(task_id)
        # Each trace isolated - no interference

threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()
```

### JSON Structure

```python
with trace() as t:
    do_something()

t.to_json("trace.json")
```

**trace.json:**
```json
{
  "tracepatch_version": "0.3.2",
  "timestamp": "2026-02-12T14:30:22.123456",
  "label": "my-trace",
  "call_count": 42,
  "was_limited": false,
  "config": {
    "max_depth": 30,
    "max_calls": 10000,
    "max_repr": 120,
    "ignore_modules": ["unittest.mock"]
  },
  "trace": [
    {
      "name": "do_something",
      "module": "__main__",
      "args": "x=42, y='hello'",
      "return_value": "{'result': 'OK'}",
      "start": 1234567890.123,
      "end": 1234567890.456,
      "elapsed_ms": 333.0,
      "children": [...]
    }
  ]
}
```

### HTML Output

```bash
tph tree trace.json --format html -o report.html
```

Creates interactive HTML with:
- Collapsible tree structure
- Color-coded timing (green/yellow/red)
- Syntax highlighting
- Dark theme

## Common Use Cases

### Debug API Handler

```python
from flask import Flask
from tracepatch import trace

app = Flask(__name__)

@app.route('/api/user/<user_id>')
@trace(label="api-user")
def get_user(user_id):
    user = fetch_from_db(user_id)
    enrich_user_data(user)
    return jsonify(user)
```

### Trace Specific Request

```python
from fastapi import FastAPI, Request
from tracepatch import trace

app = FastAPI()

@app.middleware("http")
async def trace_requests(request: Request, call_next):
    # Only trace requests with special header
    if "X-Debug-Trace" in request.headers:
        async with trace(label=f"request-{request.url.path}"):
            response = await call_next(request)
    else:
        response = await call_next(request)
    return response
```

### Debug Background Task

```python
from celery import Celery
from tracepatch import trace

app = Celery('tasks')

@app.task
@trace(label="celery-process")
def process_user_data(user_id):
    user = fetch_user(user_id)
    validate_user(user)
    save_results(user)
```

### Test-Driven Development

```python
import pytest
from tracepatch import trace

def test_complex_workflow():
    """Trace test execution to debug failures."""
    with trace(label="test-workflow") as t:
        result = complex_workflow(input_data)
    
    if not result:
        # Save trace for debugging
        t.to_json(f"/tmp/failed-test-{t._trace_id}.json")
        
    assert result
```

## Performance

- **Overhead when inactive:** ~0ns (no hooks installed)
- **Overhead when active:** ~5–10μs per function call
- **Memory:** ~1KB per captured call (includes args/return repr)
- **Recommended limits:**
  - `max_calls=10000` for typical requests (~10ms overhead)
  - `max_depth=30` to avoid deep recursion overhead
  - `max_time=60` to auto-stop runaway traces

## Documentation

- [Quickstart](docs/quickstart.md) — first trace in 60 seconds
- [Configuration Reference](docs/configuration.md) — every option explained
- [CLI Guide](docs/cli-guide.md) — all commands and flags
- [Reading the Call Tree](docs/reading-tree.md) — understanding output
- [Reading Trace Logs](docs/reading-logs.md) — JSON schema reference
- [API Reference](docs/api-reference.md) — Python API docs
- [Changelog](CHANGELOG.md) — version history

## Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT License. See [LICENSE](LICENSE) for details.
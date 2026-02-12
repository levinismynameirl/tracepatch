# tracepatch

Focused, opt-in runtime call tracing for a single execution context with production-ready safety features.

tracepatch is a debugging tool that records function calls, arguments, return values, and timing for one specific scope (a request handler, a CLI command, a background task) and produces a readable call tree. It's not a replacement for OpenTelemetry, structured logging, or APM dashboards. Think of it as a scalpel: you point it at one execution path that is misbehaving, and it tells you exactly what happened. Leave tracepatch installed in production - it has **zero overhead when inactive**.

## Features

### Core Capabilities
- **Zero overhead when inactive** - profiling hook only active inside `trace()` blocks
- **Pure Python** - no external dependencies for core tracing (optional TOML support via `tomli` on Python <3.11)
- **Full async/await support** - works in synchronous and asynchronous code
- **Context-isolated tracing** - concurrent async tasks don't interfere (uses `contextvars`)
- **Thread-safe** - each trace gets a unique ID for correlation in multi-threaded scenarios

### Safety & Performance
- **Built-in safety limits:** `max_depth`, `max_calls`, `max_time` - auto-disable if exceeded
- **Error resilience** - catches circular references, `__repr__` failures, doesn't affect traced code
- **Production-safe** - environment variable `TRACEPATCH_ENABLED=0` disables globally
- **Memory-efficient** - safe repr with truncation, circular reference detection

### Multiple Output Formats
- **Human-readable ASCII trees** with timing information
- **Colorized output** - green (fast), yellow (slow), red (very slow) based on duration
- **JSON export** for machine processing and custom analysis
- **HTML output** - interactive collapsible tree view with syntax highlighting

### Developer Experience
- **Decorator support** - use `@trace()` on functions, async functions, generators, async generators
- **Powerful CLI** (`tph`/`tracepatch`) - view logs, display trees, filter/limit depth
- **Tree filtering** - `--filter 'myapp.*'` or `--filter '!unittest'` to focus on relevant calls
- **Depth limiting** - `--depth 3` to show only top-level calls
- **TOML configuration** via `tracepatch.toml` or `pyproject.toml`
- **Environment overrides** - `TRACEPATCH_MAX_DEPTH`, `TRACEPATCH_MAX_CALLS`, etc.
- **Allowlist mode** - `include_modules` for tracing only specific modules

### Testing & Automation
- **Auto test setup** - `tph setup` instruments functions from config
- **Custom test scripts** - `[test.custom]` section for complete control  
- **Automatic caching** - traces saved to `.tracepatch_cache/` for later review
- **Git-aware safety** - warns about staged changes before operations

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

### List Traces

```bash
tph logs                    # List recent traces
tph logs --limit 10         # Show only 10 most recent
tph logs --cache-dir /path  # Search custom directory
```

### View Trace Tree

```bash
tph tree trace.json         # Display call tree
tph tree trace.json --color # Colorize by duration
tph tree trace.json --filter 'myapp.*'  # Show only myapp calls
tph tree trace.json --filter '!logging' #  Exclude logging calls
tph tree trace.json --depth 3           # Limit to 3 levels
```

### Export Formats

```bash
tph tree trace.json --format json       # Machine-readable JSON
tph tree trace.json --format html -o trace.html  # Interactive HTML
```

### Configuration

```bash
tph config              # Show current configuration
tph config --file custom.toml  # Load specific config
```

### Test Setup

```bash
tph setup               # Generate test runner from config
tph disable             # Clean up test environment
```

### Environment Variables

```bash
export TRACEPATCH_ENABLED=0        # Disable globally
export TRACEPATCH_MAX_DEPTH=10     # Override max_depth
export TRACEPATCH_MAX_CALLS=5000   # Override max_calls
export TRACEPATCH_COLOR=1          # Enable colored output
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
- **Overhead when active:** ~5-10μs per function call
- **Memory:** ~1KB per captured call (includes args/return repr)
- **Recommended limits:**
  - `max_calls=10000` for typical requests (~10ms overhead)
  - `max_depth=30` to avoid deep recursion overhead
  - `max_time=60` to auto-stop runaway traces

## Comparison With Other Tools

| Tool | Use Case | Overhead | Scope |
|------|----------|----------|-------|
| **tracepatch** | Focused debugging, one execution | Low | Single scope |
| OpenTelemetry | Distributed tracing, observability | Medium | Multi-service |
| cProfile | Performance profiling | Medium | Whole program |
| pdb/breakpoint | Interactive debugging | N/A | Manual |
| logging | Structured events | Low | Whole program |

## Limitations

- **Not for profiling:** Use `cProfile` or `py-spy` for performance analysis
- **Not for distributed tracing:** Use OpenTelemetry for multi-service workflows  
- **Not for audit logging:** Use structured logging for compliance
- **Synchronous tracing only:** No cross-task tracing (each async task isolated)

## Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT License. See [LICENSE](LICENSE) for details.

## Changelog

### v0.3.2 (2026-02-12)

**Bug Fixes:**
- Fixed double-nested cache directory issue
- Fixed `tph logs` not finding traces
- Added `unittest.mock` to default ignore list  
- Custom test scripts now respected by `tph setup`

**New Features:**
- `@trace()` decorator support (functions, async, generators, async generators)
- Tree filtering: `tph tree --filter 'pattern'`
- Depth limiting: `tph tree --depth N`
- Multiple output formats: JSON, HTML, colored text
- `max_time` parameter for auto-stop
- Circular reference detection
- Improved error handling (never crashes traced code)
- `include_modules` allowlist mode
- Environment variable overrides
- `tph init` command for starter config
- Unique `trace_id` for thread correlation
- Colorized output by duration

**Improvements:**
- Better `__repr__` failure handling
- Thread-safe trace isolation
- Enhanced CLI help and error messages

### v0.1.0 (2025-01-15)

Initial release
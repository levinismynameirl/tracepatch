# tracepatch

Focused, opt-in runtime call tracing for a single execution context.

tracepatch is a debugging tool. It records function calls, arguments, return
values, and timing for one specific scope (a request handler, a CLI command,
a background task) and produces a readable call tree. It is not a replacement
for OpenTelemetry, structured logging, or APM dashboards. Think of it as a
scalpel: you point it at one execution path that is misbehaving, and it tells
you exactly what happened. It is recommended you leave tracepatch installed in production and have it ready to use when you need it, since it has zero overhead when not active.

## Features

- Pure Python, no external dependencies.
- Zero overhead when inactive. Safe to leave installed in production; the
  profiling hook is only active inside a `trace()` block.
- Works in synchronous and asynchronous code.
- Uses `contextvars` to isolate traces per async task. Concurrent requests
  on the same event loop do not interfere with each other.
- Built-in safety limits (`max_depth`, `max_calls`) that automatically
  disable tracing if exceeded, preventing runaway overhead.
- Human-readable ASCII call tree output with timing.
- JSON export for further processing.
- Recommended to be used in production, can help diagnose issues that only occur in production environments, or issues that weren't caught in staging, they will show up in the trace and can be analyzed. Leaves no overhead when not in use, so it's safe to have it installed and ready to go when you need it.

## Installation

```
pip install tracepatch
```

Or install from source:

```
pip install .
```

## Quick start

### Synchronous

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

Output:

```
└── __main__.handle_request()  [0.03ms]
    └── __main__.fetch_user(user_id=42) -> {'id': 42, 'name': 'Alice'}  [0.01ms]
```

### Asynchronous

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

### JSON export

```python
with trace() as t:
    handle_request()

t.to_json("trace.json")
```

The JSON file contains a structured representation of the call tree with
timing in milliseconds, suitable for custom analysis scripts.

## Configuration

The `trace()` constructor accepts the following keyword arguments:

| Parameter        | Default | Description                                                |
|------------------|---------|------------------------------------------------------------|
| `ignore_modules` | `[]`    | List of module name prefixes to exclude from the trace.    |
| `max_depth`      | `30`    | Maximum call nesting depth. Deeper calls are silently skipped. |
| `max_calls`      | `10000` | Maximum total calls to record. Tracing freezes when exceeded. |
| `max_repr`       | `120`   | Maximum character length for `repr()` of arguments and return values. |

### Filtering noise

```python
with trace(ignore_modules=["logging", "urllib3", "ssl"]) as t:
    handle_request()

print(t.tree())
```

### Limiting scope

```python
with trace(max_depth=5, max_calls=500) as t:
    handle_request()

if t.was_limited:
    print("Warning: trace was truncated due to limits")

print(t.tree())
```

## API reference

### `trace(**kwargs)`

Context manager (sync and async). Returns itself. Configuration via keyword
arguments listed above.

### `t.tree() -> str`

Returns a human-readable ASCII call tree string with timing information for
each call.

### `t.to_json(path) -> None`

Writes the trace to a JSON file. `path` can be a string, a `pathlib.Path`,
or a writable file object.

### `t.call_count -> int`

Number of calls recorded.

### `t.was_limited -> bool`

True if the trace was cut short because `max_calls` was exceeded.

### `t.roots -> list[TraceNode]`

Direct access to the root `TraceNode` objects for programmatic traversal.

## How it works

tracepatch uses `sys.settrace` to install a lightweight tracing callback
that fires on function call, return, and exception events in the current
thread. On a 'call' event, the global trace function checks a
`contextvars.ContextVar` to find the active collector for the current
execution context. If no collector is active (the common case in production),
the callback returns `None` immediately and Python does not trace that frame
further, so overhead is negligible.

When a `trace()` block is entered, a new collector is created and stored in
the ContextVar. The collector records call events into a tree of `TraceNode`
objects. When the block exits, the profiling hook is removed (reference
counted, so nested traces work correctly) and the ContextVar is reset.

Because isolation is done through `contextvars` rather than thread-locals,
concurrent `asyncio` tasks each get their own independent trace even though
they share a single thread.

## Limitations

- `sys.settrace` captures Python-level calls in the thread while
  active. C-level functions (builtins, C extensions) are not captured.
- There is measurable overhead while a trace block is active. This is a
  debugging tool meant for targeted use, not always-on instrumentation.
- Traces are scoped to a single thread. If your code spawns threads, only
  the originating thread is traced by default.

## License

MIT. See LICENSE for the full text.

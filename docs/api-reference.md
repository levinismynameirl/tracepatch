# API Reference

Complete reference for the public Python API.

## `trace` Class

The primary interface.  Use as a context manager (sync or async) or as
a decorator.

### Constructor

```python
trace(
    label: str | None = None,
    *,
    max_depth: int = 30,
    max_calls: int = 10000,
    max_repr: int = 120,
    max_time: float = 60.0,
    ignore_modules: Sequence[str] = (),
    include_modules: Sequence[str] = (),
    cache: bool = True,
    cache_dir: str | Path | None = None,
)
```

| Parameter | Default | Description |
|---|---|---|
| `label` | `None` | Human-readable name for this trace |
| `max_depth` | `30` | Max call-stack nesting depth |
| `max_calls` | `10000` | Stop after N calls |
| `max_repr` | `120` | Max repr length for args/returns |
| `max_time` | `60.0` | Max seconds before auto-stop |
| `ignore_modules` | `()` | Module prefixes to exclude |
| `include_modules` | `()` | Allowlist mode (empty = all) |
| `cache` | `True` | Auto-save to `.tracepatch/traces/` |
| `cache_dir` | `None` | Override trace storage directory |

### Context Manager (Sync)

```python
with trace(label="my-op") as t:
    my_function()
print(t.tree())
```

### Context Manager (Async)

```python
async with trace(label="my-op") as t:
    await my_coroutine()
```

### Decorator

```python
@trace(label="api-handler")
def handle_request():
    ...

@trace(label="async-task")
async def background_job():
    ...
```

Each invocation of the decorated function creates an independent trace.

### Instance Methods

#### `t.tree(**kwargs) -> str`

Render the captured call tree as a string.

```python
print(t.tree())
print(t.tree(style="unicode", show_args=False))
```

Keyword arguments are forwarded to `render_tree()`.

#### `t.to_json(path: str | Path | None = None) -> str`

Serialise the trace to JSON.  If *path* is given, write to that file
and return the JSON string.  If *path* is `None`, return the string
without writing.

#### `t.summary() -> TraceSummary`

Return a `TraceSummary` computed from the captured tree.

### Class Methods

#### `trace.load(path: str | Path) -> dict`

Load and parse a saved JSON trace file.

#### `trace.logs(cache_dir=None, limit=50) -> list[dict]`

List saved traces from `.tracepatch/traces/`, sorted newest-first.

### Instance Attributes

| Attribute | Type | Description |
|---|---|---|
| `t.was_limited` | `bool` | Whether any safety limit was triggered |
| `t.call_count` | `int` | Number of calls recorded |
| `t.roots` | `list[TraceNode]` | Top-level trace nodes |

---

## `TraceNode` Dataclass

Represents a single function call in the trace tree.

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Function name |
| `module` | `str` | Module name |
| `args` | `str` | Stringified arguments |
| `return_value` | `str \| None` | Stringified return value |
| `exception` | `str \| None` | Exception string |
| `start` | `float` | Start timestamp |
| `end` | `float` | End timestamp |
| `elapsed` | `float` | Duration in seconds |
| `children` | `list[TraceNode]` | Child calls |
| `depth` | `int` | Nesting depth |
| `file` | `str \| None` | Source file path |
| `lineno` | `int \| None` | Source line number |

---

## `TraceSummary` Dataclass

Lightweight summary computed from a trace tree.

| Field | Type | Description |
|---|---|---|
| `call_count` | `int` | Total function calls |
| `max_depth_reached` | `int` | Deepest nesting level |
| `unique_functions` | `set[str]` | Set of `module.function` strings |
| `unique_modules` | `set[str]` | Set of module names |
| `total_duration_ms` | `float` | Sum of root durations (ms) |
| `slowest_call_ms` | `float` | Slowest single call (ms) |
| `slowest_call_name` | `str` | Name of the slowest call |
| `most_called` | `list[tuple[str, int]]` | Top 10 most-called functions |

### Class Method

```python
summary = TraceSummary.from_roots(roots)
```

---

## `TracepatchConfig` Dataclass

Frozen configuration object loaded from TOML.

```python
from tracepatch import TracepatchConfig, load_config

config, path = load_config()
print(config.max_depth)
```

See [Configuration Reference](configuration.md) for all fields.

### Key Methods

#### `config.to_trace_kwargs() -> dict`

Convert config to keyword arguments for `trace()`.

```python
with trace(**config.to_trace_kwargs()) as t:
    ...
```

#### `config.to_trace_config() -> TraceConfig`

Convert to the internal immutable `TraceConfig`.

#### `config._validate() -> list[str]`

Validate configuration.  Returns a list of warning strings.
Raises `ConfigError` on invalid values.

---

## `load_config(path=None) -> tuple[TracepatchConfig, Path | None]`

Load configuration from a TOML file.

Search order:
1. Explicit *path* argument
2. `tracepatch.toml` in CWD and parent directories
3. `pyproject.toml` `[tool.tracepatch]` in CWD and parent directories
4. Built-in defaults (when no file found)

Returns a tuple of `(config, config_path)` where `config_path` is
`None` when defaults are used.

---

## `ConfigError` Exception

Raised by `TracepatchConfig._validate()` when configuration values are
invalid (wrong type, out of range, invalid enum).

```python
from tracepatch import ConfigError

try:
    config._validate()
except ConfigError as e:
    print(f"Invalid config: {e}")
```

---

## Utility Functions

### `render_tree(roots, **kwargs) -> str`

Render trace nodes as an ASCII/Unicode call tree.

| Keyword | Default | Description |
|---|---|---|
| `style` | `"ascii"` | `"ascii"`, `"unicode"`, or `"ansi"` |
| `show_args` | `True` | Show arguments |
| `show_return` | `True` | Show return values |
| `show_source` | `False` | Show file:line |
| `show_self_time` | `False` | Show self-time |

### `fold_repeated_calls(nodes, threshold=3) -> list[TraceNode]`

Fold consecutive identical sibling calls into summary nodes.

### `render_summary_header(roots, label=None) -> str`

Render a statistics header for the tree.

### `collapse_tree(nodes, max_depth=4) -> list[TraceNode]`

Auto-collapse subtrees beyond the given depth.

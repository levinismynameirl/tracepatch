# tracepatch

Focused, opt-in runtime call tracing for a single execution context.

tracepatch is a debugging tool. It records function calls, arguments, return
values, and timing for one specific scope (a request handler, a CLI command,
a background task) and produces a readable call tree. It is not a replacement
for OpenTelemetry, structured logging, or APM dashboards. Think of it as a
scalpel: you point it at one execution path that is misbehaving, and it tells
you exactly what happened. It is recommended you leave tracepatch installed in production and have it ready to use when you need it, since it has zero overhead when not active.

## Features

- **Pure Python**, no external dependencies for core tracing (optional TOML support requires `tomli` on Python <3.11).
- **Zero overhead when inactive**. Safe to leave installed in production; the profiling hook is only active inside a `trace()` block.
- **Works in synchronous and asynchronous code** with full async/await support.
- **Context-isolated tracing** using `contextvars` - concurrent async tasks don't interfere with each other.
- **Built-in safety limits** (`max_depth`, `max_calls`) that automatically disable tracing if exceeded.
- **TOML configuration** support via `tracepatch.toml` or `pyproject.toml` files.
- **Powerful CLI** (`tph` / `tracepatch`) for viewing logs, displaying trees, and managing test environments.
- **Automated test setup** - automatically instrument functions for tracing with `tph setup`.
- **Git-aware safety checks** - warns about staged changes before setup/disable operations.
- **Human-readable ASCII call tree** output with timing information.
- **JSON export** for further processing and custom analysis.
- **Automatic caching** of traces to `.tracepatch_cache/` for later review.

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

### TOML Configuration Files

Instead of passing parameters directly, you can configure tracepatch via TOML files. tracepatch will automatically search for:

1. `tracepatch.toml` in the current or parent directories
2. `[tool.tracepatch]` section in `pyproject.toml`

Example `tracepatch.toml`:

```toml
# Modules to ignore during tracing (by prefix)
ignore_modules = ["urllib3", "requests", "http"]

# Maximum call nesting depth to record
max_depth = 50

# Maximum total calls to record before disabling tracing
max_calls = 20000

# Maximum character length for repr() of arguments and return values
max_repr = 200

# Enable automatic caching of traces
cache = true

# Custom cache directory (default: .tracepatch_cache)
# cache_dir = ".traces"

# Default label for traces (appears in logs)
default_label = "my-app"

# Automatically save traces to cache
auto_save = true

# Display settings
show_args = true
show_return = true
tree_style = "ascii"  # or "unicode"

# Test setup configuration (optional)
# Used by 'tph setup' command to generate test runners
[[test.files]]
path = "mymodule.py"
functions = ["my_function", "process_data"]

[[test.inputs]]
function = "my_function"
args = [42, "test"]
kwargs = {user_id = "abc123"}
```

Using config files in code:

```python
from tracepatch import trace, load_config

# Load configuration from TOML files
config, config_path = load_config()

# Use the configuration
with trace(**config.to_trace_kwargs()) as t:
    my_function()

print(t.tree())
```

## Command-Line Interface

tracepatch includes a powerful CLI for viewing traces and managing test environments. Two commands are available: `tracepatch` and the shorter alias `tph` (recommended).

### List cached traces

```bash
$ tph logs
```

Lists all trace logs in `.tracepatch_cache/` with timestamps, labels, and call counts.

Options:
- `--cache-dir DIR` - Specify custom cache directory
- `--limit N` - Limit number of results (default: 50)

### View trace metadata

```bash
$ tph view .tracepatch_cache/trace_20260212_143022_123456.json
```

Shows detailed metadata:
- Timestamp and label
- Call count and limit status
- Configuration used (max_depth, max_calls, etc.)
- Root function summary

### Display call tree

```bash
$ tph tree .tracepatch_cache/trace_20260212_143022_123456.json
```

Renders the full call tree with timing from a saved trace file.

Options:
- `--max-depth N` - Limit tree depth for readability
- `--show-args / --no-args` - Toggle argument display
- `--show-return / --no-return` - Toggle return value display

### Show configuration

```bash
$ tph config
```

Displays current configuration loaded from TOML files. Shows:
- Configuration file location (or defaults if none found)
- All tracing settings
- Test configuration if present

If no config file is found, shows helpful instructions on how to create one.

Options:
- `--file PATH` - Check specific config file

### Help

```bash
$ tph help
```

Shows comprehensive usage information with examples for all commands.

### Automated test setup workflow

tracepatch can automatically instrument and test specific functions from your configuration. This is especially useful for backend Python projects where functions might not work in isolation.

#### Quick start

```bash
# Set up test environment (reads tracepatch.toml)
$ tph setup

# Run the generated test file
$ python _tracepatch_filetotest.py

# Clean up when done
$ tph disable
```

#### Configuration

First, create a `tracepatch.toml` with test configuration:

```toml
# Basic tracing settings
max_depth = 50
max_calls = 20000
cache = true
default_label = "test-run"

# Specify which files and functions to test
[[test.files]]
path = "mymodule.py"
functions = ["my_function", "process_data", "calculate"]

[[test.files]]
path = "database.py"
functions = ["connect", "query"]

# Optional: Provide custom test inputs
[[test.inputs]]
function = "my_function"
args = [42, "test"]
kwargs = {user_id = "abc123"}

[[test.inputs]]
function = "calculate"
args = [10, 20]
kwargs = {}
```

#### Running `tph setup`

The setup command:

1. **Checks Git status** (if Git is available)
   - ⚠️  Warns if you have staged changes and asks for confirmation
   - ℹ️  Notes if you have unstaged changes
   - Continues safely if no Git or no changes

2. **Validates configuration**
   - Checks that all configured files exist
   - Verifies function signatures using AST parsing
   - Reports missing files or functions

3. **Creates necessary files**
   - Generates `__init__.py` if needed (makes directory a Python package)
   - Creates `_tracepatch_filetotest.py` with wrapper functions
   - Auto-generates default arguments for functions without custom inputs

4. **Saves setup state**
   - Stores state in `.tracepatch_cache/setup_state.json`
   - Records all created and modified files
   - **Important**: Don't delete `.tracepatch_cache/` - needed for cleanup!

#### Running the test file

The generated `_tracepatch_filetotest.py`:

- Imports and wraps your functions
- Creates wrapper functions that enable tracing
- Calls each function with configured or auto-generated inputs
- Displays results with ✓ (success) or ✗ (exception) indicators
- Shows full call tree with timing
- Saves trace to cache for later review

```bash
$ python _tracepatch_filetotest.py
Testing functions from tracepatch configuration...

Testing functions from mymodule.py:
  ✓ my_function returned: 123
  ✓ process_data returned: [1, 2, 3]
  ✗ calculate raised: TypeError: missing required argument

======================================================================
TRACE RESULTS
======================================================================
Total calls: 47

Trace saved to: .tracepatch_cache/trace_20260212_143802_618610_test-run.json
View with: tph tree .tracepatch_cache/trace_20260212_143802_618610_test-run.json

[Call tree output...]
```

#### Running `tph disable`

The disable command:

1. **Checks Git status** (if Git is available)
   - ⚠️  Warns if you have staged changes
   - Asks for confirmation before proceeding

2. **Cleans up generated files**
   - Removes `_tracepatch_filetotest.py`
   - Removes `__init__.py` if it was created by setup
   - Restores any modified files to their original state

3. **Preserves traces**
   - Keeps `.tracepatch_cache/` directory and all trace logs
   - Only removes the setup state file
   - Traces remain available for analysis with `tph logs`, `tph tree`, etc.

#### Error handling

If you run `tph setup` without a configuration file:

```
❌ Error: No tracepatch configuration file found!

What to do:
  1. Create a 'tracepatch.toml' file in your project directory
  2. OR add a [tool.tracepatch] section to your pyproject.toml

Example tracepatch.toml:
[Full example shown...]
```

If your config file exists but has no test configuration:

```
❌ Error: No test files configured!

Configuration loaded from: /path/to/tracepatch.toml
But no [[test.files]] section was found.

Add this to your config file:
[[test.files]]
path = "your_file.py"
functions = ["function_name"]
```

## Usage Examples

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

## Python API Reference

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

### `load_config(path=None, search_parents=True) -> tuple[TracepatchConfig, Path | None]`

Load configuration from TOML files.

**Parameters:**
- `path`: Optional explicit path to a TOML file
- `search_parents`: If True, search parent directories for config files

**Returns:**
- Tuple of (TracepatchConfig, config file path or None)

**Example:**
```python
from tracepatch import load_config, trace

config, config_path = load_config()
if config_path:
    print(f"Loaded from {config_path}")

with trace(**config.to_trace_kwargs()) as t:
    my_function()
```

### `TracepatchConfig`

Configuration dataclass with the following attributes:
- `ignore_modules`: List of module prefixes to exclude
- `max_depth`: Maximum call nesting depth
- `max_calls`: Maximum total calls to record
- `max_repr`: Maximum repr() length
- `cache`: Enable automatic caching
- `cache_dir`: Custom cache directory
- `default_label`: Default label for traces
- `auto_save`: Automatically save traces
- `show_args`: Show arguments in output
- `show_return`: Show return values in output
- `tree_style`: Tree rendering style ("ascii" or "unicode")

**Methods:**
- `to_trace_kwargs()`: Convert to kwargs dict for `trace()` constructor

### `trace.logs(cache_dir=None, limit=50) -> list[dict]`

Class method to list recent trace logs from `.tracepatch_cache/`.

**Parameters:**
- `cache_dir`: Optional parent directory containing `.tracepatch_cache/`
- `limit`: Maximum number of entries to return (default: 50)

**Returns:**
- List of dicts with metadata for each trace (timestamp, label, call_count, was_limited, file path)

**Example:**
```python
from tracepatch import trace

for entry in trace.logs():
    print(f"{entry['timestamp']} - {entry['label']}: {entry['call_count']} calls")
```

### `trace.load(path) -> dict`

Class method to load a complete trace log from a JSON file.

**Parameters:**
- `path`: Path to a trace JSON file

**Returns:**
- The full JSON contents as a dict

**Example:**
```python
from tracepatch import trace

data = trace.load(".tracepatch_cache/trace_20260212_143022_123456.json")
print(f"Trace had {data['call_count']} calls")
```

## Documentation

For detailed guides and examples, see the documentation in the `docs/` directory:

- **[CLI Guide](docs/cli-guide.md)** - Comprehensive guide to all CLI commands with examples
- **[Configuration Guide](docs/configuration.md)** - Complete reference for TOML configuration options
- **[Reading Logs](docs/reading-logs.md)** - Working with trace logs from Python and the command line

### Quick Links

- **CLI Commands**: See [CLI Guide](docs/cli-guide.md#available-commands) for `tph logs`, `tph tree`, `tph setup`, etc.
- **TOML Configuration**: See [Configuration Guide](docs/configuration.md#configuration-options) for all settings
- **Test Setup**: See [CLI Guide](docs/cli-guide.md#tph-setup) for automated testing workflow
- **Log Format**: See [Reading Logs](docs/reading-logs.md#json-structure) for JSON structure details

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

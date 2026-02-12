# Configuration Guide

tracepatch supports configuration via TOML files, allowing you to set default tracing behavior, display preferences, and automated test setups.

## Configuration File Locations

tracepatch automatically searches for configuration in the following order:

1. **`tracepatch.toml`** in the current directory
2. **`pyproject.toml`** with a `[tool.tracepatch]` section in the current directory
3. **Parent directories** - searches upward for the above files

You can also specify an explicit configuration file:

```python
from tracepatch import load_config

config, path = load_config(path="path/to/config.toml")
```

## Basic Configuration

Create a `tracepatch.toml` file in your project root:

```toml
# Tracing behavior
ignore_modules = ["urllib3", "requests", "http.client"]
max_depth = 50
max_calls = 20000
max_repr = 200

# Cache settings
cache = true
cache_dir = ".tracepatch_cache"
auto_save = true

# Display settings
show_args = true
show_return = true
tree_style = "ascii"
default_label = "my-app"
```

## Configuration Options

### Tracing Behavior

#### `ignore_modules` (list of strings)
**Default:** `[]`

List of module name prefixes to exclude from tracing. Any function whose module starts with one of these prefixes will not be recorded.

```toml
# Ignore all stdlib logging and HTTP libraries
ignore_modules = ["logging", "urllib3", "http", "ssl"]
```

Common modules to ignore:
- `"logging"` - Standard library logging
- `"urllib3"`, `"requests"` - HTTP client libraries
- `"http"`, `"ssl"` - Low-level networking
- `"json"`, `"yaml"` - Serialization (if very noisy)
- `"_pytest"` - pytest internals when debugging tests

#### `max_depth` (integer)
**Default:** `30`

Maximum call stack depth to record. Calls deeper than this are silently skipped. Useful for preventing excessive nesting in recursive functions.

```toml
# Allow deeper recursion tracing
max_depth = 100

# Or limit for quick overviews
max_depth = 10
```

#### `max_calls` (integer)
**Default:** `10000`

Maximum total number of function calls to record. When this limit is reached, tracing is automatically disabled to prevent runaway overhead. The trace will be marked as "limited".

```toml
# For large operations
max_calls = 50000

# For quick traces
max_calls = 1000
```

#### `max_repr` (integer)
**Default:** `120`

Maximum character length for `repr()` of arguments and return values. Longer representations are truncated with `...`.

```toml
# More detail in traces
max_repr = 500

# Minimal output
max_repr = 50
```

### Cache Settings

#### `cache` (boolean)
**Default:** `true`

Whether to automatically save traces to disk. When `true`, each completed trace is saved to a JSON file in the cache directory.

```toml
# Disable caching (useful for benchmarks/tests)
cache = false
```

#### `cache_dir` (string, optional)
**Default:** `".tracepatch_cache"`

Custom directory for storing trace logs. Relative paths are relative to the current working directory.

```toml
# Custom cache location
cache_dir = ".traces"

# Absolute path
cache_dir = "/tmp/my_traces"
```

#### `auto_save` (boolean)
**Default:** `true`

Automatically save traces when the `trace()` context exits. If `false`, you must manually call `t.to_json()`.

```toml
# Manual save control
auto_save = false
```

### Display Settings

#### `show_args` (boolean)
**Default:** `true`

Show function arguments in tree output and trace logs.

```toml
# Hide arguments for cleaner output
show_args = false
```

#### `show_return` (boolean)
**Default:** `true`

Show return values in tree output and trace logs.

```toml
# Hide return values
show_return = false
```

#### `tree_style` (string)
**Default:** `"ascii"`

Tree rendering style. Options:
- `"ascii"` - ASCII box characters (`|`, `+`, `-`)
- `"unicode"` - Unicode box drawing characters (`│`, `├`, `─`)

```toml
# Use Unicode for prettier trees
tree_style = "unicode"
```

#### `default_label` (string, optional)
**Default:** `null`

Default label applied to all traces unless overridden. Labels appear in log filenames and `tph logs` output.

```toml
# All traces get this label by default
default_label = "my-application"
```

## Test Configuration

Test configuration enables the `tph setup` / `tph disable` workflow for automated function testing.

### Basic Test Setup

```toml
[[test.files]]
path = "mymodule.py"
functions = ["function1", "function2"]

[[test.files]]
path = "database.py"
functions = ["connect", "query", "disconnect"]
```

### With Custom Inputs

Provide specific arguments for testing:

```toml
[[test.files]]
path = "calculator.py"
functions = ["add", "multiply", "divide"]

# Custom test inputs
[[test.inputs]]
function = "add"
args = [5, 3]
kwargs = {}

[[test.inputs]]
function = "multiply"
args = [4, 7]
kwargs = {}

[[test.inputs]]
function = "divide"
args = [10, 2]
kwargs = {check_zero = true}
```

### Auto-Generated Inputs

If you don't specify `[[test.inputs]]` for a function, tracepatch will attempt to generate reasonable default values:

- `int` / `float` parameters → `0`
- `str` parameters → `"test"`
- `bool` parameters → `True`
- `list` parameters → `[]`
- `dict` parameters → `{}`
- Other types → `None`

### Multiple Files Example

```toml
[[test.files]]
path = "auth.py"
functions = ["login", "logout", "validate_token"]

[[test.files]]
path = "api/handlers.py"
functions = ["handle_get", "handle_post"]

[[test.files]]
path = "utils/helpers.py"
functions = ["parse_date", "format_response"]

# Provide inputs only where needed
[[test.inputs]]
function = "login"
args = ["testuser", "password123"]
kwargs = {}

[[test.inputs]]
function = "parse_date"
args = ["2026-02-12"]
kwargs = {}
```

## Using Configuration in Code

### Load and use configuration

```python
from tracepatch import trace, load_config

# Load configuration from TOML files
config, config_path = load_config()

if config_path:
    print(f"Loaded config from: {config_path}")
else:
    print("Using default configuration")

# Use configuration with trace
with trace(**config.to_trace_kwargs()) as t:
    my_function()

print(t.tree())
```

### Override specific settings

```python
from tracepatch import trace, load_config

config, _ = load_config()

# Use config but override label
trace_kwargs = config.to_trace_kwargs()
trace_kwargs['label'] = 'special-debug-session'

with trace(**trace_kwargs) as t:
    my_function()
```

### Access configuration values

```python
from tracepatch import load_config

config, _ = load_config()

# Access configuration attributes
print(f"Max depth: {config.max_depth}")
print(f"Max calls: {config.max_calls}")
print(f"Ignored modules: {config.ignore_modules}")

# Check test configuration
for file_config in config.test.files:
    print(f"Test file: {file_config.path}")
    print(f"Functions: {', '.join(file_config.functions)}")
```

## Configuration in pyproject.toml

Instead of a separate `tracepatch.toml`, you can add configuration to your existing `pyproject.toml`:

```toml
[tool.tracepatch]
ignore_modules = ["urllib3", "requests"]
max_depth = 50
max_calls = 20000
cache = true
default_label = "my-app"

[[tool.tracepatch.test.files]]
path = "mymodule.py"
functions = ["my_function"]

[[tool.tracepatch.test.inputs]]
function = "my_function"
args = [42]
kwargs = {}
```

## Environment-Specific Configuration

You can maintain different configurations for different purposes:

### tracepatch.toml (production-safe defaults)
```toml
max_depth = 30
max_calls = 10000
ignore_modules = ["logging", "urllib3"]
cache = true
```

### tracepatch-debug.toml (deep debugging)
```toml
max_depth = 100
max_calls = 50000
max_repr = 500
ignore_modules = []  # Don't ignore anything
cache = true
default_label = "deep-debug"
```

### tracepatch-test.toml (automated testing)
```toml
max_depth = 50
max_calls = 20000
cache = true
default_label = "test-run"

[[test.files]]
path = "mymodule.py"
functions = ["func1", "func2"]
```

Load specific config:

```python
config, _ = load_config(path="tracepatch-debug.toml")
```

Or use environment variables:

```bash
# Set config path via environment
export TRACEPATCH_CONFIG="tracepatch-debug.toml"
```

## Validation and Errors

### Check your configuration

```bash
$ tph config
```

This displays your current configuration and shows whether a config file was found.

### Common issues

**No config file found:**
```
ℹ️  Using: default configuration (no config file found)

Searched for:
  - tracepatch.toml
  - pyproject.toml [tool.tracepatch]
```

**Solution:** Create a `tracepatch.toml` file or add `[tool.tracepatch]` to `pyproject.toml`.

**Invalid TOML syntax:**

If your TOML file has syntax errors, tracepatch will silently fall back to defaults. Validate your TOML:

```bash
# Install tomli (Python <3.11) or use Python 3.11+
python -c "import tomllib; tomllib.load(open('tracepatch.toml', 'rb'))"
```

**Missing test configuration:**

```
❌ Error: No test files configured!
```

**Solution:** Add `[[test.files]]` sections to your config.

## Best Practices

### Start with defaults

Begin with minimal config and add settings as needed:

```toml
# Minimal starting config
cache = true
default_label = "my-app"
```

### Use labels consistently

Choose a label strategy:
- Project name: `default_label = "myapp"`
- Environment: `default_label = "myapp-staging"`
- Team: `default_label = "backend-team"`

### Ignore noisy modules

Find noisy modules by looking at traces, then add to `ignore_modules`:

```toml
# Common noisy modules
ignore_modules = [
    "logging",
    "urllib3",
    "requests",
    "http",
    "ssl",
    "socketserver",
]
```

### Set realistic limits

Balance detail vs. performance:

```toml
# Moderate limits for most use cases
max_depth = 50
max_calls = 20000
max_repr = 200
```

### Separate test configs

Keep automated test configuration separate:

```toml
# Main config
max_depth = 30
cache = true

# Test config in separate section
[[test.files]]
path = "mymodule.py"
functions = ["critical_function"]
```

### Commit your config

Add `tracepatch.toml` to git so your team uses consistent settings:

```bash
git add tracepatch.toml
git commit -m "Add tracepatch configuration"
```

But keep `.tracepatch_cache/` in `.gitignore`:

```gitignore
# .gitignore
.tracepatch_cache/
```

## Example Configurations

### Web Application

```toml
ignore_modules = ["urllib3", "requests", "http", "ssl", "socketserver"]
max_depth = 40
max_calls = 15000
cache = true
default_label = "webapp"
show_args = true
show_return = true
```

### Data Processing Pipeline

```toml
ignore_modules = ["pandas._libs", "numpy"]
max_depth = 20
max_calls = 50000  # Large data operations
max_repr = 100  # Keep logs manageable
cache = true
default_label = "pipeline"
```

### API Client Library

```toml
ignore_modules = ["urllib3", "http", "ssl"]
max_depth = 30
max_calls = 5000
cache = true
default_label = "api-client"
show_args = true  # See API parameters
show_return = true  # See API responses
```

### Testing/Debugging

```toml
# In tracepatch-test.toml
max_depth = 100  # Deep recursion
max_calls = 100000  # Large operations
max_repr = 500  # Full details
ignore_modules = []  # Trace everything
cache = true
default_label = "debug"

[[test.files]]
path = "module.py"
functions = ["buggy_function"]

[[test.inputs]]
function = "buggy_function"
args = [42, "test"]
kwargs = {debug = true}
```

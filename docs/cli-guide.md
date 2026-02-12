# CLI Guide

The `tph` (tracepatch) command-line interface provides tools for viewing traces and managing test environments.

## Available Commands

| Command | Description |
|---------|-------------|
| `tph logs` | List cached trace logs |
| `tph view <file>` | View trace metadata and summary |
| `tph tree <file>` | Display call tree from trace |
| `tph config` | Show current configuration |
| `tph setup` | Set up automated test environment |
| `tph disable` | Clean up test environment |
| `tph help` | Show help information |

## Command Details

### tph logs

List all cached trace logs with timestamps, labels, and call counts.

```bash
$ tph logs
Found 3 trace log(s):

[1] 2026-02-12T14:38:02.618610 | test-run | 47 calls
    /path/to/.tracepatch_cache/trace_20260212_143802_618610_test-run.json

[2] 2026-02-12T14:27:57.579349 | tracepatch-example | 23 calls
    /path/to/.tracepatch_cache/trace_20260212_142757_579349_tracepatch-example.json

[3] 2026-02-12T14:24:49.862985 | tracepatch-example | 23 calls
    /path/to/.tracepatch_cache/trace_20260212_142449_862985_tracepatch-example.json
```

**Options:**
- `--cache-dir DIR` - Specify custom cache directory (default: `.tracepatch_cache`)
- `--limit N` - Maximum number of logs to display (default: 50)

**Examples:**

```bash
# List only the 10 most recent traces
$ tph logs --limit 10

# List traces from a custom directory
$ tph logs --cache-dir /tmp/my_traces
```

### tph view

View detailed metadata about a specific trace log.

```bash
$ tph view .tracepatch_cache/trace_20260212_143802_618610_test-run.json
```

**Output includes:**
- Timestamp and label
- Total call count
- Whether trace was limited (max_calls exceeded)
- Configuration used (max_depth, max_calls, etc.)
- Summary of root function calls

**Example output:**

```
======================================================================
TRACE LOG DETAILS
======================================================================
File: .tracepatch_cache/trace_20260212_143802_618610_test-run.json
Timestamp: 2026-02-12T14:38:02.618610
Label: test-run
Call count: 47
Was limited: False

Configuration:
  max_depth: 50
  max_calls: 20000
  max_repr: 200
  ignore_modules: ['urllib3', 'requests']

Root calls:
  - example.process_data (3 children)
```

### tph tree

Display the full call tree from a trace log with timing information.

```bash
$ tph tree .tracepatch_cache/trace_20260212_143802_618610_test-run.json
```

**Options:**
- `--max-depth N` - Limit tree depth for readability
- `--show-args` / `--no-args` - Control argument display
- `--show-return` / `--no-return` - Control return value display

**Examples:**

```bash
# Show only top 3 levels of calls
$ tph tree --max-depth 3 trace.json

# Hide arguments for cleaner output
$ tph tree --no-args trace.json

# Show tree without return values
$ tph tree --no-return trace.json
```

**Example output:**

```
└── example.process_data(items=[3, 5, 7]) -> [2, 5, 13]  [2.34ms]
    ├── example.calculate_fibonacci(n=3) -> 2  [0.15ms]
    │   ├── example.calculate_fibonacci(n=2) -> 1  [0.08ms]
    │   │   ├── example.calculate_fibonacci(n=1) -> 1  [0.02ms]
    │   │   └── example.calculate_fibonacci(n=0) -> 0  [0.02ms]
    │   └── example.calculate_fibonacci(n=1) -> 1  [0.02ms]
    ├── example.calculate_fibonacci(n=5) -> 5  [0.89ms]
    │   └── [25 nested calls...]
    └── example.calculate_fibonacci(n=7) -> 13  [1.12ms]
        └── [41 nested calls...]
```

### tph config

Display the current tracepatch configuration loaded from TOML files.

```bash
$ tph config
```

**Searches for configuration in:**
1. `tracepatch.toml` in current or parent directories
2. `[tool.tracepatch]` section in `pyproject.toml`

**Options:**
- `--file PATH` - Check a specific configuration file

**Example output with config file:**

```
======================================================================
TRACEPATCH CONFIGURATION
======================================================================
✓ Loaded from: /path/to/tracepatch.toml

Tracing behavior:
  max_depth: 50
  max_calls: 20000
  max_repr: 200
  ignore_modules: urllib3, requests, http

Cache settings:
  cache: True
  cache_dir: (default: .tracepatch_cache)
  auto_save: True

Display settings:
  show_args: True
  show_return: True
  tree_style: ascii
  default_label: my-app

Test configuration:
  example.py:
    - calculate_fibonacci()
    - process_data()
```

**Example output without config file:**

```
======================================================================
TRACEPATCH CONFIGURATION
======================================================================
ℹ️  Using: default configuration (no config file found)

Searched for:
  - tracepatch.toml
  - pyproject.toml [tool.tracepatch]

Create a 'tracepatch.toml' file to customize settings.

[Default settings displayed...]
```

### tph setup

Set up an automated test environment for tracing configured functions.

```bash
$ tph setup
```

**Prerequisites:**
- Must have a `tracepatch.toml` or `pyproject.toml` with `[tool.tracepatch]` section
- Configuration must include `[[test.files]]` sections

**What it does:**
1. Checks Git status (warns about staged changes)
2. Validates that configured files and functions exist
3. Creates `__init__.py` if needed
4. Generates `_tracepatch_filetotest.py` with wrapper functions
5. Saves setup state to `.tracepatch_cache/setup_state.json`

**Example output:**

```
Setting up tracepatch test environment...

ℹ️  Note: You have unstaged Git changes.
   tracepatch will create temporary files in your working directory.

Validating test configuration...
✓ Found example.py
  └─ calculate_fibonacci(n)
  └─ process_data(items)

Generating test runner: _tracepatch_filetotest.py
✓ Created test runner

======================================================================
Setup complete!
======================================================================

⚠️  IMPORTANT: Do not delete the .tracepatch_cache folder!
   It contains setup state needed for cleanup with 'tph disable'

Run tests with:
  python _tracepatch_filetotest.py

Cleanup with:
  tph disable
```

**Error handling:**

If no config file found:
```
❌ Error: No tracepatch configuration file found!

What to do:
  1. Create a 'tracepatch.toml' file in your project directory
  2. OR add a [tool.tracepatch] section to your pyproject.toml

[Example configuration shown...]
```

### tph disable

Clean up the test environment created by `tph setup`.

```bash
$ tph disable
```

**What it does:**
1. Checks Git status (warns about staged changes)
2. Removes generated files (`_tracepatch_filetotest.py`)
3. Removes `__init__.py` if it was created by setup
4. Restores any modified files
5. Removes setup state (but keeps trace logs)

**Example output:**

```
Cleaning up tracepatch test environment...

✓ Removed _tracepatch_filetotest.py
✓ Removed setup state

======================================================================
Cleanup complete!
======================================================================

The .tracepatch_cache folder and trace logs have been preserved.
```

**Git safety:**

If you have staged changes:
```
⚠️  Warning: You have staged Git changes:
   - example.py
   - src/module.py

   tracepatch will remove generated files that may affect your Git state.
   Continue? [y/N]: 
```

### tph help

Show comprehensive help information with examples.

```bash
$ tph help
```

Displays:
- All available commands
- Common usage examples
- Configuration examples
- Links to documentation

## Common Workflows

### Debugging a specific execution

```bash
# 1. Add tracing to your code
# with trace(label="bug-investigation") as t:
#     problematic_function()

# 2. Run your code
$ python my_script.py

# 3. View the trace
$ tph logs
$ tph tree .tracepatch_cache/trace_20260212_143802_618610_bug-investigation.json
```

### Testing multiple functions

```bash
# 1. Configure tests in tracepatch.toml
# [[test.files]]
# path = "mymodule.py"
# functions = ["func1", "func2", "func3"]

# 2. Set up test environment
$ tph setup

# 3. Run the generated tests
$ python _tracepatch_filetotest.py

# 4. Review traces
$ tph logs
$ tph tree .tracepatch_cache/trace_<timestamp>_test-run.json

# 5. Clean up
$ tph disable
```

### Comparing before/after changes

```bash
# 1. Trace before changes
$ python my_script.py  # with trace() block
$ tph logs  # Note the trace file

# 2. Make your changes

# 3. Trace after changes
$ python my_script.py

# 4. Compare
$ tph view trace_before.json
$ tph view trace_after.json

# Or use diff on the JSON files
$ diff <(python -m json.tool trace_before.json) \
       <(python -m json.tool trace_after.json)
```

## Tips

- Use the `tph` alias instead of `tracepatch` for faster typing
- Add meaningful labels to traces: `trace(label="checkout-flow")`
- Use `--limit` with `tph logs` for faster output when you have many traces
- The `.tracepatch_cache/` directory is automatically added to `.gitignore`
- Keep `.tracepatch_cache/` after `tph disable` - traces are valuable for analysis
- Use `--max-depth` with `tph tree` for cleaner output on deep call stacks
- Check `tph config` first to verify your TOML configuration is loaded correctly

# Configuration Reference

tracepatch is configured through TOML files, environment variables, or
direct Python keyword arguments. This page documents every option.

## Configuration Precedence

When multiple sources provide the same setting, the order is:

1. **Explicit Python keyword** — `trace(max_depth=5)` always wins
2. **Environment variables** — `TRACEPATCH_MAX_DEPTH=5`
3. **`tracepatch.toml`** — searched in CWD, then parent directories
4. **`pyproject.toml` `[tool.tracepatch]`** — fallback
5. **Built-in defaults** — always present

## Creating a Config File

```bash
tph init          # interactive prompts
tph init --yes    # skip prompts, use defaults
```

## Full Schema

```toml
# ── Tracing behaviour ──────────────────────────────────────────────
ignore_modules = ["logging", "urllib3"]   # Module prefixes to exclude
# include_modules = ["myapp"]            # Allowlist mode (empty = trace all)
max_depth = 30          # Max call-stack nesting depth
max_calls = 10000       # Stop tracing after this many calls
max_repr = 120          # Max length for repr() of args/returns
# max_repr_args = 80    # Override max_repr for arguments only
# max_repr_return = 200 # Override max_repr for return values only
max_time = 60.0         # Stop after this many seconds

# ── Cache / storage ────────────────────────────────────────────────
cache = true            # Auto-save traces to .tracepatch/traces/
auto_save = true        # Save on context-manager exit
# cache_dir = ".tracepatch"  # Override trace storage directory

# ── Display ────────────────────────────────────────────────────────
show_args = true        # Show function arguments in tree output
show_return = true      # Show return values in tree output
tree_style = "ascii"    # "ascii", "unicode", or "ansi"
color = false           # Colorise tree output by duration
# default_label = "my-app"  # Default label for all traces

# ── Test runner (`tph run`) ────────────────────────────────────────
[[test.files]]
path = "myapp/core.py"
functions = ["process", "validate"]

[[test.inputs]]
function = "process"
args = [42, "hello"]
kwargs = {}

[test.custom]
enabled = false
script = ""
```

## Option Reference

### `ignore_modules`

- **Type:** `list[str]`
- **Default:** `[]`
- **Description:** Module name prefixes to exclude from tracing. Any call
  whose module starts with one of these strings is silently skipped.

```toml
ignore_modules = ["logging", "urllib3", "ssl"]
```

### `include_modules`

- **Type:** `list[str]`
- **Default:** `[]` (trace everything)
- **Description:** When non-empty, **only** modules matching one of these
  prefixes are traced. All others are ignored. Takes priority over
  `ignore_modules`.

```toml
include_modules = ["myapp", "mylib"]
```

### `max_depth`

- **Type:** `int`
- **Default:** `30`
- **Valid range:** `1` – `1000`
- **Description:** Maximum call-stack nesting depth to record. Calls
  deeper than this are silently ignored.

### `max_calls`

- **Type:** `int`
- **Default:** `10000`
- **Valid range:** `0` – `1000000`
- **Description:** Stop recording after this many function calls. The
  trace continues to run but no new nodes are added. A value of `0`
  disables tracing entirely (zero overhead).

### `max_repr`

- **Type:** `int`
- **Default:** `120`
- **Description:** Maximum character length for `repr()` of arguments and
  return values. Longer strings are truncated with `...`.

### `max_repr_args`

- **Type:** `int | null`
- **Default:** `null` (falls back to `max_repr`)
- **Description:** Override `max_repr` for function argument strings only.
  Useful when you want shorter args but longer return values.

### `max_repr_return`

- **Type:** `int | null`
- **Default:** `null` (falls back to `max_repr`)
- **Description:** Override `max_repr` for return value strings only.

### `max_time`

- **Type:** `float`
- **Default:** `60.0`
- **Description:** Maximum wall-clock seconds before tracing automatically
  stops. Prevents runaway traces in production.

### `cache`

- **Type:** `bool`
- **Default:** `true`
- **Description:** Whether to auto-save traces to `.tracepatch/traces/`.

### `auto_save`

- **Type:** `bool`
- **Default:** `true`
- **Description:** Save on context-manager `__exit__`. When `false`, call
  `t.to_json(path)` manually.

### `cache_dir`

- **Type:** `str | null`
- **Default:** `null` (uses `.tracepatch`)
- **Description:** Override the parent directory for trace storage.

### `show_args`

- **Type:** `bool`
- **Default:** `true`
- **Description:** Include function arguments in tree/HTML output.

### `show_return`

- **Type:** `bool`
- **Default:** `true`
- **Description:** Include return values in tree/HTML output.

### `tree_style`

- **Type:** `str`
- **Default:** `"ascii"`
- **Valid values:** `"ascii"`, `"unicode"`, `"ansi"`
- **Description:** Tree connector style.
  - `ascii` — `├──`, `└──` (widest compatibility)
  - `unicode` — `├─`, `└─` (compact box-drawing)
  - `ansi` — same as `unicode` with dim-coloured connectors

### `color`

- **Type:** `bool`
- **Default:** `false`
- **Description:** Colorise tree output by call duration (green/yellow/red).
  Always disabled when stdout is not a TTY, regardless of this setting.

### `default_label`

- **Type:** `str | null`
- **Default:** `null`
- **Description:** Default label applied to all `trace()` calls that don't
  specify their own. Supports template variables:
  - `{hostname}` — `socket.gethostname()`
  - `{pid}` — `os.getpid()`
  - `{timestamp}` — ISO 8601 timestamp

```toml
default_label = "worker-{hostname}-{pid}"
```

## `pyproject.toml` Integration

All options can go under `[tool.tracepatch]`:

```toml
[tool.tracepatch]
max_depth = 50
max_calls = 20000
ignore_modules = ["urllib3"]

[[tool.tracepatch.test.files]]
path = "myapp/core.py"
functions = ["process"]
```

## Environment Variables

| Variable | Maps to | Example |
|---|---|---|
| `TRACEPATCH_ENABLED` | Enable/disable | `0` or `1` |
| `TRACEPATCH_MAX_DEPTH` | `max_depth` | `10` |
| `TRACEPATCH_MAX_CALLS` | `max_calls` | `5000` |
| `TRACEPATCH_MAX_REPR` | `max_repr` | `200` |
| `TRACEPATCH_MAX_TIME` | `max_time` | `30` |
| `TRACEPATCH_LABEL` | `default_label` | `"my-app"` |
| `TRACEPATCH_OUTPUT_DIR` | `cache_dir` | `"/tmp/traces"` |
| `TRACEPATCH_NO_CACHE` | `cache=false` | `1` |
| `TRACEPATCH_COLOR` | `color` | `1` |

Environment variables override TOML settings but are overridden by
explicit Python keyword arguments.

## Validation

```bash
tph config --validate   # exits 0 if valid, 1 if invalid
```

The validator checks:
- Unknown keys (warns for forward compatibility)
- Invalid types (e.g. `max_depth = "hello"`)
- Out-of-range values (e.g. `max_depth = -1`)
- Invalid enum values (e.g. `tree_style = "fancy"`)

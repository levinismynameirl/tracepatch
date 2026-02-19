# Reading Trace Logs

Trace log files are plain JSON stored in `.tracepatch/traces/`. This
guide explains the file naming, JSON schema, and how to work with them
programmatically.

## File Naming

```
{label}_{YYYYMMDD}_{HHMMSS}_{short-id}.json
```

Examples:

```
checkout-flow_20260219_143022_a1b2c3.json
trace_20260219_150000_def456.json
```

- **label** — the trace label, or `"trace"` if none was set
- **timestamp** — when the trace started (local time)
- **short-id** — first 6 characters of a UUID for uniqueness

Files are sorted by label first, then by timestamp. This makes
`ls` output naturally group related traces.

## JSON Schema

```json
{
  "tracepatch_version": "0.3.5",
  "schema_version": 1,
  "timestamp": "2026-02-19T14:30:22.123456",
  "label": "checkout-flow",
  "trace_id": "a1b2c3",
  "hostname": "my-machine",
  "python_version": "3.12.0",
  "platform": "darwin",
  "working_directory": "/path/to/project",
  "duration_ms": 42.3,
  "call_count": 150,
  "was_limited": false,
  "limit_reason": null,
  "config": {
    "max_depth": 30,
    "max_calls": 10000,
    "max_repr": 120,
    "ignore_modules": ["logging"]
  },
  "stats": {
    "max_depth_reached": 8,
    "unique_functions": 23,
    "unique_modules": 5,
    "slowest_call_ms": 12.3,
    "slowest_call_name": "db.query"
  },
  "trace": [...]
}
```

### Top-Level Fields

| Field | Type | Description |
|---|---|---|
| `tracepatch_version` | `str` | Library version that created the trace |
| `schema_version` | `int` | Schema version (currently `1`) |
| `timestamp` | `str` | ISO 8601 timestamp |
| `label` | `str\|null` | Trace label |
| `trace_id` | `str` | Short unique identifier |
| `hostname` | `str` | Machine hostname |
| `python_version` | `str` | Python version |
| `platform` | `str` | OS platform (`darwin`, `linux`, `win32`) |
| `working_directory` | `str` | Absolute path of the working directory |
| `duration_ms` | `float` | Total wall-clock time in milliseconds |
| `call_count` | `int` | Total function calls recorded |
| `was_limited` | `bool` | Whether any limit was triggered |
| `limit_reason` | `str\|null` | Which limit: `"max_calls"`, `"max_depth"`, `"max_time"`, or `null` |
| `config` | `object` | Configuration used for this trace |
| `stats` | `object` | Pre-computed summary statistics |
| `trace` | `array` | Array of root `TraceNode` objects |

### TraceNode Fields

Each node in the `trace` array has:

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Function name |
| `module` | `str` | Module name |
| `args` | `str` | Stringified arguments |
| `return_value` | `str\|null` | Stringified return value |
| `exception` | `str\|null` | Exception string if raised |
| `start` | `float` | Start time (`time.time()`) |
| `end` | `float` | End time |
| `elapsed_ms` | `float` | Elapsed time in milliseconds |
| `file` | `str\|null` | Source file path |
| `lineno` | `int\|null` | Source line number |
| `children` | `array` | Nested child calls |

## Working with Traces Programmatically

### Loading a Trace

```python
from tracepatch import trace

data = trace.load("path/to/trace.json")
print(data["label"])
print(data["call_count"])
```

### Listing Saved Traces

```python
logs = trace.logs()  # returns list of dicts with metadata
for entry in logs:
    print(entry["file"], entry["label"], entry["call_count"])
```

### Getting a Summary

```python
from tracepatch import trace

with trace(label="my-op") as t:
    my_function()

summary = t.summary()
print(f"Calls: {summary.call_count}")
print(f"Max depth: {summary.max_depth_reached}")
print(f"Slowest: {summary.slowest_call_name} [{summary.slowest_call_ms:.1f}ms]")
print(f"Unique functions: {len(summary.unique_functions)}")
```

## Storage Location

Traces are saved to `.tracepatch/traces/` relative to the working
directory. The directory structure is:

```
.tracepatch/
├── README.md           ← human-readable explanation
├── state.json          ← setup/cleanup state
└── traces/
    ├── .gitignore      ← contains "*" to exclude traces from git
    ├── checkout-flow_20260219_143022_a1b2c3.json
    └── trace_20260219_150000_def456.json
```

The `traces/` subdirectory is git-ignored. The top-level `.tracepatch/`
directory (including `state.json` and `README.md`) is intended to be
committed.

## Cleaning Up

```bash
tph clean --traces              # remove all trace files
tph clean --older-than 7d       # remove traces older than 7 days
tph clean --all                 # remove entire .tracepatch/ directory
```

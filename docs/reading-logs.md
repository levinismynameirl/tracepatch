# Reading trace logs

Every time a `trace()` block finishes with at least one recorded call,
tracepatch writes a JSON log file to the `.tracepatch_cache/` directory in
your working directory. These logs accumulate over time and serve as a
persistent record of past traces that you can inspect, compare, or feed
into other tools.

## Quick access with CLI

The easiest way to work with trace logs is through the `tph` CLI:

```bash
# List recent traces
$ tph logs

# View full call tree from a trace
$ tph tree .tracepatch_cache/trace_20260212_143022_817345.json

# View trace metadata and summary
$ tph view .tracepatch_cache/trace_20260212_143022_817345.json
```

See the [CLI documentation](../README.md#command-line-interface) for more details.

## Where logs are stored

By default, logs go to `.tracepatch_cache/` relative to the current working
directory. You can override this:

```python
with trace(cache_dir="/tmp/my_traces") as t:
    handle_request()
```

The directory is created automatically on first use. It contains:

- `.gitignore` -- contains `*`, so logs are never committed.
- `README` -- a short note explaining the directory.
- `trace_<timestamp>[_<label>].json` -- one file per trace.

## File naming

Log files are named with a timestamp and an optional label:

```
trace_20260212_143022_817345.json
trace_20260212_143055_012991_checkout_flow.json
```

The label comes from the `label` parameter:

```python
with trace(label="checkout_flow") as t:
    process_checkout(cart)
```

Labels make it easy to find the trace you care about when you have dozens of
log files.

## JSON structure

Each log file is a self-contained JSON document:

```json
{
  "tracepatch_version": "0.3.0",
  "timestamp": "2026-02-12T14:30:22.817345",
  "label": "checkout_flow",
  "call_count": 47,
  "was_limited": false,
  "config": {
    "max_depth": 30,
    "max_calls": 10000,
    "max_repr": 120,
    "ignore_modules": ["logging"]
  },
  "trace": [
    {
      "name": "process_checkout",
      "module": "app.checkout",
      "args": "cart=<Cart 3 items>",
      "return_value": "True",
      "start": 69384.728,
      "end": 69384.751,
      "elapsed_ms": 23.1,
      "children": [...]
    }
  ]
}
```

### Top-level fields

| Field                | Type   | Description                                           |
|----------------------|--------|-------------------------------------------------------|
| `tracepatch_version` | string | Library version that produced the log.                |
| `timestamp`          | string | ISO 8601 wall-clock time when the trace block opened. |
| `label`              | string | User-supplied label, or `null`.                       |
| `call_count`         | int    | Total number of function calls recorded.              |
| `was_limited`        | bool   | `true` if `max_calls` was hit and tracing stopped early. |
| `config`             | object | The configuration that was active during the trace.   |
| `trace`              | array  | List of root-level call nodes.                        |

### Call node fields

Each node in the `trace` tree has:

| Field          | Type   | Description                                        |
|----------------|--------|----------------------------------------------------|
| `name`         | string | Function or method name.                           |
| `module`       | string | Dotted module path (e.g., `app.checkout`).         |
| `args`         | string | Truncated repr of arguments at call time.          |
| `return_value` | string | Truncated repr of the return value, or `null`.     |
| `exception`    | string | Present only if the call raised. Format: `Type: message`. |
| `start`        | float  | `time.perf_counter()` timestamp at call entry.     |
| `end`          | float  | `time.perf_counter()` timestamp at call exit.      |
| `elapsed_ms`   | float  | Wall-clock elapsed time in milliseconds.           |
| `children`     | array  | Nested calls made during this function's execution. Present only if non-empty. |

The `start` and `end` values are monotonic clock readings from
`time.perf_counter()`. They are useful for computing relative offsets between
calls within a single trace, but they are not wall-clock times. Use the
top-level `timestamp` field for wall-clock reference.

## Listing past logs from Python

```python
from tracepatch import trace

# List the 10 most recent trace logs (newest first).
for entry in trace.logs(limit=10):
    print(entry["timestamp"], entry["label"], f'{entry["call_count"]} calls')
    print("  ", entry["file"])
```

Each entry in the list contains:

- `file` -- absolute path to the JSON log.
- `timestamp` -- ISO timestamp from the log.
- `label` -- the label, or `None`.
- `call_count` -- number of calls recorded.
- `was_limited` -- whether the trace was truncated.

## Loading a full log

```python
data = trace.load("/path/to/.tracepatch_cache/trace_20260212_143022_817345.json")

# data is the full JSON dict, including the "trace" tree.
for node in data["trace"]:
    print(node["module"], node["name"], node["elapsed_ms"], "ms")
```

Or use the `cache_path` property right after a trace:

```python
with trace(label="debug_signup") as t:
    signup_user(request)

# Saved automatically; read it back if needed.
data = trace.load(t.cache_path)
```

## Disabling the log cache

If you do not want logs written to disk (for example in tests or benchmarks):

```python
with trace(cache=False) as t:
    ...
```

## Reading logs from the command line

### Using the tracepatch CLI

The `tph` command provides convenient access to traces:

```bash
# List all traces with metadata
$ tph logs

# Display a specific trace's call tree
$ tph tree .tracepatch_cache/trace_20260212_143022_817345.json

# View trace metadata and configuration
$ tph view .tracepatch_cache/trace_20260212_143022_817345.json

# Filter tree depth for readability
$ tph tree --max-depth 5 .tracepatch_cache/trace_20260212_143022_817345.json
```

### Using standard Unix tools

The files are plain JSON, so standard tools work:

```bash
# List all trace logs by date (newest first)
ls -lt .tracepatch_cache/

# Pretty-print the most recent one
cat .tracepatch_cache/$(ls -t .tracepatch_cache/trace_*.json | head -1) | python -m json.tool

# Search for a specific function in all logs
grep -l '"name": "process_checkout"' .tracepatch_cache/trace_*.json

# Count calls in each log
for f in .tracepatch_cache/trace_*.json; do
    echo "$f: $(python -c "import json; print(json.load(open('$f'))['call_count'])")"
done
```

## Comparing two traces

A common workflow is to trace a request before and after a change, then
compare:

```python
from tracepatch import trace

logs = trace.logs(limit=2)
old = trace.load(logs[1]["file"])
new = trace.load(logs[0]["file"])

print(f"Before: {old['call_count']} calls")
print(f"After:  {new['call_count']} calls")
```

Since the JSON structure is stable, you can also diff them with standard
tools:

```bash
diff <(python -m json.tool old_trace.json) <(python -m json.tool new_trace.json)
```

# Quickstart

Get your first trace in under 60 seconds.

## 1. Install

```bash
pip install tracepatch
```

## 2. Write Your First Trace

```python
from tracepatch import trace

def load_user(user_id):
    return {"id": user_id, "name": "Alice", "email": "alice@example.com"}

def validate(user):
    assert user["name"], "name required"
    return True

def handle_signup(user_id):
    user = load_user(user_id)
    validate(user)
    return user

with trace(label="signup") as t:
    handle_signup(42)

print(t.tree())
```

**Output:**

```
└── __main__.handle_signup(user_id=42) -> {'id': 42, ...}  [0.05ms]
    ├── __main__.load_user(user_id=42) -> {'id': 42, ...}  [0.01ms]
    └── __main__.validate(user={'id': 42, ...}) -> True     [0.01ms]
```

## 3. Understanding the Output

Each line shows:

```
module.function(args) -> return_value  [elapsed_time]
```

- **module** — the Python module where the function is defined
- **function** — the function name
- **args** — captured argument values (truncated to `max_repr` characters)
- **return_value** — what the function returned
- **elapsed_time** — wall-clock time for the call including children

Tree connectors (`├──`, `└──`) show the parent-child call relationships.

## 4. Save and Review with the CLI

```python
# Save the trace to disk
t.to_json("my-trace.json")
```

Or enable auto-saving (the default):

```python
with trace(label="signup", cache=True) as t:
    handle_signup(42)
# Trace auto-saved to .tracepatch/traces/signup_20260219_143022_a1b2c3.json
```

Then review from the command line:

```bash
tph logs                          # list saved traces
tph tree .tracepatch/traces/*.json  # display as a call tree
tph stats .tracepatch/traces/*.json # detailed statistics
```

## 5. Configure with `tracepatch.toml`

```bash
tph init    # interactive setup
```

This creates a `tracepatch.toml` with sensible defaults. Edit it to
customise tracing:

```toml
ignore_modules = ["logging", "urllib3"]
max_depth = 30
max_calls = 10000
max_repr = 120
```

Then load it in your code:

```python
from tracepatch import trace, load_config

config = load_config()
with trace(**config.to_trace_kwargs()) as t:
    my_function()
```

## What's Next

- [Configuration Reference](configuration.md) — every option explained
- [Reading the Call Tree](reading-tree.md) — understanding complex traces
- [CLI Guide](cli-guide.md) — all commands and flags
- [Reading Trace Logs](reading-logs.md) — JSON schema reference

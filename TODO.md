# tracepatch — Master Development TODO

> **Status:** Alpha → Production-Ready Roadmap  
> **Last updated:** 2026-02-19  
> **Guiding principle:** Zero-dependency core. No AI. No magic. Just a precise, honest, deeply useful tool.

This document is the single source of truth for everything that must be built, fixed, refactored, or documented before tracepatch can be considered a serious production library. It is organized from the inside out: fix the foundation first, then build upward.

---

## Table of Contents

1. [Critical Bug Fixes & Broken Functionality](#1-critical-bug-fixes--broken-functionality)
2. [Architecture & Code Quality](#2-architecture--code-quality)
3. [Naming, UX & CLI Overhaul](#3-naming-ux--cli-overhaul)
4. [Trace Storage — Rename, Redesign, Relocate](#4-trace-storage--rename-redesign-relocate)
5. [Configuration System — Complete Overhaul](#5-configuration-system--complete-overhaul)
6. [Tree View — Major Enhancement](#6-tree-view--major-enhancement)
7. [Python API — Completeness & Ergonomics](#7-python-api--completeness--ergonomics)
8. [CLI — Feature Completion](#8-cli--feature-completion)
9. [Test Infrastructure — `tph run` Replacement](#9-test-infrastructure--tph-run-replacement)
10. [pytest Plugin & Fixture Integration](#10-pytest-plugin--fixture-integration)
11. [Web Framework Integrations](#11-web-framework-integrations)
12. [Jupyter Notebook Integration](#12-jupyter-notebook-integration)
13. [Data Science & Pipeline Tracing](#13-data-science--pipeline-tracing)
14. [Educational Mode](#14-educational-mode)
15. [Performance & Reliability Hardening](#15-performance--reliability-hardening)
16. [Developer Tooling (Ruff, CI/CD, Packaging)](#16-developer-tooling-ruff-cicd-packaging)
17. [Documentation — Complete Rewrite](#17-documentation--complete-rewrite)
18. [Test Suite — Gaps & New Coverage](#18-test-suite--gaps--new-coverage)

---

## 1. Critical Bug Fixes & Broken Functionality

These are things that are already "implemented" but are either silently broken, inconsistent, or dangerous. Fix these before touching anything else.

### 1.1 Version Number Inconsistency

- **Problem:** Three different version strings coexist:
  - `src/tracepatch/__init__.py` hardcodes `__version__ = "0.1.0"`
  - `src/tracepatch/_trace.py` embeds `"tracepatch_version": "0.3.4"` inside `to_json()`
  - `pyproject.toml` declares version `0.3.5`
- **Fix:**
  - Pin a single source of truth: `pyproject.toml`
  - Read it dynamically in `__init__.py` using `importlib.metadata.version("tracepatch")`
  - Remove the hardcoded string from `to_json()` — replace with the dynamic version
  - Add a `__version__` export to `__init__.py` that reads from metadata
  - Add a test that asserts `tracepatch.__version__ == importlib.metadata.version("tracepatch")`

### 1.2 `include_modules` Is Configured But Never Enforced

- **Problem:** `TracepatchConfig.include_modules` (allowlist mode) is parsed from TOML and stored, but `_Collector._should_ignore()` in `_trace.py` never consults it. A user sets `include_modules = ["myapp"]` expecting only their app to be traced. Nothing changes.
- **Fix:**
  - Pass `include_modules` into `TraceConfig` (the immutable inner config)
  - In `_Collector._should_ignore()`, if `include_modules` is non-empty, return `True` (ignore) for any module not matching a prefix in the include list
  - Wire `include_modules` through `TracepatchConfig.to_trace_kwargs()` so it reaches `trace()`
  - Add tests for include/exclude mode and combined behavior

### 1.3 `tree_style` Setting Is Ignored

- **Problem:** `TracepatchConfig.tree_style` accepts `"ascii"` or `"unicode"` but `render_tree()` in `_trace.py` always uses ASCII connectors. The unicode path never executes.
- **Fix:**
  - Add `render_tree_unicode(roots)` function using `└`, `├`, `─`, `│` box-drawing characters (which are already in `render_tree` — consolidate)
  - Accept a `style` parameter in `render_tree()` that dispatches accordingly
  - Wire through `t.tree(style=...)` and the CLI `tph tree --style unicode`
  - The `tree_style` value from config must reach the tree rendering call

### 1.4 `show_args` and `show_return` Are Configured But Not Wired

- **Problem:** Both `show_args` and `show_return` are parsed from config and stored, but `render_tree()` unconditionally shows args and return values. There is no code path that respects these flags.
- **Fix:**
  - Pass `show_args` and `show_return` into `render_tree()` as parameters
  - When `show_args=False`, render function signature as `func_name()` (no args)
  - When `show_return=False`, omit the `-> value` part
  - Both must also apply to `render_tree_colored()` and `render_tree_unicode()`
  - The HTML renderer must respect these flags too
  - Wire from `TracepatchConfig.to_trace_kwargs()` and from the CLI

### 1.5 `max_time` Is Not Configurable via TOML

- **Problem:** The `trace()` constructor and `TraceConfig` both accept `max_time`, but `TracepatchConfig` has no `max_time` field. A user cannot configure the time limit in their `tracepatch.toml`. The default of 60 seconds is hardcoded and silently applied.
- **Fix:**
  - Add `max_time: float` to `TracepatchConfig` with default `60.0`
  - Parse it from TOML in `TracepatchConfig.from_dict()`
  - Export it from `to_trace_kwargs()`
  - Add `max_time` to `CLI --tree` and `tph config` display output
  - Document it in `docs/configuration.md`

### 1.6 Dead Code After Early Return in `load_config()`

- **Problem:** In `config.py`, after the `if tomllib is None` block applies env overrides and returns, there is a second unreachable `return TracepatchConfig.default(), None` statement. This is dead code that will confuse readers and linters.
- **Fix:** Remove the unreachable line. Ensure ruff or a linter catches this going forward.

### 1.7 `_apply_env_overrides` Mutates a Dataclass Directly

- **Problem:** `_apply_env_overrides(config)` modifies fields on the `TracepatchConfig` dataclass in-place (e.g., `config.max_calls = 0`). Dataclasses are not protected from this, but the pattern is unsafe — any reference to the config object sees the mutation. This also interacts badly if `TracepatchConfig` is ever made `frozen=True`.
- **Fix:**
  - Change `_apply_env_overrides` to return a *new* `TracepatchConfig` instance with the overrides applied (using `dataclasses.replace`)
  - Update all call sites in `load_config()` to use the returned value
  - Ultimately work toward making `TracepatchConfig` `frozen=True` (see §2.3)

### 1.8 CLI Documentation References Non-Existent Options

- **Problem:** `docs/cli-guide.md` documents `tph tree --max-depth N`, `--show-args`, `--no-args`, `--show-return`, `--no-return` options. None of these exist in the actual `argparse` setup in `cli.py`.
- **Fix (immediate):** Update the docs to match reality. Remove the phantom options.
- **Fix (proper):** Add the real options to the CLI (see §8).

### 1.9 `_count_nodes` Defined Twice in `cli.py`

- **Problem:** The generator function `_count_nodes(nodes)` is defined twice in `cli.py` — once near `_limit_depth` and once near `cmd_tree`. Python silently uses the last definition.
- **Fix:** Remove the duplicate. Keep one definition near the top of the file where it is used by both.

### 1.10 `_format_elapsed` Defined in Both `_trace.py` and `cli.py`

- **Problem:** The exact same function body exists in both modules. Any bug fix or behavior change requires updating both.
- **Fix:** Move `_format_elapsed` to `_trace.py` (it already lives there). Import it in `cli.py` instead of redefining.

### 1.11 `trace.__call__` (Decorator) Reuses the Same Instance

- **Problem:** When `trace()` is used as a decorator via `@trace(label="x")`, the same `trace` instance is shared across all invocations of the decorated function. This means the second call into the function tries to re-enter an already-entered context manager, which may cause undefined behavior (the token gets reset, the collector gets cleared).
- **Fix:**
  - Document clearly that each call to `trace()` is a one-shot context manager
  - Make the decorator mode create a **fresh** `trace(...)` instance for each function call, not reuse the outer one
  - Write a test that calls a decorated function twice and asserts both get independent, complete traces

### 1.12 HTML Renderer Does Not Escape User Data

- **Problem:** Function names, argument values, and return values are inserted directly into HTML in `nodes_to_html()`. If a repr contains `<script>` or any HTML entities, the output will be malformed or exploitable.
- **Fix:**
  - Use `html.escape()` from the standard library on all user-derived strings before inserting them into HTML output
  - Add a test where a function argument contains `<>`

---

## 2. Architecture & Code Quality

Clean up the internal design so the codebase is maintainable long-term.

### 2.1 Module Responsibility Split

- **Problem:** `cli.py` contains 908 lines including business logic (tree rendering, HTML generation, JSON conversion, filter application, depth limiting). These belong in the core library, not the CLI layer.
- **Fix — Extract these to `_trace.py` or a new `_render.py` module:**
  - `render_tree_colored()` → move to `_trace.py` (alongside `render_tree`)
  - `nodes_to_json()` → move to `_trace.py`
  - `nodes_to_html()` → move to `_render.py`
  - `_filter_node()`, `_apply_filter()` → move to `_trace.py`
  - `_limit_depth()` → move to `_trace.py`
  - `_dict_to_node()` → move to `_trace.py`
  - `_colorize_by_duration()` → move to `_render.py`
  - CLI commands become thin dispatch functions that call library code

### 2.2 `instrumentation.py` Is a God Module

- **Problem:** `instrumentation.py` does: git subprocess calls, code generation (string concatenation to build Python source), AST parsing, file I/O, default value generation, and setup/cleanup orchestration. This is five separate concerns in one file.
- **Fix — Split into:**
  - `_codegen.py` — The `create_test_runner()` function and template logic only
  - `_git.py` — The `check_git_status()` function only
  - `_setup.py` — `SetupState`, `setup_test_environment()`, `cleanup_test_environment()`
  - `_introspect.py` — `get_function_signature()`, `generate_default_value()`
  - Keep `instrumentation.py` as a re-export shim during transition if needed for backwards compatibility

### 2.3 Make `TracepatchConfig` Immutable

- **Problem:** `TracepatchConfig` is a plain `@dataclass` with no `frozen=True`, while `TraceConfig` (the internal one) is `frozen=True`. Any code can mutate the user-facing config at any time.
- **Fix:**
  - Add `frozen=True` to `TracepatchConfig`
  - Fix `_apply_env_overrides` first (see §1.7)
  - Add `@dataclasses.dataclass(frozen=True)` to all config-related dataclasses

### 2.4 Consolidate `TraceConfig` and `TracepatchConfig`

- **Problem:** There are two config objects: `TraceConfig` (immutable, used internally by `_Collector`) and `TracepatchConfig` (mutable, user-facing). The mapping between them is done manually in `to_trace_kwargs()`. Fields like `max_time` are in `TraceConfig` but missing from `TracepatchConfig`. They will drift apart.
- **Fix:**
  - Keep `TraceConfig` as the runtime-validated immutable config passed to `_Collector`
  - `TracepatchConfig.to_trace_kwargs()` must produce a complete dict that covers all `TraceConfig` fields
  - Add a `TracepatchConfig.to_trace_config()` method that produces a `TraceConfig` directly
  - Strictly test that no field is silently lost in translation

### 2.5 Remove All String-Building Code Generation in `instrumentation.py`

- **Problem:** `create_test_runner()` builds Python source code by concatenating string literals in a loop (`imports.append("    result = func()\n")`). This is extremely fragile, unreadable, untestable, and produces poorly formatted output.
- **Fix:**
  - Use a proper template string (Python's `string.Template`) or a `textwrap.dedent` multi-line f-string
  - The generated file must be valid, ruff-clean Python
  - Add a test that parses the generated file with `ast.parse()` to verify it is syntactically valid

### 2.6 Consistent Use of `Path` vs `str`

- **Problem:** The codebase mixes `str` and `Path` throughout. Some public API accepts `Union[str, Path]`, some only `str`, some only `Path`. This causes unnecessary `isinstance` checks everywhere.
- **Fix:**
  - All public API that accepts file paths must accept `Union[str, Path]`
  - All internal functions must work with `Path` objects, converting at the boundary
  - Audit every function signature and standardize

### 2.7 `COLORS` Dictionary Belongs in a Constants Module

- **Problem:** ANSI color codes are hardcoded as a dict at the top of `cli.py`. They will be needed in `_render.py` too once rendering moves there.
- **Fix:** Move to `_render.py` or a `_constants.py`. Import everywhere needed.

### 2.8 Remove `subprocess` Dependency from Core

- **Problem:** `instrumentation.py` imports and calls `subprocess` to run `git` commands. This is a side-effect import that adds startup time and is completely irrelevant to the core tracing functionality.
- **Fix:**
  - Move Git integration to `_git.py`
  - Make it lazily imported only when `tph setup` / `tph disable` is actually invoked
  - Add a `HAS_GIT` check that gracefully degrades instead of failing with `FileNotFoundError`

---

## 3. Naming, UX & CLI Overhaul

The current command naming is inconsistent, confusing, and non-obvious to new users.

### 3.1 Resolve the `tph init` vs `tph setup` Confusion

- **Problem:**
  - `tph init` creates `tracepatch.toml` — this is initializtion of **configuration**
  - `tph setup` creates `_tracepatch_filetotest.py` from config — this is initialization of a **test runner**
  - A new user has no idea which to run first or what the difference is
  - `tph disable` exists but there is no `tph enable` (the opposite workflow)
- **Fix — Rename and clarify:**
  - Keep `tph init` — creates the config file. Rename its description to "Initialize project configuration". This is the first command a user runs.
  - Rename `tph setup` → `tph run` (see §9 for full redesign). The current "setup then manually run then disable" workflow is wrong.
  - Rename `tph disable` → `tph clean` (it removes generated files, not "disables" anything)
  - Add `--help` text to every command that tells the user what to do next

### 3.2 Rename `_tracepatch_filetotest.py`

- **Problem:** The generated test runner file is named `_tracepatch_filetotest.py`. This name is cryptic, breaks Python naming conventions (should be snake_case, not `filetotest`), and pollutes the project root.
- **Fix:**
  - Move the generated file to `.tracepatch/runner.py` (inside the tracepatch data directory)
  - If a user must run it in their project context (for imports to work), generate it as `.tracepatch/trace_runner.py` alongside a clear instruction
  - Never place generated files in the project root without explicit user consent

### 3.3 Rename `.tracepatch_cache` → `.tracepatch`

- **Problem:** `.tracepatch_cache` is a mouthful, and the word "cache" implies the folder can be safely deleted. It cannot — it contains the `setup_state.json` that `tph clean` needs.
- **Fix:**
  - Rename the directory to `.tracepatch` (the library's own data directory)
  - Inside `.tracepatch/`:
    - `traces/` — all JSON trace logs (this *sub*-directory is what gets gitignored with `*`)
    - `state.json` — setup/cleanup state (never gitignored)
    - `README.md` — self-documentation
  - Update `_CACHE_DIR_NAME` throughout the codebase
  - The `.gitignore` inside `.tracepatch/` must only ignore `traces/*`, not everything
  - Update all references in docs, tests, and CLI output

### 3.4 Interactive `tph init`

- **Problem:** `tph init` generates a static TOML template with commented-out sections. A new user has no idea what values to put in.
- **Fix:**
  - Make `tph init` ask a small set of questions interactively (using `input()`):
    1. "What is your main source directory? (e.g., `src/myapp` or `.`) [.]"
    2. "Do you want to trace all modules or just specific ones? (all/specific) [all]"
    3. "What modules do you want to ignore? (comma-separated, or press Enter to skip) [logging, urllib3]"
  - Use answers to generate a tailored `tracepatch.toml`
  - Add `--no-interactive` / `--yes` flags to skip prompts (for CI use)
  - At the end, print a clear "What's next" section:
    ```
    ✓ Created tracepatch.toml
    
    What's next:
      1. In your code: from tracepatch import trace
      2. Wrap a function: with trace(label="my-op") as t: my_function()
      3. View results:   print(t.tree())
      4. Or from CLI:    tph logs / tph tree <file>
    ```

### 3.5 Consistent CLI Output Formatting

- **Problem:** CLI output is inconsistent. Some places use `✓`, others use `✅`. Some use `❌`, others use `Error:`. Error messages go to stderr inconsistently.
- **Fix:**
  - Create a `_cli_output.py` module with `ok(msg)`, `err(msg)`, `warn(msg)`, `info(msg)` helpers
  - `ok()` → `✓ {msg}` to stdout
  - `err()` → `✗ {msg}` to stderr
  - `warn()` → `! {msg}` to stdout
  - `info()` → `  {msg}` to stdout
  - All emoji use plain ASCII alternatives when stdout is not a TTY (`os.isatty(sys.stdout.fileno())`)
  - All error paths exit with non-zero codes

### 3.6 `tph` Binary — Add Shell Completions

- **Scope:** Low priority but high polish. Once CLI is stable, generate shell completion scripts for bash, zsh, and fish using `argcomplete` or a hand-written `tph completions` subcommand.

---

## 4. Trace Storage — Rename, Redesign, Relocate

### 4.1 New Directory Structure: `.tracepatch/`

Replace the flat `.tracepatch_cache/` with a proper data directory:

```
.tracepatch/
├── README.md              ← human-readable explanation
├── state.json             ← setup/cleanup state (persistent, never gitignored)
└── traces/
    ├── .gitignore         ← contains "*" to exclude all trace logs
    ├── 20260219_143022_abc123.json
    └── 20260219_150000_def456_checkout-flow.json
```

- Trace log filenames: `{YYYYMMDD}_{HHMMSS}_{6-char-id}_{label}.json` (label optional)
- The `traces/` subdirectory is what gets gitignored
- The top-level `.tracepatch/` directory is tracked in git (so `state.json` and `README.md` are safe)

### 4.2 Trace File Naming

- **Current:** `trace_20260212_143022_123456.json` or `trace_20260212_143022_123456_checkout_flow.json`
- **Problem:** Hard to parse visually. The label is appended at the end after confusing numbers.
- **New format:** `{label}_{timestamp}_{short-id}.json` where label comes first if present
  - With label: `checkout-flow_20260219_143022_a1b2c3.json`
  - Without label: `trace_20260219_143022_a1b2c3.json`
- This makes sorted ls output group by label naturally
- The short ID is the first 6 chars of a UUID (collision-safe enough for local traces)

### 4.3 Trace File Schema — Add Metadata Fields

The current JSON schema is missing context that makes traces much more useful:

```json
{
  "tracepatch_version": "0.4.0",
  "schema_version": 1,
  "timestamp": "2026-02-19T14:30:22.123456",
  "label": "checkout_flow",
  "trace_id": "a1b2c3",
  "hostname": "my-machine",
  "python_version": "3.12.0",
  "platform": "darwin",
  "working_directory": "/path/to/project",
  "duration_ms": 42.3,
  "call_count": 150,
  "was_limited": false,
  "limit_reason": null,
  "config": { ... },
  "stats": {
    "max_depth_reached": 8,
    "unique_functions": 23,
    "unique_modules": 5,
    "slowest_call_ms": 12.3,
    "slowest_call_name": "db.query"
  },
  "trace": [ ... ]
}
```

- `schema_version` allows future migrations
- `hostname`, `python_version`, `platform` are essential for debugging environment-specific issues
- `working_directory` helps when trace files are moved or shared
- `duration_ms` is the total wall-clock time of the trace block
- `limit_reason` explains *why* the trace was limited: `"max_calls"`, `"max_depth"`, `"max_time"`, or `null`
- `stats` pre-computes basic analytics so the CLI doesn't have to re-traverse the whole tree

### 4.4 Implement a `TraceSummary` Class

- A lightweight Python object computed from a `TraceNode` tree without needing to load the full JSON
- Fields: `call_count`, `max_depth_reached`, `unique_functions: set[str]`, `unique_modules: set[str]`, `total_duration_ms`, `slowest_node: TraceNode`, `most_called: list[tuple[str, int]]`
- Used by `tph view`, `tph logs`, and statistics output
- Exposed via `t.summary()` on the `trace` object after context exit

---

## 5. Configuration System — Complete Overhaul

### 5.1 Add `max_time` to `TracepatchConfig` and TOML

- Already noted in §1.5. Add `max_time: float = 60.0` to config and documentation.

### 5.2 Add `color` to `TracepatchConfig`

- **Problem:** Color control currently only exists via environment variable `TRACEPATCH_COLOR=1`. It should be configurable in TOML.
- **Fix:** Add `color: bool = False` to `TracepatchConfig` (default off to be safe in CI/piped output). Respect TTY detection: if stdout is not a TTY, color is always off regardless of config.

### 5.3 Add `max_repr_args` and `max_repr_return` as Separate Limits

- **Problem:** `max_repr` applies to both argument reprs and return value reprs. Often you want shorter args (they appear many times in a loop) but longer return values.
- **Fix:** Add `max_repr_args: int` and `max_repr_return: int` with backward-compatible fallback to `max_repr` if the specific ones are not set.

### 5.4 Environment Variable Coverage Gap

- **Problem:** Only 4 env vars are documented: `TRACEPATCH_ENABLED`, `TRACEPATCH_MAX_DEPTH`, `TRACEPATCH_MAX_CALLS`, `TRACEPATCH_COLOR`. Several config options have no env override.
- **Fix — Add env overrides for:**
  - `TRACEPATCH_MAX_REPR` (already partially implemented, but underdocumented)
  - `TRACEPATCH_MAX_TIME`
  - `TRACEPATCH_LABEL` (default label for all traces)
  - `TRACEPATCH_OUTPUT_DIR` (override cache directory)
  - `TRACEPATCH_NO_CACHE=1` (disable all file I/O, equivalent to `cache=false`)
  - `TRACEPATCH_COLOR` (already exists, just needs docs)
- All env vars must be documented in `tph config` output and in docs

### 5.5 Config Validation with Useful Error Messages

- **Problem:** `TracepatchConfig.from_dict()` silently uses defaults for unknown keys and invalid values. A typo in TOML is invisible.
- **Fix:**
  - Add `_validate()` method to `TracepatchConfig` that raises `ConfigError` (a new exception class) with a descriptive message for:
    - Unknown keys (warn, don't fail — for forward compatibility)
    - Invalid types (e.g., `max_depth = "hello"`)
    - Out-of-range values (e.g., `max_depth = -1`, `max_calls = 0` without explicit intent)
    - Invalid enum values (e.g., `tree_style = "fancy"`)
  - Call `_validate()` from `from_dict()` before returning
  - `tph config` must surface validation errors with line numbers if possible

### 5.6 `tph config --validate` Flag

- Add a `--validate` flag to `tph config` that explicitly validates the config file and exits with code 0 (valid) or 1 (invalid). Useful in CI.

### 5.7 `pyproject.toml` Section Must Support the Full Schema

- **Problem:** The `[tool.tracepatch]` section in `pyproject.toml` is supported for basic options, but `[[test.files]]` array tables won't work inside `[tool.tracepatch]` due to how TOML nesting works.
- **Fix:** Document the correct `pyproject.toml` structure explicitly:
  ```toml
  [tool.tracepatch]
  max_depth = 50
  max_calls = 20000
  
  [[tool.tracepatch.test.files]]
  path = "myapp/core.py"
  functions = ["process"]
  ```
- Add a test that loads this exact structure

### 5.8 Config `default_label` Should Support Hostname and PID Expansion

- Allow simple template variables in `default_label`:
  - `{hostname}` → `socket.gethostname()`
  - `{pid}` → `os.getpid()`
  - `{timestamp}` → ISO timestamp
  - Example: `default_label = "worker-{hostname}-{pid}"`
- No templating engine needed — implement with `str.format_map` and a small dict

---

## 6. Tree View — Major Enhancement

The tree view is the flagship feature of tracepatch. It must be exceptional.

### 6.1 Add Source File and Line Number to Each Node

- **Problem:** The current tree shows `module.function(args)` but not where in the source code the function is defined. When you have `myapp.process(data=[...])`, you don't know if it's in `myapp/core.py:45` or `myapp/utils.py:12`.
- **Fix:**
  - Add `file: Optional[str]` and `lineno: Optional[int]` to `TraceNode`
  - Capture `frame.f_code.co_filename` and `frame.f_code.co_firstlineno` in `_Collector.handle_call()`
  - Store them in the JSON schema
  - Display in tree (optional, behind `--show-source` flag to avoid clutter by default)
  - In HTML view, show file/line as a clickable tooltip or secondary line

### 6.2 Add Call Count Annotation (Loop Detection)

- **Problem:** When a function is called 500 times in a loop, the current tree shows 500 separate nodes. This is impossible to read and buries the insight ("this function is being called too many times").
- **Fix — "Call Folding" for repeated sibling calls:**
  - After capturing, post-process the tree to detect runs of sibling nodes with the same `name` and `module`
  - Fold them: display as a single node with `[×500]` annotation
  - Example: `myapp.process(item=...)  [×500]  [avg: 0.12ms, total: 60ms]`
  - When folded, show `min/avg/max` timing instead of just one time
  - Add `--no-fold` flag to disable folding and show all raw calls
  - Fold threshold should be configurable: `fold_threshold = 3` (fold if ≥ 3 consecutive identical calls)

### 6.3 Add Per-Call Statistics to the Tree Summary Header

Before the tree, print a statistics header:

```
Trace: checkout_flow
────────────────────────────────────────────────────────────────────────
Recorded:     150 calls across 5 modules  |  Duration: 42.3ms
Max depth:    8 levels                    |  Unique functions: 23
Slowest:      db.query [12.3ms]           |  Most called: app.validate [×48]
────────────────────────────────────────────────────────────────────────
```

- This requires `TraceSummary` (§4.4)
- Always show when printing via `t.tree()` or `tph tree`
- Can be suppressed with `--no-summary`

### 6.4 Show "Self Time" vs "Total Time"

- **Problem:** The current `[timing]` is the *total* elapsed time of a function including all its children. It's impossible to know how much time a function itself spent (excluding children).
- **Fix:**
  - Compute `self_time = elapsed - sum(child.elapsed for child in children)`
  - Store `self_elapsed` on `TraceNode`
  - In the tree, show `[42ms / self: 3ms]` format
  - Add `--show-self-time` / `--no-self-time` flag (default: off to keep output compact)

### 6.5 Rich HTML Tree — Full Redesign

The current HTML output is a minimal proof-of-concept. Redesign it properly:

**Structure:**
```
┌─────────────────────────────────────────────────────────────┐
│ HEADER: trace label, timestamp, call count, duration        │
├────────────┬────────────────────────────────────────────────┤
│ STATS      │ CALL TREE                                       │
│ panel      │   Searchable, expandable, colorized            │
│ (summary)  │   Each node: module, func, args, ret, timing   │
└────────────┴────────────────────────────────────────────────┘
```

**Must-have features:**
- Expand/Collapse all buttons
- Search box that highlights matching function/module names
- Click a node to see full args and return value (modal or side panel)
- Color coding by timing (already partially exists, needs consistency)
- "Top 10 slowest" sidebar panel
- "Most called" sidebar panel
- Fold/Unfold repeated calls (matching §6.2)
- Export to PNG button (using browser `print()` or CSS)

**Technical:**
- All CSS and JS must be inline (single self-contained HTML file, no CDN)
- Must work offline (no external resources)
- Must pass basic HTML5 validation
- Must be under 100KB for a typical trace (aggressive CSS/JS minification or just clean code)

### 6.6 Unicode Tree Style (Actually Implement It)

- See §1.3 for context. The implementation is straightforward: swap connector strings.
- ASCII set: `└──`, `├──`, `│   `, `    `
- Unicode set: `└─ `, `├─ `, `│  `, `   ` (box-drawing chars, slightly wider spacing)
- Add `ANSI set`: same as Unicode but with dim color on connectors for visual clarity

### 6.7 Flamegraph Export (SVG)

- Implement a `t.to_flamegraph("flame.svg")` method
- The flamegraph format: each function is a horizontal bar, width proportional to total time, stacked vertically by call depth
- Pure Python SVG generation — no external dependencies
- `tph flamegraph <trace-file> -o output.svg` command
- This is the single most requested feature by profiler users and data scientists

### 6.8 `t.tree()` Must Work After the Context Exits

- **Current behavior:** Works correctly after `__exit__`
- **Edge case:** After `to_json()` is called, the internal state is unchanged. Good.
- **Add:** `t.stats()` method that returns a `TraceSummary` object (§4.4). Works at any time after context exit.

### 6.9 Collapsed View by Default for Large Traces

- **Problem:** A trace with 10,000 calls will produce an unusable wall of text in the terminal.
- **Fix:**
  - Add `--collapse N` flag: auto-collapse subtrees that have fewer than `N` total calls and whose root took less than `X` ms
  - Add a smart default: if total nodes > 200, auto-collapse to depth 4 and warn the user
  - The collapsed node shows: `[+N more calls, Xms total]`

---

## 7. Python API — Completeness & Ergonomics

### 7.1 `@trace` Decorator Without Parentheses

- **Problem:** `@trace()` works as a decorator factory. But `@trace` (without parentheses) does not — it would pass the function as the first positional argument to `trace.__init__`, which only accepts keyword args after `self`.
- **Fix:**
  - Add support for `@trace` (no-call decorator) by detecting if the first positional arg to `__init__` is callable
  - OR create a separate `traced` decorator function (not a class) that is purely for decoration:
    ```python
    from tracepatch import traced  # New export
    
    @traced(label="compute")
    def expensive_function(): ...
    ```
  - `traced` is a simple factory: `def traced(**kwargs): return lambda func: trace(**kwargs)(func)`
  - Export `traced` from `__init__.py`

### 7.2 `trace.current()` — Access Active Trace from Nested Code

- **Problem:** Inside a function being traced, there's no way to access the current `trace` object without threading it through as a parameter. This makes it impossible to add annotations from inside traced code.
- **Fix:**
  - Add a `trace.current() -> Optional[trace]` class method
  - Returns the active `trace` instance for the current context, or `None` if not inside a trace
  - Works across async contexts (uses `_active_collector` ContextVar)
  - Use case: `trace.current().annotate("checkpoint: validation passed")`

### 7.3 `t.annotate(message: str)` — Custom Annotations

- **Problem:** There's no way to add user-defined notes to a trace. You can't say "this is where the slow query happened" without it showing up in the tree naturally.
- **Fix:**
  - Add `t.annotate(message)` method that inserts a synthetic `TraceNode` with `name="[annotation]"` and `args=message` at the current stack depth
  - These appear in the tree as `[annotation] "message"  [—]`
  - Also callable as `trace.annotate(message)` when accessed via `trace.current()`

### 7.4 `t.pause()` and `t.resume()` — Selective Tracing Windows

- **Problem:** Sometimes you want to trace only a portion of the code inside a `trace()` block. For example, you want to skip over a known-slow third-party operation.
- **Fix:**
  - Add `t.pause()` — temporarily disables the trace hook without exiting the block
  - Add `t.resume()` — re-enables it
  - The paused interval appears in the tree as `[paused: 12.3ms]` if desired
  - Thread-safe and async-safe

### 7.5 `trace(filter=...)` — Inline Filter at Capture Time

- **Problem:** `ignore_modules` filters by module prefix at capture time. But there's no way to provide a custom filter function. What if I want to ignore all private methods (starting with `_`)?
- **Fix:**
  - Add `filter: Optional[Callable[[str, str], bool]]` parameter to `trace()`:
    - Signature: `filter(module: str, function_name: str) -> bool`
    - Return `True` to include, `False` to exclude
  - Applied in `_Collector._should_ignore()` after the built-in checks

### 7.6 `trace.from_file(path)` — Load and Re-Render a Trace

- **Problem:** `trace.load(path)` returns raw JSON. There's no Python-native way to re-render a saved trace as a tree without going through the CLI.
- **Fix:**
  - Add `trace.from_file(path) -> trace` class method that loads a JSON trace file and reconstructs the node tree
  - The returned `trace` object has no collector (tracing is not active) but all display methods work: `.tree()`, `.to_json()`, `.stats()`, `.to_flamegraph()`, etc.
  - This enables workflow: save, load, filter, re-render programmatically

### 7.7 Clean Up `__init__.py` Exports

- **Current exports:** `trace`, `load_config`, `TracepatchConfig`
- **Add to exports:** `traced`, `TraceNode`, `TracepatchConfig`, `ConfigError`
- **Remove from exports:** Internal helpers should never appear in `__all__`
- Ensure `from tracepatch import *` only exports the public API
- Add `py.typed` marker (already exists — verify it is correctly placed)

---

## 8. CLI — Feature Completion

### 8.1 `tph tree` — Missing Options (Add What Docs Already Claim Exists)

- Add `--show-args` / `--no-args` (default: `--show-args`)
- Add `--show-return` / `--no-return` (default: `--show-return`)
- Add `--style [ascii|unicode|ansi]` (default: `ascii`)
- Add `--stats` / `--no-stats` (show/hide the summary header)
- Add `--fold / --no-fold` (control call folding, see §6.2)
- Add `--self-time` (show self time alongside total time)
- Add `--collapse N` (auto-collapse shallow/fast subtrees)

### 8.2 `tph tree --watch` — Live Tree Update

- When a trace is being written to in real-time (from another process), `tph tree --watch <file>` polls the file every 500ms and re-renders when it changes
- This is a lightweight "live view" for long-running operations
- Clears the terminal and re-renders: `os.system('clear')` or ANSI escape sequences

### 8.3 `tph diff <file1> <file2>` — Compare Two Traces

- Compares two trace files, showing:
  - Functions present in one but not the other
  - Functions whose call count changed by >10%
  - Functions whose timing changed by >20%
  - New exceptions that appeared
- Output format:
  ```
  + myapp.new_validator()      added      [3.2ms]
  - myapp.old_check()          removed
  ~ db.query()                 slower     [0.8ms → 4.2ms  +425%]
  ~ app.process()              more calls [×3 → ×12]
  ```

### 8.4 `tph stats <file>` — Statistics Report

Print a detailed statistics report for a trace:

```
Top 10 slowest functions:
  1.  db.query              12.3ms  (×3,  avg 4.1ms,  max 8.2ms)
  2.  http.request           8.1ms  (×1)
  ...

Top 10 most called functions:
  1.  app.validate         ×1,482  (avg 0.02ms, total 29.6ms)
  2.  utils.sanitize       ×1,480  ...
  ...

Module breakdown:
  myapp          72 calls  (48%)   total: 22.1ms
  db             18 calls  (12%)   total: 15.3ms
  http            3 calls   (2%)   total: 8.1ms
  ...
```

### 8.5 `tph export <file> --format [flamegraph|csv|html]`

- `flamegraph` → writes SVG (implements §6.7)
- `csv` → writes a flat CSV with columns: `module,function,args,return_value,elapsed_ms,depth,parent`
- `html` → writes the full HTML tree (already partially implemented, needs cleanup per §6.5)

### 8.6 `tph logs` — Better Filtering

- Add `--label PATTERN` to filter logs by label (glob matching)
- Add `--since DURATION` to show only traces from the last N minutes/hours (e.g., `--since 1h`)
- Add `--limited` flag to show only traces that hit a limit
- Add `--min-calls N` and `--max-calls N` range filters

### 8.7 `tph clean [--all | --older-than DURATION]`

- `tph clean` (no args) — removes only the setup state (`state.json`), keeps trace logs
- `tph clean --traces` — removes all trace JSON files from `.tracepatch/traces/`
- `tph clean --older-than 7d` — removes trace files older than 7 days
- `tph clean --all` — removes the entire `.tracepatch/` directory

### 8.8 Non-Zero Exit Codes for All Failure Paths

- Every command must exit with code `1` on any error
- Add a `--quiet` flag that suppresses informational output (errors still go to stderr)
- Add a `--json-output` flag to most commands to emit machine-readable JSON instead of human text (useful for CI integration)

---

## 9. Test Infrastructure — `tph run` Replacement

The current `tph setup` → `python _tracepatch_filetotest.py` → `tph disable` workflow is too convoluted. Replace it with `tph run`.

### 9.1 `tph run [FILE] [FUNCTION...]`

- **New command replacing `tph setup` + manual execution:**
  ```bash
  # Run with config
  tph run                          # uses [[test.files]] from config
  
  # Run a specific file and function
  tph run myapp/core.py::process   # trace one specific function
  
  # Run with arguments
  tph run myapp/core.py::process --args '[42, "hello"]'
  ```
- Everything happens inline: no generated files, no separate cleanup step
- The trace is saved to `.tracepatch/traces/` automatically
- After running, the tree is printed immediately to terminal
- No files are left behind in the project root — ever

### 9.2 Move Generated Runner to `.tracepatch/` If Still Needed

- If a "generate a runnable file" workflow must exist (e.g., for users who want to customize the runner), generate it to `.tracepatch/runner.py`, never to the project root
- Make this explicit: `tph generate-runner --output .tracepatch/runner.py`
- Document that this file is safe to edit and re-run

### 9.3 Remove `tph disable` — Make Cleanup Unnecessary

- If `tph run` never writes files to the project root, there is nothing to clean up
- Remove or repurpose `tph disable` → `tph clean` (for trace log management, see §8.7)

### 9.4 `state.json` Must Be Explicitly Structured

- If setup state must persist (e.g., for rollback of modified files), document the exact schema
- Add schema version to `state.json`
- Add a `tph status` command that shows what `state.json` contains

---

## 10. pytest Plugin & Fixture Integration

### 10.1 Create `tracepatch.pytest_plugin` Module

Create a pytest plugin as a separate submodule (not installed by default, but available via extras):

Install: `pip install tracepatch[pytest]`

### 10.2 `tracepatch` Fixture

```python
def test_my_function(tracepatch):
    result = my_function(42)
    assert result == "expected"
    
    # The tracepatch fixture provides the trace automatically
    assert tracepatch.call_count > 0
    assert "my_function" in tracepatch.tree()
```

- The `tracepatch` fixture starts a trace before the test, stops it after
- The trace is automatically saved to `.tracepatch/traces/` with `label=test_name`
- If the test fails, the trace path is shown in the failure output: "trace saved to: ..."
- Configurable scope: `@pytest.fixture(scope="session")` equivalent via config

### 10.3 `trace_assert` Fixture Helper

```python
def test_no_db_calls(tracepatch):
    do_business_logic()
    tracepatch.assert_not_called("db.*")  # Fails if any db.* call appears
    tracepatch.assert_called("myapp.validate")
    tracepatch.assert_max_calls(50)
    tracepatch.assert_max_depth(5)
    tracepatch.assert_under_ms("myapp.process", 100)
```

These become powerful performance regression tests.

### 10.4 `--tracepatch` pytest CLI Flag

- `pytest --tracepatch` — enable tracepatch for all tests (applies fixture globally)
- `pytest --tracepatch-save` — save all traces regardless of pass/fail
- `pytest --tracepatch-fail-on-limited` — fail tests whose trace was limited (hit max_calls)
- `pytest --tracepatch-output DIR` — save traces to a specific directory

### 10.5 Register the Plugin via Entry Point

In `pyproject.toml`:
```toml
[project.entry-points."pytest11"]
tracepatch = "tracepatch.pytest_plugin"
```

This allows the plugin to be auto-discovered by pytest when installed.

---

## 11. Web Framework Integrations

### 11.1 FastAPI Middleware

```python
from tracepatch.integrations.fastapi import TracepatchMiddleware

app.add_middleware(
    TracepatchMiddleware,
    label_fn=lambda request: f"{request.method} {request.url.path}",
    ignore_modules=["starlette", "uvicorn", "fastapi"],
    save=True,
)
```

- Traces each request independently using `async with trace()`
- Each trace labeled with method + path
- Saves to `.tracepatch/traces/{label}_{timestamp}.json`
- Adds `X-Tracepatch-ID` response header with the trace ID
- Must have negligible overhead when disabled: check a `TracepatchMiddleware.enabled` flag

### 11.2 Flask Middleware

```python
from tracepatch.integrations.flask import init_tracepatch

init_tracepatch(app, ignore_modules=["flask", "werkzeug"])
```

- Uses Flask's `before_request` / `after_request` hooks
- Each request gets its own trace using thread-local storage (Flask is synchronous/thread-per-request)
- Same labeling and save behavior as FastAPI integration

### 11.3 Django Middleware

```python
# settings.py
MIDDLEWARE = [
    "tracepatch.integrations.django.TracepatchMiddleware",
    ...
]

TRACEPATCH = {
    "ignore_modules": ["django", "urllib3"],
    "save": True,
}
```

- Standard Django middleware class
- Reads config from `settings.TRACEPATCH`
- Each request traced from `process_request` to `process_response`

### 11.4 WSGI Middleware (Framework-Agnostic)

```python
from tracepatch.integrations.wsgi import TracepatchMiddleware

app = TracepatchMiddleware(app, label_fn=lambda environ: environ.get("PATH_INFO", "/"))
```

- Works with any WSGI app (Bottle, Pyramid, raw WSGI, etc.)
- Wraps the `__call__` in a `trace()` context

### 11.5 All Integrations Must Be Optional Extras

In `pyproject.toml`:
```toml
[project.optional-dependencies]
fastapi = ["tracepatch"]          # no extra deps needed
flask = ["tracepatch"]
django = ["tracepatch"]
```

The integration files live under `src/tracepatch/integrations/` but import the framework lazily — never at module load time. If the framework is not installed, importing the integration raises `ImportError` with a helpful message.

---

## 12. Jupyter Notebook Integration

### 12.1 `t.show()` — Render Tree Inline in Jupyter

```python
from tracepatch import trace

with trace() as t:
    process_data(df)

t.show()  # Renders HTML tree inline in the notebook cell output
```

- Detects if running in Jupyter via `IPython` and `ipynbname`
- If in Jupyter: uses `IPython.display.HTML(t.to_html())` to render inline
- If not in Jupyter: falls back to `print(t.tree())`

### 12.2 `%tracepatch` IPython Magic Command

```python
# In a Jupyter cell:
%%tracepatch --label "data-processing" --max-calls 5000
result = preprocess(df)
model.fit(result)
```

- Wraps the cell in a `trace()` context
- After execution, renders the tree inline (via `t.show()`)
- Accepts same options as `trace()`: `--label`, `--max-depth`, `--max-calls`, etc.
- Register magic via `load_ipython_extension()`

### 12.3 Notebook Integration Is an Optional Extra

```
pip install tracepatch[notebook]
```

Required extras: `ipython` (soft dependency — loaded lazily).

---

## 13. Data Science & Pipeline Tracing

### 13.1 `trace` Inside Data Pipelines — Best Practices Documentation

- Write a dedicated guide: `docs/data-science.md`
- Cover: pandas, numpy, scikit-learn, PyTorch model forward passes
- Include examples with `ignore_modules = ["pandas", "numpy"]` to capture only user pipeline code
- Show how to use `max_calls` sensibly inside a pipeline that processes thousands of rows

### 13.2 Pipeline Step Tracing Pattern

A higher-level API for tracing pipeline stages:

```python
from tracepatch import Pipeline

with Pipeline(label="sklearn-training") as pipe:
    with pipe.step("load"):
        df = load_data("train.csv")
    with pipe.step("preprocess"):
        X, y = preprocess(df)
    with pipe.step("train"):
        model.fit(X, y)

pipe.summary()  # Shows per-step timing, call counts, hot functions
```

- `Pipeline` is a thin wrapper that creates named sub-traces for each step
- `pipe.summary()` prints a table:
  ```
  Step         Calls  Duration  % of Total
  ──────────────────────────────────────────
  load           142    1.23s     31.2%
  preprocess     891    2.04s     51.8%
  train           23    0.67s     17.0%
  ```

### 13.3 Memory Usage Tracking (Optional, Opt-In)

- **This is a significant feature.** Add an opt-in `track_memory=True` parameter to `trace()`.
- When enabled, record `tracemalloc` snapshots at call entry and exit
- Add `memory_delta_kb` to `TraceNode`
- Show in tree: `db.query(...)  [12ms, +4.2 KB]`
- **Hard constraint:** `tracemalloc` has real overhead. It must be explicitly opt-in. Never on by default. Well documented.

### 13.4 `t.profile()` — Statistical Profiling Mode (Light Version)

- In contrast to `trace()` which captures every call, add a `profile()` context manager (or `trace(sample=0.1)`) that samples ~10% of calls
- Use `sys.setprofile` (call/return hooks, lower overhead than `sys.settrace`) 
- Produces approximate timing without the full call tree
- Outputs: function call counts and cumulative time (similar to `cProfile` output but readable)
- This is the bridge between "scalpel debugging" and "profiling"

---

## 14. Educational Mode

### 14.1 `explain=True` Parameter

```python
with trace(explain=True) as t:
    fibonacci(10)

print(t.explain())
```

Instead of just a tree, `explain()` produces a narrative:

```
The program started by calling fibonacci(n=10).
  It then called fibonacci(n=9) and fibonacci(n=8) to compute the result.
  This continued recursively. The function fibonacci was called 177 times total.
  
Key observations:
  ● fibonacci is called recursively — each call triggers 2 more calls until n <= 1
  ● The deepest the call stack reached was 11 levels (fibonacci(n=0))
  ● 177 calls were made to compute a single result — this is exponential growth
  ● Total time: 0.32ms across all 177 calls (avg 0.002ms each)
  
This is an example of a recursive algorithm with exponential time complexity O(2^n).
Tip: This function would be much faster with memoization (caching previous results).
```

- The narrative is generated from the tree structure using pure Python logic (NO external AI/LLM)
- Detect patterns:
  - Recursion (same function appears as ancestor)
  - Loops (same function called many times from same parent)
  - Deep nesting (depth > 10)
  - Exceptions
  - Very slow calls (> 10% of total time)
  - Single-call functions (utility functions)
- Each pattern maps to a pre-written explanatory template
- Tone: clear, neutral, educational. Not patronizing.

### 14.2 Complexity Annotations

For educational use, add automatic complexity hints based on the observed call pattern:

- If `f(n)` calls itself once: `O(n)` hint
- If `f(n)` calls itself twice: `O(2^n)` hint
- If `f(n)` calls `g(n)` in a loop: `O(n)` per invocation of `f`
- **These are heuristics, not proofs.** Always label them as "observed pattern" not "proven complexity."

### 14.3 `tph explain <file>` — CLI Command

```bash
tph explain .tracepatch/traces/fibonacci_trace.json
```

Outputs the narrative explanation to stdout. Add `--verbose` for deeper analysis.

### 14.4 Side-By-Side Comparison Mode for Teaching

```python
from tracepatch import compare

@compare(label_a="recursive", label_b="memoized")
def fibonacci_recursive(n): ...

@compare.b
def fibonacci_memoized(n, memo={}): ...

compare.run(fibonacci_recursive, fibonacci_memoized, args=[10])
compare.show()  # Side-by-side HTML or terminal output
```

This is a teaching tool for showing how two implementations of the same function differ in their call patterns.

---

## 15. Performance & Reliability Hardening

### 15.1 Benchmark the Tracer Overhead

- Add a `benchmarks/` directory with reproducible micro-benchmarks using `timeit`
- Measure overhead of `sys.settrace` hook per call at various call volumes
- Publish the results in documentation so users know what to expect
- Target: overhead ≤ 5x slowdown for a function called 1,000 times (reasonable for debugging use)

### 15.2 Improve Stack Unwinding on Frame Mismatch

- **Current code in `handle_return`:** If the function name at the top of the stack doesn't match the returning frame, it does a linear scan backward through the stack. If it can't find a match, it silently returns.
- **Problem:** This can leave "zombie" nodes in the stack that accumulate over time, causing corrupted trees in long-running traces.
- **Fix:**
  - Track the frame's code object ID (`id(frame.f_code)`) alongside the function name on the stack
  - Match on code ID, not name (handles multiple functions with the same name)
  - Add a maximum stack corruption threshold: if more than 10 mismatches occur, log a warning and reset the stack

### 15.3 Thread Safety Improvements

- **Current:** `_trace_lock` protects `sys.settrace` install/uninstall. But `_trace_refcount` is modified under the lock while the hot path runs lock-free.
- **Verify:** Confirm that `ContextVar` correctly isolates collectors across threads (not just async tasks). Write a stress test with `threading.Thread`.
- **Add:** A test that starts 10 threads simultaneously, each running a `trace()` block, and verifies no cross-contamination.

### 15.4 Protect Against Trace Re-Entrance During Exception Handling

- If the traced code triggers code inside tracepatch (e.g., a `__repr__` calls a traced function), we need to ensure the re-entrant call is not recorded in the wrong collector.
- The current `_BUILTIN_IGNORE_PREFIXES` approach covers `tracepatch.*` but not the re-entrance path via `__repr__` calls from user objects.
- Add a `_in_safe_repr` thread-local flag to disable tracing during `_safe_repr` execution.

### 15.5 `max_calls` Counter Atomicity

- **Problem:** `_Collector.call_count` is incremented in `handle_call()`. In Python's GIL-protected world this is safe for CPython, but good practice is to document this assumption and add a note about PyPy/sub-interpreter limitations.

### 15.6 Empty Trace Optimization

- When `max_calls = 0` (tracing disabled), the `_global_trace` function is installed but immediately returns `None`. The sys.settrace overhead is still paid.
- **Fix:** When `max_calls == 0`, skip calling `_install_trace()` entirely in `trace.__enter__()`. The context manager becomes a no-op with zero overhead.

### 15.7 Async Generator Edge Cases

- Test `trace()` inside an async generator that is iterated across multiple event loop ticks
- Test `trace()` inside a `asyncio.TaskGroup` with multiple concurrent tasks
- Test `trace()` with `contextvars.copy_context().run()`

---

## 16. Developer Tooling (Ruff, CI/CD, Packaging)

### 16.1 Add Ruff Configuration to `pyproject.toml`

- **CRITICAL:** Ruff is a development tool. It must NOT be added to `[project.dependencies]` or `[project.optional-dependencies]`. It belongs only in dev tooling.
- Add to `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py310"
line-length = 100

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "F",   # pyflakes
    "I",   # isort
    "UP",  # pyupgrade
    "B",   # flake8-bugbear
    "SIM", # flake8-simplify
    "TCH", # flake8-type-checking
    "RUF", # ruff-specific rules
]
ignore = [
    "E501",  # line length enforced by formatter
    "B008",  # do not perform function calls in default args
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]  # allow assert in tests

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

- Add `.ruff_cache/` to `.gitignore`
- Add ruff to the dev dependencies section of `pyproject.toml` under `[project.optional-dependencies].dev` but **the library itself must have zero hard dependency on ruff**

### 16.2 `.gitignore` — Proper Entries

Current `.gitignore` is unknown (not read yet). Ensure it includes:

```gitignore
# Python
__pycache__/
*.py[cod]
*.so
dist/
build/
*.egg-info/
.eggs/

# tracepatch
.tracepatch/traces/
_tracepatch_filetotest.py

# Development tools
.ruff_cache/
.mypy_cache/
.pytest_cache/
.coverage
htmlcov/

# Virtual environments
.venv/
venv/
env/

# IDEs
.idea/
.vscode/
*.swp

# macOS
.DS_Store
```

### 16.3 GitHub Actions CI Pipeline

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: pytest --tb=short
  
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff
      - run: ruff check src/ tests/
      - run: ruff format --check src/ tests/
```

### 16.4 GitHub Actions Release Pipeline

Create `.github/workflows/release.yml`:

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - "v*"

jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write  # for trusted publishing
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install hatch
      - run: hatch build
      - uses: pypa/gh-action-pypi-publish@release/v1
```

### 16.5 Proper Author Information in `pyproject.toml`

- The `authors` field is currently `[{ name = "" }]` — empty. Fill in proper author info.
- Add `maintainers` field if relevant.

### 16.6 Add `CHANGELOG.md`

- Create `CHANGELOG.md` following [Keep a Changelog](https://keepachangelog.com/) format
- Document every version from the beginning
- Link `CHANGELOG.md` from `README.md`

### 16.7 Development Setup Documentation

Create `CONTRIBUTING.md` that covers:

```markdown
## Development Setup

git clone https://github.com/levinismynameirl/tracepatch
cd tracepatch
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pip install ruff  # NOT a project dependency — dev tool only

## Running Tests
pytest

## Linting
ruff check src/ tests/
ruff format src/ tests/

## Building
hatch build
```

### 16.8 Type Checking (mypy or pyright)

- Add `py.typed` marker (already present — verify it is at the right path: `src/tracepatch/py.typed`)
- Add `mypy` or `pyright` to dev dependencies
- Add to CI pipeline
- Fix all type errors (currently there are likely several, esp. with `Optional` vs `|` and `Any` usage)
- Configuration in `pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.10"
strict = true
warn_unused_ignores = true
```

---

## 17. Documentation — Complete Rewrite

### 17.1 README.md — Full Rewrite

The current README is good but needs:

- A one-sentence value proposition at the very top: what problem does tracepatch solve, for whom, when?
- A "when to use / when NOT to use" section (currently referenced in `__init__.py` but not in README)
- Working quick-start that a new user can copy-paste and get output in under 60 seconds
- Screenshots or ASCII art examples of actual tree output (with realistic-looking code, not `add(1, 2)`)
- Links to all doc pages
- Badges: `PyPI version`, `Python versions`, `License`, `CI status`
- Clear "zero overhead when inactive" explanation with a code sample showing how to leave it in production

### 17.2 `docs/quickstart.md` — New File

A focused, step-by-step guide for someone who just ran `pip install tracepatch`:

1. First trace in 3 lines of code
2. Understanding the output
3. Saving and reviewing traces with the CLI
4. Configuring with `tracepatch.toml`
5. Where to go next (links to other guides)

### 17.3 `docs/configuration.md` — Complete Rewrite

Current doc is incomplete (stops at `max_repr`). Must cover:

- Every configuration option with type, default, valid range, and a concrete example
- The full TOML schema with a working complete example
- Environment variables (complete table)
- `pyproject.toml` integration (exact syntax)
- Configuration precedence order (explicit path > `tracepatch.toml` > `pyproject.toml` > defaults > env vars)

### 17.4 `docs/cli-guide.md` — Fix and Expand

- Fix all references to non-existent options (see §1.8)
- Add complete examples for every command with actual plausible output
- Add a "Common Workflows" section:
  - "I want to trace a single function and see the tree immediately"
  - "I want to save traces from a FastAPI app and review them later"
  - "I want to add tracepatch to my pytest run"
  - "I want to understand why my Django view is slow"

### 17.5 `docs/reading-tree.md` — Expand

Current doc is decent. Expand with:

- Explanation of timing numbers: what "elapsed" means, why self-time matters
- How to use `--filter` effectively
- How to read folded call nodes (§6.2)
- Understanding the statistics summary header (§6.3)
- Common patterns and what they indicate (deep nesting, wide fan-out, repeated calls)

### 17.6 `docs/integrations/` — New Directory

Create separate guides for each integration:

- `docs/integrations/fastapi.md`
- `docs/integrations/flask.md`
- `docs/integrations/django.md`
- `docs/integrations/pytest.md`
- `docs/integrations/jupyter.md`
- `docs/integrations/data-science.md`

### 17.7 `docs/api-reference.md` — New File

Full API reference for the Python public API:

- `trace` class: all parameters, all methods
- `TracepatchConfig`: all fields
- `TraceNode`: all fields
- `load_config()`: signature, return type, search behavior
- `traced` decorator: usage examples
- `ConfigError`: when it's raised

### 17.8 `docs/educational.md` — New File

Guide for teachers and students:

- How to use tracepatch in a classroom setting
- Using `explain=True` to generate narrative output
- Side-by-side comparison feature
- Recommended exercises: recursive algorithms, sorting, data structures

### 17.9 `docs/performance.md` — New File

For teams who want to use tracepatch in production/staging:

- Overhead model and benchmarks (from §15.1)
- Safe patterns: trace only specific operations, use `include_modules`
- Using env vars to disable in production without code changes
- What `max_calls`, `max_depth`, `max_time` protect you from
- Thread safety guarantees

### 17.10 Docstrings — Comprehensive Audit

Every public function and class must have a complete NumPy-style or Google-style docstring:

- Parameters with types
- Return type
- Side effects (file I/O, sys.settrace installation)
- Exceptions raised
- Thread safety notes
- Examples in docstring with `>>>` examples

Run `pydocstyle` or `ruff D*` rules to enforce.

---

## 18. Test Suite — Gaps & New Coverage

### 18.1 Move Tests That Are Currently Missing

The existing test suite (`tests/test_tracepatch.py`) covers core functionality well. Add:

### 18.2 Tests for `config.py`

- `load_config()` with explicit path
- `load_config()` with `tracepatch.toml` in current directory
- `load_config()` with `pyproject.toml` `[tool.tracepatch]`
- `load_config()` parent directory search
- `load_config()` when no config file exists (returns defaults)
- `TracepatchConfig.from_dict()` with all fields
- `TracepatchConfig.from_dict()` with missing fields (should use defaults)
- `_apply_env_overrides()` for each env var
- `TRACEPATCH_ENABLED=0` disables tracing
- `save_config()` and round-trip (save then load)
- `ConfigError` raised for invalid values (once §5.5 is implemented)

### 18.3 Tests for `cli.py`

- `cmd_init` creates `tracepatch.toml`
- `cmd_init --force` overwrites existing
- `cmd_logs` with empty cache
- `cmd_logs` with multiple traces (sorted newest-first)
- `cmd_view` with valid trace file
- `cmd_view` with non-existent file (error)
- `cmd_tree` with various `--format` options
- `cmd_tree --filter 'app.*'`
- `cmd_tree --filter '!stdlib'`
- `cmd_tree --depth 3`
- `cmd_config` with and without config file
- All commands: verify exit code 0 on success, 1 on failure

### 18.4 Tests for `include_modules` (Once Implemented per §1.2)

- `include_modules=["myapp"]` traces only `myapp.*` calls
- `include_modules=[]` traces everything (default)
- Combination of `include_modules` and `ignore_modules`

### 18.5 Tests for `show_args=False` and `show_return=False` (Once Implemented per §1.4)

### 18.6 Tests for `tree_style="unicode"` (Once Implemented per §1.3)

### 18.7 Tests for the New Trace Storage Layout (§4.1)

- `_ensure_data_dir()` creates `.tracepatch/traces/` not `.tracepatch_cache/`
- `.gitignore` is written to `.tracepatch/traces/` not the top-level directory
- `state.json` is at `.tracepatch/state.json` not inside `traces/`

### 18.8 Tests for Thread Safety (§15.3)

- 10 concurrent threads, each with own `trace()` block, no cross-contamination

### 18.9 Tests for Decorator Mode Edge Cases (§1.11)

- Decorated function called twice: both calls are traced independently
- Decorated async function
- Decorated generator function

### 18.10 Tests for HTML Output Safety (§1.12)

- Args containing `<script>alert(1)</script>` — must be escaped in HTML output

### 18.11 Regression Test for Dead Code in `load_config` (§1.6)

- Verify `tomllib is None` path returns before the dead line

### 18.12 Property-Based Tests with `hypothesis`

- Add `hypothesis` as optional dev dependency
- Write property-based tests for:
  - `_safe_repr()` never raises, always returns a string
  - `render_tree()` never raises on arbitrary `TraceNode` trees
  - `TraceConfig` with random valid inputs never causes `_Collector` to raise

### 18.13 Test File Organization

- Split `tests/test_tracepatch.py` into logical files:
  - `tests/test_core.py` — basic trace behavior
  - `tests/test_config.py` — configuration
  - `tests/test_cli.py` — CLI commands
  - `tests/test_render.py` — tree/HTML/JSON rendering
  - `tests/test_cache.py` — file I/O and cache management
  - `tests/test_integrations.py` — framework integrations (skipped if deps not installed)
  - `tests/conftest.py` — shared fixtures (already exists, review and expand)

---

## Appendix A: Priority Matrix

| Section | Priority | Effort | Impact |
|---------|----------|--------|--------|
| §1 — Bug Fixes | **P0** | Low | Critical |
| §3.3 — Rename `.tracepatch_cache` | **P0** | Medium | UX |
| §3.1 — Fix init/setup confusion | **P0** | Low | UX |
| §2.1 — Module split | P1 | Medium | Maintainability |
| §6.1 — Source line numbers | P1 | Low | Core value |
| §6.2 — Call folding | P1 | Medium | Core value |
| §6.3 — Stats header | P1 | Low | Core value |
| §4.3 — Schema metadata | P1 | Low | Core value |
| §5 — Config overhaul | P1 | Medium | Completeness |
| §8 — CLI features | P1 | Medium | Core value |
| §6.5 — HTML redesign | P2 | High | Polish |
| §10 — pytest plugin | P2 | High | Ecosystem |
| §11 — Framework integrations | P2 | High | Ecosystem |
| §6.7 — Flamegraph | P2 | Medium | Power users |
| §14 — Educational mode | P2 | High | Differentiation |
| §12 — Jupyter | P3 | Medium | Niche |
| §13 — Data science | P3 | Medium | Niche |
| §16 — CI/CD | P1 | Low | Infrastructure |
| §17 — Documentation | P1 | High | Adoption |

---

## Appendix B: What a Developer From Each Context Needs

### B.1 The Junior Developer / CS Student
- `tph init` that works in 30 seconds and explains itself
- A tree that tells them *what happened*, not just *what was called*
- Recursive calls that fold instead of showing 177 identical nodes
- `explain=True` output that says "this is recursion, here's why it's slow"

### B.2 The Teacher
- `explain=True` narrative output
- Side-by-side comparison of two implementations
- HTML export they can share with a class
- Complexity hints based on call patterns

### B.3 The Data Scientist
- Works inside Jupyter with `t.show()` and `%%tracepatch` magic
- `Pipeline` wrapper for pipeline stages
- HTML tree they can share in a notebook
- Flamegraph SVG for presentations
- `ignore_modules=["pandas","numpy"]` to see only their code

### B.4 The Small Team Backend Developer
- `tph run myapp/core.py::process` — zero setup
- `tph diff` to compare before/after a refactor
- pytest fixture that saves traces on test failure
- Low-config: works well from `pyproject.toml` `[tool.tracepatch]`

### B.5 The Senior Engineer / Large Company
- FastAPI/Django/Flask middleware they can drop in
- Proper thread-safety guarantees and documentation
- CI integration with `tph config --validate` health check
- `trace.from_file()` for programmatic analysis
- `tph stats` for performance regression detection
- Structured JSON schema they can push to an observability pipeline

---

*This document is living and should be updated as tasks are completed and new issues are discovered.*

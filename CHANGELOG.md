# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-23

### Added

#### Core Tracing
- `track_memory` parameter — per-call memory delta tracking via `tracemalloc`
  (recorded as `memory_delta_kb` on `TraceNode`)
- `sample` parameter — statistical sampling (float 0–1) to randomly skip calls
  for lower-overhead profiling
- `TraceNode.file` and `TraceNode.lineno` fields for source location on every
  captured call
- `TraceSummary` dataclass with pre-computed stats: `call_count`,
  `max_depth_reached`, `unique_functions`, `unique_modules`,
  `total_duration_ms`, `slowest_call_ms`, `slowest_call_name`, `most_called`
- `trace.summary()`, `trace.explain()`, `trace.show()`, `trace.to_flamegraph()`
  methods
- `trace.load(path)` classmethod to reload a complete trace from JSON
- `trace._trace_id` (UUID) for trace correlation
- `collapse_tree(nodes, max_depth)` — auto-collapse deep subtrees into
  synthetic summary nodes
- `fold_repeated_calls(nodes, threshold)` — fold consecutive identical siblings
  into a single node with avg/min/max timing
- `render_summary_header(roots, label)` — statistics header for tree output
- Pattern-based node filtering via `_filter_node()` / `_apply_filter()`
- `include_modules` parameter now enforced in `_Collector._should_ignore()`
  (was parsed but never consulted)
- `style` parameter for `render_tree()` — choose `"ascii"` or `"unicode"`
- `show_args` / `show_return` parameters on `render_tree()` — control display
  of arguments and return values

#### CLI
- `tph init` — create a starter `tracepatch.toml` (with `--force`, `--yes`)
- `tph stats <file>` — detailed statistics report for a trace file
- `tph explain <file>` — narrative explanation of a trace (`--verbose`)
- `tph diff <file1> <file2>` — side-by-side comparison of two trace files
- `tph export <file>` — export to CSV, HTML, or flamegraph SVG
  (`--format`, `--output`)
- `tph help` — dedicated help command
- `tph tree` gains `--style`, `--no-args`, `--no-return`, `--show-source`,
  `--self-time`, `--no-stats`, `--no-fold`, `--fold-threshold`, `--collapse`
- `tph logs` gains `--label` (glob filter), `--limited` (show only limited
  traces)
- `tph config` gains `--file`, `--validate`
- `tph clean` gains `--traces`, `--older-than DURATION`, `--all`

#### Configuration
- `max_time`, `color`, `auto_save`, `default_label` fields on
  `TracepatchConfig`
- `max_repr_args` / `max_repr_return` — separate repr limits for arguments vs
  return values
- `expand_label()` — template variable expansion (`{hostname}`, `{pid}`,
  `{timestamp}`)
- `_validate()` method — validates config values, raises `ConfigError` for
  invalid types/ranges, warns on unknown keys
- `ConfigError` exception class
- Environment variable overrides: `TRACEPATCH_MAX_TIME`, `TRACEPATCH_LABEL`,
  `TRACEPATCH_OUTPUT_DIR`, `TRACEPATCH_NO_CACHE`, `TRACEPATCH_COLOR`

#### Pytest Plugin
- `TraceResult` class wrapping trace data with assertion helpers:
  `assert_called`, `assert_not_called`, `assert_called_once`,
  `assert_called_n_times`, `assert_max_calls`, `assert_max_depth`,
  `assert_under_ms`, `assert_self_time_under_ms`, `assert_no_exceptions`,
  `assert_call_order`
- CLI flags: `--tracepatch`, `--tracepatch-save`, `--tracepatch-save-on-failure`,
  `--tracepatch-fail-on-limited`, `--tracepatch-output DIR`
- `@pytest.mark.tracepatch(**kwargs)` marker for per-test configuration
  overrides
- Auto-apply fixture when `--tracepatch` flag is used or marker is present
- JUnit XML metadata attachment (`tracepatch.call_count`,
  `tracepatch.was_limited`)
- `_safe_filename()` for Windows-safe trace file names

#### Jupyter / Notebook Support
- `%%tracepatch` cell magic with `--label`, `--max-depth`, `--max-calls`,
  `--max-repr`, `--max-time`, `--no-cache` flags
- `show()` for inline HTML rendering (falls back to text outside notebooks)
- `load_ipython_extension()` for `%load_ext tracepatch`
- `notebook` optional dependency group (`ipython>=7.0`)

#### Data Science
- `Pipeline` class with `step()` context manager for multi-stage workflow
  tracing
- `StepResult` / `PipelineResult` dataclasses with per-step call counts,
  durations, and a `table()` summary
- `_educational.explain()` — narrative trace analysis detecting recursion, hot
  loops, slow calls, exceptions, and complexity heuristics

#### Modules & Architecture
- `_flamegraph.py` — interactive SVG flamegraph generation with tooltips
- `_render.py` — `render_tree_colored()`, `nodes_to_html()` with interactive
  HTML dashboard
- `_codegen.py` — test-runner code generation extracted from `instrumentation.py`
- `_git.py` — git status checks extracted from `instrumentation.py`
- `_introspect.py` — function signature introspection extracted from
  `instrumentation.py`
- `_setup.py` — test environment setup/cleanup extracted from
  `instrumentation.py`
- `_cli_output.py` — consistent CLI output formatting (`ok`, `err`, `warn`,
  `info`) with TTY auto-detection
- `integrations/` — web framework integrations: FastAPI (ASGI), Flask, Django,
  generic WSGI

#### JSON Output
- `schema_version`, `trace_id`, `hostname`, `python_version`, `platform`,
  `working_directory` fields
- `duration_ms`, `limit_reason` fields
- `config` section with all trace parameters
- `stats` section with aggregate trace statistics

#### Packaging & Tooling
- `pytest11` entry point for auto-discovered pytest plugin
- Optional dependency groups: `dev`, `config-save`, `pytest`, `notebook`
- Ruff configuration (lint rules, format settings, per-file ignores)
- GitHub Actions CI and release workflows
- `py.typed` marker for PEP 561
- `CONTRIBUTING.md`

#### Documentation
- `docs/quickstart.md`
- `docs/configuration.md`
- `docs/cli-guide.md`
- `docs/reading-tree.md`
- `docs/reading-logs.md`
- `docs/api-reference.md`
- `docs/data-science.md`

### Changed

- CLI command `setup` renamed to `run` (old name kept as hidden alias)
- CLI command `disable` renamed to `clean` (old name kept as hidden alias)
- Data directory renamed from `.tracepatch_cache/` to `.tracepatch/traces/`
  (backward-compat fallback in `trace.logs()`)
- `__version__` now read dynamically via `importlib.metadata` instead of
  hardcoded
- `_apply_env_overrides()` returns a new `TracepatchConfig` instance instead of
  mutating in-place
- `instrumentation.py` decomposed into `_codegen.py`, `_git.py`,
  `_introspect.py`, `_setup.py`
- Rendering functions moved from `cli.py` to `_render.py`
- Filter/depth/count utilities moved from `cli.py` to `_trace.py`
- `_format_elapsed` consolidated to single definition (was duplicated in
  `cli.py`)
- Decorator mode (`@trace()`) now creates a fresh instance per call (supports
  sync, async, generator, and async generator functions)
- `trace.to_json()` accepts both file paths and writable file objects
- Cache file naming changed to `{label}_{YYYYMMDD}_{HHMMSS}_{short-id}.json`
  for natural sorting
- `_TraceResult` renamed to `TraceResult` (backward-compat alias kept)

### Fixed

- `_count_and_time` in `collapse_tree()` — double-counted elapsed time by
  looping over children; now correctly uses the node's own wall-clock elapsed
- `handle_return` generator fragility — return events on suspended
  generator/coroutine frames could mis-match the call stack; now checks
  `co_name`, `co_filename`, and `co_firstlineno` for disambiguation
- `_codegen.py` module path construction — `".."` now skipped alongside `"."`
  and `"src"` when building module paths
- Decorator reuse bug — `@trace(label="x")` previously shared a single instance
  across all invocations
- Hardcoded version string in `to_json()` output replaced with dynamic
  `__version__`
- Duplicate `_count_nodes` and `_format_elapsed` definitions removed from
  `cli.py`
- Dead code after early return in `load_config()` removed
- HTML escaping in `nodes_to_html()` — user data now passed through
  `html.escape()` to prevent XSS/malformed output
- `include_modules` was configured in TOML but never enforced in
  `_Collector._should_ignore()`
- `show_args` / `show_return` were parsed but never wired to rendering
- pytest fixture rewritten with `try/finally` — `sys.exc_info()` now forwarded
  to `trace.__exit__()` so the trace sees test exceptions
- `_safe_filename()` uses `re.sub(r"[^\w.\-]", "_", ...)` instead of brittle
  manual `.replace()` chains

## [0.3.5] - 2025-01-01

### Added
- Initial public release
- `sys.settrace`-based call tracing with async support via `contextvars`
- JSON trace output with `to_json()` / `to_dict()`
- ASCII tree rendering with `render_tree()`
- TOML configuration via `tracepatch.toml`
- CLI (`tph`) with `logs`, `view`, `tree`, `config`, `setup`, `disable` commands
- Automatic trace caching
- Test environment scaffolding via `tph setup`

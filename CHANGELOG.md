# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `include_modules` parameter for allowlist-based module filtering
- `style` parameter for `render_tree()` — choose `"ascii"` or `"unicode"`
- `show_args` / `show_return` parameters for tree rendering
- `max_time` configuration field
- `color` configuration field
- Environment variable overrides: `TRACEPATCH_MAX_TIME`, `TRACEPATCH_LABEL`,
  `TRACEPATCH_OUTPUT_DIR`, `TRACEPATCH_NO_CACHE`, `TRACEPATCH_COLOR`
- HTML escaping in `nodes_to_html()` output
- Ruff configuration in `pyproject.toml`
- GitHub Actions CI and release workflows
- `CHANGELOG.md` and `CONTRIBUTING.md`

### Changed
- CLI command `setup` renamed to `run` (old name kept as alias)
- CLI command `disable` renamed to `clean` (old name kept as alias)
- Data directory renamed from `.tracepatch_cache/` to `.tracepatch/traces/`
- `__version__` now read dynamically via `importlib.metadata`
- `_apply_env_overrides()` returns new instance instead of mutating

### Fixed
- Hardcoded version string in `to_json()` output
- Duplicate `_count_nodes` and `_format_elapsed` definitions in `cli.py`
- Decorator reuse bug — each `@trace` invocation now creates a fresh instance
- Dead code after early return in `load_config()`

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

# Contributing to tracepatch

## Development Setup

```bash
git clone https://github.com/levinismynameirl/tracepatch
cd tracepatch
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Ruff is included in the dev dependencies but is **not** a runtime dependency of
the library.

## Running Tests

```bash
pytest
```

## Linting & Formatting

```bash
ruff check src/ tests/
ruff format src/ tests/
```

## Building

```bash
pip install hatch
hatch build
```

## Project Structure

```
src/tracepatch/
├── __init__.py          # Public API exports
├── _trace.py            # Core tracing engine
├── cli.py               # CLI entry point (tph)
├── config.py            # TOML configuration loading
├── instrumentation.py   # Test scaffolding / setup
└── py.typed             # PEP 561 marker
```

## Guidelines

- **Zero runtime dependencies** (except `tomli` on Python < 3.11).
- All public functions and classes must have docstrings.
- New features require tests.
- Run `ruff check` and `ruff format` before committing.
- Never break existing passing tests.

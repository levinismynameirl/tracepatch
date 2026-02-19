"""
tracepatch -- focused, opt-in runtime call tracing for a single execution context.

Not a replacement for OpenTelemetry or structured logging. This is a scalpel
for debugging one problematic request, task, or command at a time.

Usage:

    from tracepatch import trace

    with trace() as t:
        my_function()
    print(t.tree())

    async with trace() as t:
        await my_coroutine()
    t.to_json("trace.json")

Configuration:

    from tracepatch import load_config

    config = load_config()  # Loads from tracepatch.toml or pyproject.toml
    with trace(**config.to_trace_kwargs()) as t:
        my_function()
"""

from tracepatch._pipeline import Pipeline
from tracepatch._trace import TraceSummary, trace
from tracepatch.config import ConfigError, TracepatchConfig, load_config

__all__ = [
    "ConfigError",
    "Pipeline",
    "TraceSummary",
    "TracepatchConfig",
    "load_config",
    "trace",
]


def _get_version() -> str:
    """Read the package version from installed metadata.

    Returns
    -------
    str
        The version string from ``pyproject.toml`` via ``importlib.metadata``.
    """
    from importlib.metadata import version as _meta_version

    return _meta_version("tracepatch")


__version__: str = _get_version()

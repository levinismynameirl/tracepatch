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

from tracepatch._trace import trace
from tracepatch.config import load_config, TracepatchConfig

__all__ = ["trace", "load_config", "TracepatchConfig"]
__version__ = "0.1.0"

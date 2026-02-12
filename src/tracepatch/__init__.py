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
"""

from tracepatch._trace import trace

__all__ = ["trace"]
__version__ = "0.1.0"

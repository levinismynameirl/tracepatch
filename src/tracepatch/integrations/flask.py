"""Flask integration for tracepatch.

Usage::

    from tracepatch.integrations.flask import init_tracepatch

    init_tracepatch(app, ignore_modules=["flask", "werkzeug"])

Each request gets its own trace using thread-local storage (Flask is
synchronous / thread-per-request).  Traces are labelled with the HTTP
method and path, and optionally saved to disk.

Requires: ``flask`` (imported lazily).
"""

from __future__ import annotations

import contextlib
from typing import Any

try:
    from flask import Flask, g
    from flask import request as flask_request
except ImportError as exc:
    raise ImportError(
        "tracepatch.integrations.flask requires 'flask'. Install with: pip install flask"
    ) from exc


def init_tracepatch(
    app: Flask,
    *,
    ignore_modules: list[str] | None = None,
    save: bool = False,
    enabled: bool = True,
    **trace_kwargs: Any,
) -> None:
    """Attach tracepatch hooks to a Flask application.

    Parameters
    ----------
    app:
        The Flask application instance.
    ignore_modules:
        Module prefixes to exclude from tracing.
    save:
        Whether to save each trace to disk automatically.
    enabled:
        Master switch.  When *False* the hooks are registered but
        do nothing.
    **trace_kwargs:
        Forwarded to ``trace()``.
    """
    _ignore = ignore_modules or []

    @app.before_request
    def _tp_before() -> None:
        if not enabled:
            return
        from tracepatch._trace import trace as _trace_cls

        label = f"{flask_request.method} {flask_request.path}"
        t = _trace_cls(
            label=label,
            ignore_modules=_ignore,
            **trace_kwargs,
        )
        t.__enter__()
        g._tracepatch_trace = t

    @app.after_request
    def _tp_after(response: Any) -> Any:
        t = getattr(g, "_tracepatch_trace", None)
        if t is None:
            return response
        t.__exit__(None, None, None)
        if save:
            t._save_to_cache()
        return response

    @app.teardown_request
    def _tp_teardown(exc: BaseException | None) -> None:
        t = getattr(g, "_tracepatch_trace", None)
        if t is not None:
            # Ensure cleanup if after_request was not reached (e.g. error)
            with contextlib.suppress(Exception):
                t.__exit__(None, None, None)

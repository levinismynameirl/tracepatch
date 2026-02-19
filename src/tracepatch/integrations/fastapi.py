"""FastAPI / Starlette ASGI middleware for tracepatch.

Usage::

    from tracepatch.integrations.fastapi import TracepatchMiddleware

    app.add_middleware(
        TracepatchMiddleware,
        label_fn=lambda request: f"{request.method} {request.url.path}",
        ignore_modules=["starlette", "uvicorn", "fastapi"],
        save=True,
    )

Each incoming request is traced independently using an async
``trace()`` context.  The trace is labelled using *label_fn* (which
receives the ASGI ``Request`` object) and optionally saved to disk.

A ``X-Tracepatch-ID`` response header is added when *save* is True.

Requires: ``fastapi`` or ``starlette`` (imported lazily).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    from starlette.middleware.base import BaseHTTPMiddleware
except ImportError as exc:
    raise ImportError(
        "tracepatch.integrations.fastapi requires 'starlette' (or 'fastapi'). "
        "Install with: pip install fastapi"
    ) from exc

if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.requests import Request
    from starlette.responses import Response


class TracepatchMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that traces each request with tracepatch.

    Parameters
    ----------
    app:
        The ASGI application.
    label_fn:
        A callable ``(request) -> str`` returning the trace label.
        Defaults to ``"METHOD /path"``.
    ignore_modules:
        Module prefixes to exclude from tracing.
    save:
        Whether to automatically save each trace to disk.
    enabled:
        Master switch.  When *False* the middleware is a no-op.
    **trace_kwargs:
        Forwarded to ``trace()``.
    """

    def __init__(
        self,
        app: Any,
        label_fn: Callable[[Request], str] | None = None,
        ignore_modules: list[str] | None = None,
        save: bool = False,
        enabled: bool = True,
        **trace_kwargs: Any,
    ) -> None:
        super().__init__(app)
        self.label_fn = label_fn or (lambda r: f"{r.method} {r.url.path}")
        self.ignore_modules = ignore_modules or []
        self.save = save
        self.enabled = enabled
        self.trace_kwargs = trace_kwargs

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Wrap the downstream handler in a trace context."""
        if not self.enabled:
            return await call_next(request)

        from tracepatch._trace import trace as _trace_cls

        label = self.label_fn(request)
        async with _trace_cls(
            label=label,
            ignore_modules=self.ignore_modules,
            **self.trace_kwargs,
        ) as t:
            response: Response = await call_next(request)

        if self.save:
            t._save_to_cache()
            if t.cache_path is not None:
                response.headers["X-Tracepatch-ID"] = t._trace_id

        return response

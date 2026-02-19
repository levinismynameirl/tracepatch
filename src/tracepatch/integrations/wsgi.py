"""Framework-agnostic WSGI middleware for tracepatch.

Usage::

    from tracepatch.integrations.wsgi import TracepatchMiddleware

    app = TracepatchMiddleware(
        app,
        label_fn=lambda environ: environ.get("PATH_INFO", "/"),
    )

Works with any WSGI application (Bottle, Pyramid, raw WSGI, etc.).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


class TracepatchMiddleware:
    """WSGI middleware that wraps each request in a ``trace()`` context.

    Parameters
    ----------
    app:
        The WSGI application to wrap.
    label_fn:
        A callable ``(environ) -> str`` returning the trace label.
        Defaults to ``PATH_INFO``.
    ignore_modules:
        Module prefixes to exclude from tracing.
    save:
        Whether to automatically save each trace to disk.
    enabled:
        Master switch.  When *False* the middleware is a pass-through.
    **trace_kwargs:
        Forwarded to ``trace()``.
    """

    def __init__(
        self,
        app: Any,
        label_fn: Callable[..., str] | None = None,
        ignore_modules: list[str] | None = None,
        save: bool = False,
        enabled: bool = True,
        **trace_kwargs: Any,
    ) -> None:
        self.app = app
        self.label_fn = label_fn or (lambda env: env.get("PATH_INFO", "/"))
        self.ignore_modules = ignore_modules or []
        self.save = save
        self.enabled = enabled
        self.trace_kwargs = trace_kwargs

    def __call__(
        self,
        environ: dict[str, Any],
        start_response: Callable[..., Any],
    ) -> Iterable[bytes]:
        """WSGI entry point."""
        if not self.enabled:
            return self.app(environ, start_response)

        from tracepatch._trace import trace as _trace_cls

        label = self.label_fn(environ)
        with _trace_cls(
            label=label,
            ignore_modules=self.ignore_modules,
            **self.trace_kwargs,
        ) as t:
            result = self.app(environ, start_response)

        if self.save:
            t._save_to_cache()

        return result

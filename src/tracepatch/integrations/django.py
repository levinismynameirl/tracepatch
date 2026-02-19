"""Django middleware for tracepatch.

Usage in ``settings.py``::

    MIDDLEWARE = [
        "tracepatch.integrations.django.TracepatchMiddleware",
        ...
    ]

    TRACEPATCH = {
        "ignore_modules": ["django", "urllib3"],
        "save": True,
    }

Each request is traced from ``process_request`` to ``process_response``.
Configuration is read from ``settings.TRACEPATCH``.

Requires: ``django`` (imported lazily).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    from django.conf import settings
except ImportError as exc:
    raise ImportError(
        "tracepatch.integrations.django requires 'django'. "
        "Install with: pip install django"
    ) from exc

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


class TracepatchMiddleware:
    """Django middleware that traces each request with tracepatch.

    Reads configuration from ``settings.TRACEPATCH`` (a dict).

    Supported keys:

    * ``ignore_modules``: ``list[str]`` — module prefixes to exclude.
    * ``save``: ``bool`` — auto-save each trace to disk.
    * ``enabled``: ``bool`` — master switch (default ``True``).
    * Any additional keys are forwarded to ``trace()``.
    """

    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response
        self._cfg: dict[str, Any] = getattr(settings, "TRACEPATCH", {})

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Wrap the downstream handler in a trace context."""
        enabled = self._cfg.get("enabled", True)
        if not enabled:
            return self.get_response(request)

        from tracepatch._trace import trace as _trace_cls

        ignore = self._cfg.get("ignore_modules", [])
        save = self._cfg.get("save", False)
        kwargs = {
            k: v
            for k, v in self._cfg.items()
            if k not in ("ignore_modules", "save", "enabled")
        }

        label = f"{request.method} {request.path}"
        with _trace_cls(label=label, ignore_modules=ignore, **kwargs) as t:
            response = self.get_response(request)

        if save:
            t._save_to_cache()

        return response

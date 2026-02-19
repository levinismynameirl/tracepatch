"""Pipeline step-tracing for multi-stage data workflows.

Provides a thin wrapper around :class:`~tracepatch._trace.trace` that
lets you tag individual pipeline stages and get per-step statistics.

Usage::

    from tracepatch import Pipeline

    with Pipeline(label="sklearn-training") as pipe:
        with pipe.step("load"):
            df = load_data("train.csv")
        with pipe.step("preprocess"):
            X, y = preprocess(df)
        with pipe.step("train"):
            model.fit(X, y)

    pipe.summary()

All ``trace()`` keyword arguments are forwarded through the
constructor.
"""

from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator


@dataclass
class StepResult:
    """Per-step statistics for a single pipeline stage.

    Attributes
    ----------
    name:
        User-provided step name.
    call_count:
        Number of traced function calls during this step.
    duration_s:
        Wall-clock duration in seconds.
    """

    name: str
    call_count: int = 0
    duration_s: float = 0.0


@dataclass
class PipelineResult:
    """Aggregated results for an entire pipeline run.

    Attributes
    ----------
    label:
        Pipeline label (from the constructor).
    steps:
        Ordered list of per-step results.
    total_duration_s:
        Total wall-clock duration across all steps.
    """

    label: str
    steps: list[StepResult] = field(default_factory=list)
    total_duration_s: float = 0.0

    def table(self) -> str:
        """Return a formatted text table of per-step results.

        Returns
        -------
        str
            Multi-line table ready for ``print()``.
        """
        lines = []
        header = f"{'Step':<20}{'Calls':>8}{'Duration':>12}{'% of Total':>12}"
        lines.append(header)
        lines.append("\u2500" * len(header))
        for step in self.steps:
            pct = (step.duration_s / self.total_duration_s * 100) if self.total_duration_s else 0.0
            dur = _format_duration(step.duration_s)
            lines.append(f"{step.name:<20}{step.call_count:>8}{dur:>12}{pct:>11.1f}%")
        return "\n".join(lines)


def _format_duration(seconds: float) -> str:
    """Format *seconds* as a human-readable string.

    Returns values like ``1.23s``, ``456.7ms``, or ``12.3µs``.
    """
    if seconds >= 1.0:
        return f"{seconds:.2f}s"
    ms = seconds * 1000
    if ms >= 1.0:
        return f"{ms:.1f}ms"
    us = seconds * 1_000_000
    return f"{us:.1f}\u00b5s"


class Pipeline:
    """Thin wrapper around :class:`~tracepatch._trace.trace` for pipeline tracing.

    Creates a single trace context for the entire pipeline and records
    per-step call counts and durations so you can see where time is
    spent.

    Parameters
    ----------
    label:
        Human-readable pipeline label.
    **kwargs:
        Forwarded to :class:`~tracepatch._trace.trace`.
    """

    def __init__(self, *, label: str = "pipeline", **kwargs: Any) -> None:
        self._label = label
        self._trace_kwargs = kwargs
        self._trace: Any = None  # trace instance
        self._steps: list[StepResult] = []
        self._total_start: float = 0.0
        self._total_end: float = 0.0

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> Pipeline:
        from tracepatch._trace import trace as _trace

        self._trace = _trace(label=self._label, **self._trace_kwargs)
        self._trace.__enter__()
        self._total_start = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._total_end = time.perf_counter()
        if self._trace is not None:
            self._trace.__exit__(exc_type, exc_val, exc_tb)

    async def __aenter__(self) -> Pipeline:
        from tracepatch._trace import trace as _trace

        self._trace = _trace(label=self._label, **self._trace_kwargs)
        await self._trace.__aenter__()
        self._total_start = time.perf_counter()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._total_end = time.perf_counter()
        if self._trace is not None:
            await self._trace.__aexit__(exc_type, exc_val, exc_tb)

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    @contextlib.contextmanager
    def step(self, name: str) -> Generator[StepResult, None, None]:
        """Context manager that tracks a named pipeline step.

        Parameters
        ----------
        name:
            Human-readable step name (e.g. ``"load"``, ``"train"``).

        Yields
        ------
        StepResult
            A mutable result object populated on exit with call count
            and duration.
        """
        result = StepResult(name=name)
        call_count_before = 0
        if self._trace is not None:
            call_count_before = self._trace.call_count
        start = time.perf_counter()
        try:
            yield result
        finally:
            result.duration_s = time.perf_counter() - start
            if self._trace is not None:
                result.call_count = self._trace.call_count - call_count_before
            self._steps.append(result)

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    @property
    def steps(self) -> list[StepResult]:
        """Ordered list of completed steps."""
        return list(self._steps)

    @property
    def result(self) -> PipelineResult:
        """Build and return the full :class:`PipelineResult`."""
        total = self._total_end - self._total_start if self._total_end else 0.0
        return PipelineResult(
            label=self._label,
            steps=list(self._steps),
            total_duration_s=total,
        )

    @property
    def trace(self) -> Any:
        """Direct access to the underlying :class:`~tracepatch._trace.trace` instance."""
        return self._trace

    def summary(self) -> str:
        """Print and return a formatted summary table.

        Returns
        -------
        str
            The formatted table text.
        """
        text = self.result.table()
        print(text)
        return text

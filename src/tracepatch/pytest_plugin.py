"""Pytest plugin for tracepatch.

Provides:

* A ``tracepatch`` fixture that wraps each test in a trace context and
  exposes assertion helpers.
* CLI flags (``--tracepatch``, ``--tracepatch-save``,
  ``--tracepatch-save-on-failure``, ``--tracepatch-fail-on-limited``,
  ``--tracepatch-output DIR``).
* A ``@pytest.mark.tracepatch(...)`` marker for per-test configuration
  overrides.

Install with::

    pip install tracepatch[pytest]

The plugin is auto-discovered by pytest via the ``pytest11`` entry
point.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from tracepatch._trace import TraceNode


# ======================================================================
# Plugin configuration via CLI flags
# ======================================================================


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register tracepatch CLI flags with pytest."""
    group = parser.getgroup("tracepatch", "tracepatch call tracing")
    group.addoption(
        "--tracepatch",
        action="store_true",
        default=False,
        help="Enable tracepatch for all tests.",
    )
    group.addoption(
        "--tracepatch-save",
        action="store_true",
        default=False,
        help="Save all traces regardless of pass/fail.",
    )
    group.addoption(
        "--tracepatch-save-on-failure",
        action="store_true",
        default=False,
        help="Save traces only when the test fails.",
    )
    group.addoption(
        "--tracepatch-fail-on-limited",
        action="store_true",
        default=False,
        help="Fail tests whose trace was limited (hit max_calls).",
    )
    group.addoption(
        "--tracepatch-output",
        type=str,
        default=None,
        metavar="DIR",
        help="Save traces to this directory instead of .tracepatch/traces/.",
    )


# ======================================================================
# Fixture wrapper with assertion helpers
# ======================================================================


@dataclass
class TraceResult:
    """Wrapper exposed by the ``tracepatch`` fixture.

    Provides the captured trace data plus convenience assertion helpers
    for performance and correctness checks in tests.
    """

    _roots: list[TraceNode] = field(default_factory=list)
    _call_count: int = 0
    _was_limited: bool = False
    _label: str = ""
    _trace_obj: Any = None  # the real trace instance

    # --- read-only properties -------------------------------------------

    @property
    def call_count(self) -> int:
        """Total number of captured calls."""
        return self._call_count

    @property
    def was_limited(self) -> bool:
        """Whether the trace was cut short by a limit."""
        return self._was_limited

    @property
    def roots(self) -> list[TraceNode]:
        """Root-level trace nodes."""
        return self._roots

    def tree(self) -> str:
        """Return the human-readable ASCII call tree."""
        if self._trace_obj is not None:
            return self._trace_obj.tree()
        return "<no trace>"

    # --- internal tree walkers -----------------------------------------

    def _all_nodes(self) -> list[TraceNode]:
        """Collect every node from the tree in pre-order."""
        nodes: list[TraceNode] = []

        def _walk(node: TraceNode) -> None:
            nodes.append(node)
            for c in node.children:
                _walk(c)

        for r in self._roots:
            _walk(r)
        return nodes

    def _all_fqns(self) -> set[str]:
        """Collect all fully-qualified function names from the tree."""
        return {
            (f"{n.module}.{n.name}" if n.module else n.name)
            for n in self._all_nodes()
        }

    def _match_fqns(self, pattern: str) -> set[str]:
        """Return FQNs matching a glob-like pattern (supports ``*``)."""
        import fnmatch

        return {fqn for fqn in self._all_fqns() if fnmatch.fnmatch(fqn, pattern)}

    def _count_fqn_occurrences(self, pattern: str) -> int:
        """Count total call occurrences matching *pattern*."""
        import fnmatch

        count = 0
        for n in self._all_nodes():
            fqn = f"{n.module}.{n.name}" if n.module else n.name
            if fnmatch.fnmatch(fqn, pattern):
                count += 1
        return count

    # --- assertion helpers -----------------------------------------------

    def assert_called(self, pattern: str) -> None:
        """Assert at least one call matches *pattern* (glob)."""
        if not self._match_fqns(pattern):
            pytest.fail(f"Expected a call matching '{pattern}', but none found")

    def assert_not_called(self, pattern: str) -> None:
        """Assert no call matches *pattern* (glob)."""
        matches = self._match_fqns(pattern)
        if matches:
            pytest.fail(
                f"Expected no calls matching '{pattern}', but found: "
                f"{', '.join(sorted(matches))}"
            )

    def assert_called_once(self, pattern: str) -> None:
        """Assert exactly one call matches *pattern* (glob)."""
        count = self._count_fqn_occurrences(pattern)
        if count != 1:
            pytest.fail(
                f"Expected exactly 1 call matching '{pattern}', but found {count}"
            )

    def assert_called_n_times(self, pattern: str, n: int) -> None:
        """Assert exactly *n* calls match *pattern* (glob)."""
        count = self._count_fqn_occurrences(pattern)
        if count != n:
            pytest.fail(
                f"Expected exactly {n} calls matching '{pattern}', but found {count}"
            )

    def assert_max_calls(self, max_n: int) -> None:
        """Assert total call count does not exceed *max_n*."""
        if self._call_count > max_n:
            pytest.fail(
                f"Expected at most {max_n} calls, but got {self._call_count}"
            )

    def assert_max_depth(self, max_d: int) -> None:
        """Assert tree depth does not exceed *max_d*."""
        from tracepatch._trace import TraceSummary

        summary = TraceSummary.from_roots(self._roots)
        if summary.max_depth_reached > max_d:
            pytest.fail(
                f"Expected max depth {max_d}, but reached "
                f"{summary.max_depth_reached}"
            )

    def assert_under_ms(self, pattern: str, max_ms: float) -> None:
        """Assert every call matching *pattern* took <*max_ms* (total elapsed)."""
        import fnmatch

        for n in self._all_nodes():
            fqn = f"{n.module}.{n.name}" if n.module else n.name
            if fnmatch.fnmatch(fqn, pattern):
                ms = n.elapsed * 1000
                if ms > max_ms:
                    pytest.fail(
                        f"{fqn} took {ms:.2f}ms (total), exceeding limit of {max_ms}ms"
                    )

    def assert_self_time_under_ms(self, pattern: str, max_ms: float) -> None:
        """Assert self-time of every call matching *pattern* is below *max_ms*.

        Self-time is elapsed time minus the sum of direct children's
        elapsed times.  This is useful for catching functions that are
        slow in their own right, regardless of how long their callees
        take.
        """
        import fnmatch

        for n in self._all_nodes():
            fqn = f"{n.module}.{n.name}" if n.module else n.name
            if fnmatch.fnmatch(fqn, pattern):
                child_sum = sum(c.elapsed for c in n.children)
                self_ms = max(0.0, n.elapsed - child_sum) * 1000
                if self_ms > max_ms:
                    pytest.fail(
                        f"{fqn} self-time was {self_ms:.2f}ms, exceeding limit of {max_ms}ms"
                    )

    def assert_no_exceptions(self) -> None:
        """Assert no ``TraceNode`` in the tree has an exception recorded."""
        for n in self._all_nodes():
            if n.exception is not None:
                fqn = f"{n.module}.{n.name}" if n.module else n.name
                pytest.fail(f"{fqn} raised an exception: {n.exception}")

    def assert_call_order(self, patterns: list[str]) -> None:
        """Assert functions matching *patterns* were called in order.

        For each pattern in *patterns*, finds the *first* call in the
        trace (pre-order traversal) that matches.  Asserts that these
        first occurrences appear in strictly increasing order.

        Parameters
        ----------
        patterns:
            Glob patterns, each expected to match at least one call.
        """
        import fnmatch

        all_nodes = self._all_nodes()
        prev_idx = -1
        prev_pat = ""
        for pat in patterns:
            found = False
            for idx, n in enumerate(all_nodes):
                fqn = f"{n.module}.{n.name}" if n.module else n.name
                if fnmatch.fnmatch(fqn, pat):
                    if idx <= prev_idx:
                        pytest.fail(
                            f"Expected '{pat}' to be called after '{prev_pat}', "
                            f"but it appeared earlier or at the same position"
                        )
                    prev_idx = idx
                    prev_pat = pat
                    found = True
                    break
            if not found:
                pytest.fail(f"Expected a call matching '{pat}', but none found")


# Backward compatibility alias — the class was previously named with a
# leading underscore.  Keep the old name importable so that existing code
# referencing ``_TraceResult`` continues to work.
_TraceResult = TraceResult


# ======================================================================
# Fixture
# ======================================================================


def _safe_filename(label: str) -> str:
    """Sanitise a test node ID into a safe filename.

    Replaces characters that are problematic on Windows (``[]():`` etc.)
    with underscores.
    """
    return re.sub(r"[^\w.\-]", "_", label)


@pytest.fixture()
def tracepatch(request: pytest.FixtureRequest) -> TraceResult:  # type: ignore[misc]
    """Run the enclosing test inside a tracepatch trace context.

    Returns a :class:`TraceResult` with the captured data and assertion
    helpers such as ``assert_called``, ``assert_max_calls`` etc.

    Per-test configuration can be set via the ``tracepatch`` marker::

        @pytest.mark.tracepatch(max_depth=5, include_modules=["myapp"])
        def test_something(tracepatch):
            ...
    """
    from tracepatch._trace import trace as _trace_cls

    # Determine label from the test name
    label = request.node.nodeid

    # Per-test configuration from @pytest.mark.tracepatch(...)
    trace_kwargs: dict[str, Any] = {"label": label}
    marker = request.node.get_closest_marker("tracepatch")
    if marker is not None:
        trace_kwargs.update(marker.kwargs)

    t = _trace_cls(**trace_kwargs)
    result = TraceResult(_label=label, _trace_obj=t)

    # Use a proper try/finally so we see whether the test raised.
    test_failed = False
    t.__enter__()
    try:
        yield result  # type: ignore[misc]
    except BaseException:
        test_failed = True
        raise
    finally:
        # Pass exception info through so the trace knows about failures.
        import sys

        exc_info = sys.exc_info()
        t.__exit__(*exc_info)

        # Populate result after trace completes
        result._roots = t.roots
        result._call_count = t.call_count
        result._was_limited = t.was_limited

        # CLI flags
        config = request.config
        fail_on_limited = config.getoption("--tracepatch-fail-on-limited", default=False)
        save_always = config.getoption("--tracepatch-save", default=False)
        save_on_failure = config.getoption("--tracepatch-save-on-failure", default=False)
        output_dir = config.getoption("--tracepatch-output", default=None)

        if fail_on_limited and result._was_limited:
            pytest.fail(f"Trace was limited for {label}")

        should_save = save_always or (save_on_failure and test_failed)
        if should_save:
            out = Path(output_dir) if output_dir else Path(".tracepatch") / "traces"
            out.mkdir(parents=True, exist_ok=True)
            safe_name = _safe_filename(label)
            t.to_json(out / f"{safe_name}.json")

        # Attach trace metadata to JUnit XML report when available.
        if hasattr(request.node, "user_properties"):
            request.node.user_properties.append(
                ("tracepatch.call_count", result._call_count)
            )
            request.node.user_properties.append(
                ("tracepatch.was_limited", result._was_limited)
            )


# ======================================================================
# Marker registration
# ======================================================================


def pytest_configure(config: pytest.Config) -> None:
    """Register the ``tracepatch`` marker."""
    config.addinivalue_line(
        "markers",
        "tracepatch(**kwargs): per-test configuration for the tracepatch fixture "
        "(max_depth, max_calls, include_modules, ignore_modules, etc.)",
    )


# ======================================================================
# Auto-apply fixture when --tracepatch is used
# ======================================================================


def pytest_collection_modifyitems(
    session: pytest.Session,
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """If ``--tracepatch`` is given, request the fixture for every test.

    Also auto-apply the fixture for tests decorated with
    ``@pytest.mark.tracepatch(...)``.
    """
    global_enabled = config.getoption("--tracepatch", default=False)

    for item in items:
        if not isinstance(item, pytest.Function):
            continue

        has_marker = item.get_closest_marker("tracepatch") is not None

        if (global_enabled or has_marker) and "tracepatch" not in item.fixturenames:
            item.fixturenames.append("tracepatch")

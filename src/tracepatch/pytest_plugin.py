"""Pytest plugin for tracepatch.

Provides:

* A ``tracepatch`` fixture that wraps each test in a trace context and
  exposes assertion helpers.
* CLI flags (``--tracepatch``, ``--tracepatch-save``,
  ``--tracepatch-fail-on-limited``, ``--tracepatch-output DIR``).

Install with::

    pip install tracepatch[pytest]

The plugin is auto-discovered by pytest via the ``pytest11`` entry
point.
"""

from __future__ import annotations

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
class _TraceResult:
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

    # --- assertion helpers ---------------------------------------------

    def _all_fqns(self) -> set[str]:
        """Collect all fully-qualified function names from the tree."""
        fqns: set[str] = set()

        def _walk(node: TraceNode) -> None:
            fqn = f"{node.module}.{node.name}" if node.module else node.name
            fqns.add(fqn)
            for c in node.children:
                _walk(c)

        for r in self._roots:
            _walk(r)
        return fqns

    def _match_fqns(self, pattern: str) -> set[str]:
        """Return FQNs matching a glob-like pattern (supports ``*``)."""
        import fnmatch

        return {fqn for fqn in self._all_fqns() if fnmatch.fnmatch(fqn, pattern)}

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
        """Assert every call matching *pattern* took <*max_ms* milliseconds."""
        import fnmatch

        def _check(node: TraceNode) -> None:
            fqn = f"{node.module}.{node.name}" if node.module else node.name
            if fnmatch.fnmatch(fqn, pattern):
                ms = node.elapsed * 1000
                if ms > max_ms:
                    pytest.fail(
                        f"{fqn} took {ms:.2f}ms, exceeding limit of {max_ms}ms"
                    )
            for c in node.children:
                _check(c)

        for r in self._roots:
            _check(r)


# ======================================================================
# Fixture
# ======================================================================


@pytest.fixture()
def tracepatch(request: pytest.FixtureRequest) -> _TraceResult:
    """Run the enclosing test inside a tracepatch trace context.

    Returns a ``_TraceResult`` with the captured data and assertion
    helpers such as ``assert_called``, ``assert_max_calls`` etc.
    """
    from tracepatch._trace import trace as _trace_cls

    # Determine label from the test name
    label = request.node.nodeid

    t = _trace_cls(label=label)
    t.__enter__()

    result = _TraceResult(_label=label, _trace_obj=t)

    yield result  # type: ignore[misc]

    t.__exit__(None, None, None)

    # Populate result after trace completes
    result._roots = t.roots
    result._call_count = t.call_count
    result._was_limited = t.was_limited

    # CLI flags
    config = request.config
    fail_on_limited = config.getoption("--tracepatch-fail-on-limited", default=False)
    save = config.getoption("--tracepatch-save", default=False)
    output_dir = config.getoption("--tracepatch-output", default=None)

    if fail_on_limited and result._was_limited:
        pytest.fail(f"Trace was limited for {label}")

    if save:
        out = Path(output_dir) if output_dir else Path(".tracepatch") / "traces"
        out.mkdir(parents=True, exist_ok=True)
        safe_name = label.replace("/", "_").replace("::", "_").replace(" ", "_")
        t.to_json(out / f"{safe_name}.json")


# ======================================================================
# Auto-apply fixture when --tracepatch is used
# ======================================================================


def pytest_collection_modifyitems(
    session: pytest.Session,
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """If ``--tracepatch`` is given, request the fixture for every test."""
    if not config.getoption("--tracepatch", default=False):
        return

    for item in items:
        if isinstance(item, pytest.Function):
            item.fixturenames.append("tracepatch")

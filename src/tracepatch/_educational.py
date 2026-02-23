"""Educational mode for tracepatch.

Generates a narrative explanation of a trace tree by detecting common
patterns (recursion, loops, deep nesting, exceptions, hot functions)
and producing pre-written educational text.
This is not a replacement for human analysis, but can provide quick
and helpful insights, especially for those new to reading call trees.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tracepatch._trace import TraceNode


# ======================================================================
# Pattern detectors
# ======================================================================


def _detect_recursion(
    roots: list[TraceNode],
) -> list[dict[str, object]]:
    """Find functions that appear as their own ancestor (direct recursion).

    Returns a list of dicts: ``{"name": str, "max_depth": int, "count": int}``.
    """
    results: dict[str, dict[str, object]] = {}

    def _walk(node: TraceNode, ancestors: set[str], depth: int) -> None:
        fqn = f"{node.module}.{node.name}" if node.module else node.name
        if fqn in ancestors:
            entry = results.setdefault(fqn, {"name": fqn, "max_depth": 0, "count": 0})
            entry["count"] = int(entry["count"]) + 1  # type: ignore[arg-type]
            if depth > int(entry["max_depth"]):  # type: ignore[arg-type]
                entry["max_depth"] = depth
        new_ancestors = ancestors | {fqn}
        for c in node.children:
            _walk(c, new_ancestors, depth + 1)

    for r in roots:
        _walk(r, set(), 0)

    return list(results.values())


def _detect_hot_loops(
    roots: list[TraceNode],
    threshold: int = 5,
) -> list[dict[str, object]]:
    """Find functions called many times from the same parent.

    Returns a list of dicts: ``{"name": str, "parent": str, "count": int}``.
    """
    results: list[dict[str, object]] = []

    def _walk(node: TraceNode) -> None:
        if not node.children:
            return
        counts: dict[str, int] = {}
        for c in node.children:
            fqn = f"{c.module}.{c.name}" if c.module else c.name
            counts[fqn] = counts.get(fqn, 0) + 1
        parent_fqn = f"{node.module}.{node.name}" if node.module else node.name
        for name, cnt in counts.items():
            if cnt >= threshold:
                results.append({"name": name, "parent": parent_fqn, "count": cnt})
        for c in node.children:
            _walk(c)

    for r in roots:
        _walk(r)

    return results


def _detect_slow_calls(
    roots: list[TraceNode],
    total_ms: float,
    pct_threshold: float = 10.0,
) -> list[dict[str, object]]:
    """Find calls that consume ≥ pct_threshold% of total time.

    Returns a list of dicts: ``{"name": str, "ms": float, "pct": float}``.
    """
    results: list[dict[str, object]] = []
    if total_ms <= 0:
        return results

    def _walk(node: TraceNode) -> None:
        ms = node.elapsed * 1000
        pct = (ms / total_ms) * 100
        if pct >= pct_threshold:
            fqn = f"{node.module}.{node.name}" if node.module else node.name
            results.append({"name": fqn, "ms": round(ms, 2), "pct": round(pct, 1)})
        for c in node.children:
            _walk(c)

    for r in roots:
        _walk(r)

    return results


def _detect_exceptions(roots: list[TraceNode]) -> list[dict[str, object]]:
    """Find calls that raised exceptions.

    Returns a list of dicts: ``{"name": str, "exception": str}``.
    """
    results: list[dict[str, object]] = []

    def _walk(node: TraceNode) -> None:
        if node.exception:
            fqn = f"{node.module}.{node.name}" if node.module else node.name
            results.append({"name": fqn, "exception": node.exception})
        for c in node.children:
            _walk(c)

    for r in roots:
        _walk(r)

    return results


# ======================================================================
# Complexity heuristics
# ======================================================================


def _guess_complexity(
    roots: list[TraceNode],
) -> list[dict[str, str]]:
    """Heuristic complexity hints based on observed call patterns.

    Returns a list of ``{"name": str, "hint": str}`` dicts.

    These are *observed patterns*, **not** proven complexity bounds.
    """
    # Count self-recursive calls per function
    func_self_calls: dict[str, int] = {}

    def _walk(node: TraceNode) -> None:
        fqn = f"{node.module}.{node.name}" if node.module else node.name
        child_same = sum(
            1 for c in node.children if (f"{c.module}.{c.name}" if c.module else c.name) == fqn
        )
        if child_same > 0:
            func_self_calls[fqn] = max(func_self_calls.get(fqn, 0), child_same)
        for c in node.children:
            _walk(c)

    for r in roots:
        _walk(r)

    hints: list[dict[str, str]] = []
    for name, branches in func_self_calls.items():
        if branches == 1:
            hints.append({"name": name, "hint": "O(n) — linear recursion (observed pattern)"})
        elif branches == 2:
            hints.append({"name": name, "hint": "O(2^n) — binary recursion (observed pattern)"})
        elif branches >= 3:
            hints.append(
                {
                    "name": name,
                    "hint": f"O({branches}^n) — {branches}-way recursion (observed pattern)",
                }
            )

    return hints


# ======================================================================
# Narrative generation
# ======================================================================


def explain(
    roots: list[TraceNode],
    *,
    verbose: bool = False,
) -> str:
    """Generate a narrative explanation of the trace.

    The output is a human-readable summary describing what happened,
    key observations (recursion, loops, slow calls, exceptions), and
    optional complexity hints.

    Parameters
    ----------
    roots:
        Root-level trace nodes.
    verbose:
        When True, include complexity hints and deeper analysis.

    Returns
    -------
    str
    """
    from tracepatch._trace import TraceSummary

    if not roots:
        return "The trace is empty — no calls were captured."

    summary = TraceSummary.from_roots(roots)
    lines: list[str] = []

    # --- Opening summary -------------------------------------------------
    first = roots[0]
    fqn0 = f"{first.module}.{first.name}" if first.module else first.name
    if len(roots) == 1:
        lines.append(f"The program started by calling {fqn0}({first.args}).")
    else:
        names = ", ".join(f"{r.module}.{r.name}" if r.module else r.name for r in roots[:3])
        more = f" and {len(roots) - 3} more" if len(roots) > 3 else ""
        lines.append(f"The program made {len(roots)} top-level calls: {names}{more}.")

    lines.append(
        f"In total, {summary.call_count} function call(s) were recorded "
        f"across {summary.unique_module_count} module(s)."
    )
    lines.append(f"The deepest the call stack reached was {summary.max_depth_reached} level(s).")
    lines.append("")

    # --- Pattern observations -------------------------------------------
    lines.append("Key observations:")

    observations = 0

    # Recursion
    recursion = _detect_recursion(roots)
    for rec in recursion:
        observations += 1
        lines.append(
            f"  \u25cf {rec['name']} is called recursively "
            f"(max depth {rec['max_depth']}, {rec['count']} recursive call(s))"
        )

    # Hot loops
    loops = _detect_hot_loops(roots)
    for loop in loops[:5]:
        observations += 1
        lines.append(
            f"  \u25cf {loop['name']} is called {loop['count']} times "
            f"from {loop['parent']} (possible loop)"
        )

    # Slow calls
    slow = _detect_slow_calls(roots, summary.total_duration_ms)
    for s in slow[:5]:
        observations += 1
        lines.append(f"  \u25cf {s['name']} is slow — {s['ms']}ms ({s['pct']}% of total time)")

    # Exceptions
    exceptions = _detect_exceptions(roots)
    for exc in exceptions[:3]:
        observations += 1
        lines.append(f"  \u25cf {exc['name']} raised: {exc['exception']}")

    # Deep nesting
    if summary.max_depth_reached > 10:
        observations += 1
        lines.append(
            f"  \u25cf Deep nesting detected ({summary.max_depth_reached} levels) "
            f"— consider refactoring to reduce call depth"
        )

    if observations == 0:
        lines.append("  (no notable patterns detected)")

    # --- Complexity hints (verbose) -------------------------------------
    if verbose:
        hints = _guess_complexity(roots)
        if hints:
            lines.append("")
            lines.append("Complexity hints (observed patterns, not proofs):")
            for h in hints:
                lines.append(f"  \u25cf {h['name']}: {h['hint']}")

    # --- Closing stats ---------------------------------------------------
    lines.append("")
    from tracepatch._trace import _format_elapsed

    dur = _format_elapsed(summary.total_duration_ms / 1000)
    lines.append(f"Total time: {dur} across {summary.call_count} call(s).")
    if summary.slowest_call_name:
        lines.append(
            f"Slowest single call: {summary.slowest_call_name} "
            f"[{_format_elapsed(summary.slowest_call_ms / 1000)}]"
        )

    return "\n".join(lines)

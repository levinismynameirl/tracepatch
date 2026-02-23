"""Flamegraph SVG generator for tracepatch.

Produces a self-contained, interactive SVG flamegraph from a list of
``TraceNode`` roots.  The flamegraph format shows each function as a
horizontal bar whose width is proportional to its *total* elapsed time,
stacked vertically by call depth.

All SVG generation is pure Python — no external dependencies.
"""

from __future__ import annotations

import html as _html
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tracepatch._trace import TraceNode

# --- Colour palette (warm gradient for flame effect) ---------------------
_PALETTE = [
    "#f8696b",
    "#fb8c62",
    "#fdae61",
    "#fee08b",
    "#e6f48d",
    "#a6d96a",
    "#66bd63",
    "#1a9850",
    "#f9cb5b",
    "#f08e54",
    "#e0574f",
    "#d73d47",
    "#fca55d",
    "#fdcb6e",
    "#e67e22",
    "#d35400",
]


def _color_for(name: str) -> str:
    """Deterministic colour for a function name based on hash."""
    return _PALETTE[hash(name) % len(_PALETTE)]


def _format_ms(seconds: float) -> str:
    """Human-friendly elapsed time as milliseconds or seconds string."""
    ms = seconds * 1000
    if ms < 1:
        return f"{ms * 1000:.0f}\u00b5s"
    if ms < 1000:
        return f"{ms:.2f}ms"
    return f"{seconds:.3f}s"


def nodes_to_flamegraph(
    roots: list[TraceNode],
    *,
    title: str = "Flamegraph",
    width: int = 1200,
    row_height: int = 20,
    font_size: int = 11,
) -> str:
    """Generate a self-contained SVG flamegraph string.

    Parameters
    ----------
    roots:
        Top-level trace nodes.
    title:
        Title shown at the top of the SVG.
    width:
        SVG pixel width.
    row_height:
        Height of each stack frame bar in pixels.
    font_size:
        Font size for labels.

    Returns
    -------
    str
        Complete SVG document as a string.
    """
    if not roots:
        return _empty_svg(title, width, row_height)

    # Determine total duration for x-axis scaling
    total_time = sum(r.elapsed for r in roots)
    if total_time <= 0:
        total_time = 1e-9  # avoid division by zero

    # Compute maximum depth for SVG height
    max_depth = 0

    def _find_max_depth(node: TraceNode, depth: int) -> None:
        nonlocal max_depth
        if depth > max_depth:
            max_depth = depth
        for c in node.children:
            _find_max_depth(c, depth + 1)

    for r in roots:
        _find_max_depth(r, 0)

    title_height = 30
    svg_height = title_height + (max_depth + 2) * row_height
    usable_width = width - 20  # 10px margin each side

    rects: list[str] = []

    def _render_node(node: TraceNode, x_offset: float, depth: int) -> None:
        """Recursively render a node and its children as SVG rects."""
        bar_width = (node.elapsed / total_time) * usable_width
        if bar_width < 0.5:
            return  # too narrow to display

        # Flamegraph: deepest calls at bottom, roots at top
        y = title_height + depth * row_height
        color = _color_for(f"{node.module}.{node.name}")
        fqn = _html.escape(f"{node.module}.{node.name}")
        args_esc = _html.escape(node.args[:80])
        elapsed_str = _format_ms(node.elapsed)

        # Truncate label to fit bar
        max_chars = max(1, int(bar_width / (font_size * 0.6)))
        label = f"{node.module}.{node.name}"
        if len(label) > max_chars:
            label = label[: max_chars - 1] + "\u2026"
        label_esc = _html.escape(label)

        tooltip = f"{fqn}({args_esc}) [{elapsed_str}]"

        rects.append(
            f'<g class="frame">'
            f"<title>{tooltip}</title>"
            f'<rect x="{x_offset + 10:.2f}" y="{y}" '
            f'width="{bar_width:.2f}" height="{row_height - 2}" '
            f'fill="{color}" rx="1" />'
        )
        if bar_width > font_size * 2:
            text_x = x_offset + 10 + 3
            text_y = y + row_height - 5
            rects.append(
                f'<text x="{text_x:.2f}" y="{text_y}" '
                f'font-size="{font_size}" fill="#000" '
                f'clip-path="url(#clip-{len(rects)})">'
                f"{label_esc}</text>"
            )
        rects.append("</g>")

        # Render children left-to-right within this node's span
        child_x = x_offset
        for child in node.children:
            _render_node(child, child_x, depth + 1)
            child_x += (child.elapsed / total_time) * usable_width

    x_cursor = 0.0
    for root in roots:
        _render_node(root, x_cursor, 0)
        x_cursor += (root.elapsed / total_time) * usable_width

    safe_title = _html.escape(title)
    rects_str = "\n".join(rects)

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg"
     width="{width}" height="{svg_height}"
     viewBox="0 0 {width} {svg_height}"
     font-family="monospace">
<style>
.frame rect:hover {{ stroke: #000; stroke-width: 1; opacity: 0.8; }}
.frame text {{ pointer-events: none; }}
</style>
<rect width="100%" height="100%" fill="#fafafa"/>
<text x="10" y="20" font-size="14" font-weight="bold" fill="#333">{safe_title}</text>
{rects_str}
</svg>"""


def _empty_svg(title: str, width: int, row_height: int) -> str:
    """Return a minimal SVG indicating no data."""
    safe_title = _html.escape(title)
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{row_height * 3}" font-family="monospace">\n'
        f'<rect width="100%" height="100%" fill="#fafafa"/>\n'
        f'<text x="10" y="20" font-size="14" fill="#333">'
        f"{safe_title}</text>\n"
        f'<text x="10" y="45" font-size="12" fill="#999">'
        f"No calls to display.</text>\n"
        f"</svg>"
    )

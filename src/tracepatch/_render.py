"""Rendering helpers for tracepatch trace trees.

Provides coloured terminal output and HTML generation for trace node
trees.  All user-derived strings in HTML output are escaped via
``html.escape()`` to prevent XSS.
"""

from __future__ import annotations

import html as _html
import sys

from tracepatch._trace import TraceNode, _format_elapsed

# ANSI colour codes used for duration-based colouring.
COLORS = {
    "reset": "\033[0m",
    "green": "\033[92m",  # Fast (<10ms)
    "yellow": "\033[93m",  # Slow (10ms-100ms)
    "red": "\033[91m",  # Very slow (>100ms)
    "gray": "\033[90m",  # Metadata
}


def _colorize_by_duration(text: str, elapsed_ms: float) -> str:
    """Colorize *text* based on call duration.

    Green: < 10ms (fast)
    Yellow: 10ms - 100ms (slow)
    Red: > 100ms (very slow)

    No colour is applied when stdout is not a TTY.
    """
    if not sys.stdout.isatty():
        return text

    if elapsed_ms < 10:
        return f"{COLORS['green']}{text}{COLORS['reset']}"
    elif elapsed_ms < 100:
        return f"{COLORS['yellow']}{text}{COLORS['reset']}"
    else:
        return f"{COLORS['red']}{text}{COLORS['reset']}"


def render_tree_colored(
    roots: list[TraceNode],
    *,
    show_args: bool = True,
    show_return: bool = True,
) -> str:
    """Render tree with ANSI colours based on call duration.

    Parameters
    ----------
    roots:
        Top-level trace nodes.
    show_args:
        Include argument strings in output.
    show_return:
        Include return values / exceptions in output.

    Returns
    -------
    str
    """
    lines: list[str] = []

    def _walk(node: TraceNode, prefix: str, is_last: bool) -> None:
        connector = "└── " if is_last else "├── "
        ret = ""
        if show_return:
            if node.exception is not None:
                ret = f" !! {node.exception}"
            elif node.return_value is not None:
                ret = f" -> {node.return_value}"

        timing = _format_elapsed(node.elapsed)
        elapsed_ms = node.elapsed * 1000
        args_part = f"({node.args})" if show_args else "()"
        label = f"{node.module}.{node.name}{args_part}{ret}  [{timing}]"

        colored_label = _colorize_by_duration(label, elapsed_ms)
        lines.append(f"{prefix}{connector}{colored_label}")

        extension = "    " if is_last else "│   "
        child_prefix = prefix + extension
        for i, child in enumerate(node.children):
            _walk(child, child_prefix, i == len(node.children) - 1)

    for i, root in enumerate(roots):
        _walk(root, "", i == len(roots) - 1)

    return "\n".join(lines)


def nodes_to_html(roots: list[TraceNode], title: str = "Trace Tree") -> str:
    """Convert trace nodes to a rich interactive HTML document.

    The output is a single self-contained HTML file with:

    * A header bar showing the trace label, total call count, duration,
      max depth, and unique function count.
    * A two-column layout: a sidebar with "Top 10 Slowest" and
      "Top 10 Most Called" panels, and the main call tree.
    * Expand / Collapse All buttons.
    * A search box that highlights matching function and module names.
    * Click-to-expand detail for each node showing full args and return
      value in a modal overlay.
    * Colour-coded timing (fast / slow / very-slow).

    All CSS and JS are inlined — no external resources.  All user-derived
    strings are escaped via ``html.escape()`` to prevent XSS.

    Parameters
    ----------
    roots:
        Trace nodes to render.
    title:
        Page / heading title.

    Returns
    -------
    str
        Self-contained HTML document.
    """
    from tracepatch._trace import TraceSummary

    safe_title = _html.escape(title)
    summary = TraceSummary.from_roots(roots)

    # -- Gather per-function statistics for sidebar panels ----------------
    func_stats: dict[str, dict[str, object]] = {}

    def _gather(node: TraceNode) -> None:
        fqn = f"{node.module}.{node.name}" if node.module else node.name
        entry = func_stats.setdefault(fqn, {"count": 0, "total_ms": 0.0, "max_ms": 0.0})
        entry["count"] += 1  # type: ignore[operator]
        ms = node.elapsed * 1000
        entry["total_ms"] += ms  # type: ignore[operator]
        if ms > entry["max_ms"]:  # type: ignore[operator]
            entry["max_ms"] = ms
        for c in node.children:
            _gather(c)

    for r in roots:
        _gather(r)

    slowest = sorted(func_stats.items(), key=lambda x: x[1]["total_ms"], reverse=True)[:10]  # type: ignore[arg-type]
    most_called = sorted(func_stats.items(), key=lambda x: x[1]["count"], reverse=True)[:10]  # type: ignore[arg-type]

    # -- Build sidebar HTML -----------------------------------------------
    def _sidebar_list(items: list[tuple[str, dict[str, object]]], value_key: str) -> str:
        parts: list[str] = []
        for fname, st in items:
            safe_name = _html.escape(fname)
            if value_key == "total_ms":
                val = f"{_format_elapsed(st['total_ms'] / 1000)}"  # type: ignore[operator]
            else:
                val = f"\u00d7{st['count']}"
            parts.append(
                f"<li><span class='sb-name'>{safe_name}</span>"
                f"<span class='sb-val'>{val}</span></li>"
            )
        return "\n".join(parts)

    slowest_html = _sidebar_list(slowest, "total_ms")
    most_called_html = _sidebar_list(most_called, "count")

    # -- Build tree HTML --------------------------------------------------
    tree_parts: list[str] = []
    _node_id = 0

    def _node_to_html(node: TraceNode) -> None:
        nonlocal _node_id
        nid = _node_id
        _node_id += 1
        has_children = len(node.children) > 0
        toggle = "\u25bc" if has_children else "\u2022"
        elapsed_ms = node.elapsed * 1000

        timing_class = "fast" if elapsed_ms < 10 else ("slow" if elapsed_ms < 100 else "very-slow")
        timing_str = _format_elapsed(node.elapsed)

        # Truncated args/return for inline display
        short_args = _html.escape(node.args[:80] + ("\u2026" if len(node.args) > 80 else ""))
        full_args = _html.escape(node.args)
        full_ret = _html.escape(node.return_value or "")
        full_exc = _html.escape(node.exception or "")

        tree_parts.append(f"<div class='node' id='n{nid}'>")
        onclick = " onclick='tp_toggle(this)'" if has_children else ""
        tree_parts.append(f"<span class='toggle'{onclick}>{toggle}</span>")

        tree_parts.append(f"<span class='module'>{_html.escape(node.module)}</span>.")
        tree_parts.append(f"<span class='name'>{_html.escape(node.name)}</span>")
        tree_parts.append(f"(<span class='args'>{short_args}</span>)")

        if node.exception:
            tree_parts.append(
                f" <span class='exception'>!! {_html.escape(node.exception[:60])}</span>"
            )
        elif node.return_value:
            short_ret = _html.escape(
                node.return_value[:60] + ("\u2026" if len(node.return_value) > 60 else "")
            )
            tree_parts.append(f" <span class='return'>\u2192 {short_ret}</span>")

        tree_parts.append(f" <span class='timing {timing_class}'>[{timing_str}]</span>")

        # Hidden data attributes for modal detail
        tree_parts.append(
            f"<span class='detail-data' hidden "
            f"data-args='{full_args}' data-ret='{full_ret}' "
            f"data-exc='{full_exc}' "
            f"data-mod='{_html.escape(node.module)}' "
            f"data-name='{_html.escape(node.name)}' "
            f"data-time='{timing_str}'></span>"
        )
        # Info button
        tree_parts.append("<span class='info-btn' onclick='tp_detail(this)'>\u24d8</span>")

        tree_parts.append("</div>")

        if has_children:
            tree_parts.append("<div class='children'>")
            for child in node.children:
                _node_to_html(child)
            tree_parts.append("</div>")

    for root in roots:
        _node_to_html(root)

    tree_html = "\n".join(tree_parts)
    dur_str = _format_elapsed(summary.total_duration_ms / 1000)

    # -- Assemble full HTML document --------------------------------------
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{safe_title}</title>
<style>
*,*::before,*::after{{box-sizing:border-box}}
body{{font-family:'Monaco','Menlo','Courier New',monospace;margin:0;padding:0;background:#1e1e1e;color:#d4d4d4;font-size:13px}}
#header{{background:#252526;padding:12px 20px;border-bottom:1px solid #3c3c3c;display:flex;align-items:center;gap:24px;flex-wrap:wrap}}
#header h1{{margin:0;font-size:16px;color:#4ec9b0}}
.hstat{{color:#858585;font-size:12px}}
.hstat b{{color:#d4d4d4}}
#toolbar{{background:#2d2d2d;padding:8px 20px;border-bottom:1px solid #3c3c3c;display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
#toolbar button{{background:#0e639c;color:#fff;border:none;padding:4px 12px;border-radius:3px;cursor:pointer;font-size:12px}}
#toolbar button:hover{{background:#1177bb}}
#search{{padding:4px 8px;background:#3c3c3c;border:1px solid #555;color:#d4d4d4;border-radius:3px;font-size:12px;width:220px}}
#layout{{display:flex;height:calc(100vh - 98px);overflow:hidden}}
#sidebar{{width:260px;min-width:200px;background:#252526;border-right:1px solid #3c3c3c;overflow-y:auto;padding:10px}}
#sidebar h3{{font-size:12px;color:#4ec9b0;margin:14px 0 6px;text-transform:uppercase;letter-spacing:.5px}}
#sidebar ul{{list-style:none;padding:0;margin:0}}
#sidebar li{{display:flex;justify-content:space-between;padding:3px 0;font-size:11px;border-bottom:1px solid #2d2d2d}}
.sb-name{{color:#dcdcaa;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:160px}}
.sb-val{{color:#608b4e;white-space:nowrap}}
#main{{flex:1;overflow:auto;padding:16px 20px}}
.tree{{margin:0}}
.node{{margin:2px 0;white-space:nowrap}}
.toggle{{cursor:pointer;user-select:none;color:#569cd6;margin-right:5px;display:inline-block;width:14px;text-align:center}}
.children{{margin-left:20px;padding-left:10px;border-left:1px solid #3c3c3c}}
.hidden{{display:none}}
.name{{color:#dcdcaa}}.module{{color:#4ec9b0}}.args{{color:#ce9178}}.return{{color:#b5cea8}}.exception{{color:#f48771}}
.timing{{color:#608b4e}}.timing.fast{{color:#4ec9b0}}.timing.slow{{color:#ce9178}}.timing.very-slow{{color:#f48771}}
.highlight{{background:#613214;border-radius:2px;padding:0 2px}}
.info-btn{{cursor:pointer;color:#569cd6;margin-left:6px;font-size:11px;opacity:.5}}
.info-btn:hover{{opacity:1}}
.detail-data{{display:none}}
#modal-overlay{{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.6);z-index:100;align-items:center;justify-content:center}}
#modal-overlay.open{{display:flex}}
#modal{{background:#252526;border:1px solid #3c3c3c;border-radius:6px;padding:20px;max-width:700px;width:90%;max-height:80vh;overflow:auto;color:#d4d4d4}}
#modal h2{{margin-top:0;font-size:14px;color:#4ec9b0}}
#modal pre{{background:#1e1e1e;padding:10px;border-radius:4px;overflow-x:auto;font-size:12px;white-space:pre-wrap;word-break:break-all}}
#modal .close{{float:right;cursor:pointer;font-size:18px;color:#858585;background:none;border:none;padding:0}}
#modal .close:hover{{color:#d4d4d4}}
@media print{{#sidebar{{display:none}}#header,#toolbar{{background:#fff;color:#000;border-color:#ccc}}body{{background:#fff;color:#000}}}}
</style>
</head>
<body>
<div id="header">
<h1>{safe_title}</h1>
<span class="hstat">Calls: <b>{summary.call_count}</b></span>
<span class="hstat">Duration: <b>{dur_str}</b></span>
<span class="hstat">Max depth: <b>{summary.max_depth_reached}</b></span>
<span class="hstat">Unique functions: <b>{summary.unique_function_count}</b></span>
<span class="hstat">Modules: <b>{summary.unique_module_count}</b></span>
</div>
<div id="toolbar">
<button onclick="tp_expandAll()">Expand All</button>
<button onclick="tp_collapseAll()">Collapse All</button>
<input id="search" type="text" placeholder="Search functions\u2026" oninput="tp_search(this.value)">
</div>
<div id="layout">
<div id="sidebar">
<h3>Top 10 Slowest</h3>
<ul>{slowest_html}</ul>
<h3>Top 10 Most Called</h3>
<ul>{most_called_html}</ul>
</div>
<div id="main">
<div class="tree">
{tree_html}
</div>
</div>
</div>
<div id="modal-overlay" onclick="if(event.target===this)tp_closeModal()">
<div id="modal">
<button class="close" onclick="tp_closeModal()">&times;</button>
<h2 id="modal-title"></h2>
<h4>Arguments</h4><pre id="modal-args"></pre>
<h4>Return Value</h4><pre id="modal-ret"></pre>
<div id="modal-exc-section" style="display:none"><h4>Exception</h4><pre id="modal-exc"></pre></div>
<p id="modal-time" style="color:#608b4e"></p>
</div>
</div>
<script>
function tp_toggle(el){{var c=el.parentElement.nextElementSibling;if(c&&c.classList.contains('children')){{c.classList.toggle('hidden');el.textContent=c.classList.contains('hidden')?'\\u25b6':'\\u25bc'}}}}
function tp_expandAll(){{document.querySelectorAll('.children').forEach(function(c){{c.classList.remove('hidden')}});document.querySelectorAll('.toggle').forEach(function(t){{if(t.onclick)t.textContent='\\u25bc'}})}}
function tp_collapseAll(){{document.querySelectorAll('.children').forEach(function(c){{c.classList.add('hidden')}});document.querySelectorAll('.toggle').forEach(function(t){{if(t.onclick)t.textContent='\\u25b6'}})}}
function tp_search(q){{q=q.toLowerCase();document.querySelectorAll('.node').forEach(function(n){{var m=n.querySelector('.module'),nm=n.querySelector('.name');var t=((m?m.textContent:'')+'.'+((nm?nm.textContent:''))).toLowerCase();if(q&&t.indexOf(q)!==-1){{if(m)m.classList.add('highlight');if(nm)nm.classList.add('highlight');var p=n.parentElement;while(p){{if(p.classList&&p.classList.contains('children')&&p.classList.contains('hidden')){{p.classList.remove('hidden');var pr=p.previousElementSibling;if(pr){{var tg=pr.querySelector('.toggle');if(tg)tg.textContent='\\u25bc'}}}}p=p.parentElement}}}}else{{if(m)m.classList.remove('highlight');if(nm)nm.classList.remove('highlight')}}}})}}
function tp_detail(btn){{var d=btn.parentElement.querySelector('.detail-data');if(!d)return;document.getElementById('modal-title').textContent=d.dataset.mod+'.'+d.dataset.name;document.getElementById('modal-args').textContent=d.dataset.args||'(none)';document.getElementById('modal-ret').textContent=d.dataset.ret||'(none)';var exc=d.dataset.exc;var es=document.getElementById('modal-exc-section');if(exc){{es.style.display='block';document.getElementById('modal-exc').textContent=exc}}else{{es.style.display='none'}}document.getElementById('modal-time').textContent='Elapsed: '+d.dataset.time;document.getElementById('modal-overlay').classList.add('open')}}
function tp_closeModal(){{document.getElementById('modal-overlay').classList.remove('open')}}
document.addEventListener('keydown',function(e){{if(e.key==='Escape')tp_closeModal()}});
</script>
</body>
</html>"""

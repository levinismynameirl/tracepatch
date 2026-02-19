"""Command-line interface for tracepatch."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from tracepatch._cli_output import err, info, ok, warn
from tracepatch._render import nodes_to_html, render_tree_colored
from tracepatch._trace import (
    TraceNode,
    _apply_filter,
    _count_nodes,
    _dict_to_node,
    _limit_depth,
    collapse_tree,
    fold_repeated_calls,
    nodes_to_json,
    render_summary_header,
    render_tree,
    trace,
)
from tracepatch.config import load_config


# Lazy import for setup/cleanup (avoid subprocess overhead at import time).
def _lazy_setup():
    from tracepatch._setup import cleanup_test_environment, setup_test_environment

    return setup_test_environment, cleanup_test_environment


def format_trace_entry(entry: dict[str, Any], index: int) -> str:
    """Format a single trace log entry for display."""
    timestamp = entry.get("timestamp", "unknown")
    label = entry.get("label") or "(no label)"
    call_count = entry.get("call_count", 0)
    limited = " [LIMITED]" if entry.get("was_limited") else ""
    file_path = entry.get("file", "")

    return f"[{index}] {timestamp} | {label} | {call_count} calls{limited}\n    {file_path}"


def cmd_logs(args: argparse.Namespace) -> int:
    """List cached trace logs."""
    cache_dir = args.cache_dir
    limit = args.limit

    logs = trace.logs(cache_dir=cache_dir, limit=limit)

    # Apply optional filters
    label_pat = getattr(args, "label", None)
    show_limited = getattr(args, "limited", False)

    if label_pat:
        import fnmatch

        logs = [e for e in logs if fnmatch.fnmatch(e.get("label", ""), label_pat)]

    if show_limited:
        logs = [e for e in logs if e.get("was_limited")]

    if not logs:
        if cache_dir:
            info(f"No trace logs found in {cache_dir}/.tracepatch/traces/")
        else:
            info("No trace logs found in .tracepatch/traces/")
        info("Traces are saved to .tracepatch/traces/ by default.")
        return 0

    print(f"Found {len(logs)} trace log(s):\n")
    for i, entry in enumerate(logs, 1):
        print(format_trace_entry(entry, i))
        print()

    return 0


def cmd_view(args: argparse.Namespace) -> int:
    """View a trace log file."""
    path = Path(args.file)

    if not path.exists():
        err(f"File not found: {path}")
        return 1

    try:
        data = trace.load(path)
    except Exception as e:
        err(f"Failed to load trace file: {e}")
        return 1

    # Display metadata
    print("=" * 70)
    print("TRACE METADATA")
    print("=" * 70)
    print(f"File: {path}")
    print(f"Timestamp: {data.get('timestamp', 'unknown')}")
    print(f"Label: {data.get('label') or '(no label)'}")
    print(f"Call count: {data.get('call_count', 0)}")
    print(f"Was limited: {data.get('was_limited', False)}")

    # Display config
    config = data.get("config", {})
    if config:
        print("\nConfiguration:")
        print(f"  max_depth: {config.get('max_depth')}")
        print(f"  max_calls: {config.get('max_calls')}")
        print(f"  max_repr: {config.get('max_repr')}")
        ignore_modules = config.get("ignore_modules", [])
        if ignore_modules:
            print(f"  ignore_modules: {', '.join(ignore_modules)}")

    # Display summary
    trace_data = data.get("trace", [])
    print(f"\nRoot calls: {len(trace_data)}")

    # Show JSON if requested
    if args.json:
        print("\n" + "=" * 70)
        print("RAW JSON")
        print("=" * 70)
        print(json.dumps(data, indent=2))

    return 0


def cmd_tree(args: argparse.Namespace) -> int:
    """Display a trace log as a call tree."""
    path = Path(args.file)

    if not path.exists():
        err(f"File not found: {path}")
        return 1

    try:
        data = trace.load(path)
    except Exception as e:
        err(f"Failed to load trace file: {e}")
        return 1

    # Reconstruct trace nodes from JSON
    trace_data = data.get("trace", [])
    if not trace_data:
        if hasattr(args, "format") and args.format == "json":
            print("[]")
        elif hasattr(args, "format") and args.format == "html":
            print(nodes_to_html([], title=f"Trace: {data.get('label') or path.name}"))
        else:
            print("No calls captured in this trace.")
        return 0

    roots = [_dict_to_node(node_dict) for node_dict in trace_data]

    # Apply filter if specified
    if hasattr(args, "filter") and args.filter:
        original_count = sum(1 for _ in _count_nodes(roots))
        roots = _apply_filter(roots, args.filter)
        filtered_count = sum(1 for _ in _count_nodes(roots))
        if not (hasattr(args, "format") and args.format in ("json", "html")):
            print(f"Filter: {args.filter} ({filtered_count}/{original_count} calls shown)")

    # Apply depth limit if specified
    if hasattr(args, "depth") and args.depth is not None:
        roots = _limit_depth(roots, args.depth)
        if not (hasattr(args, "format") and args.format in ("json", "html")):
            print(f"Depth limit: {args.depth} levels")

    # Apply call folding
    no_fold = getattr(args, "no_fold", False)
    if not no_fold:
        fold_threshold = getattr(args, "fold_threshold", 3)
        roots = fold_repeated_calls(roots, threshold=fold_threshold)

    # Apply collapse
    collapse_depth = getattr(args, "collapse", None)
    total_nodes = sum(1 for _ in _count_nodes(roots))
    if collapse_depth is not None:
        roots = collapse_tree(roots, max_depth=collapse_depth)
    elif total_nodes > 200:
        warn("Large trace (>200 nodes); auto-collapsing to depth 4. Use --no-fold or --collapse N.")
        roots = collapse_tree(roots, max_depth=4)

    # Check if no calls match filter
    if not roots:
        if hasattr(args, "format") and args.format == "json":
            print("[]")
        elif hasattr(args, "format") and args.format == "html":
            print(nodes_to_html([], title=f"Trace: {data.get('label') or path.name}"))
        else:
            print("No calls match the filter criteria.")
        return 0

    # Resolve display options
    show_args = not getattr(args, "no_args", False)
    show_return = not getattr(args, "no_return", False)
    show_source = getattr(args, "show_source", False)
    show_self_time = getattr(args, "self_time", False)
    style = getattr(args, "style", "ascii") or "ascii"
    show_stats = not getattr(args, "no_stats", False)

    # Output based on format
    fmt = getattr(args, "format", "text") or "text"
    if fmt == "json":
        print(nodes_to_json(roots))
    elif fmt == "html":
        title = f"Trace: {data.get('label') or path.name}"
        html_content = nodes_to_html(roots, title=title)
        if hasattr(args, "output") and args.output:
            output_path = Path(args.output)
            output_path.write_text(html_content, encoding="utf-8")
            ok(f"HTML tree saved to: {output_path}")
        else:
            print(html_content)
    else:
        # Text format — optional stats header
        label = data.get("label") or path.name
        if show_stats:
            print(render_summary_header(roots, label=label))
            print()

        if data.get("was_limited"):
            warn("This trace was limited (max_calls or max_depth exceeded)")

        use_color = getattr(args, "color", False) or os.environ.get(
            "TRACEPATCH_COLOR", ""
        ).lower() in ("1", "true", "yes")

        if use_color:
            print(
                render_tree_colored(
                    roots,
                    show_args=show_args,
                    show_return=show_return,
                )
            )
        else:
            print(
                render_tree(
                    roots,
                    style=style,
                    show_args=show_args,
                    show_return=show_return,
                    show_source=show_source,
                    show_self_time=show_self_time,
                )
            )

    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """Show current configuration."""
    from tracepatch.config import ConfigError

    config, config_path = load_config(path=args.file)

    # --validate mode: validate and exit
    if hasattr(args, "validate") and args.validate:
        try:
            warnings = config._validate()
            for w in warnings:
                warn(w)
            if config_path:
                ok(f"Config valid: {config_path}")
            else:
                ok("Config valid (defaults)")
            return 0
        except ConfigError as e:
            err(f"Config invalid: {e}")
            return 1

    print("=" * 70)
    print("TRACEPATCH CONFIGURATION")
    print("=" * 70)

    if config_path:
        ok(f"Loaded from: {config_path}")
    elif args.file:
        err(f"Config file not found: {args.file}")
        info("Using: default configuration")
        print()
        info("To create a config file, see: https://github.com/levinismynameirl/tracepatch")
    else:
        info("Using: default configuration (no config file found)")
        print()
        info("Searched for:")
        info("  - tracepatch.toml")
        info("  - pyproject.toml [tool.tracepatch]")
        print()
        info("Create a 'tracepatch.toml' file to customize settings.")

    print()
    print("Tracing behavior:")
    print(f"  max_depth: {config.max_depth}")
    print(f"  max_calls: {config.max_calls}")
    print(f"  max_repr: {config.max_repr}")
    if config.max_repr_args is not None:
        print(f"  max_repr_args: {config.max_repr_args}")
    if config.max_repr_return is not None:
        print(f"  max_repr_return: {config.max_repr_return}")
    print(f"  max_time: {config.max_time}")
    if config.ignore_modules:
        print(f"  ignore_modules: {', '.join(config.ignore_modules)}")
    if config.include_modules:
        print(f"  include_modules: {', '.join(config.include_modules)}")

    print()
    print("Cache settings:")
    print(f"  cache: {config.cache}")
    print(f"  cache_dir: {config.cache_dir or '(default: .tracepatch)'}")
    print(f"  auto_save: {config.auto_save}")

    print()
    print("Display settings:")
    print(f"  show_args: {config.show_args}")
    print(f"  show_return: {config.show_return}")
    print(f"  tree_style: {config.tree_style}")
    print(f"  color: {config.color}")
    if config.default_label:
        print(f"  default_label: {config.default_label}")

    print()
    print("Environment variables:")
    info("TRACEPATCH_ENABLED=0|1       - Enable/disable tracing")
    info("TRACEPATCH_MAX_DEPTH=N       - Override max_depth")
    info("TRACEPATCH_MAX_CALLS=N       - Override max_calls")
    info("TRACEPATCH_MAX_REPR=N        - Override max_repr")
    info("TRACEPATCH_MAX_TIME=N        - Override max_time")
    info("TRACEPATCH_LABEL=str         - Override default_label")
    info("TRACEPATCH_OUTPUT_DIR=path   - Override cache_dir")
    info("TRACEPATCH_NO_CACHE=1        - Disable caching")
    info("TRACEPATCH_COLOR=1           - Enable colored output")

    # Show test configuration if present
    if config.test.files:
        print()
        print("Test configuration:")
        for file_config in config.test.files:
            print(f"  {file_config.path}:")
            for func in file_config.functions:
                print(f"    - {func}()")

        if config.test.inputs:
            print()
            print("  Custom inputs:")
            for input_config in config.test.inputs:
                print(
                    f"    {input_config.function}: args={input_config.args}, kwargs={input_config.kwargs}"
                )

    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    """Set up test environment for tracing functions."""
    # Load configuration
    config, config_path = load_config()

    if not config_path:
        err("No tracepatch configuration file found!")
        print()
        print("What to do:", file=sys.stderr)
        print("  1. Create a 'tracepatch.toml' file in your project directory", file=sys.stderr)
        print("  2. OR add a [tool.tracepatch] section to your pyproject.toml", file=sys.stderr)
        print()
        print("Example tracepatch.toml:", file=sys.stderr)
        print(
            """
# Basic tracing settings
max_depth = 30
max_calls = 10000
cache = true

# Test configuration
[[test.files]]
path = "mymodule.py"
functions = ["my_function", "another_function"]

# Optional: Provide custom test inputs
[[test.inputs]]
function = "my_function"
args = [42]
kwargs = {}
""",
            file=sys.stderr,
        )
        print(
            "For more details, visit: https://github.com/levinismynameirl/tracepatch",
            file=sys.stderr,
        )
        return 1

    if not config.test.files:
        err("No test files configured!")
        print()
        print(f"Configuration loaded from: {config_path}", file=sys.stderr)
        print("But no [[test.files]] section was found.", file=sys.stderr)
        print()
        print("Add this to your config file:", file=sys.stderr)
        print(
            """
[[test.files]]
path = "your_file.py"
functions = ["function_name"]
""",
            file=sys.stderr,
        )
        return 1

    # Set up test environment
    working_dir = Path.cwd()
    try:
        setup_test_environment, _ = _lazy_setup()
        setup_test_environment(config, working_dir)
        return 0
    except Exception as e:
        err(f"Setup failed: {e}")
        return 1


def cmd_disable(args: argparse.Namespace) -> int:
    """Disable and clean up test environment.

    Supports extended cleanup modes via ``--traces``, ``--older-than``,
    and ``--all`` flags.
    """
    import shutil

    working_dir = Path.cwd()
    clean_all = getattr(args, "clean_all", False)
    traces_only = getattr(args, "traces", False)
    older_than = getattr(args, "older_than", None)

    if clean_all:
        tp_dir = working_dir / ".tracepatch"
        if tp_dir.exists():
            shutil.rmtree(tp_dir)
            ok("Removed .tracepatch/ directory")
        else:
            info("No .tracepatch/ directory found")
        return 0

    if traces_only or older_than:
        traces_dir = working_dir / ".tracepatch" / "traces"
        if not traces_dir.exists():
            info("No .tracepatch/traces/ directory found")
            return 0

        if older_than:
            import re

            m = re.match(r"^(\d+)([dhm])$", older_than)
            if not m:
                err("Invalid duration format. Use e.g. 7d, 24h, 30m")
                return 1
            amount = int(m.group(1))
            unit = m.group(2)
            multiplier = {"d": 86400, "h": 3600, "m": 60}[unit]
            cutoff = time.time() - amount * multiplier
            removed = 0
            for f in traces_dir.glob("*.json"):
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    removed += 1
            ok(f"Removed {removed} trace file(s) older than {older_than}")
        else:
            removed = 0
            for f in traces_dir.glob("*.json"):
                f.unlink()
                removed += 1
            ok(f"Removed {removed} trace file(s)")
        return 0

    _, cleanup_test_environment = _lazy_setup()
    success = cleanup_test_environment(working_dir)
    return 0 if success else 1


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize a tracepatch.toml configuration file.

    When run interactively (default), prompts the user for basic settings.
    Use ``--yes`` / ``--no-interactive`` to skip prompts and generate
    a sensible default config.
    """
    config_file = Path("tracepatch.toml")

    if config_file.exists() and not args.force:
        err(f"{config_file} already exists.")
        info("Use --force to overwrite.")
        return 1

    interactive = not args.yes

    # Defaults
    src_dir = "."
    trace_mode = "all"
    ignore_modules = ["unittest.mock", "logging"]

    if interactive:
        print("Setting up tracepatch configuration...\n")
        raw = input("What is your main source directory? (e.g., src/myapp or .) [.]: ").strip()
        if raw:
            src_dir = raw

        raw = input("Trace all modules or only specific ones? (all/specific) [all]: ").strip()
        if raw.lower().startswith("s"):
            trace_mode = "specific"
            raw = input("Which module prefixes to trace? (comma-separated): ").strip()
            include_modules = [m.strip() for m in raw.split(",") if m.strip()]
        else:
            include_modules = []

        raw = input(
            "Modules to ignore? (comma-separated, Enter to skip) [unittest.mock, logging]: "
        ).strip()
        if raw:
            ignore_modules = [m.strip() for m in raw.split(",") if m.strip()]
        print()
    else:
        include_modules = []

    # Build TOML content
    lines: list[str] = [
        "# Tracepatch Configuration",
        "# See: https://github.com/levinismynameirl/tracepatch",
        "",
        "# Tracing behavior",
        f"ignore_modules = {ignore_modules!r}",
    ]

    if trace_mode == "specific" and include_modules:
        lines.append(f"include_modules = {include_modules!r}")
    else:
        lines.append("# include_modules = []  # Allowlist mode: only trace these prefixes")

    lines += [
        "max_depth = 30",
        "max_calls = 10000",
        "max_repr = 120",
        "max_time = 60.0",
        "",
        "# Cache settings",
        "cache = true",
        "auto_save = true",
        "",
        "# Display settings",
        "show_args = true",
        "show_return = true",
        'tree_style = "ascii"',
        "",
        "# Test configuration (for `tph run`)",
        "# [[test.files]]",
        f'# path = "{src_dir}/mymodule.py"',
        '# functions = ["my_function"]',
    ]

    config_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok(f"Created {config_file}")
    print()
    print("What's next:")
    info("1. In your code:  from tracepatch import trace")
    info("2. Wrap a function:  with trace(label='my-op') as t: my_function()")
    info("3. View results:  print(t.tree())")
    info("4. Or from CLI:  tph logs / tph tree <file>")

    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    """Generate a narrative explanation of a trace file."""
    path = Path(args.file)
    if not path.exists():
        err(f"File not found: {path}")
        return 1

    try:
        data = trace.load(path)
    except Exception as e:
        err(f"Failed to load trace file: {e}")
        return 1

    trace_data = data.get("trace", [])
    if not trace_data:
        info("No calls captured in this trace.")
        return 0

    roots = [_dict_to_node(node_dict) for node_dict in trace_data]

    from tracepatch._educational import explain

    verbose = getattr(args, "verbose", False)
    print(explain(roots, verbose=verbose))
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """Print a detailed statistics report for a trace file."""
    path = Path(args.file)
    if not path.exists():
        err(f"File not found: {path}")
        return 1

    try:
        data = trace.load(path)
    except Exception as e:
        err(f"Failed to load trace file: {e}")
        return 1

    trace_data = data.get("trace", [])
    if not trace_data:
        info("No calls captured in this trace.")
        return 0

    from tracepatch._trace import TraceSummary, _format_elapsed

    roots = [_dict_to_node(node_dict) for node_dict in trace_data]
    summary = TraceSummary.from_roots(roots)

    # Per-function stats
    func_stats: dict[str, dict[str, Any]] = {}

    def _gather(node: TraceNode) -> None:
        fqn = f"{node.module}.{node.name}" if node.module else node.name
        entry = func_stats.setdefault(fqn, {"count": 0, "total_ms": 0.0, "max_ms": 0.0})
        entry["count"] += 1
        ms = node.elapsed * 1000
        entry["total_ms"] += ms
        if ms > entry["max_ms"]:
            entry["max_ms"] = ms
        for c in node.children:
            _gather(c)

    for r in roots:
        _gather(r)

    # Module breakdown
    module_stats: dict[str, dict[str, float | int]] = {}
    for fqn, info_d in func_stats.items():
        mod = fqn.rsplit(".", 1)[0] if "." in fqn else fqn
        m = module_stats.setdefault(mod, {"calls": 0, "total_ms": 0.0})
        m["calls"] += info_d["count"]
        m["total_ms"] += info_d["total_ms"]

    label = data.get("label") or path.name
    print(f"Trace: {label}")
    print("=" * 70)

    # Top 10 slowest
    slowest = sorted(func_stats.items(), key=lambda x: x[1]["total_ms"], reverse=True)[:10]
    print("\nTop 10 slowest functions:")
    for i, (fname, st) in enumerate(slowest, 1):
        avg_ms = st["total_ms"] / st["count"] if st["count"] else 0
        print(
            f"  {i:>2}.  {fname:<35} {_format_elapsed(st['total_ms'] / 1000):>10}"
            f"  (\u00d7{st['count']},  avg {_format_elapsed(avg_ms / 1000)},"
            f"  max {_format_elapsed(st['max_ms'] / 1000)})"
        )

    # Top 10 most called
    most_called = sorted(func_stats.items(), key=lambda x: x[1]["count"], reverse=True)[:10]
    print("\nTop 10 most called functions:")
    for i, (fname, st) in enumerate(most_called, 1):
        avg_ms = st["total_ms"] / st["count"] if st["count"] else 0
        print(
            f"  {i:>2}.  {fname:<35} \u00d7{st['count']:<6}"
            f"  (avg {_format_elapsed(avg_ms / 1000)},"
            f"  total {_format_elapsed(st['total_ms'] / 1000)})"
        )

    # Module breakdown
    total_calls = summary.call_count or 1
    print("\nModule breakdown:")
    for mod, ms in sorted(module_stats.items(), key=lambda x: x[1]["total_ms"], reverse=True):
        pct = ms["calls"] / total_calls * 100
        print(
            f"  {mod:<30} {int(ms['calls']):>5} calls ({pct:>4.0f}%)"
            f"   total: {_format_elapsed(ms['total_ms'] / 1000)}"
        )

    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    """Compare two trace files side-by-side."""
    path_a = Path(args.file1)
    path_b = Path(args.file2)
    for p in (path_a, path_b):
        if not p.exists():
            err(f"File not found: {p}")
            return 1

    try:
        data_a = trace.load(path_a)
        data_b = trace.load(path_b)
    except Exception as e:
        err(f"Failed to load trace file: {e}")
        return 1

    from tracepatch._trace import _format_elapsed

    def _gather_funcs(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        roots = [_dict_to_node(n) for n in data.get("trace", [])]

        def _walk(node: TraceNode) -> None:
            fqn = f"{node.module}.{node.name}" if node.module else node.name
            entry = result.setdefault(fqn, {"count": 0, "total_ms": 0.0})
            entry["count"] += 1
            entry["total_ms"] += node.elapsed * 1000
            for c in node.children:
                _walk(c)

        for r in roots:
            _walk(r)
        return result

    funcs_a = _gather_funcs(data_a)
    funcs_b = _gather_funcs(data_b)

    all_funcs = sorted(set(funcs_a) | set(funcs_b))

    label_a = data_a.get("label") or path_a.name
    label_b = data_b.get("label") or path_b.name
    print(f"Diff: {label_a}  vs  {label_b}")
    print("=" * 70)

    changes: list[str] = []
    for fn in all_funcs:
        in_a = fn in funcs_a
        in_b = fn in funcs_b
        if in_b and not in_a:
            ms_b = funcs_b[fn]["total_ms"]
            changes.append(f"+ {fn:<40} added      [{_format_elapsed(ms_b / 1000)}]")
        elif in_a and not in_b:
            changes.append(f"- {fn:<40} removed")
        else:
            a = funcs_a[fn]
            b = funcs_b[fn]
            # Timing change
            if a["total_ms"] > 0:
                timing_pct = (b["total_ms"] - a["total_ms"]) / a["total_ms"] * 100
            else:
                timing_pct = 0
            count_a = a["count"]
            count_b = b["count"]
            if abs(timing_pct) > 20:
                direction = "slower" if timing_pct > 0 else "faster"
                changes.append(
                    f"~ {fn:<40} {direction:<10}"
                    f" [{_format_elapsed(a['total_ms'] / 1000)}"
                    f" -> {_format_elapsed(b['total_ms'] / 1000)}"
                    f"  {timing_pct:+.0f}%]"
                )
            if count_a > 0 and abs(count_b - count_a) / count_a > 0.1:
                changes.append(
                    f"~ {fn:<40} calls      [\u00d7{count_a} -> \u00d7{count_b}]"
                )

    if changes:
        for line in changes:
            print(line)
    else:
        info("No significant differences found.")

    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Export a trace to CSV, HTML, or flamegraph SVG."""
    path = Path(args.file)
    if not path.exists():
        err(f"File not found: {path}")
        return 1

    try:
        data = trace.load(path)
    except Exception as e:
        err(f"Failed to load trace file: {e}")
        return 1

    trace_data = data.get("trace", [])
    if not trace_data:
        info("No calls captured in this trace.")
        return 0

    roots = [_dict_to_node(node_dict) for node_dict in trace_data]
    fmt = args.format or "csv"
    output_path = Path(args.output) if args.output else None

    if fmt == "csv":
        import csv
        import io

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["module", "function", "args", "return_value", "elapsed_ms", "depth", "parent"])

        def _csv_walk(node: TraceNode, depth: int, parent: str) -> None:
            fqn = f"{node.module}.{node.name}"
            writer.writerow([
                node.module,
                node.name,
                node.args,
                node.return_value or "",
                f"{node.elapsed * 1000:.4f}",
                depth,
                parent,
            ])
            for c in node.children:
                _csv_walk(c, depth + 1, fqn)

        for r in roots:
            _csv_walk(r, 0, "")

        content = buf.getvalue()
        if output_path:
            output_path.write_text(content, encoding="utf-8")
            ok(f"CSV exported to: {output_path}")
        else:
            print(content, end="")

    elif fmt == "html":
        title = f"Trace: {data.get('label') or path.name}"
        content = nodes_to_html(roots, title=title)
        if output_path:
            output_path.write_text(content, encoding="utf-8")
            ok(f"HTML exported to: {output_path}")
        else:
            print(content)

    elif fmt == "flamegraph":
        from tracepatch._flamegraph import nodes_to_flamegraph

        title = f"Trace: {data.get('label') or path.name}"
        content = nodes_to_flamegraph(roots, title=title)
        if output_path:
            output_path.write_text(content, encoding="utf-8")
            ok(f"Flamegraph SVG exported to: {output_path}")
        else:
            print(content)

    else:
        err(f"Unknown format: {fmt}")
        return 1

    return 0


def cmd_help(args: argparse.Namespace) -> int:
    """Show help information."""
    print("""
tracepatch - Focused runtime call tracing for Python
====================================================

USAGE:
  tracepatch <command> [options]
  tph <command> [options]

COMMANDS:
  logs              List cached trace logs
  view <file>       View trace metadata and summary
  tree <file>       Display trace as a call tree
  stats <file>      Detailed statistics report
  diff <a> <b>      Compare two trace files
  export <file>     Export trace to CSV or HTML
  config            Show current configuration
  init              Create a starter tracepatch.toml
  run               Run traced test environment from config
  clean             Clean up generated files and test state
  help              Show this help message

TREE OPTIONS:
  --filter PATTERN  Filter calls by module (e.g., 'app.*' or '!stdlib')
  --depth N         Limit tree depth to N levels
  --style S         ascii | unicode | ansi (default: ascii)
  --color           Colorize output by call duration
  --no-args         Hide function arguments
  --no-return       Hide return values
  --show-source     Show source file:line for each call
  --self-time       Show self-time alongside total time
  --no-stats        Hide the summary header
  --no-fold         Disable folding of repeated calls
  --collapse N      Auto-collapse subtrees at depth N
  --format F        text | json | html (default: text)

CLEAN OPTIONS:
  --traces          Remove all trace JSON files
  --older-than D    Remove traces older than D (e.g., 7d, 24h)
  --all             Remove entire .tracepatch/ directory

LOGS OPTIONS:
  --label PATTERN   Filter logs by label (glob pattern)
  --limited         Show only traces that hit a limit

EXAMPLES:
  # Trace and view immediately
  tracepatch tree .tracepatch/traces/my-trace_20260219_143022_abc123.json

  # Compact tree view
  tracepatch tree trace.json --no-args --style unicode --self-time

  # Compare two traces
  tracepatch diff before.json after.json

  # Export to CSV
  tracepatch export trace.json --format csv -o trace.csv

  # Statistics report
  tracepatch stats trace.json

  # Validate config in CI
  tracepatch config --validate

PYTHON API:
  from tracepatch import trace

  with trace() as t:
      my_function()
  print(t.tree())

For more information, visit: https://github.com/levinismynameirl/tracepatch
""")
    return 0


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="tracepatch",
        description="Focused runtime call tracing for Python",
        add_help=False,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # logs command
    logs_parser = subparsers.add_parser("logs", help="List cached trace logs")
    logs_parser.add_argument(
        "--cache-dir",
        type=str,
        default=None,
        help="Parent directory containing .tracepatch/",
    )
    logs_parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of logs to list (default: 50)",
    )
    logs_parser.add_argument(
        "--label",
        type=str,
        default=None,
        help="Filter logs by label (glob pattern)",
    )
    logs_parser.add_argument(
        "--limited",
        action="store_true",
        help="Show only traces that hit a limit",
    )

    # view command
    view_parser = subparsers.add_parser("view", help="View trace metadata and summary")
    view_parser.add_argument("file", help="Path to trace JSON file")
    view_parser.add_argument(
        "--json",
        action="store_true",
        help="Show raw JSON data",
    )

    # tree command
    tree_parser = subparsers.add_parser("tree", help="Display trace as a call tree")
    tree_parser.add_argument("file", help="Path to trace JSON file")
    tree_parser.add_argument(
        "--filter", help="Filter calls by module pattern (e.g., 'app.*' or '!structlog')"
    )
    tree_parser.add_argument("--depth", type=int, help="Limit tree depth to N levels")
    tree_parser.add_argument(
        "--format",
        choices=["text", "json", "html"],
        default="text",
        help="Output format (default: text)",
    )
    tree_parser.add_argument(
        "--color",
        action="store_true",
        help="Colorize output by call duration",
    )
    tree_parser.add_argument("--output", "-o", help="Output file for HTML format")
    tree_parser.add_argument(
        "--style",
        choices=["ascii", "unicode", "ansi"],
        default="ascii",
        help="Tree connector style (default: ascii)",
    )
    tree_parser.add_argument(
        "--no-args",
        action="store_true",
        help="Hide function arguments",
    )
    tree_parser.add_argument(
        "--no-return",
        action="store_true",
        help="Hide return values",
    )
    tree_parser.add_argument(
        "--show-source",
        action="store_true",
        help="Show source file and line number for each call",
    )
    tree_parser.add_argument(
        "--self-time",
        action="store_true",
        help="Show self-time alongside total elapsed time",
    )
    tree_parser.add_argument(
        "--no-stats",
        action="store_true",
        help="Hide the summary statistics header",
    )
    tree_parser.add_argument(
        "--no-fold",
        action="store_true",
        help="Disable automatic folding of repeated sibling calls",
    )
    tree_parser.add_argument(
        "--fold-threshold",
        type=int,
        default=3,
        help="Minimum consecutive identical calls to fold (default: 3)",
    )
    tree_parser.add_argument(
        "--collapse",
        type=int,
        default=None,
        metavar="N",
        help="Auto-collapse subtrees deeper than N levels",
    )

    # config command
    config_parser = subparsers.add_parser("config", help="Show current configuration")
    config_parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to specific config file to load",
    )
    config_parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate config and exit with code 0 (valid) or 1 (invalid)",
    )

    # init command
    init_parser = subparsers.add_parser("init", help="Create a starter tracepatch.toml config file")
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing config file",
    )
    init_parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip interactive prompts and use defaults",
    )

    # run command (replaces old "setup")
    subparsers.add_parser("run", help="Run traced test environment from config")
    # Backward-compat alias
    subparsers.add_parser("setup", help=argparse.SUPPRESS)

    # clean command (replaces old "disable")
    clean_parser = subparsers.add_parser("clean", help="Clean up generated files and test state")
    clean_parser.add_argument(
        "--traces",
        action="store_true",
        help="Remove all trace JSON files from .tracepatch/traces/",
    )
    clean_parser.add_argument(
        "--older-than",
        type=str,
        default=None,
        metavar="DURATION",
        help="Remove trace files older than DURATION (e.g., 7d, 24h)",
    )
    clean_parser.add_argument(
        "--all",
        action="store_true",
        dest="clean_all",
        help="Remove the entire .tracepatch/ directory",
    )
    # Backward-compat alias
    subparsers.add_parser("disable", help=argparse.SUPPRESS)

    # stats command
    stats_parser = subparsers.add_parser("stats", help="Detailed statistics report for a trace")
    stats_parser.add_argument("file", help="Path to trace JSON file")

    # explain command
    explain_parser = subparsers.add_parser(
        "explain", help="Generate a narrative explanation of a trace"
    )
    explain_parser.add_argument("file", help="Path to trace JSON file")
    explain_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Include complexity hints and deeper analysis",
    )

    # diff command
    diff_parser = subparsers.add_parser("diff", help="Compare two trace files")
    diff_parser.add_argument("file1", help="First trace JSON file")
    diff_parser.add_argument("file2", help="Second trace JSON file")

    # export command
    export_parser = subparsers.add_parser("export", help="Export trace to CSV or HTML")
    export_parser.add_argument("file", help="Path to trace JSON file")
    export_parser.add_argument(
        "--format",
        choices=["csv", "html", "flamegraph"],
        default="csv",
        help="Export format (default: csv)",
    )
    export_parser.add_argument("--output", "-o", help="Output file path")

    # help command
    subparsers.add_parser("help", help="Show help information")

    # Parse arguments
    args = parser.parse_args()

    # If no command specified, show help
    if not args.command:
        return cmd_help(args)

    # Dispatch to command handler
    if args.command == "logs":
        return cmd_logs(args)
    elif args.command == "view":
        return cmd_view(args)
    elif args.command == "tree":
        return cmd_tree(args)
    elif args.command == "config":
        return cmd_config(args)
    elif args.command == "init":
        return cmd_init(args)
    elif args.command in ("run", "setup"):
        return cmd_setup(args)
    elif args.command in ("clean", "disable"):
        return cmd_disable(args)
    elif args.command == "stats":
        return cmd_stats(args)
    elif args.command == "explain":
        return cmd_explain(args)
    elif args.command == "diff":
        return cmd_diff(args)
    elif args.command == "export":
        return cmd_export(args)
    elif args.command == "help":
        return cmd_help(args)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

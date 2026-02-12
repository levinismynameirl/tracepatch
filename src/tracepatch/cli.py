"""Command-line interface for tracepatch."""

from __future__ import annotations

import argparse
import json
import sys
import os
from pathlib import Path
from typing import Any, Optional

from tracepatch._trace import trace, render_tree, TraceNode
from tracepatch.config import load_config
from tracepatch.instrumentation import setup_test_environment, cleanup_test_environment


# ANSI color codes
COLORS = {
    'reset': '\033[0m',
    'green': '\033[92m',    # Fast (<10ms)
    'yellow': '\033[93m',  # Slow (10ms-100ms)
    'red': '\033[91m',      # Very slow (>100ms)
    'gray': '\033[90m',     # Metadata
}


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
    
    # If cache_dir is not specified, use current directory as parent
    # trace.logs() will look for .tracepatch_cache/ inside it
    logs = trace.logs(cache_dir=cache_dir, limit=limit)
    
    if not logs:
        if cache_dir:
            print(f"No trace logs found in {cache_dir}/.tracepatch_cache/")
        else:
            print("No trace logs found in .tracepatch_cache/")
        print(f"Traces are saved to .tracepatch_cache/ by default.")
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
        print(f"Error: File not found: {path}", file=sys.stderr)
        return 1
    
    try:
        data = trace.load(path)
    except Exception as e:
        print(f"Error: Failed to load trace file: {e}", file=sys.stderr)
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
    config = data.get('config', {})
    if config:
        print(f"\nConfiguration:")
        print(f"  max_depth: {config.get('max_depth')}")
        print(f"  max_calls: {config.get('max_calls')}")
        print(f"  max_repr: {config.get('max_repr')}")
        ignore_modules = config.get('ignore_modules', [])
        if ignore_modules:
            print(f"  ignore_modules: {', '.join(ignore_modules)}")
    
    # Display summary
    trace_data = data.get('trace', [])
    print(f"\nRoot calls: {len(trace_data)}")
    
    # Show JSON if requested
    if args.json:
        print("\n" + "=" * 70)
        print("RAW JSON")
        print("=" * 70)
        print(json.dumps(data, indent=2))
    
    return 0


def _filter_node(node: TraceNode, pattern: str, exclude: bool = False) -> bool:
    """Check if a node matches the filter pattern.
    
    Args:
        node: The TraceNode to check
        pattern: Module pattern to match (e.g., "app.*" or "structlog")
        exclude: If True, exclude matches; if False, include only matches
    
    Returns:
        True if node should be kept based on filter
    """
    import fnmatch
    module_name = node.module
    matches = fnmatch.fnmatch(module_name, pattern)
    return not matches if exclude else matches


def _apply_filter(nodes: list[TraceNode], pattern: str) -> list[TraceNode]:
    """Apply filter pattern to a list of trace nodes recursively.
    
    Args:
        nodes: List of TraceNodes to filter
        pattern: Filter pattern (e.g., "app.*" or "!structlog")
    
    Returns:
        Filtered list of TraceNodes
    """
    exclude = pattern.startswith("!")
    if exclude:
        pattern = pattern[1:]  # Remove the ! prefix
    
    filtered = []
    for node in nodes:
        if _filter_node(node, pattern, exclude):
            # Create a new node with filtered children
            new_node = TraceNode(
                name=node.name,
                module=node.module,
                args=node.args,
                return_value=node.return_value,
                exception=node.exception,
                start=node.start,
                end=node.end,
                elapsed=node.elapsed,
                children=_apply_filter(node.children, pattern),
                depth=node.depth,
            )
            filtered.append(new_node)
        else:
            # If parent doesn't match, still check children
            filtered.extend(_apply_filter(node.children, pattern))
    
    return filtered


def _limit_depth(nodes: list[TraceNode], max_depth: int, current_depth: int = 0) -> list[TraceNode]:
    """Limit the depth of trace nodes.
    
    Args:
        nodes: List of TraceNodes to limit
        max_depth: Maximum depth to include
        current_depth: Current depth level
    
    Returns:
        List of TraceNodes limited to max_depth
    """
    if current_depth >= max_depth:
        return []
    
    limited = []
    for node in nodes:
        # Create new node with limited children
        child_count = len(node.children)
        limited_children = _limit_depth(node.children, max_depth, current_depth + 1)
        
        new_node = TraceNode(
            name=node.name,
            module=node.module,
            args=node.args,
            return_value=node.return_value,
            exception=node.exception,
            start=node.start,
            end=node.end,
            elapsed=node.elapsed,
            children=limited_children,
            depth=node.depth,
        )
        
        # Add indication if children were truncated
        if current_depth + 1 >= max_depth and child_count > 0:
            # Add a marker node to show truncation
            truncated_node = TraceNode(
                name=f"[{child_count} nested calls...]",
                module="",
                args="",
                start=0,
                end=0,
                elapsed=0,
                children=[],
                depth=node.depth + 1,
            )
            new_node.children.append(truncated_node)
        
        limited.append(new_node)
    
    return limited


def cmd_tree(args: argparse.Namespace) -> int:
    """Display a trace log as a call tree."""
    path = Path(args.file)
    
    if not path.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        return 1
    
    try:
        data = trace.load(path)
    except Exception as e:
        print(f"Error: Failed to load trace file: {e}", file=sys.stderr)
        return 1
    
    # Reconstruct trace nodes from JSON
    trace_data = data.get('trace', [])
    if not trace_data:
        if hasattr(args, 'format') and args.format == 'json':
            print("[]")
        elif hasattr(args, 'format') and args.format == 'html':
            print(nodes_to_html([], title=f"Trace: {data.get('label') or path.name}"))
        else:
            print("No calls captured in this trace.")
        return 0
    
    roots = [_dict_to_node(node_dict) for node_dict in trace_data]
    
    # Apply filter if specified
    if hasattr(args, 'filter') and args.filter:
        original_count = sum(1 for _ in _count_nodes(roots))
        roots = _apply_filter(roots, args.filter)
        filtered_count = sum(1 for _ in _count_nodes(roots))
        if not (hasattr(args, 'format') and args.format in ('json', 'html')):
            print(f"Filter: {args.filter} ({filtered_count}/{original_count} calls shown)")
    
    # Apply depth limit if specified
    if hasattr(args, 'depth') and args.depth is not None:
        roots = _limit_depth(roots, args.depth)
        if not (hasattr(args, 'format') and args.format in ('json', 'html')):
            print(f"Depth limit: {args.depth} levels")
    
    # Check if no calls match filter
    if not roots:
        if hasattr(args, 'format') and args.format == 'json':
            print("[]")
        elif hasattr(args, 'format') and args.format == 'html':
            print(nodes_to_html([], title=f"Trace: {data.get('label') or path.name}"))
        else:
            print("No calls match the filter criteria.")
        return 0
    
    # Output based on format
    if hasattr(args, 'format'):
        if args.format == 'json':
            print(nodes_to_json(roots))
        elif args.format == 'html':
            title = f"Trace: {data.get('label') or path.name}"
            html_content = nodes_to_html(roots, title=title)
            
            # Save to file if output file is specified
            if hasattr(args, 'output') and args.output:
                output_path = Path(args.output)
                output_path.write_text(html_content, encoding='utf-8')
                print(f"HTML tree saved to: {output_path}")
            else:
                print(html_content)
        else:
            # Default text format with optional coloring
            if hasattr(args, 'color') and args.color:
                # Display basic info
                print(f"Trace: {data.get('label') or path.name}")
                print(f"Time: {data.get('timestamp', 'unknown')}")
                print(f"Calls: {data.get('call_count', 0)}")
                if data.get('was_limited'):
                    print("⚠️  This trace was limited (max_calls or max_depth exceeded)")
                print()
                print(render_tree_colored(roots))
            else:
                # Display basic info
                print(f"Trace: {data.get('label') or path.name}")
                print(f"Time: {data.get('timestamp', 'unknown')}")
                print(f"Calls: {data.get('call_count', 0)}")
                if data.get('was_limited'):
                    print("⚠️  This trace was limited (max_calls or max_depth exceeded)")
                print()
                print(render_tree(roots))
    else:
        # Default: text format without colors and with metadata
        print(f"Trace: {data.get('label') or path.name}")
        print(f"Time: {data.get('timestamp', 'unknown')}")
        print(f"Calls: {data.get('call_count', 0)}")
        if data.get('was_limited'):
            print("⚠️  This trace was limited (max_calls or max_depth exceeded)")
        print()
        
        # Check for --color flag (environment variable)
        use_color = os.environ.get('TRACEPATCH_COLOR', '').lower() in ('1', 'true', 'yes')
        if use_color:
            print(render_tree_colored(roots))
        else:
            print(render_tree(roots))
    
    return 0


def _count_nodes(nodes: list[TraceNode]):
    """Generator to count all nodes in a tree."""
    for node in nodes:
        yield node
        yield from _count_nodes(node.children)


def _colorize_by_duration(text: str, elapsed_ms: float) -> str:
    """Colorize text based on call duration.
    
    Green: < 10ms (fast)
    Yellow: 10ms - 100ms (slow)
    Red: > 100ms (very slow)
    """
    if not sys.stdout.isatty():
        return text  # Don't colorize if not in a terminal
    
    if elapsed_ms < 10:
        return f"{COLORS['green']}{text}{COLORS['reset']}"
    elif elapsed_ms < 100:
        return f"{COLORS['yellow']}{text}{COLORS['reset']}"
    else:
        return f"{COLORS['red']}{text}{COLORS['reset']}"


def _format_elapsed(seconds: float) -> str:
    """Human-friendly elapsed time string."""
    ms = seconds * 1000
    if ms < 1:
        return f"{seconds * 1_000_000:.0f}us"
    if ms < 1000:
        return f"{ms:.2f}ms"
    return f"{seconds:.3f}s"


def render_tree_colored(roots: list[TraceNode]) -> str:
    """Render tree with colors based on call duration."""
    lines: list[str] = []

    def _walk(node: TraceNode, prefix: str, is_last: bool) -> None:
        connector = "└── " if is_last else "├── "
        ret = ""
        if node.exception is not None:
            ret = f" !! {node.exception}"
        elif node.return_value is not None:
            ret = f" -> {node.return_value}"

        timing = _format_elapsed(node.elapsed)
        elapsed_ms = node.elapsed * 1000
        label = f"{node.module}.{node.name}({node.args}){ret}  [{timing}]"
        
        # Colorize based on duration
        colored_label = _colorize_by_duration(label, elapsed_ms)
        lines.append(f"{prefix}{connector}{colored_label}")

        extension = "    " if is_last else "│   "
        child_prefix = prefix + extension
        for i, child in enumerate(node.children):
            _walk(child, child_prefix, i == len(node.children) - 1)

    for i, root in enumerate(roots):
        _walk(root, "", i == len(roots) - 1)

    return "\n".join(lines)


def nodes_to_json(roots: list[TraceNode]) -> str:
    """Convert trace nodes to JSON format."""
    def node_to_dict(node: TraceNode) -> dict[str, Any]:
        return {
            "name": node.name,
            "module": node.module,
            "args": node.args,
            "return_value": node.return_value,
            "exception": node.exception,
            "start": node.start,
            "end": node.end,
            "elapsed_ms": round(node.elapsed * 1000, 4),
            "children": [node_to_dict(c) for c in node.children] if node.children else [],
        }
    
    return json.dumps([node_to_dict(r) for r in roots], indent=2)


def nodes_to_html(roots: list[TraceNode], title: str = "Trace Tree") -> str:
    """Convert trace nodes to interactive HTML with collapsible tree."""
    html_parts = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        f"<title>{title}</title>",
        "<style>",
        "body { font-family: 'Monaco', 'Courier New', monospace; padding: 20px; background: #1e1e1e; color: #d4d4d4; }",
        "h1 { color: #4ec9b0; }",
        ".tree { margin: 20px 0; }",
        ".node { margin: 2px 0; }",
        ".toggle { cursor: pointer; user-select: none; color: #569cd6; margin-right: 5px; }",
        ".children { margin-left: 20px; padding-left: 10px; border-left: 1px solid #3c3c3c; }",
        ".hidden { display: none; }",
        ".name { color: #dcdcaa; }",
        ".module { color: #4ec9b0; }",
        ".args { color: #ce9178; }",
        ".return { color: #b5cea8; }",
        ".exception { color: #f48771; }",
        ".timing { color: #608b4e; }",
        ".timing.fast { color: #4ec9b0; }",
        ".timing.slow { color: #ce9178; }",
        ".timing.very-slow { color: #f48771; }",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>{title}</h1>",
        "<div class='tree'>",
    ]
    
    def node_to_html(node: TraceNode, depth: int = 0) -> None:
        has_children = len(node.children) > 0
        toggle = "▼" if has_children else "•"
        elapsed_ms = node.elapsed * 1000
        
        # Determine timing class
        timing_class = "fast" if elapsed_ms < 10 else "slow" if elapsed_ms < 100 else "very-slow"
        timing_str = _format_elapsed(node.elapsed)
        
        # Build the line
        html_parts.append(f"<div class='node' style='margin-left: {depth * 20}px;'>")
        if has_children:
            html_parts.append(f"<span class='toggle' onclick='toggleNode(this)'>{ toggle}</span>")
        else:
            html_parts.append(f"<span class='toggle'>{toggle}</span>")
        
        html_parts.append(f"<span class='module'>{node.module}</span>.")
        html_parts.append(f"<span class='name'>{node.name}</span>")
        html_parts.append(f"(<span class='args'>{node.args}</span>)")
        
        if node.exception:
            html_parts.append(f" <span class='exception'>!! {node.exception}</span>")
        elif node.return_value:
            html_parts.append(f" <span class='return'>→ {node.return_value}</span>")
        
        html_parts.append(f" <span class='timing {timing_class}'>[{timing_str}]</span>")
        html_parts.append("</div>")
        
        if has_children:
            html_parts.append("<div class='children'>")
            for child in node.children:
                node_to_html(child, depth + 1)
            html_parts.append("</div>")
    
    for root in roots:
        node_to_html(root)
    
    html_parts.extend([
        "</div>",
        "<script>",
        "function toggleNode(toggle) {",
        "  const node = toggle.parentElement;",
        "  const children = node.nextElementSibling;",
        "  if (children && children.classList.contains('children')) {",
        "    children.classList.toggle('hidden');",
        "    toggle.textContent = children.classList.contains('hidden') ? '▶' : '▼';",
        "  }",
        "}",
        "</script>",
        "</body>",
        "</html>",
    ])
    
    return "\n".join(html_parts)


def _count_nodes(nodes: list[TraceNode]):
    """Generator to count all nodes in a tree."""
    for node in nodes:
        yield node
        yield from _count_nodes(node.children)


def _dict_to_node(d: dict[str, Any]) -> TraceNode:
    """Convert a dict (from JSON) back to a TraceNode."""
    node = TraceNode(
        name=d.get("name", ""),
        module=d.get("module", ""),
        args=d.get("args", ""),
        return_value=d.get("return_value"),
        exception=d.get("exception"),
        start=d.get("start", 0.0),
        end=d.get("end", 0.0),
        elapsed=d.get("elapsed_ms", 0.0) / 1000.0,  # Convert back to seconds
        children=[],
        depth=0,
    )
    
    # Recursively convert children
    for child_dict in d.get("children", []):
        node.children.append(_dict_to_node(child_dict))
    
    return node


def cmd_config(args: argparse.Namespace) -> int:
    """Show current configuration."""
    config, config_path = load_config(path=args.file)
    
    print("=" * 70)
    print("TRACEPATCH CONFIGURATION")
    print("=" * 70)
    
    if config_path:
        print(f"✓ Loaded from: {config_path}")
    elif args.file:
        print(f"❌ Error: Config file not found: {args.file}")
        print("ℹ️  Using: default configuration")
        print()
        print("To create a config file, see: https://github.com/levinismynameirl/tracepatch")
    else:
        print("ℹ️  Using: default configuration (no config file found)")
        print()
        print("Searched for:")
        print("  - tracepatch.toml")
        print("  - pyproject.toml [tool.tracepatch]")
        print()
        print("Create a 'tracepatch.toml' file to customize settings.")
    
    print()
    print("Tracing behavior:")
    print(f"  max_depth: {config.max_depth}")
    print(f"  max_calls: {config.max_calls}")
    print(f"  max_repr: {config.max_repr}")
    if config.ignore_modules:
        print(f"  ignore_modules: {', '.join(config.ignore_modules)}")
    
    print()
    print("Cache settings:")
    print(f"  cache: {config.cache}")
    print(f"  cache_dir: {config.cache_dir or '(default: .tracepatch_cache)'}")
    print(f"  auto_save: {config.auto_save}")
    
    print()
    print("Display settings:")
    print(f"  show_args: {config.show_args}")
    print(f"  show_return: {config.show_return}")
    print(f"  tree_style: {config.tree_style}")
    if config.default_label:
        print(f"  default_label: {config.default_label}")
    
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
                print(f"    {input_config.function}: args={input_config.args}, kwargs={input_config.kwargs}")
    
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    """Set up test environment for tracing functions."""
    # Load configuration
    config, config_path = load_config()
    
    if not config_path:
        print("❌ Error: No tracepatch configuration file found!", file=sys.stderr)
        print()
        print("What to do:", file=sys.stderr)
        print("  1. Create a 'tracepatch.toml' file in your project directory", file=sys.stderr)
        print("  2. OR add a [tool.tracepatch] section to your pyproject.toml", file=sys.stderr)
        print()
        print("Example tracepatch.toml:", file=sys.stderr)
        print("""
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
""", file=sys.stderr)
        print("For more details, visit: https://github.com/levinismynameirl/tracepatch", file=sys.stderr)
        return 1
    
    if not config.test.files:
        print("❌ Error: No test files configured!", file=sys.stderr)
        print()
        print(f"Configuration loaded from: {config_path}", file=sys.stderr)
        print("But no [[test.files]] section was found.", file=sys.stderr)
        print()
        print("Add this to your config file:", file=sys.stderr)
        print("""
[[test.files]]
path = "your_file.py"
functions = ["function_name"]
""", file=sys.stderr)
        return 1
    
    # Set up test environment
    working_dir = Path.cwd()
    try:
        setup_test_environment(config, working_dir)
        return 0
    except Exception as e:
        print(f"Error during setup: {e}", file=sys.stderr)
        return 1


def cmd_disable(args: argparse.Namespace) -> int:
    """Disable and clean up test environment."""
    working_dir = Path.cwd()
    
    success = cleanup_test_environment(working_dir)
    return 0 if success else 1


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize a tracepatch.toml configuration file."""
    import textwrap
    
    config_file = Path("tracepatch.toml")
    
    if config_file.exists() and not args.force:
        print(f"❌ Error: {config_file} already exists.")
        print("   Use --force to overwrite.")
        return 1
    
    # Generate a starter configuration
    starter_config = textwrap.dedent("""
        # Tracepatch Configuration
        # See: https://github.com/levinismynameirl/tracepatch
        
        # Tracing behavior
        ignore_modules = ["unittest.mock", "logging"]  # Module prefixes to exclude
        # include_modules = ["myapp"]  # Allowlist mode: only trace these modules
        max_depth = 30  # Maximum call nesting depth
        max_calls = 10000  # Stop tracing after this many calls
        max_repr = 120  # Max length for repr() of args/returns
        
        # Cache settings
        cache = true  # Auto-save traces to .tracepatch_cache/
        # cache_dir = ".custom_cache"  # Custom cache directory
        auto_save = true  # Automatically save traces on exit
        
        # Display settings
        show_args = true  # Show function arguments in tree
        show_return = true  # Show return values in tree
        tree_style = "ascii"  # "ascii" or "unicode"
        # default_label = "my-trace"  # Default label for traces
        
        # Test configuration (for `tph setup`)
        [test.files]
        # Functions to trace during tests
        # [[test.files]]
        # path = "myapp/core.py"
        # functions = ["process", "validate"]
        
        [test.inputs]
        # Custom test inputs
        # [[test.inputs]]
        # function = "process"
        # args = [42]
        # kwargs = {}
        
        [test.custom]
        # Use a custom test script instead of auto-generation
        enabled = false
        script = ""
    """).strip()
    
    config_file.write_text(starter_config + "\\n", encoding="utf-8")
    print(f"✅ Created {config_file}")
    print()
    print("Next steps:")
    print("  1. Edit tracepatch.toml to customize settings")
    print("  2. Use `tph config` to verify your configuration")
    print("  3. Add @trace() decorators or use context managers in your code")
    print()
    print("Environment variables (override config):")
    print("  TRACEPATCH_ENABLED=0     - Disable tracing globally")
    print("  TRACEPATCH_MAX_DEPTH=N   - Override max_depth")
    print("  TRACEPATCH_MAX_CALLS=N   - Override max_calls")
    print("  TRACEPATCH_COLOR=1       - Enable colored output")
    
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
  config            Show current configuration
  setup             Set up test environment for tracing
  disable           Clean up and disable test environment
  help              Show this help message

EXAMPLES:
  # List recent traces
  tracepatch logs
  
  # View a specific trace file
  tracepatch view .tracepatch_cache/trace_20260212_143022_123456.json
  
  # Display trace as a call tree
  tracepatch tree .tracepatch_cache/trace_20260212_143022_123456.json
  
  # Show current configuration
  tracepatch config
  
  # Set up test environment (creates test runner from config)
  tracepatch setup
  
  # Run the generated test file
  python _tracepatch_filetotest.py
  
  # Clean up test environment
  tracepatch disable

CONFIGURATION:
  tracepatch looks for configuration in:
    1. tracepatch.toml (in current or parent directories)
    2. pyproject.toml [tool.tracepatch] section
  
  Example tracepatch.toml:
  
    ignore_modules = ["urllib3", "requests"]
    max_depth = 50
    max_calls = 20000
    max_repr = 200
    cache = true
    cache_dir = ".traces"
    default_label = "my-app"
    show_args = true
    show_return = true
    tree_style = "ascii"
    
    # Test setup configuration
    [[test.files]]
    path = "mymodule.py"
    functions = ["my_function", "process_data"]
    
    [[test.inputs]]
    function = "my_function"
    args = [42, "test"]
    kwargs = {}

PYTHON API:
  from tracepatch import trace
  
  with trace() as t:
      my_function()
  print(t.tree())

For more information, visit: https://github.com/tracepatch/tracepatch
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
        help="Parent directory containing .tracepatch_cache/",
    )
    logs_parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of logs to list (default: 50)",
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
    tree_parser.add_argument("--filter", help="Filter calls by module pattern (e.g., 'app.*' or '!structlog')")
    tree_parser.add_argument("--depth", type=int, help="Limit tree depth to N levels")
    tree_parser.add_argument("--format", choices=['text', 'json', 'html'], default='text',
                           help="Output format (default: text)")
    tree_parser.add_argument("--color", action="store_true", 
                           help="Colorize output by call duration (green=fast, yellow=slow, red=very slow)")
    tree_parser.add_argument("--output", "-o", help="Output file for HTML format")
    
    # config command
    config_parser = subparsers.add_parser("config", help="Show current configuration")
    config_parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to specific config file to load",
    )
    
    # init command
    init_parser = subparsers.add_parser("init", help="Create a starter tracepatch.toml config file")
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing config file",
    )
    
    # setup command
    subparsers.add_parser("setup", help="Set up test environment for tracing")
    
    # disable command
    subparsers.add_parser("disable", help="Clean up and disable test environment")
    
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
    elif args.command == "setup":
        return cmd_setup(args)
    elif args.command == "disable":
        return cmd_disable(args)
    elif args.command == "help":
        return cmd_help(args)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

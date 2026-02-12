"""Command-line interface for tracepatch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from tracepatch._trace import trace, render_tree, TraceNode
from tracepatch.config import load_config
from tracepatch.instrumentation import setup_test_environment, cleanup_test_environment


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
    
    if not logs:
        print("No trace logs found.")
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
    
    # Display basic info
    print(f"Trace: {data.get('label') or path.name}")
    print(f"Time: {data.get('timestamp', 'unknown')}")
    print(f"Calls: {data.get('call_count', 0)}")
    if data.get('was_limited'):
        print("⚠️  This trace was limited (max_calls or max_depth exceeded)")
    print()
    
    # Reconstruct trace nodes from JSON
    trace_data = data.get('trace', [])
    if not trace_data:
        print("No calls captured in this trace.")
        return 0
    
    roots = [_dict_to_node(node_dict) for node_dict in trace_data]
    
    # Render tree
    print(render_tree(roots))
    
    return 0


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
    
    # config command
    config_parser = subparsers.add_parser("config", help="Show current configuration")
    config_parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to specific config file to load",
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

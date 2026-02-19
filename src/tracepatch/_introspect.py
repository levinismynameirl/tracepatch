"""Source-code introspection utilities for tracepatch.

Provides helpers that inspect Python source files to extract function
signatures and generate sensible default argument values.
"""

from __future__ import annotations

import ast
from pathlib import Path  # noqa: TC003
from typing import Any


def get_function_signature(
    file_path: Path,
    func_name: str,
) -> list[tuple[str, str | None]] | None:
    """Extract a simplified function signature from a Python file.

    Parameters
    ----------
    file_path:
        Path to the ``.py`` file.
    func_name:
        Name of the function to extract.

    Returns
    -------
    list[tuple[str, str | None]] | None
        List of ``(param_name, "default" | None)`` pairs, or ``None`` if
        the function was not found.
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                args: list[tuple[str, str | None]] = []
                defaults_start = len(node.args.args) - len(node.args.defaults)

                for i, arg in enumerate(node.args.args):
                    default_idx = i - defaults_start
                    if default_idx >= 0:
                        args.append((arg.arg, "default"))
                    else:
                        args.append((arg.arg, None))

                return args

        return None
    except Exception:
        return None


def generate_default_value(param_name: str, annotation: str | None = None) -> Any:
    """Generate a reasonable default value for a parameter.

    Parameters
    ----------
    param_name:
        Name of the parameter (used for heuristic matching).
    annotation:
        Optional type annotation string (currently unused).

    Returns
    -------
    Any
        A sensible placeholder value.
    """
    lower = param_name.lower()
    if "id" in lower:
        return 1
    elif "name" in lower:
        return "test_name"
    elif "count" in lower or "num" in lower:
        return 10
    elif "email" in lower:
        return "test@example.com"
    elif "url" in lower:
        return "https://example.com"
    elif "path" in lower:
        return "/tmp/test"
    elif "list" in lower or "items" in lower:
        return []
    elif "dict" in lower or "data" in lower:
        return {}
    elif "bool" in lower or "is_" in lower:
        return False
    else:
        return None

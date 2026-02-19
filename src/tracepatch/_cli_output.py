"""Consistent CLI output formatting for tracepatch.

Provides ``ok()``, ``err()``, ``warn()``, and ``info()`` helpers that
automatically pick between Unicode symbols and plain ASCII depending on
whether stdout/stderr is a TTY.  Error messages are always sent to
*stderr*.

Usage::

    from tracepatch._cli_output import ok, err, warn, info

    ok("Created tracepatch.toml")   # → "✓ Created tracepatch.toml"
    err("File not found: x.py")     # → "✗ File not found: x.py" (stderr)
    warn("Staged Git changes")      # → "! Staged Git changes"
    info("Using default config")    # → "  Using default config"
"""

from __future__ import annotations

import sys


def _is_tty(stream: object) -> bool:
    """Return ``True`` if *stream* is connected to a terminal."""
    try:
        return hasattr(stream, "fileno") and stream.isatty()  # type: ignore[union-attr]
    except Exception:
        return False


# Symbols selected at call time based on TTY status.
_OK_TTY = "✓"
_OK_PLAIN = "OK:"
_ERR_TTY = "✗"
_ERR_PLAIN = "ERR:"
_WARN_TTY = "!"
_WARN_PLAIN = "WARN:"


def ok(msg: str) -> None:
    """Print a success message to *stdout*.

    Parameters
    ----------
    msg:
        The message to display.
    """
    prefix = _OK_TTY if _is_tty(sys.stdout) else _OK_PLAIN
    print(f"{prefix} {msg}")


def err(msg: str) -> None:
    """Print an error message to *stderr*.

    Parameters
    ----------
    msg:
        The error message to display.
    """
    prefix = _ERR_TTY if _is_tty(sys.stderr) else _ERR_PLAIN
    print(f"{prefix} {msg}", file=sys.stderr)


def warn(msg: str) -> None:
    """Print a warning message to *stdout*.

    Parameters
    ----------
    msg:
        The warning message to display.
    """
    prefix = _WARN_TTY if _is_tty(sys.stdout) else _WARN_PLAIN
    print(f"{prefix} {msg}")


def info(msg: str) -> None:
    """Print an informational message to *stdout* (indented, no prefix).

    Parameters
    ----------
    msg:
        The message to display.
    """
    print(f"  {msg}")

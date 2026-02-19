"""Git integration helpers for tracepatch.

This module is only imported when ``tph run`` / ``tph clean`` is
invoked — it is not loaded at library import time.
"""

from __future__ import annotations

import subprocess
from pathlib import Path  # noqa: TC003


def check_git_status(working_dir: Path) -> tuple[bool, list[str], list[str]]:
    """Check if Git is available and get status of changed files.

    Parameters
    ----------
    working_dir:
        Working directory to check.

    Returns
    -------
    tuple[bool, list[str], list[str]]
        ``(has_git, staged_files, unstaged_files)``
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return False, [], []

        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        staged = result.stdout.strip().split("\n") if result.stdout.strip() else []

        result = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        unstaged = result.stdout.strip().split("\n") if result.stdout.strip() else []

        return True, staged, unstaged
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, [], []

"""Test setup and instrumentation helpers for tracepatch.

This module re-exports the public API that was previously defined here.
The implementation has been split into:

- ``_git.py``        — Git status checking
- ``_introspect.py`` — Function signature extraction
- ``_codegen.py``    — Test runner code generation
- ``_setup.py``      — SetupState, setup / cleanup orchestration
"""

from __future__ import annotations

from tracepatch._codegen import create_test_runner
from tracepatch._git import check_git_status
from tracepatch._introspect import generate_default_value, get_function_signature
from tracepatch._setup import (
    SetupState,
    cleanup_test_environment,
    ensure_init_file,
    setup_test_environment,
)

__all__ = [
    "SetupState",
    "check_git_status",
    "cleanup_test_environment",
    "create_test_runner",
    "ensure_init_file",
    "generate_default_value",
    "get_function_signature",
    "setup_test_environment",
]

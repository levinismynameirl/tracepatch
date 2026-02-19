"""Jupyter/IPython integration for tracepatch.

Provides:

* :func:`show` — render a trace inline in a Jupyter notebook
  (falls back to ``print(tree)`` outside notebooks).
* :func:`load_ipython_extension` — registers the ``%%tracepatch``
  cell magic command so users can say ``%load_ext tracepatch`` in a
  notebook cell.

All IPython imports are lazy so that ``tracepatch`` remains
zero-dependency at runtime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tracepatch._trace import trace as _trace_type


# ------------------------------------------------------------------
# Public helpers
# ------------------------------------------------------------------


def _is_notebook() -> bool:
    """Detect whether code is running inside a Jupyter/IPython notebook.

    Returns *True* when an ``IPython`` kernel with a ``ZMQInteractiveShell``
    is active — this is the standard Jupyter notebook / JupyterLab shell.
    Returns *False* in plain IPython terminals and when ``IPython`` is not
    installed.
    """
    try:
        from IPython import get_ipython  # type: ignore[import-untyped]

        shell = get_ipython()
        if shell is None:
            return False
        # Jupyter notebooks use ZMQInteractiveShell
        return type(shell).__name__ == "ZMQInteractiveShell"
    except ImportError:
        return False


def show(t: _trace_type) -> None:
    """Render a completed trace inline.

    When running inside a Jupyter notebook the trace is rendered as
    an interactive HTML tree using ``IPython.display.HTML``.  Outside a
    notebook the plain-text tree is printed to stdout.

    Parameters
    ----------
    t:
        A :class:`~tracepatch._trace.trace` instance (used after the
        context manager has exited).
    """
    if _is_notebook():
        try:
            from IPython.display import HTML, display  # type: ignore[import-untyped]

            from tracepatch._render import nodes_to_html

            label = getattr(t, "_label", None) or "Trace"
            html = nodes_to_html(t.roots, title=label)
            display(HTML(html))
            return
        except ImportError:
            pass

    # Fallback: plain text
    print(t.tree())


# ------------------------------------------------------------------
# IPython magic
# ------------------------------------------------------------------


def _parse_magic_args(line: str) -> dict[str, object]:
    """Parse ``%%tracepatch`` line arguments into ``trace()`` kwargs.

    Accepted flags (mirrors :class:`~tracepatch._trace.trace` constructor):

    * ``--label NAME``
    * ``--max-depth N``
    * ``--max-calls N``
    * ``--max-repr N``
    * ``--max-time SECS``
    * ``--no-cache``
    """
    import shlex

    tokens = shlex.split(line)
    kwargs: dict[str, object] = {}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--label" and i + 1 < len(tokens):
            kwargs["label"] = tokens[i + 1]
            i += 2
        elif tok == "--max-depth" and i + 1 < len(tokens):
            kwargs["max_depth"] = int(tokens[i + 1])
            i += 2
        elif tok == "--max-calls" and i + 1 < len(tokens):
            kwargs["max_calls"] = int(tokens[i + 1])
            i += 2
        elif tok == "--max-repr" and i + 1 < len(tokens):
            kwargs["max_repr"] = int(tokens[i + 1])
            i += 2
        elif tok == "--max-time" and i + 1 < len(tokens):
            kwargs["max_time"] = float(tokens[i + 1])
            i += 2
        elif tok == "--no-cache":
            kwargs["cache"] = False
            i += 1
        else:
            i += 1
    return kwargs


def _register_magic(ipython: object) -> None:
    """Register the ``%%tracepatch`` cell magic on *ipython*.

    Parameters
    ----------
    ipython:
        An active :class:`~IPython.core.interactiveshell.InteractiveShell`
        instance (passed by ``load_ipython_extension``).
    """
    from IPython.core.magic import register_cell_magic  # type: ignore[import-untyped]

    @register_cell_magic  # type: ignore[misc]
    def tracepatch(line: str, cell: str) -> None:
        """``%%tracepatch`` — wrap a notebook cell in a trace context.

        Usage inside a Jupyter cell::

            %%tracepatch --label "my-trace" --max-calls 5000
            result = some_pipeline(data)

        After executing the cell body the trace tree is rendered inline.
        """
        from tracepatch._trace import trace as _trace

        kwargs = _parse_magic_args(line)
        with _trace(**kwargs) as t:  # type: ignore[arg-type]
            # Execute the cell body in the user's namespace
            ipython.run_cell(cell)  # type: ignore[union-attr]

        show(t)


def load_ipython_extension(ipython: object) -> None:
    """Entry point for ``%load_ext tracepatch``.

    Registers the ``%%tracepatch`` cell magic command.  Called
    automatically by IPython when a user runs::

        %load_ext tracepatch

    Parameters
    ----------
    ipython:
        The active :class:`~IPython.core.interactiveshell.InteractiveShell`.
    """
    _register_magic(ipython)

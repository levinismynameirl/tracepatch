"""Test-runner code generation for tracepatch.

Builds the ``trace_runner.py`` script that ``tph run`` creates inside the
``.tracepatch/`` directory to exercise user-specified functions under trace.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tracepatch._introspect import generate_default_value, get_function_signature

if TYPE_CHECKING:
    from tracepatch._setup import SetupState
    from tracepatch.config import TracepatchConfig


def create_test_runner(
    config: TracepatchConfig,
    working_dir: Path,
    state: SetupState,
) -> Path:
    """Create a test-runner file that imports and traces specified functions.

    The runner is written to ``.tracepatch/trace_runner.py`` so it never
    pollutes the project root.

    Parameters
    ----------
    config:
        Loaded TracepatchConfig.
    working_dir:
        Directory where the runner script will be written.
    state:
        ``SetupState`` instance — updated in-place with created files.

    Returns
    -------
    Path
        Path to the generated test-runner script.
    """
    from tracepatch._trace import _CACHE_DIR_NAME

    runner_dir = working_dir / _CACHE_DIR_NAME
    runner_dir.mkdir(exist_ok=True)
    test_file = runner_dir / "trace_runner.py"

    # Build imports
    imports = ["from tracepatch import trace, load_config\n"]
    imports.append("import sys\n")
    imports.append("from pathlib import Path\n")
    imports.append("import functools\n\n")

    imports.append("# Add project root (parent of .tracepatch/) to path\n")
    imports.append("sys.path.insert(0, str(Path(__file__).resolve().parent.parent))\n\n")

    # Import functions from configured files
    imported_funcs: list[str] = []
    for file_config in config.test.files:
        file_path = Path(file_config.path)
        if not file_path.exists():
            continue

        module_parts: list[str] = []
        for part in file_path.with_suffix("").parts:
            if part in ("src", "."):
                continue
            module_parts.append(part)

        module_path = ".".join(module_parts)

        for func_name in file_config.functions:
            imports.append(f"from {module_path} import {func_name} as _{func_name}_original\n")
            imported_funcs.append(func_name)

    imports.append("\n\n")
    imports.append("# Create traced wrappers for imported functions\n")
    imports.append("_active_trace = None\n\n")

    for func_name in imported_funcs:
        imports.append(f"def {func_name}(*args, **kwargs):\n")
        imports.append(f'    """Traced wrapper for {func_name}."""\n')
        imports.append(f"    return _{func_name}_original(*args, **kwargs)\n\n")

    imports.append("\n")

    # Build test execution code
    test_code: list[str] = []
    test_code.append("def main():\n")
    test_code.append('    """Run traced tests."""\n')
    test_code.append("    config, config_path = load_config()\n")
    test_code.append("    if config_path:\n")
    test_code.append("        print(f'Using config from: {config_path}')\n")
    test_code.append("    \n")
    test_code.append("    # Get trace kwargs from config\n")
    test_code.append("    trace_kwargs = config.to_trace_kwargs()\n")
    test_code.append("    if 'label' not in trace_kwargs or trace_kwargs['label'] is None:\n")
    test_code.append("        trace_kwargs['label'] = 'test-run'\n")
    test_code.append("    \n")
    test_code.append("    print('\\nRunning tests with tracing enabled...')\n")
    test_code.append("    print('=' * 70)\n")
    test_code.append("    \n")
    test_code.append("    with trace(**trace_kwargs) as t:\n")

    for file_config in config.test.files:
        for func_name in file_config.functions:
            custom_input = None
            for input_config in config.test.inputs:
                if input_config.function == func_name:
                    custom_input = input_config
                    break

            if custom_input:
                args_str = ", ".join(repr(arg) for arg in custom_input.args)
                kwargs_str = ", ".join(f"{k}={v!r}" for k, v in custom_input.kwargs.items())
                all_args = ", ".join(filter(None, [args_str, kwargs_str]))
                test_code.append(f"        # Testing {func_name} with custom inputs\n")
                test_code.append("        try:\n")
                test_code.append(f"            result = {func_name}({all_args})\n")
                test_code.append(f"            print(f'✓ {func_name} returned: {{result}}')\n")
                test_code.append("        except Exception as e:\n")
                test_code.append(
                    f"            print(f'✗ {func_name} raised: {{type(e).__name__}}: {{e}}')\n"
                )
            else:
                file_path = Path(file_config.path)
                sig = get_function_signature(file_path, func_name)

                if sig is None or len(sig) == 0:
                    test_code.append(f"        # Testing {func_name} (no parameters)\n")
                    test_code.append("        try:\n")
                    test_code.append(f"            result = {func_name}()\n")
                    test_code.append(f"            print(f'✓ {func_name} returned: {{result}}')\n")
                    test_code.append("        except Exception as e:\n")
                    test_code.append(
                        f"            print(f'✗ {func_name} raised: {{type(e).__name__}}: {{e}}')\n"
                    )
                else:
                    test_code.append(f"        # Testing {func_name} (auto-generated inputs)\n")
                    test_code.append("        try:\n")
                    args_list: list[str] = []
                    for param_name, has_default in sig:
                        if param_name == "self":
                            continue
                        if has_default:
                            break
                        default_val = generate_default_value(param_name)
                        args_list.append(repr(default_val))

                    args_str = ", ".join(args_list) if args_list else ""
                    test_code.append(f"            result = {func_name}({args_str})\n")
                    test_code.append(f"            print(f'✓ {func_name} returned: {{result}}')\n")
                    test_code.append("        except Exception as e:\n")
                    test_code.append(
                        f"            print(f'✗ {func_name} raised: {{type(e).__name__}}: {{e}}')\n"
                    )

            test_code.append("        \n")

    test_code.append("    \n")
    test_code.append("    # Display results\n")
    test_code.append("    print('\\n' + '=' * 70)\n")
    test_code.append("    print('TRACE RESULTS')\n")
    test_code.append("    print('=' * 70)\n")
    test_code.append("    print(f'Total calls: {t.call_count}')\n")
    test_code.append("    if t.was_limited:\n")
    test_code.append("        print('⚠️  Trace was limited (max_calls or max_depth exceeded)')\n")
    test_code.append("    \n")
    test_code.append("    if t.cache_path:\n")
    test_code.append("        print(f'\\nTrace saved to: {t.cache_path}')\n")
    test_code.append("        print(f'View with: tph tree {t.cache_path}')\n")
    test_code.append("    \n")
    test_code.append("    print('\\n' + t.tree())\n")
    test_code.append("\n\n")
    test_code.append("if __name__ == '__main__':\n")
    test_code.append("    main()\n")

    content = "".join(imports) + "".join(test_code)
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(content)

    state.test_runner_path = test_file
    state.created_files.append(test_file)

    return test_file

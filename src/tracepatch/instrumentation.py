"""Test setup and instrumentation helpers for tracepatch."""

from __future__ import annotations

import ast
import inspect
import json
import subprocess
from pathlib import Path
from typing import Any, Optional

from tracepatch.config import TracepatchConfig, TestFileConfig, TestInputConfig
from tracepatch._trace import _CACHE_DIR_NAME


def check_git_status(working_dir: Path) -> tuple[bool, list[str], list[str]]:
    """Check if Git is available and get status of changed files.
    
    Returns:
        Tuple of (has_git, staged_files, unstaged_files)
    """
    try:
        # Check if git is available
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return False, [], []
        
        # Get staged changes
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=5
        )
        staged = result.stdout.strip().split("\n") if result.stdout.strip() else []
        
        # Get unstaged changes
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=5
        )
        unstaged = result.stdout.strip().split("\n") if result.stdout.strip() else []
        
        return True, staged, unstaged
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, [], []


class SetupState:
    """Tracks what was done during setup for later cleanup."""
    
    def __init__(self):
        self.created_files: list[Path] = []
        self.modified_files: list[tuple[Path, str]] = []  # (path, backup_content)
        self.test_runner_path: Optional[Path] = None
        self.cache_dir: Optional[Path] = None
    
    def save(self, cache_dir: Path) -> None:
        """Save setup state to a JSON file in the cache directory."""
        state_file = cache_dir / "setup_state.json"
        data = {
            "created_files": [str(p) for p in self.created_files],
            "modified_files": [(str(p), content) for p, content in self.modified_files],
            "test_runner_path": str(self.test_runner_path) if self.test_runner_path else None,
            "cache_dir": str(cache_dir),
        }
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.cache_dir = cache_dir
    
    @classmethod
    def load(cls, cache_dir: Path) -> Optional["SetupState"]:
        """Load setup state from a JSON file in the cache directory."""
        state_file = cache_dir / "setup_state.json"
        if not state_file.exists():
            return None
        
        with open(state_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        state = cls()
        state.created_files = [Path(p) for p in data.get("created_files", [])]
        state.modified_files = [(Path(p), content) for p, content in data.get("modified_files", [])]
        test_runner = data.get("test_runner_path")
        state.test_runner_path = Path(test_runner) if test_runner else None
        cache_dir_str = data.get("cache_dir")
        state.cache_dir = Path(cache_dir_str) if cache_dir_str else cache_dir
        return state


def get_function_signature(file_path: Path, func_name: str) -> Optional[inspect.Signature]:
    """Extract function signature from a Python file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        
        tree = ast.parse(source)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                # Build a simplified signature representation
                args = []
                defaults_start = len(node.args.args) - len(node.args.defaults)
                
                for i, arg in enumerate(node.args.args):
                    default_idx = i - defaults_start
                    if default_idx >= 0:
                        # Has a default value
                        args.append((arg.arg, "default"))
                    else:
                        args.append((arg.arg, None))
                
                return args
        
        return None
    except Exception:
        return None


def generate_default_value(param_name: str, annotation: Optional[str] = None) -> Any:
    """Generate a reasonable default value for a parameter."""
    # Common parameter name patterns
    if "id" in param_name.lower():
        return 1
    elif "name" in param_name.lower():
        return "test_name"
    elif "count" in param_name.lower() or "num" in param_name.lower():
        return 10
    elif "email" in param_name.lower():
        return "test@example.com"
    elif "url" in param_name.lower():
        return "https://example.com"
    elif "path" in param_name.lower():
        return "/tmp/test"
    elif "list" in param_name.lower() or "items" in param_name.lower():
        return []
    elif "dict" in param_name.lower() or "data" in param_name.lower():
        return {}
    elif "bool" in param_name.lower() or "is_" in param_name.lower():
        return False
    else:
        # Generic defaults
        return None


def create_test_runner(
    config: TracepatchConfig,
    working_dir: Path,
    state: SetupState,
) -> Path:
    """Create a test runner file that imports and traces specified functions."""
    
    test_file = working_dir / "_tracepatch_filetotest.py"
    
    # Build imports
    imports = ["from tracepatch import trace, load_config\n"]
    imports.append("import sys\n")
    imports.append("from pathlib import Path\n")
    imports.append("import functools\n\n")
    
    # Add the working directory to sys.path
    imports.append(f"# Add working directory to path\n")
    imports.append(f"sys.path.insert(0, str(Path(__file__).parent))\n\n")
    
    # Import functions from configured files
    imported_funcs = []
    for file_config in config.test.files:
        file_path = Path(file_config.path)
        if not file_path.exists():
            continue
        
        # Convert file path to module path
        module_parts = []
        for part in file_path.with_suffix("").parts:
            if part in ("src", "."):
                continue
            module_parts.append(part)
        
        module_path = ".".join(module_parts)
        
        # Import the functions
        for func_name in file_config.functions:
            imports.append(f"from {module_path} import {func_name} as _{func_name}_original\n")
            imported_funcs.append(func_name)
    
    imports.append("\n\n")
    
    # Create traced wrapper decorator
    imports.append("# Create traced wrappers for imported functions\n")
    imports.append("_active_trace = None\n\n")
    
    # Create wrapper functions that use the shared trace context
    for func_name in imported_funcs:
        imports.append(f"def {func_name}(*args, **kwargs):\n")
        imports.append(f"    \"\"\"Traced wrapper for {func_name}.\"\"\"\n")
        imports.append(f"    return _{func_name}_original(*args, **kwargs)\n\n")
    
    imports.append("\n")
    
    # Build test execution code
    test_code = []
    test_code.append("def main():\n")
    test_code.append("    \"\"\"Run traced tests.\"\"\"\n")
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
    
    # Create function calls
    for file_config in config.test.files:
        for func_name in file_config.functions:
            # Check if we have custom inputs for this function
            custom_input = None
            for input_config in config.test.inputs:
                if input_config.function == func_name:
                    custom_input = input_config
                    break
            
            if custom_input:
                # Use provided arguments
                args_str = ", ".join(repr(arg) for arg in custom_input.args)
                kwargs_str = ", ".join(f"{k}={repr(v)}" for k, v in custom_input.kwargs.items())
                all_args = ", ".join(filter(None, [args_str, kwargs_str]))
                test_code.append(f"        # Testing {func_name} with custom inputs\n")
                test_code.append(f"        try:\n")
                test_code.append(f"            result = {func_name}({all_args})\n")
                test_code.append(f"            print(f'✓ {func_name} returned: {{result}}')\n")
                test_code.append(f"        except Exception as e:\n")
                test_code.append(f"            print(f'✗ {func_name} raised: {{type(e).__name__}}: {{e}}')\n")
            else:
                # Try to call with no arguments or generate defaults
                file_path = Path(file_config.path)
                sig = get_function_signature(file_path, func_name)
                
                if sig is None or len(sig) == 0:
                    # No parameters, call directly
                    test_code.append(f"        # Testing {func_name} (no parameters)\n")
                    test_code.append(f"        try:\n")
                    test_code.append(f"            result = {func_name}()\n")
                    test_code.append(f"            print(f'✓ {func_name} returned: {{result}}')\n")
                    test_code.append(f"        except Exception as e:\n")
                    test_code.append(f"            print(f'✗ {func_name} raised: {{type(e).__name__}}: {{e}}')\n")
                else:
                    # Generate default arguments
                    test_code.append(f"        # Testing {func_name} (auto-generated inputs)\n")
                    test_code.append(f"        try:\n")
                    args_list = []
                    for param_name, has_default in sig:
                        if param_name == "self":
                            continue
                        if has_default:
                            break  # Stop at first default param
                        default_val = generate_default_value(param_name)
                        args_list.append(repr(default_val))
                    
                    args_str = ", ".join(args_list) if args_list else ""
                    test_code.append(f"            result = {func_name}({args_str})\n")
                    test_code.append(f"            print(f'✓ {func_name} returned: {{result}}')\n")
                    test_code.append(f"        except Exception as e:\n")
                    test_code.append(f"            print(f'✗ {func_name} raised: {{type(e).__name__}}: {{e}}')\n")
            
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
    
    # Write the file
    content = "".join(imports) + "".join(test_code)
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(content)
    
    state.test_runner_path = test_file
    state.created_files.append(test_file)
    
    return test_file


def ensure_init_file(directory: Path, state: SetupState) -> None:
    """Ensure __init__.py exists in the directory."""
    init_file = directory / "__init__.py"
    if not init_file.exists():
        init_file.write_text("# Auto-generated by tracepatch\n", encoding="utf-8")
        state.created_files.append(init_file)


def setup_test_environment(config: TracepatchConfig, working_dir: Path) -> SetupState:
    """Set up test environment based on configuration.
    
    Returns:
        SetupState object containing information about what was created/modified.
    """
    state = SetupState()
    
    print("Setting up tracepatch test environment...")
    print()
    
    # Check Git status
    has_git, staged, unstaged = check_git_status(working_dir)
    if has_git:
        if staged:
            print("⚠️  Warning: You have staged Git changes:")
            for file in staged[:5]:  # Show max 5 files
                print(f"   - {file}")
            if len(staged) > 5:
                print(f"   ... and {len(staged) - 5} more")
            print()
            print("   tracepatch will create files that may affect your Git state.")
            response = input("   Continue? [y/N]: ").strip().lower()
            if response not in ('y', 'yes'):
                print("\nSetup cancelled.")
                return state
            print()
        elif unstaged:
            print("ℹ️  Note: You have unstaged Git changes.")
            print("   tracepatch will create temporary files in your working directory.")
            print()
    
    # Ensure __init__.py exists
    ensure_init_file(working_dir, state)
    if state.created_files and state.created_files[-1].name == "__init__.py":
        print(f"✓ Created {working_dir / '__init__.py'}")
    
    # Validate configured files exist
    print("\nValidating test configuration...")
    for file_config in config.test.files:
        file_path = working_dir / file_config.path
        if not file_path.exists():
            print(f"✗ File not found: {file_path}")
        else:
            print(f"✓ Found {file_path}")
            for func in file_config.functions:
                sig = get_function_signature(file_path, func)
                if sig is not None:
                    params = [p[0] for p in sig if p[0] != "self"]
                    print(f"  └─ {func}({', '.join(params)})")
                else:
                    print(f"  └─ {func}()")
    
    # Create test runner
    print("\nCreating test runner...")
    test_runner = create_test_runner(config, working_dir, state)
    print(f"✓ Created {test_runner.name}")
    
    # Ensure cache directory exists and save state there
    cache_dir = working_dir / _CACHE_DIR_NAME
    cache_dir.mkdir(exist_ok=True)
    state.save(cache_dir)
    
    print(f"\n{'=' * 70}")
    print("Setup complete!")
    print(f"{'=' * 70}")
    print()
    print("⚠️  IMPORTANT: Do not delete the .tracepatch_cache folder!")
    print("   It contains setup state needed for cleanup with 'tph disable'")
    print()
    print(f"Run tests with:")
    print(f"  python {test_runner.name}")
    print()
    print(f"Cleanup with:")
    print(f"  tph disable")
    print()
    
    return state


def cleanup_test_environment(working_dir: Path) -> bool:
    """Clean up test environment using saved state.
    
    Returns:
        True if cleanup was successful, False otherwise.
    """
    cache_dir = working_dir / _CACHE_DIR_NAME
    
    if not cache_dir.exists():
        print("Error: Cache directory not found!")
        print("Cannot cleanup without setup state.")
        return False
    
    state = SetupState.load(cache_dir)
    
    if state is None:
        print("No active tracepatch setup found.")
        print("Nothing to clean up.")
        return False
    
    print("Cleaning up tracepatch test environment...")
    print()
    
    # Check Git status
    has_git, staged, unstaged = check_git_status(working_dir)
    if has_git:
        if staged:
            print("⚠️  Warning: You have staged Git changes:")
            for file in staged[:5]:  # Show max 5 files
                print(f"   - {file}")
            if len(staged) > 5:
                print(f"   ... and {len(staged) - 5} more")
            print()
            print("   tracepatch will remove generated files that may affect your Git state.")
            response = input("   Continue? [y/N]: ").strip().lower()
            if response not in ('y', 'yes'):
                print("\nCleanup cancelled.")
                return False
            print()
        elif unstaged:
            print("ℹ️  Note: You have unstaged Git changes.")
            print("   tracepatch will remove temporary files from your working directory.")
            print()
    
    # Restore modified files
    for file_path, backup_content in state.modified_files:
        if file_path.exists():
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(backup_content)
            print(f"✓ Restored {file_path}")
    
    # Remove created files (except those in cache)
    for file_path in state.created_files:
        if file_path.exists() and not str(file_path).startswith(str(cache_dir)):
            file_path.unlink()
            print(f"✓ Removed {file_path}")
    
    # Remove setup state from cache
    state_file = cache_dir / "setup_state.json"
    if state_file.exists():
        state_file.unlink()
        print(f"✓ Removed setup state")
    
    print(f"\n{'=' * 70}")
    print("Cleanup complete!")
    print(f"{'=' * 70}")
    print()
    print("The .tracepatch_cache folder and trace logs have been preserved.")
    print()
    
    return True

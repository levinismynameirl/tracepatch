"""Configuration management for tracepatch via TOML files."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None  # type: ignore

try:
    import tomli_w
except ImportError:
    tomli_w = None  # type: ignore


def _apply_env_overrides(config: TracepatchConfig) -> None:
    """Apply environment variable overrides to configuration.
    
    Supported environment variables:
    - TRACEPATCH_ENABLED: 0|1|false|true - Enable/disable tracing (sets max_calls to 0 if disabled)
    - TRACEPATCH_MAX_DEPTH: int - Override max_depth
    - TRACEPATCH_MAX_CALLS: int - Override max_calls
    - TRACEPATCH_MAX_REPR: int - Override max_repr
    """
    # Check if tracing is globally disabled
    enabled = os.environ.get('TRACEPATCH_ENABLED', '').lower()
    if enabled in ('0', 'false', 'no'):
        config.max_calls = 0  # Effectively disable tracing
        return
    
    # Override numeric settings if provided
    if 'TRACEPATCH_MAX_DEPTH' in os.environ:
        try:
            config.max_depth = int(os.environ['TRACEPATCH_MAX_DEPTH'])
        except ValueError:
            pass
    
    if 'TRACEPATCH_MAX_CALLS' in os.environ:
        try:
            config.max_calls = int(os.environ['TRACEPATCH_MAX_CALLS'])
        except ValueError:
            pass
    
    if 'TRACEPATCH_MAX_REPR' in os.environ:
        try:
            config.max_repr = int(os.environ['TRACEPATCH_MAX_REPR'])
        except ValueError:
            pass


@dataclass
class TestFileConfig:
    """Configuration for a file to test."""
    path: str
    functions: list[str]
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestFileConfig:
        return cls(
            path=data.get("path", ""),
            functions=data.get("functions", [])
        )


@dataclass
class TestInputConfig:
    """Configuration for test function inputs."""
    function: str
    args: list[Any]
    kwargs: dict[str, Any]
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestInputConfig:
        return cls(
            function=data.get("function", ""),
            args=data.get("args", []),
            kwargs=data.get("kwargs", {})
        )


@dataclass
class CustomTestConfig:
    """Configuration for custom test script."""
    enabled: bool
    script: str
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CustomTestConfig:
        return cls(
            enabled=data.get("enabled", False),
            script=data.get("script", "")
        )
    
    @classmethod
    def default(cls) -> CustomTestConfig:
        return cls(enabled=False, script="")


@dataclass
class TestConfig:
    """Test setup configuration."""
    files: list[TestFileConfig]
    inputs: list[TestInputConfig]
    custom: CustomTestConfig
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestConfig:
        files = [TestFileConfig.from_dict(f) for f in data.get("files", [])]
        inputs = [TestInputConfig.from_dict(i) for i in data.get("inputs", [])]
        custom_data = data.get("custom", {})
        custom = CustomTestConfig.from_dict(custom_data) if custom_data else CustomTestConfig.default()
        return cls(files=files, inputs=inputs, custom=custom)
    
    @classmethod
    def default(cls) -> TestConfig:
        return cls(files=[], inputs=[], custom=CustomTestConfig.default())


@dataclass
class TracepatchConfig:
    """Configuration loaded from TOML file."""

    # Tracing behavior
    ignore_modules: list[str]
    include_modules: list[str]  # Allowlist mode - trace only these modules
    max_depth: int
    max_calls: int
    max_repr: int

    # Cache settings
    cache: bool
    cache_dir: Optional[str]

    # Output settings
    default_label: Optional[str]
    auto_save: bool

    # Display settings
    show_args: bool
    show_return: bool
    tree_style: str  # "ascii" or "unicode"
    
    # Test configuration
    test: TestConfig

    @classmethod
    def default(cls) -> TracepatchConfig:
        """Return default configuration."""
        return cls(
            ignore_modules=["unittest.mock"],
            include_modules=[],  # Empty = trace all (except ignored)
            max_depth=30,
            max_calls=10_000,
            max_repr=120,
            cache=True,
            cache_dir=None,
            default_label=None,
            auto_save=True,
            show_args=True,
            show_return=True,
            tree_style="ascii",
            test=TestConfig.default(),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TracepatchConfig:
        """Create config from a dictionary, filling in defaults for missing values."""
        defaults = cls.default()
        
        # Handle test config if present
        test_data = data.get("test", {})
        test_config = TestConfig.from_dict(test_data) if test_data else TestConfig.default()
        
        return cls(
            ignore_modules=data.get("ignore_modules", defaults.ignore_modules),
            include_modules=data.get("include_modules", defaults.include_modules),
            max_depth=data.get("max_depth", defaults.max_depth),
            max_calls=data.get("max_calls", defaults.max_calls),
            max_repr=data.get("max_repr", defaults.max_repr),
            cache=data.get("cache", defaults.cache),
            cache_dir=data.get("cache_dir", defaults.cache_dir),
            default_label=data.get("default_label", defaults.default_label),
            auto_save=data.get("auto_save", defaults.auto_save),
            show_args=data.get("show_args", defaults.show_args),
            show_return=data.get("show_return", defaults.show_return),
            tree_style=data.get("tree_style", defaults.tree_style),
            test=test_config,
        )

    def to_trace_kwargs(self) -> dict[str, Any]:
        """Convert config to kwargs for trace() constructor."""
        return {
            "ignore_modules": self.ignore_modules,
            "max_depth": self.max_depth,
            "max_calls": self.max_calls,
            "max_repr": self.max_repr,
            "cache": self.cache,
            "cache_dir": self.cache_dir,
            "label": self.default_label,
        }


def load_config(
    path: Optional[Union[str, Path]] = None,
    search_parents: bool = True,
) -> tuple[TracepatchConfig, Optional[Path]]:
    """Load tracepatch configuration from a TOML file.

    Searches for configuration in the following order:
    1. The path specified by the `path` argument
    2. `tracepatch.toml` in the current directory
    3. `pyproject.toml` in the current directory (looking for [tool.tracepatch])
    4. If `search_parents` is True, search parent directories for the above files
    
    Environment variables can override settings:
    - TRACEPATCH_ENABLED=0|1|false|true - Enable/disable tracing globally
    - TRACEPATCH_MAX_DEPTH=N - Override max_depth
    - TRACEPATCH_MAX_CALLS=N - Override max_calls
    - TRACEPATCH_COLOR=1 - Enable colored output

    Parameters
    ----------
    path:
        Explicit path to a TOML configuration file.
    search_parents:
        If True, search parent directories for config files.

    Returns
    -------
    Tuple of (TracepatchConfig instance, config file path or None).
    """
    import os
    
    if tomllib is None:
        # TOML library not available, return defaults
        config = TracepatchConfig.default()
        # Apply environment variable overrides
        _apply_env_overrides(config)
        return config, None
        return TracepatchConfig.default(), None

    # If explicit path provided, try to load it
    if path is not None:
        config_path = Path(path)
        if config_path.exists():
            config = _load_from_file(config_path)
            if config is not None:
                _apply_env_overrides(config)
                return config, config_path
        config = TracepatchConfig.default()
        _apply_env_overrides(config)
        return config, None

    # Search for config files
    search_dir = Path.cwd()
    while True:
        # Try tracepatch.toml first
        tracepatch_toml = search_dir / "tracepatch.toml"
        if tracepatch_toml.exists():
            config = _load_from_file(tracepatch_toml, section=None)
            if config is not None:
                _apply_env_overrides(config)
                return config, tracepatch_toml

        # Try pyproject.toml with [tool.tracepatch] section
        pyproject_toml = search_dir / "pyproject.toml"
        if pyproject_toml.exists():
            config = _load_from_file(pyproject_toml, section="tool.tracepatch")
            if config is not None:
                _apply_env_overrides(config)
                return config, pyproject_toml

        # Move to parent directory
        if not search_parents or search_dir.parent == search_dir:
            break
        search_dir = search_dir.parent

    # No config found, return defaults
    config = TracepatchConfig.default()
    _apply_env_overrides(config)
    return config, None


def _load_from_file(
    path: Path,
    section: Optional[str] = None,
) -> Optional[TracepatchConfig]:
    """Load configuration from a TOML file.

    Parameters
    ----------
    path:
        Path to TOML file.
    section:
        Dot-separated section path (e.g., "tool.tracepatch").
        If None, uses the root of the TOML file.

    Returns
    -------
    TracepatchConfig if loaded successfully, None if section not found.
    """
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)

        # Navigate to the specified section
        if section is not None:
            for key in section.split("."):
                data = data.get(key, {})
                if not isinstance(data, dict):
                    return None

        # If we got an empty dict, it means the section doesn't exist
        if not data:
            return None

        return TracepatchConfig.from_dict(data)
    except Exception:
        # If anything goes wrong, return None
        return None


def save_config(config: TracepatchConfig, path: Union[str, Path]) -> None:
    """Save configuration to a TOML file.

    Parameters
    ----------
    config:
        Configuration to save.
    path:
        Destination file path.
    """
    if tomli_w is None:
        raise ImportError(
            "tomli_w is required to save TOML configuration. "
            "Install with: pip install tomli-w"
        )

    config_dict = {
        "ignore_modules": config.ignore_modules,
        "include_modules": config.include_modules,
        "max_depth": config.max_depth,
        "max_calls": config.max_calls,
        "max_repr": config.max_repr,
        "cache": config.cache,
        "cache_dir": config.cache_dir,
        "default_label": config.default_label,
        "auto_save": config.auto_save,
        "show_args": config.show_args,
        "show_return": config.show_return,
        "tree_style": config.tree_style,
    }

    # Remove None values
    config_dict = {k: v for k, v in config_dict.items() if v is not None}

    output_path = Path(path)
    with open(output_path, "wb") as f:
        tomli_w.dump(config_dict, f)

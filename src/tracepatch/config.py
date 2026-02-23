"""Configuration management for tracepatch via TOML files."""

from __future__ import annotations

import contextlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class ConfigError(Exception):
    """Raised when a configuration file contains invalid values."""


def _apply_env_overrides(config: TracepatchConfig) -> TracepatchConfig:
    """Apply environment variable overrides to configuration.

    Returns a *new* ``TracepatchConfig`` instance with overrides applied.
    The original *config* is never mutated.

    Supported environment variables
    --------------------------------
    - ``TRACEPATCH_ENABLED``: ``0|1|false|true`` — sets ``max_calls=0`` when disabled.
    - ``TRACEPATCH_MAX_DEPTH``: int — override ``max_depth``.
    - ``TRACEPATCH_MAX_CALLS``: int — override ``max_calls``.
    - ``TRACEPATCH_MAX_REPR``: int — override ``max_repr``.
    - ``TRACEPATCH_MAX_TIME``: float — override ``max_time``.
    - ``TRACEPATCH_LABEL``: str — override ``default_label``.
    - ``TRACEPATCH_OUTPUT_DIR``: str — override ``cache_dir``.
    - ``TRACEPATCH_NO_CACHE``: ``1`` — set ``cache=False``.
    - ``TRACEPATCH_COLOR``: ``1|true`` — set ``color=True``.

    Parameters
    ----------
    config:
        The base configuration to apply overrides on top of.

    Returns
    -------
    TracepatchConfig
        A new configuration instance with environment overrides applied.
    """
    from dataclasses import fields as _fields

    overrides: dict[str, Any] = {}

    # Check if tracing is globally disabled
    enabled = os.environ.get("TRACEPATCH_ENABLED", "").lower()
    if enabled in ("0", "false", "no"):
        overrides["max_calls"] = 0
        # Build immediately — nothing else matters when disabled
        return TracepatchConfig(
            **{f.name: overrides.get(f.name, getattr(config, f.name)) for f in _fields(config)}
        )

    # Override numeric settings if provided
    for env_var, field_name, cast in (
        ("TRACEPATCH_MAX_DEPTH", "max_depth", int),
        ("TRACEPATCH_MAX_CALLS", "max_calls", int),
        ("TRACEPATCH_MAX_REPR", "max_repr", int),
        ("TRACEPATCH_MAX_TIME", "max_time", float),
    ):
        raw = os.environ.get(env_var)
        if raw is not None:
            with contextlib.suppress(ValueError):
                overrides[field_name] = cast(raw)

    # String overrides
    raw_label = os.environ.get("TRACEPATCH_LABEL")
    if raw_label is not None:
        overrides["default_label"] = raw_label

    raw_output = os.environ.get("TRACEPATCH_OUTPUT_DIR")
    if raw_output is not None:
        overrides["cache_dir"] = raw_output

    # Boolean overrides
    if os.environ.get("TRACEPATCH_NO_CACHE", "").lower() in ("1", "true", "yes"):
        overrides["cache"] = False

    if os.environ.get("TRACEPATCH_COLOR", "").lower() in ("1", "true", "yes"):
        overrides["color"] = True

    if not overrides:
        return config

    return TracepatchConfig(
        **{f.name: overrides.get(f.name, getattr(config, f.name)) for f in _fields(config)}
    )


@dataclass(frozen=True)
class TestFileConfig:
    """Configuration for a file to test."""

    path: str
    functions: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestFileConfig:
        return cls(path=data.get("path", ""), functions=data.get("functions", []))


@dataclass(frozen=True)
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
            kwargs=data.get("kwargs", {}),
        )


@dataclass(frozen=True)
class CustomTestConfig:
    """Configuration for custom test script."""

    enabled: bool
    script: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CustomTestConfig:
        return cls(enabled=data.get("enabled", False), script=data.get("script", ""))

    @classmethod
    def default(cls) -> CustomTestConfig:
        return cls(enabled=False, script="")


@dataclass(frozen=True)
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
        custom = (
            CustomTestConfig.from_dict(custom_data) if custom_data else CustomTestConfig.default()
        )
        return cls(files=files, inputs=inputs, custom=custom)

    @classmethod
    def default(cls) -> TestConfig:
        return cls(files=[], inputs=[], custom=CustomTestConfig.default())


@dataclass(frozen=True)
class TracepatchConfig:
    """Configuration loaded from TOML file.

    Attributes
    ----------
    ignore_modules:
        Module name prefixes to exclude from tracing.
    include_modules:
        Allowlist mode — when non-empty, *only* these module prefixes are traced.
    max_depth:
        Maximum call-stack nesting to record.
    max_calls:
        Maximum total recorded calls before tracing is disabled.
    max_repr:
        Maximum character length for ``repr()`` of args/return values.
        Acts as a fallback when ``max_repr_args`` or ``max_repr_return`` are
        not explicitly set.
    max_repr_args:
        Maximum character length for ``repr()`` of arguments.  Falls back to
        ``max_repr`` when ``None``.
    max_repr_return:
        Maximum character length for ``repr()`` of return values.  Falls back
        to ``max_repr`` when ``None``.
    max_time:
        Maximum trace duration in seconds.
    cache:
        Whether to persist traces to disk automatically.
    cache_dir:
        Directory for trace storage (``None`` → default).
    default_label:
        Default label applied to all traces.  Supports ``{hostname}``,
        ``{pid}``, and ``{timestamp}`` template variables.
    auto_save:
        Automatically save traces on context exit.
    show_args:
        Show function arguments in tree output.
    show_return:
        Show return values in tree output.
    tree_style:
        Tree rendering style: ``"ascii"`` or ``"unicode"``.
    color:
        Enable ANSI colour output (always ``False`` when stdout is not a TTY).
    test:
        Test setup configuration.
    """

    # Tracing behavior
    ignore_modules: list[str]
    include_modules: list[str]
    max_depth: int
    max_calls: int
    max_repr: int
    max_repr_args: int | None
    max_repr_return: int | None
    max_time: float

    # Cache settings
    cache: bool
    cache_dir: str | None

    # Output settings
    default_label: str | None
    auto_save: bool

    # Display settings
    show_args: bool
    show_return: bool
    tree_style: str
    color: bool

    # Test configuration
    test: TestConfig

    # ------------------------------------------------------------------
    # Known TOML keys (for validation)
    # ------------------------------------------------------------------

    _KNOWN_KEYS: frozenset[str] = frozenset(
        {
            "ignore_modules",
            "include_modules",
            "max_depth",
            "max_calls",
            "max_repr",
            "max_repr_args",
            "max_repr_return",
            "max_time",
            "cache",
            "cache_dir",
            "default_label",
            "auto_save",
            "show_args",
            "show_return",
            "tree_style",
            "color",
            "test",
        }
    )

    def effective_max_repr_args(self) -> int:
        """Return the effective max repr length for arguments.

        Falls back to ``max_repr`` when ``max_repr_args`` is ``None``.

        Returns
        -------
        int
        """
        return self.max_repr_args if self.max_repr_args is not None else self.max_repr

    def effective_max_repr_return(self) -> int:
        """Return the effective max repr length for return values.

        Falls back to ``max_repr`` when ``max_repr_return`` is ``None``.

        Returns
        -------
        int
        """
        return self.max_repr_return if self.max_repr_return is not None else self.max_repr

    def expand_label(self, label: str | None = None) -> str | None:
        """Expand template variables in a label string.

        Supported variables: ``{hostname}``, ``{pid}``, ``{timestamp}``.

        Parameters
        ----------
        label:
            Label to expand.  Defaults to ``self.default_label``.

        Returns
        -------
        str | None
            Expanded label, or ``None`` if no label is set.
        """
        import datetime
        import os
        import socket

        raw = label if label is not None else self.default_label
        if raw is None:
            return None
        return raw.format_map(
            {
                "hostname": socket.gethostname(),
                "pid": os.getpid(),
                "timestamp": datetime.datetime.now().strftime("%Y%m%d_%H%M%S"),
            }
        )

    @classmethod
    def default(cls) -> TracepatchConfig:
        """Return default configuration with sensible production defaults.

        Returns
        -------
        TracepatchConfig
        """
        return cls(
            ignore_modules=["unittest.mock"],
            include_modules=[],
            max_depth=30,
            max_calls=10_000,
            max_repr=120,
            max_repr_args=None,
            max_repr_return=None,
            max_time=60.0,
            cache=True,
            cache_dir=None,
            default_label=None,
            auto_save=True,
            show_args=True,
            show_return=True,
            tree_style="ascii",
            color=False,
            test=TestConfig.default(),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TracepatchConfig:
        """Create config from a dictionary, filling in defaults for missing values.

        Raises :class:`ConfigError` for clearly invalid values (wrong type,
        out of range, unknown enum).

        Parameters
        ----------
        data:
            Parsed TOML dictionary.

        Returns
        -------
        TracepatchConfig
        """
        defaults = cls.default()

        test_data = data.get("test", {})
        test_config = TestConfig.from_dict(test_data) if test_data else TestConfig.default()

        config = cls(
            ignore_modules=data.get("ignore_modules", defaults.ignore_modules),
            include_modules=data.get("include_modules", defaults.include_modules),
            max_depth=data.get("max_depth", defaults.max_depth),
            max_calls=data.get("max_calls", defaults.max_calls),
            max_repr=data.get("max_repr", defaults.max_repr),
            max_repr_args=data.get("max_repr_args", defaults.max_repr_args),
            max_repr_return=data.get("max_repr_return", defaults.max_repr_return),
            max_time=data.get("max_time", defaults.max_time),
            cache=data.get("cache", defaults.cache),
            cache_dir=data.get("cache_dir", defaults.cache_dir),
            default_label=data.get("default_label", defaults.default_label),
            auto_save=data.get("auto_save", defaults.auto_save),
            show_args=data.get("show_args", defaults.show_args),
            show_return=data.get("show_return", defaults.show_return),
            tree_style=data.get("tree_style", defaults.tree_style),
            color=data.get("color", defaults.color),
            test=test_config,
        )

        config._validate(data)
        return config

    def _validate(self, raw_data: dict[str, Any] | None = None) -> list[str]:
        """Validate configuration values and return a list of error messages.

        Raises :class:`ConfigError` for critical errors (wrong types, out of
        range).  Returns a list of warning strings for unknown keys.

        Parameters
        ----------
        raw_data:
            The original dict from TOML, used to detect unknown keys.

        Returns
        -------
        list[str]
            Warning messages (non-fatal).

        Raises
        ------
        ConfigError
            On invalid types or out-of-range values.
        """
        warnings: list[str] = []

        # Check unknown keys
        if raw_data is not None:
            for key in raw_data:
                if key not in self._KNOWN_KEYS:
                    warnings.append(f"Unknown config key: {key!r}")

        # Type checks
        if not isinstance(self.max_depth, int) or self.max_depth < 1:
            raise ConfigError(f"max_depth must be a positive integer, got {self.max_depth!r}")
        if not isinstance(self.max_calls, int) or self.max_calls < 0:
            raise ConfigError(f"max_calls must be a non-negative integer, got {self.max_calls!r}")
        if not isinstance(self.max_repr, int) or self.max_repr < 1:
            raise ConfigError(f"max_repr must be a positive integer, got {self.max_repr!r}")
        if self.max_repr_args is not None and (
            not isinstance(self.max_repr_args, int) or self.max_repr_args < 1
        ):
            raise ConfigError(
                f"max_repr_args must be a positive integer, got {self.max_repr_args!r}"
            )
        if self.max_repr_return is not None and (
            not isinstance(self.max_repr_return, int) or self.max_repr_return < 1
        ):
            raise ConfigError(
                f"max_repr_return must be a positive integer, got {self.max_repr_return!r}"
            )
        if not isinstance(self.max_time, (int, float)) or self.max_time <= 0:
            raise ConfigError(f"max_time must be a positive number, got {self.max_time!r}")

        # Enum checks
        if self.tree_style not in ("ascii", "unicode"):
            raise ConfigError(f"tree_style must be 'ascii' or 'unicode', got {self.tree_style!r}")

        return warnings

    def to_trace_kwargs(self) -> dict[str, Any]:
        """Convert config to kwargs suitable for the ``trace()`` constructor.

        Returns
        -------
        dict[str, Any]
            Keyword arguments accepted by ``trace()``.
        """
        return {
            "ignore_modules": self.ignore_modules,
            "include_modules": self.include_modules,
            "max_depth": self.max_depth,
            "max_calls": self.max_calls,
            "max_repr": self.effective_max_repr_args(),
            "max_time": self.max_time,
            "cache": self.cache,
            "cache_dir": self.cache_dir,
            "label": self.expand_label(),
        }

    def to_trace_config(self):
        """Create a ``TraceConfig`` from this configuration.

        Returns
        -------
        TraceConfig
            Internal immutable config for the tracing engine.
        """
        from tracepatch._trace import TraceConfig

        return TraceConfig(
            ignore_modules=tuple(self.ignore_modules),
            include_modules=tuple(self.include_modules),
            max_depth=self.max_depth,
            max_calls=self.max_calls,
            max_repr=self.max_repr,
            max_time=self.max_time,
        )


def load_config(
    path: str | Path | None = None,
    search_parents: bool = True,
) -> tuple[TracepatchConfig, Path | None]:
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

    if tomllib is None:
        # TOML library not available, return defaults
        config = TracepatchConfig.default()
        # Apply environment variable overrides
        config = _apply_env_overrides(config)
        return config, None

    # If explicit path provided, try to load it
    if path is not None:
        config_path = Path(path)
        if config_path.exists():
            config = _load_from_file(config_path)
            if config is not None:
                config = _apply_env_overrides(config)
                return config, config_path
        config = TracepatchConfig.default()
        config = _apply_env_overrides(config)
        return config, None

    # Search for config files
    search_dir = Path.cwd()
    while True:
        # Try tracepatch.toml first
        tracepatch_toml = search_dir / "tracepatch.toml"
        if tracepatch_toml.exists():
            config = _load_from_file(tracepatch_toml, section=None)
            if config is not None:
                config = _apply_env_overrides(config)
                return config, tracepatch_toml

        # Try pyproject.toml with [tool.tracepatch] section
        pyproject_toml = search_dir / "pyproject.toml"
        if pyproject_toml.exists():
            config = _load_from_file(pyproject_toml, section="tool.tracepatch")
            if config is not None:
                config = _apply_env_overrides(config)
                return config, pyproject_toml

        # Move to parent directory
        if not search_parents or search_dir.parent == search_dir:
            break
        search_dir = search_dir.parent

    # No config found, return defaults
    config = TracepatchConfig.default()
    config = _apply_env_overrides(config)
    return config, None


def _load_from_file(
    path: Path,
    section: str | None = None,
) -> TracepatchConfig | None:
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


def save_config(config: TracepatchConfig, path: str | Path) -> None:
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
            "tomli_w is required to save TOML configuration. Install with: pip install tomli-w"
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

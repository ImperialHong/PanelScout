"""Configuration helpers for the PanelScout CLI baseline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import os
from pathlib import Path
import tomllib
from typing import Any

APP_NAME = "panelscout"
DEFAULT_USER_AGENT = "PanelScout/0.1 (metadata-only; local use)"
DEFAULT_DOWNLOAD_ROOT = Path("~/Downloads")
SUPPORTED_SOURCES = ("zaimanhua",)


class ConfigError(ValueError):
    """Raised when a PanelScout config file is invalid."""


@dataclass(frozen=True)
class PanelScoutConfig:
    """Runtime settings used by the current metadata-only skeleton."""

    data_dir: Path
    database_path: Path
    cache_dir: Path
    session_dir: Path
    download_root: Path
    user_agent: str = DEFAULT_USER_AGENT
    request_delay_seconds: float = 2.0
    max_concurrency_per_domain: int = 1
    source: str = "zaimanhua"
    metadata_only: bool = True

    def as_display_dict(self) -> dict[str, str | int | float | bool]:
        """Return config values in a CLI-friendly, serializable form."""

        values = asdict(self)
        return {
            key: str(value) if isinstance(value, Path) else value
            for key, value in values.items()
        }


def default_config_path() -> Path:
    """Return the default per-user TOML config path."""

    configured = os.environ.get("PANELSCOUT_CONFIG")
    if configured:
        return Path(configured).expanduser()

    config_home = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
    return config_home / APP_NAME / "config.toml"


def default_config() -> PanelScoutConfig:
    """Return conservative defaults for local metadata collection."""

    data_home = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser()
    cache_home = Path(os.environ.get("XDG_CACHE_HOME", "~/.cache")).expanduser()
    data_dir = data_home / APP_NAME

    return PanelScoutConfig(
        data_dir=data_dir,
        database_path=data_dir / "panelscout.sqlite3",
        cache_dir=cache_home / APP_NAME,
        session_dir=data_dir / "sessions",
        download_root=DEFAULT_DOWNLOAD_ROOT.expanduser(),
    )


def load_config(path: str | Path | None = None) -> PanelScoutConfig:
    """Load a TOML config file, or return defaults when it does not exist."""

    config_path = Path(path).expanduser() if path is not None else default_config_path()
    config = default_config()

    if not config_path.exists():
        return config

    with config_path.open("rb") as file:
        raw_config = tomllib.load(file)

    return build_config(raw_config)


def build_config(raw_config: dict[str, Any]) -> PanelScoutConfig:
    """Build a validated config object from parsed TOML data."""

    config_values = asdict(default_config())
    overrides = _flatten_config(raw_config)
    _reject_unknown_keys(overrides)

    if "data_dir" in overrides:
        data_dir = _coerce_path(overrides["data_dir"])
        config_values["data_dir"] = data_dir
        if "database_path" not in overrides:
            config_values["database_path"] = data_dir / "panelscout.sqlite3"
        if "session_dir" not in overrides:
            config_values["session_dir"] = data_dir / "sessions"

    for key, value in overrides.items():
        if key in {
            "data_dir",
            "database_path",
            "cache_dir",
            "session_dir",
            "download_root",
        }:
            config_values[key] = _coerce_path(value)
        else:
            config_values[key] = value

    config = PanelScoutConfig(**config_values)
    _validate_config(config)
    return config


def _flatten_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    allowed_sections = ("panelscout", "paths", "network", "source")
    flattened: dict[str, Any] = {}

    for section in allowed_sections:
        section_values = raw_config.get(section, {})
        if not isinstance(section_values, dict):
            raise ConfigError(f"[{section}] must be a table")
        flattened.update(section_values)

    top_level = {
        key: value
        for key, value in raw_config.items()
        if key not in allowed_sections
    }
    flattened.update(top_level)
    return flattened


def _reject_unknown_keys(values: dict[str, Any]) -> None:
    allowed_keys = {field.name for field in fields(PanelScoutConfig)}
    unknown = sorted(set(values) - allowed_keys)
    if unknown:
        joined = ", ".join(unknown)
        raise ConfigError(f"Unknown config key(s): {joined}")


def _coerce_path(value: Any) -> Path:
    if isinstance(value, Path):
        return value.expanduser()
    if isinstance(value, str):
        return Path(value).expanduser()
    raise ConfigError(f"Expected path string, got {type(value).__name__}")


def _validate_config(config: PanelScoutConfig) -> None:
    if config.source not in SUPPORTED_SOURCES:
        supported = ", ".join(SUPPORTED_SOURCES)
        raise ConfigError(f"Unsupported source '{config.source}'. Supported: {supported}")
    if not isinstance(config.request_delay_seconds, int | float):
        raise ConfigError("request_delay_seconds must be a number")
    if config.request_delay_seconds < 1:
        raise ConfigError("request_delay_seconds must be at least 1")
    if not isinstance(config.max_concurrency_per_domain, int):
        raise ConfigError("max_concurrency_per_domain must be an integer")
    if not 1 <= config.max_concurrency_per_domain <= 2:
        raise ConfigError("max_concurrency_per_domain must be 1 or 2")
    if not config.metadata_only:
        raise ConfigError("PanelScout MVP 1 must remain metadata_only")
    if not config.user_agent.strip():
        raise ConfigError("user_agent cannot be blank")

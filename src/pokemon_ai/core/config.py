"""Loading and validating the configuration.

Merge order (the last one wins):
1. `default.yaml`;
2. `emulator.yaml`, in its own `emulator` section;
3. the extra YAML files given with `--config`, in order;
4. single overrides `section.key=value` given with `--set`.

Relative paths are relative to the current directory.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

DEFAULT_CONFIG_DIR = Path("config")
SECTION_FILES = {"emulator": "emulator.yaml"}


class ConfigError(Exception):
    pass


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LoggingConfig(_Section):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    file: Path | None = None


class UIConfig(_Section):
    """Refresh rates of the interface. They do not change what the agent does."""

    frame_rate: int = Field(default=30, gt=0, le=60, description="Screen images sent per second")
    state_rate: int = Field(default=10, gt=0, description="State updates sent per second")
    observation_interval: int = Field(
        default=8, gt=0, description="Frames between two reads of the game state"
    )
    log_max_rows: int = Field(default=5000, gt=0)


class EmulatorConfig(_Section):
    rom_path: Path = Path("ROM/Pokemon - Red Version (USA, Europe) (SGB Enhanced).zip")
    rom_sha1: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    headless: bool = False
    speed: int = Field(default=1, ge=0, description="Speed multiplier, 0 = unlimited")
    scale: int = Field(default=3, ge=1, le=8)
    sound: bool = False
    savestate_dir: Path = Path("assets/states")


class GameConfig(_Section):
    game: str = "pokemon_red"  # game adapter (see game/adapter.py)
    reveal_mode: Literal["viewport", "full_map_on_entry"] = "viewport"


class RunConfig(_Section):
    agent: str = "random"  # registry name, `package.module:Class` or `file.py:Class`
    data_dir: Path = Path("data/agents")  # one sub-folder per agent: what it learns


class AppConfig(_Section):
    random_seed: int = 42
    logging: LoggingConfig = LoggingConfig()
    ui: UIConfig = UIConfig()
    emulator: EmulatorConfig = EmulatorConfig()
    game: GameConfig = GameConfig()
    run: RunConfig = RunConfig()
    # Free options of each agent: `agents.<name>.<option>` (validated by the agent itself).
    agents: dict[str, dict[str, Any]] = Field(default_factory=dict)


def load_config(
    config_dir: Path = DEFAULT_CONFIG_DIR,
    override_files: Iterable[Path] = (),
    overrides: Iterable[str] = (),
) -> AppConfig:
    data: dict[str, Any] = {}
    default_file = config_dir / "default.yaml"
    if default_file.exists():
        data = _deep_merge(data, _read_yaml(default_file))
    for section, filename in SECTION_FILES.items():
        path = config_dir / filename
        if path.exists():
            data = _deep_merge(data, {section: _read_yaml(path)})
    for path in override_files:
        if not path.exists():
            raise ConfigError(f"Configuration file not found: {path}")
        data = _deep_merge(data, _read_yaml(path))
    for override in overrides:
        data = _deep_merge(data, parse_override(override))

    try:
        return AppConfig.model_validate(data)
    except ValidationError as error:
        raise ConfigError(format_validation_error(error)) from None


def parse_override(override: str) -> dict[str, Any]:
    """Turn `emulator.speed=2` into a nested dictionary (the value is read as YAML)."""
    key, separator, raw_value = override.partition("=")
    if not separator or not key.strip():
        raise ConfigError(f"Invalid override '{override}': expected section.key=value")
    try:
        value = yaml.safe_load(raw_value)
    except yaml.YAMLError as error:
        raise ConfigError(f"Invalid value in '{override}': {error}") from None
    result: dict[str, Any] = {}
    node = result
    *parents, leaf = key.strip().split(".")
    for part in parents:
        node = node.setdefault(part, {})
    node[leaf] = value
    return result


def format_validation_error(error: ValidationError) -> str:
    lines = ["Invalid configuration:"]
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"]) or "<root>"
        received = repr(item.get("input"))
        if len(received) > 60:
            received = received[:57] + "..."
        lines.append(f"  - {location}: {item['msg']} (received: {received})")
    return "\n".join(lines)


def dump_config(config: AppConfig) -> str:
    return yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False, allow_unicode=True)


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ConfigError(f"Invalid YAML in {path}: {error}") from None
    if content is None:
        return {}
    if not isinstance(content, Mapping):
        raise ConfigError(f"{path} must contain a YAML dictionary at the top level")
    return dict(content)


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged

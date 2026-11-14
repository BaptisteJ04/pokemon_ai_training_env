"""Savestates by name: the folder `emulator.savestate_dir` (sub-folders allowed)."""

from __future__ import annotations

from pokemon_ai.core.config import AppConfig
from pokemon_ai.emulator.state_manager import SaveStateManager


def savestate_manager(config: AppConfig) -> SaveStateManager:
    return SaveStateManager(config.emulator.savestate_dir)

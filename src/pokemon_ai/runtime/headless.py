"""Run without the interface: the agent plays at unlimited speed."""

from __future__ import annotations

import logging

from pokemon_ai.core.config import AppConfig
from pokemon_ai.core.event_bus import EventBus
from pokemon_ai.emulator.pyboy_adapter import PyBoyEmulator
from pokemon_ai.emulator.rom import load_rom
from pokemon_ai.env.session import GameSession
from pokemon_ai.game.adapter import game_adapter
from pokemon_ai.runtime.controllers import make_controller
from pokemon_ai.runtime.loop import Mode, SessionLoop
from pokemon_ai.runtime.savestates import savestate_manager

logger = logging.getLogger(__name__)


def run_headless(config: AppConfig, *, frames: int | None, initial_state: str | None = None) -> str:
    """Play `frames` frames (None: until interrupted) and return the final status."""
    rom = load_rom(config.emulator.rom_path, config.emulator.rom_sha1)
    bus = EventBus()
    controller = make_controller(config, bus=bus)
    with PyBoyEmulator(rom, headless=True, sound=config.emulator.sound) as emulator:
        if initial_state is not None:
            emulator.load_state(savestate_manager(config).load(initial_state, rom_sha1=rom.sha1))
        session = GameSession(
            emulator,
            bus,
            rom_sha1=rom.sha1,
            reveal_mode=config.game.reveal_mode,
            observation_interval=config.ui.observation_interval,
            adapter=game_adapter(config.game.game),
        )
        loop = SessionLoop(session, controller, speed=0, mode=Mode.AUTONOMOUS)
        try:
            status = loop.run(frames)
        except KeyboardInterrupt:
            status = "interrupted"
    data_dir = controller.agent.setup_info.data_dir
    if data_dir is not None:
        data_dir.mkdir(parents=True, exist_ok=True)
        controller.agent.save(data_dir)  # what was learned, for the next runs
    logger.info("Run finished: %s", status)
    return status

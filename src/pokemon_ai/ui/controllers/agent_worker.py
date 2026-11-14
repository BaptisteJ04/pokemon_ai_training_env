"""Agent thread: it owns the emulator and runs the session loop.

The emulator is created in this thread and never leaves it. The interface sends commands
(thread-safe queue) and receives screen copies and immutable values through signals.
"""

from __future__ import annotations

import logging
import queue
from collections.abc import Callable

import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from pokemon_ai.core.config import AppConfig
from pokemon_ai.core.event_bus import EventBus
from pokemon_ai.emulator.base import GameEmulator
from pokemon_ai.emulator.state_manager import SaveStateManager
from pokemon_ai.env.session import Controller, GameSession
from pokemon_ai.game.adapter import game_adapter
from pokemon_ai.runtime.loop import Command, LoopCallbacks, Mode, SessionLoop

logger = logging.getLogger(__name__)


def to_qimage(screen: np.ndarray) -> QImage:
    """Independent copy of the screen (the numpy array can be freed afterwards)."""
    height, width, _ = screen.shape
    data = np.ascontiguousarray(screen)
    return QImage(data.data, width, height, 3 * width, QImage.Format.Format_RGB888).copy()


class AgentWorker(QThread):
    frame_ready = Signal(QImage)
    state_ready = Signal(object)  # GameState
    world_map_ready = Signal(object)  # WorldMap
    failed = Signal(str)

    def __init__(
        self,
        config: AppConfig,
        bus: EventBus,
        emulator_factory: Callable[[], GameEmulator],
        controller: Controller,
        *,
        initial_state: bytes | None = None,
        savestates: SaveStateManager | None = None,
        mode: Mode = Mode.MANUAL,
    ) -> None:
        super().__init__()
        self.setObjectName("agent-worker")
        self.commands: queue.Queue[Command] = queue.Queue()
        self.status: str | None = None
        self._config = config
        self._bus = bus
        self._emulator_factory = emulator_factory
        self._controller = controller
        self._initial_state = initial_state
        self._savestates = savestates
        self._mode = mode

    def send(self, command: Command) -> None:
        self.commands.put(command)

    def run(self) -> None:
        emulator: GameEmulator | None = None
        try:
            emulator = self._emulator_factory()
            emulator.start()
            if self._initial_state is not None:
                emulator.load_state(self._initial_state)
            rom = getattr(emulator, "rom", None)
            session = GameSession(
                emulator,
                self._bus,
                rom_sha1=rom.sha1 if rom is not None else "",
                reveal_mode=self._config.game.reveal_mode,
                observation_interval=self._config.ui.observation_interval,
                savestates=self._savestates,
                adapter=game_adapter(self._config.game.game),
            )
            loop = SessionLoop(
                session,
                self._controller,
                self.commands,
                speed=self._config.emulator.speed,
                mode=self._mode,
                frame_rate=self._config.ui.frame_rate,
                state_rate=self._config.ui.state_rate,
                callbacks=LoopCallbacks(
                    on_frame=lambda screen: self.frame_ready.emit(to_qimage(screen)),
                    on_state=self.state_ready.emit,
                    on_world_map=self.world_map_ready.emit,
                ),
            )
            self.status = loop.run()
        except Exception as error:
            logger.exception("The agent stopped on an error")
            self.status = "error"
            self.failed.emit(f"{type(error).__name__} : {error}")
        finally:
            if emulator is not None:
                emulator.stop()

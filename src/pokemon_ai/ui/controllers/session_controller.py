"""Life cycle of a session seen from the interface: worker and event bridge.

All methods are called from the interface thread. They only send commands to the worker: none of
them touches the emulator or the agent state.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from pokemon_ai.core.config import AppConfig
from pokemon_ai.core.event_bus import EventBus
from pokemon_ai.emulator.base import GameEmulator
from pokemon_ai.emulator.controls import Button
from pokemon_ai.emulator.state_manager import SaveStateManager
from pokemon_ai.env.session import Controller
from pokemon_ai.runtime.loop import (
    ControllerCommand,
    LoadState,
    Mode,
    Pause,
    Resume,
    SaveState,
    SetButtons,
    SetMode,
    SetSpeed,
    Stop,
)
from pokemon_ai.ui.controllers.agent_worker import AgentWorker
from pokemon_ai.ui.controllers.event_bridge import EventBridge

logger = logging.getLogger(__name__)


class SessionController(QObject):
    frame_ready = Signal(QImage)
    state_ready = Signal(object)
    world_map_ready = Signal(object)
    event_received = Signal(object)
    running_changed = Signal(bool)
    failed = Signal(str)

    def __init__(
        self,
        config: AppConfig,
        emulator_factory: Callable[[], GameEmulator],
        controller_factory: Callable[[EventBus], Controller],
        *,
        rom_sha1: str = "",
        savestates: SaveStateManager | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.bus = EventBus()
        self.bridge = EventBridge(self.bus, self)
        self.bridge.event_received.connect(self.event_received)
        self.savestates = savestates
        self.mode = Mode.MANUAL
        self.capabilities: frozenset[str] = frozenset()
        self.agent_name = ""
        self.paused = False
        self._emulator_factory = emulator_factory
        self._controller_factory = controller_factory
        self._rom_sha1 = rom_sha1
        self._worker: AgentWorker | None = None

    @property
    def running(self) -> bool:
        return self._worker is not None

    @property
    def rom_sha1(self) -> str:
        return self._rom_sha1

    def start(self, initial_state: bytes | None = None) -> None:
        if self._worker is not None:
            return
        controller = self._controller_factory(self.bus)
        # Interface commands the agent understands (core/commands.py).
        self.capabilities = frozenset(getattr(controller, "capabilities", frozenset()))
        self.agent_name = controller.name
        self.paused = False
        worker = AgentWorker(
            self.config,
            self.bus,
            self._emulator_factory,
            controller,
            initial_state=initial_state,
            savestates=self.savestates,
            mode=self.mode,
        )
        worker.frame_ready.connect(self.frame_ready)
        worker.state_ready.connect(self.state_ready)
        worker.world_map_ready.connect(self.world_map_ready)
        worker.failed.connect(self.failed)
        worker.finished.connect(self._on_finished)
        self._worker = worker
        worker.start()
        self.running_changed.emit(True)
        logger.info("Session started (agent: %s)", controller.name)

    def stop(self, wait: bool = True) -> None:
        if self._worker is None:
            return
        self._worker.send(Stop())
        if wait:
            self._worker.wait()
            self._on_finished()

    def pause(self) -> None:
        self._send(Pause())
        self.paused = True

    def resume(self) -> None:
        self._send(Resume())
        self.paused = False

    def set_speed(self, speed: int) -> None:
        self._send(SetSpeed(speed))

    def set_mode(self, mode: Mode) -> None:
        self.mode = mode
        self._send(SetMode(mode))

    def set_buttons(self, buttons: frozenset[Button]) -> None:
        self._send(SetButtons(buttons))

    def save_state(self, name: str, description: str = "") -> None:
        self._send(SaveState(name, description))

    def load_state(self, state: bytes, name: str = "") -> None:
        self._send(LoadState(state, name))

    def send_to_controller(self, payload: object) -> None:
        """Command for the agent (for example a destination chosen on the map)."""
        self._send(ControllerCommand(payload))

    def shutdown(self) -> None:
        self.stop()
        self.bridge.close()

    def _send(self, command: object) -> None:
        if self._worker is not None:
            self._worker.send(command)  # type: ignore[arg-type]

    def _on_finished(self) -> None:
        worker, self._worker = self._worker, None
        if worker is None:
            return
        worker.wait()
        logger.info("Session finished: %s", worker.status)
        self.running_changed.emit(False)

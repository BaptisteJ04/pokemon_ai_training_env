"""Main window: game, map, agent status and logs, in two columns of two panels.

The window has no decision logic: it shows what the worker sends and passes the user's commands
to the `SessionController`.
"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QImage
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pokemon_ai.core.commands import NAVIGATE, Explore, Navigate
from pokemon_ai.core.config import AppConfig
from pokemon_ai.core.events import AgentEvent, EventType
from pokemon_ai.emulator.state_manager import SaveStateError, SaveStateManager
from pokemon_ai.game.models.game_state import GameState, PlayerState
from pokemon_ai.game.models.map import Position
from pokemon_ai.game.models.world_map import WorldMap
from pokemon_ai.runtime.loop import Mode
from pokemon_ai.ui.controllers.event_bridge import LogBridge
from pokemon_ai.ui.controllers.session_controller import SessionController
from pokemon_ai.ui.widgets.agent_status import AgentStatus
from pokemon_ai.ui.widgets.game_view import KEY_HELP, GameView
from pokemon_ai.ui.widgets.log_view import LogView
from pokemon_ai.ui.widgets.map_view import MapView

SPEEDS = (("x1", 1), ("x2", 2), ("x4", 4), ("Unlimited", 0))
SCALES = (2, 3, 4)
MODES = (("Manual", Mode.MANUAL), ("Autonomous", Mode.AUTONOMOUS))


def _group(title: str, widget: QWidget) -> QGroupBox:
    box = QGroupBox(title)
    layout = QVBoxLayout(box)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.addWidget(widget)
    return box


class MainWindow(QMainWindow):
    def __init__(
        self,
        config: AppConfig,
        session: SessionController,
        savestates: SaveStateManager | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Pokemon Autonomous Agent")
        self.config = config
        self.session = session
        self.savestates = savestates

        self.game_view = GameView(min(max(config.emulator.scale, SCALES[0]), SCALES[-1]))
        self.map_view = MapView()
        self.agent_status = AgentStatus()
        self.log_view = LogView(config.ui.log_max_rows)
        self._build_layout()
        self._build_toolbar()
        self.status_label = QLabel()
        self.statusBar().addPermanentWidget(self.status_label)
        self.statusBar().showMessage(f"Manual mode: click on the game. {KEY_HELP}")

        self.log_bridge = LogBridge(self)
        self.log_bridge.record_received.connect(self.log_view.add_log)
        self.log_bridge.install()

        session.frame_ready.connect(self.on_frame)
        session.state_ready.connect(self.on_state)
        session.world_map_ready.connect(self.on_world_map)
        session.event_received.connect(self.on_event)
        session.running_changed.connect(self.on_running_changed)
        session.failed.connect(self.on_failed)
        self.game_view.buttons_changed.connect(session.set_buttons)
        self.map_view.cell_activated.connect(self.navigate_to)
        self.agent_status.set_mode("Manual")
        self._frames_received: list[float] = []
        self.last_state: GameState | None = None
        self.on_running_changed(False)

    # --- Construction ---

    def _build_layout(self) -> None:
        left = QSplitter(Qt.Orientation.Vertical)
        left.addWidget(_group("Game View", self.game_view))
        left.addWidget(_group("Agent Status", self.agent_status))
        left.setStretchFactor(0, 3)
        left.setStretchFactor(1, 2)
        right = QSplitter(Qt.Orientation.Vertical)
        right.addWidget(_group("Map View", self.map_view))
        right.addWidget(_group("Logs and events", self.log_view))
        right.setStretchFactor(0, 3)
        right.setStretchFactor(1, 2)
        central = QSplitter(Qt.Orientation.Horizontal)
        central.addWidget(left)
        central.addWidget(right)
        central.setStretchFactor(0, 2)
        central.setStretchFactor(1, 3)
        self.setCentralWidget(central)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Control")
        toolbar.setObjectName("control")
        self.addToolBar(toolbar)
        self.start_action = toolbar.addAction("Start", self.start)
        self.stop_action = toolbar.addAction("Stop", self.session.stop)
        self.pause_action = toolbar.addAction("Pause")
        self.pause_action.setCheckable(True)
        self.pause_action.toggled.connect(self.set_paused)
        toolbar.addSeparator()
        toolbar.addWidget(QLabel(" Mode "))
        self.mode_box = QComboBox()
        for label, mode in MODES:
            self.mode_box.addItem(label, mode)
        self.mode_box.currentIndexChanged.connect(self._on_mode_selected)
        toolbar.addWidget(self.mode_box)
        toolbar.addWidget(QLabel(" Speed "))
        self.speed_box = QComboBox()
        for label, speed in SPEEDS:
            self.speed_box.addItem(label, speed)
        self.speed_box.setCurrentIndex(
            next((i for i, (_, s) in enumerate(SPEEDS) if s == self.config.emulator.speed), 0)
        )
        self.speed_box.currentIndexChanged.connect(
            lambda _: self.session.set_speed(self.speed_box.currentData())
        )
        toolbar.addWidget(self.speed_box)
        toolbar.addWidget(QLabel(" Zoom "))
        self.scale_box = QComboBox()
        for scale in SCALES:
            self.scale_box.addItem(f"x{scale}", scale)
        self.scale_box.setCurrentIndex(SCALES.index(self.game_view.scale))
        self.scale_box.currentIndexChanged.connect(
            lambda _: self.game_view.set_scale(self.scale_box.currentData())
        )
        toolbar.addWidget(self.scale_box)
        toolbar.addSeparator()
        self.explore_action = toolbar.addAction("Explore", self.explore)
        self.explore_action.setToolTip(
            "Autonomous mode: explore. Double-click on the map to choose a destination."
        )
        toolbar.addSeparator()
        self.save_action = toolbar.addAction("Save state", self.ask_save_state)
        self.load_action = toolbar.addAction("Load state", self.ask_load_state)

    # --- Commands ---

    def start(self, initial_state: bytes | None = None) -> None:
        self.pause_action.setChecked(False)
        self.session.mode = Mode(self.mode_box.currentData())
        self.session.start(initial_state)
        self.session.set_speed(self.speed_box.currentData())
        self.game_view.setFocus()

    def set_paused(self, paused: bool) -> None:
        if paused:
            self.session.pause()
        else:
            self.session.resume()
        self.pause_action.setText("Resume" if paused else "Pause")

    def set_mode(self, mode: Mode) -> None:
        self.mode_box.setCurrentIndex(next(i for i, (_, m) in enumerate(MODES) if m == mode))

    def _on_mode_selected(self, _index: int) -> None:
        mode = Mode(self.mode_box.currentData())  # Qt gives the value back as a string
        self.session.set_mode(mode)
        self.agent_status.set_mode(self.mode_box.currentText())
        if mode == Mode.MANUAL:
            self.game_view.setFocus()
            self.statusBar().showMessage(f"Manual mode: click on the game. {KEY_HELP}")
        else:
            self.statusBar().showMessage(
                "Autonomous mode: double-click on the map to choose a destination, "
                "'Explore' to go back to exploring"
            )

    def ask_save_state(self) -> None:
        name, accepted = QInputDialog.getText(self, "Save state", "Savestate name:")
        if accepted and name.strip():
            self.session.save_state(name.strip(), "Saved from the interface")

    def ask_load_state(self) -> None:
        names = [info.name for info in _safe_list(self.savestates)]
        if not names:
            QMessageBox.information(self, "Load state", "No savestate available.")
            return
        name, accepted = QInputDialog.getItem(self, "Load state", "Savestate:", names, 0, False)
        if accepted:
            self.load_named_state(name)

    def load_named_state(self, name: str) -> None:
        if self.savestates is None:
            return
        state = self.savestates.load(name, rom_sha1=self.session.rom_sha1 or None)
        if self.session.running:
            self.session.load_state(state, name)
        else:
            self.start(state)

    # --- Updates from the session ---

    def on_frame(self, image: QImage) -> None:
        self.game_view.set_frame(image)
        now = time.monotonic()
        self._frames_received = [t for t in self._frames_received if now - t < 1.0] + [now]

    def on_state(self, state: GameState) -> None:
        self.last_state = state
        self.agent_status.set_state(state)
        if isinstance(state.player, PlayerState):
            self.map_view.set_position(state.player.position)
        self._update_status()

    def on_world_map(self, world_map: WorldMap) -> None:
        self.map_view.set_world_map(world_map)

    def on_event(self, event: AgentEvent) -> None:
        self.log_view.add_event(event)
        payload = event.payload
        if event.event_type == EventType.SEARCH_COMPLETED and payload.get("success"):
            self.map_view.show_search(
                [Position(*p) for p in payload.get("path", [])],
                [Position(*p) for p in payload.get("expanded", [])],
                Position(*payload["destination"]) if "destination" in payload else None,
            )
        elif event.event_type == EventType.POSITION_CHANGED:
            self.map_view.add_traveled(Position(payload["map_id"], payload["x"], payload["y"]))
        elif event.event_type == EventType.GOAL_SELECTED:
            self.agent_status.on_goal_event(payload)

    def supports(self, capability: str) -> bool:
        """Does the current agent understand this command (`Agent.capabilities`)?"""
        if capability in getattr(self.session, "capabilities", frozenset()):
            return True
        name = getattr(self.session, "agent_name", "the agent")
        self.statusBar().showMessage(f"{name} does not handle this command")
        return False

    def navigate_to(self, target: Position) -> None:
        """Double-click on the map: the agent goes to this tile (autonomous mode)."""
        if not self.session.running or not self.supports(NAVIGATE):
            return
        self.set_mode(Mode.AUTONOMOUS)
        self.session.send_to_controller(Navigate(target))
        self.statusBar().showMessage(f"Destination: map {target.map_id} ({target.x}, {target.y})")

    def explore(self) -> None:
        if not self.supports(NAVIGATE):
            return
        self.set_mode(Mode.AUTONOMOUS)
        self.session.send_to_controller(Explore())

    def on_running_changed(self, running: bool) -> None:
        self.start_action.setEnabled(not running)
        for action in (self.stop_action, self.pause_action, self.save_action):
            action.setEnabled(running)
        capabilities = getattr(self.session, "capabilities", frozenset())
        self.explore_action.setEnabled(running and NAVIGATE in capabilities)
        if not running:
            self.pause_action.setChecked(False)
        self._update_status()

    def on_failed(self, message: str) -> None:
        self.statusBar().showMessage(f"Agent error: {message}")

    def _update_status(self) -> None:
        state = "running" if self.session.running else "stopped"
        frame = f"frame {self.last_state.frame}" if self.last_state is not None else ""
        fps = f"{len(self._frames_received)} img/s" if self.session.running else ""
        self.status_label.setText("  |  ".join(part for part in (state, frame, fps) if part))

    def closeEvent(self, event: QCloseEvent) -> None:
        self.session.shutdown()
        self.log_bridge.uninstall()
        super().closeEvent(event)


def _safe_list(manager: SaveStateManager | None):
    if manager is None:
        return []
    try:
        return manager.list()
    except (OSError, SaveStateError):
        return []

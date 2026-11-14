"""Session loop: commands, frame pacing and control modes.

The loop runs in the agent's thread. The interface talks to it through a command queue and only
receives copies (screen image) or immutable values (state, world map) through callbacks. The
speed only sets the pace of the emulation (x1 = 60 frames per second, 0 = unlimited). The agent's
computation does not depend on it, since the agent reasons in game frames, not in real time.
"""

from __future__ import annotations

import queue
import time
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np

from pokemon_ai.core.events import EventType
from pokemon_ai.emulator.controls import Button, InputStep
from pokemon_ai.env.session import Controller, GameSession
from pokemon_ai.game.models.game_state import GameState
from pokemon_ai.game.models.world_map import WorldMap

GAME_FPS = 60
MAX_BATCH_FRAMES = 16  # unlimited speed: frames emulated between two reads of the commands
PAUSE_POLL_SECONDS = 0.01
MAX_LAG_SECONDS = 0.1  # beyond this delay the pace restarts from now (no catching up in a burst)


class Mode(StrEnum):
    MANUAL = "MANUAL"
    AUTONOMOUS = "AUTONOMOUS"


@dataclass(frozen=True, slots=True)
class Pause:
    pass


@dataclass(frozen=True, slots=True)
class Resume:
    pass


@dataclass(frozen=True, slots=True)
class Stop:
    pass


@dataclass(frozen=True, slots=True)
class SetSpeed:
    speed: int  # multiplier of real time, 0 = unlimited


@dataclass(frozen=True, slots=True)
class SetMode:
    mode: Mode


@dataclass(frozen=True, slots=True)
class SetButtons:
    """Buttons held by the user (manual mode only)."""

    buttons: frozenset[Button]


@dataclass(frozen=True, slots=True)
class SaveState:
    name: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class LoadState:
    state: bytes = field(repr=False)
    name: str = ""


@dataclass(frozen=True, slots=True)
class ControllerCommand:
    """Command passed as is to the controller (if it has a `handle` method)."""

    payload: object


type Command = (
    Pause | Resume | Stop | SetSpeed | SetMode | SetButtons | SaveState | LoadState
    | ControllerCommand
)  # fmt: skip


@dataclass(slots=True)
class LoopCallbacks:
    on_frame: Callable[[np.ndarray], None] | None = None
    on_state: Callable[[GameState], None] | None = None
    on_world_map: Callable[[WorldMap], None] | None = None


class SessionLoop:
    def __init__(
        self,
        session: GameSession,
        controller: Controller,
        commands: queue.Queue[Command] | None = None,
        *,
        speed: int = 1,
        mode: Mode = Mode.MANUAL,
        frame_rate: int = 30,
        state_rate: int = 10,
        callbacks: LoopCallbacks | None = None,
        clock: Callable[[], float] = time.perf_counter,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.session = session
        self.controller = controller
        self.commands: queue.Queue[Command] = commands if commands is not None else queue.Queue()
        self.speed = speed
        self.mode = Mode(mode)
        self.paused = False
        self.running = False
        self.callbacks = callbacks or LoopCallbacks()
        self.frames_run = 0
        self._frame_period = 1 / frame_rate
        self._state_period = 1 / state_rate
        self._clock, self._sleep = clock, sleep
        self._held: frozenset[Button] = frozenset()
        self._plan: deque[frozenset[Button]] = deque()  # one entry per frame (autonomous mode)
        self._next_due = 0.0
        self._frame_due = float("-inf")  # next screen image to send
        self._state_due = float("-inf")  # next state and map update to send
        self._sent_state: GameState | None = None
        self._sent_map_version = -1

    def send(self, command: Command) -> None:
        """Thread-safe: can be called from the interface."""
        self.commands.put(command)

    def run(
        self, max_frames: int | None = None, after_step: Callable[[], str | None] | None = None
    ) -> str:
        """Run until `Stop` (or `max_frames` frames) and return the final status.

        `after_step`, called after each step, can stop the loop by returning a status.
        """
        self.running = True
        self.session.publish(
            EventType.AGENT_STARTED,
            mode=self.mode.value,
            speed=self.speed,
            controller=self.controller.name,
        )
        self.session.observe()
        self._send_updates(force=True)
        status = "error"
        try:
            while self.running:
                if max_frames is not None and self.frames_run >= max_frames:
                    status = "completed"
                    break
                self.run_once()
                stop = after_step() if after_step is not None else None
                if stop:
                    status = stop
                    break
            else:
                status = "stopped"
        finally:
            self.session.emulator.set_held_buttons(frozenset())
            self.session.publish(EventType.AGENT_STOPPED, status=status, frames=self.frames_run)
        return status

    def run_once(self) -> None:
        self._process_commands()
        if not self.running:
            return
        if self.paused:
            self._sleep(PAUSE_POLL_SECONDS)
            return
        if self.speed > 0:
            now = self._clock()
            if now < self._next_due:
                self._sleep(min(self._next_due - now, PAUSE_POLL_SECONDS))
                return
            if now - self._next_due > MAX_LAG_SECONDS:
                self._next_due = now
            self._next_due += 1 / (GAME_FPS * self.speed)
            limit = 1
        else:
            limit = MAX_BATCH_FRAMES

        buttons, frames = self._next_inputs(limit)
        self.session.advance(buttons, frames)
        self.frames_run += frames
        self._send_updates()

    # --- Inputs ---

    def _next_inputs(self, limit: int) -> tuple[frozenset[Button], int]:
        if self.mode == Mode.MANUAL:
            return self._held, limit
        if not self._plan:
            state = self.session.observe().state
            self._plan.extend(expand(self.controller.decide(state)) or [frozenset()])
        buttons, frames = self._plan.popleft(), 1
        while frames < limit and self._plan and self._plan[0] == buttons:
            self._plan.popleft()
            frames += 1
        return buttons, frames

    def _process_commands(self) -> None:
        while True:
            try:
                command = self.commands.get_nowait()
            except queue.Empty:
                return
            self._apply(command)

    def _apply(self, command: Command) -> None:
        session = self.session
        match command:
            case Pause() if not self.paused:
                self.paused = True
                session.emulator.set_held_buttons(frozenset())
                session.publish(EventType.AGENT_PAUSED, frame=session.emulator.frame_count)
            case Resume() if self.paused:
                self.paused = False
                self._next_due = self._clock()
                session.publish(EventType.AGENT_RESUMED, frame=session.emulator.frame_count)
            case Stop():
                self.running = False
            case SetSpeed(speed):
                if speed < 0:
                    raise ValueError("The speed cannot be negative")
                self.speed = speed
                self._next_due = self._clock()
            case SetMode(mode) if mode != self.mode:
                self.mode = Mode(mode)
                self._held = frozenset()
                self._plan.clear()
                session.emulator.set_held_buttons(frozenset())
                session.publish(EventType.MODE_CHANGED, mode=mode.value)
            case SetButtons(buttons):
                if self.mode == Mode.MANUAL:
                    self._held = buttons
            case SaveState(name, description):
                session.save_state(name, description)
            case LoadState(state, name):
                self._plan.clear()
                session.load_state(state, name)
                restart = getattr(self.controller, "restart", None)
                if restart is not None:
                    restart()  # another situation: a new episode for the agent
                self._send_updates(force=True)
            case ControllerCommand(payload):
                handler = getattr(self.controller, "handle", None)
                if handler is not None:
                    self._plan.clear()
                    handler(payload)
            case _:
                pass  # no effect in the current state (for example Pause while paused)

    # --- Updates for the interface ---

    def _send_updates(self, force: bool = False) -> None:
        now = self._clock()
        callbacks = self.callbacks
        if callbacks.on_frame and (force or _due(now, self._frame_due)):
            self._frame_due = _next_due(now, self._frame_due, self._frame_period)
            callbacks.on_frame(self.session.emulator.get_screenshot())
        if not (force or _due(now, self._state_due)):
            return
        self._state_due = _next_due(now, self._state_due, self._state_period)
        state = self.session.state
        if callbacks.on_state and state is not None and state is not self._sent_state:
            self._sent_state = state
            callbacks.on_state(state)
        if callbacks.on_world_map and self.session.map_version != self._sent_map_version:
            self._sent_map_version = self.session.map_version
            callbacks.on_world_map(self.session.world_map)


def _due(now: float, deadline: float) -> bool:
    return now + 1e-6 >= deadline  # small tolerance: frames fall right on the deadlines


def _next_due(now: float, deadline: float, period: float) -> float:
    """Regular deadlines. After a delay (pause, long computation) restart from now."""
    return deadline + period if now - deadline < period else now + period


def expand(steps: Iterable[InputStep]) -> list[frozenset[Button]]:
    """Input sequence -> held buttons, frame by frame."""
    frames: list[frozenset[Button]] = []
    for step in steps:
        if step.button is not None:
            frames.extend([frozenset({step.button})] * step.hold_frames)
        frames.extend([frozenset()] * step.wait_frames)
    return frames

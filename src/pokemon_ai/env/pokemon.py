"""Pokemon environment: `GameEnvironment` on top of the emulator.

It uses a `GameSession` (state reading filtered by the `KnowledgeBase`, events published on the
bus for the interface). `step` plays the action frame by frame and then observes, like a Gym
environment. The interface (`SessionLoop` + `AgentController`) gives the agent exactly the same
observations and results.
"""

from __future__ import annotations

import numpy as np

from pokemon_ai.core.event_bus import EventBus
from pokemon_ai.core.state import Observation
from pokemon_ai.emulator.base import GameEmulator
from pokemon_ai.emulator.controls import InputStep
from pokemon_ai.env.actions import AgentAction, as_inputs
from pokemon_ai.env.base import GameEnvironment, StepResult
from pokemon_ai.env.events import diff_events
from pokemon_ai.env.session import GameSession
from pokemon_ai.game.knowledge import KnowledgeBase
from pokemon_ai.game.models.game_state import GameState


class PokemonEnv(GameEnvironment):
    def __init__(
        self,
        emulator: GameEmulator,
        *,
        bus: EventBus | None = None,
        session: GameSession | None = None,
        rom_sha1: str = "",
        reveal_mode: str = "viewport",
        observation_interval: int = 8,
    ) -> None:
        self.session = session or GameSession(
            emulator,
            bus or EventBus(),
            rom_sha1=rom_sha1,
            reveal_mode=reveal_mode,
            observation_interval=observation_interval,
        )
        self._observation: Observation[GameState] | None = None

    @property
    def emulator(self) -> GameEmulator:
        return self.session.emulator

    @property
    def frame(self) -> int:
        return self.session.emulator.frame_count

    @property
    def knowledge(self) -> KnowledgeBase:
        return self.session.observer.knowledge

    def reset(
        self, start: bytes | None = None, knowledge: KnowledgeBase | None = None
    ) -> Observation[GameState]:
        state = start if start is not None else self.session.emulator.save_state()
        self.session.load_state(state, knowledge=knowledge)
        self._observation = self.session.observe()
        return self._observation

    def observe(self) -> Observation[GameState]:
        if self._observation is None:
            self._observation = self.session.observe()
        return self._observation

    def step(self, action: AgentAction) -> StepResult:
        previous = self.observe().state
        frames = self.play(as_inputs(action))
        self._observation = self.session.observe()
        return step_result(previous, self._observation, frames)

    def screen(self) -> np.ndarray:
        return self.session.emulator.get_screenshot()

    def save_state(self) -> bytes:
        return self.session.emulator.save_state()

    def load_state(self, state: bytes) -> Observation[GameState]:
        self.session.load_state(state, knowledge=self.knowledge)
        self._observation = self.session.observe()
        return self._observation

    def play(self, steps: list[InputStep]) -> int:
        """Play the inputs frame by frame (the state is read regularly). Returns the frames."""
        total = 0
        for step in steps:
            if step.button is not None and step.hold_frames:
                self.session.advance(frozenset({step.button}), step.hold_frames)
            if step.wait_frames:
                self.session.advance(frozenset(), step.wait_frames)
            total += step.total_frames
        return total


def step_result(
    previous: GameState | None, observation: Observation[GameState], frames: int
) -> StepResult:
    """Result of a step: new observation and the game events since the previous state."""
    return StepResult(observation, frames, diff_events(previous, observation.state))

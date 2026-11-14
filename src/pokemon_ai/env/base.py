"""Environment interface: everything an agent can do with the game, and nothing else.

An agent only needs this interface. The environment knows nothing about agents: it observes,
plays the actions it receives and reports what changed.

- `reset(start)`: restart from a savestate, with blank knowledge (or a given one);
- `observe()`: the state as a player sees it (`GameState`, filtered by the `KnowledgeBase`);
- `step(action)`: play an action (elementary or button sequence) and return the result;
- `screen()`: the screen image, for agents that want pixels;
- `save_state()` / `load_state()`: savestates (the knowledge is not part of them).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from pokemon_ai.core.state import Observation
from pokemon_ai.env.actions import AgentAction
from pokemon_ai.game.knowledge import KnowledgeBase
from pokemon_ai.game.models.game_state import GameState


@dataclass(frozen=True, slots=True)
class GameEvent:
    """Something a player would see change between two observations (see `env/events.py`)."""

    kind: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StepResult:
    observation: Observation[GameState]
    frames: int  # game frames played during this step
    events: tuple[GameEvent, ...] = ()

    @property
    def state(self) -> GameState:
        return self.observation.state


class GameEnvironment(ABC):
    @abstractmethod
    def reset(
        self, start: bytes | None = None, knowledge: KnowledgeBase | None = None
    ) -> Observation[GameState]:
        """Restart from the savestate `start` (None: the current emulator state).

        The knowledge starts blank unless `knowledge` is given.
        """

    @abstractmethod
    def observe(self) -> Observation[GameState]: ...

    @abstractmethod
    def step(self, action: AgentAction) -> StepResult: ...

    @abstractmethod
    def screen(self) -> np.ndarray: ...

    @abstractmethod
    def save_state(self) -> bytes: ...

    @abstractmethod
    def load_state(self, state: bytes) -> Observation[GameState]:
        """Load a savestate and keep the knowledge gained so far."""

    @property
    @abstractmethod
    def frame(self) -> int: ...

    @property
    @abstractmethod
    def knowledge(self) -> KnowledgeBase: ...

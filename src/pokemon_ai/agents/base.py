"""Base class of agents: the only contract between an agent and the platform.

To write an agent, subclass `Agent` and implement `act`. Everything else is optional:

    class MyAgent(Agent):
        name = "my_agent"

        def act(self, observation):          # observation.state is a GameState
            return Action.MOVE_UP             # or a sequence of InputStep

        def observe_result(self, result):    # StepResult: new observation and game events
            ...

        def save(self, directory): ...        # keep what was learned between runs
        def load(self, directory): ...

Then run `uv run pokemon-ai --agent my_package.my_module:MyAgent` (interface or `--headless`).

The agent gets an `AgentSetup` when it is created: the configuration (including its own section
`agents.<name>`), the event bus (to feed the interface), the game rules and its data folder.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Self

from pokemon_ai.core.config import AppConfig
from pokemon_ai.core.event_bus import EventBus
from pokemon_ai.core.events import AgentEvent, EventType
from pokemon_ai.core.state import Observation
from pokemon_ai.env.actions import AgentAction
from pokemon_ai.env.base import StepResult
from pokemon_ai.game.data.game_data import GameRules, default_rules
from pokemon_ai.game.models.game_state import GameState


@dataclass(slots=True)
class AgentSetup:
    config: AppConfig = field(default_factory=AppConfig)
    options: dict[str, Any] = field(default_factory=dict)  # section `agents.<name>`
    bus: EventBus | None = None
    rules: GameRules = field(default_factory=default_rules)
    data_dir: Path | None = None  # what the agent learns, kept between runs


class Agent(ABC):
    name: str = "agent"
    # Interface commands the agent understands (see `core/commands.py`).
    capabilities: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self.setup_info = AgentSetup()

    @classmethod
    def create(cls, setup: AgentSetup) -> Self:
        """Build the agent (called by the registry and the interface)."""
        agent = cls()
        agent.setup(setup)
        return agent

    def setup(self, setup: AgentSetup) -> None:
        self.setup_info = setup

    @property
    def options(self) -> dict[str, Any]:
        return self.setup_info.options

    def reset(self, observation: Observation[GameState]) -> None:
        """Start of an episode (new game or loaded savestate)."""

    @abstractmethod
    def act(self, observation: Observation[GameState]) -> AgentAction:
        """Next action: an elementary `Action` or a sequence of `InputStep`."""

    def observe_result(self, result: StepResult) -> None:
        """Result of the last action (useful to learn)."""

    def save(self, directory: Path) -> None:
        """Save what was learned (kept between runs)."""

    def load(self, directory: Path) -> None:
        """Load what was learned (nothing if the folder is empty)."""

    def handle(self, command: object) -> None:
        """Command from the interface (see `capabilities`). Ignored by default."""

    def publish(self, event_type: EventType, **payload: Any) -> None:
        bus = self.setup_info.bus
        if bus is not None:
            bus.publish(AgentEvent(event_type, payload))

    def publish_decision(self, action: AgentAction, reason: str = "", **values: Any) -> None:
        """Standard decision event, shown in the log."""
        label = action.value if hasattr(action, "value") else "inputs"
        self.publish(
            EventType.ACTION_SELECTED, action=label, reason=reason, agent=self.name, **values
        )

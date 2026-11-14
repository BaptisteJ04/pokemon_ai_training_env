"""Adapter between an `Agent` and the session loop (interface and headless mode).

The `SessionLoop` asks for inputs each time the previous ones have been played (`decide`).
The adapter turns that into the agent cycle: result of the previous step (`observe_result`),
then `act` on the new observation. The agent sees the same thing as in step-by-step mode
(`PokemonEnv.step`).
"""

from __future__ import annotations

from collections.abc import Sequence

from pokemon_ai.agents.base import Agent
from pokemon_ai.core.state import Observation
from pokemon_ai.emulator.controls import InputStep
from pokemon_ai.env.actions import as_inputs
from pokemon_ai.env.pokemon import step_result
from pokemon_ai.game.models.game_state import GameState


class AgentController:
    def __init__(self, agent: Agent) -> None:
        self.agent = agent
        self._previous: GameState | None = None
        self._started = False

    @property
    def name(self) -> str:
        return self.agent.name

    @property
    def capabilities(self) -> frozenset[str]:
        return self.agent.capabilities

    def restart(self) -> None:
        """New episode (a savestate was loaded): the agent starts again from `reset`."""
        self._previous, self._started = None, False

    def decide(self, state: GameState) -> Sequence[InputStep]:
        observation = Observation(state, 1.0, "memory", state.frame)
        if not self._started:
            self._started = True
            self.agent.reset(observation)
        elif self._previous is not None:
            frames = state.frame - self._previous.frame
            self.agent.observe_result(step_result(self._previous, observation, frames))
        self._previous = state
        return as_inputs(self.agent.act(observation))

    def handle(self, command: object) -> None:
        self.agent.handle(command)

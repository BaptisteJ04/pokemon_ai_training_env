"""Two minimal agents: they show the `Agent` contract and serve as references."""

from __future__ import annotations

import random

from pokemon_ai.agents.base import Agent, AgentSetup
from pokemon_ai.core.actions import Action
from pokemon_ai.core.state import Observation
from pokemon_ai.env.actions import AgentAction
from pokemon_ai.game.models.game_state import GameState

MOVES = (Action.MOVE_UP, Action.MOVE_DOWN, Action.MOVE_LEFT, Action.MOVE_RIGHT)


class IdleAgent(Agent):
    """Does nothing: the game keeps running."""

    name = "idle"

    def act(self, observation: Observation[GameState]) -> AgentAction:
        return Action.WAIT


class RandomAgent(Agent):
    """Random elementary actions.

    Options (`agents.random.*`): `seed` (default: `random_seed`) and `press_probability`
    (chance of pressing A or B instead of moving, default 0.15).
    """

    name = "random"

    def setup(self, setup: AgentSetup) -> None:
        super().setup(setup)
        seed = self.options.get("seed", setup.config.random_seed)
        self.random = random.Random(seed)
        self.press_probability = float(self.options.get("press_probability", 0.15))

    def act(self, observation: Observation[GameState]) -> AgentAction:
        if self.random.random() < self.press_probability:
            return self.random.choice((Action.PRESS_A, Action.PRESS_B))
        return self.random.choice(MOVES)

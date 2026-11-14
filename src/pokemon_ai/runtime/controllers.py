"""Create the controller of autonomous mode: the chosen agent, wrapped for the session loop."""

from __future__ import annotations

from pokemon_ai.agents.registry import create_agent
from pokemon_ai.core.config import AppConfig
from pokemon_ai.core.event_bus import EventBus
from pokemon_ai.runtime.agent_controller import AgentController


def make_controller(
    config: AppConfig, spec: str | None = None, bus: EventBus | None = None
) -> AgentController:
    return AgentController(create_agent(config, spec, bus))

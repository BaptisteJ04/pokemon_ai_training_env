"""Agent registry: a short name, a `package.module:Class` path, or a `file.py:Class` path
(an agent written outside this repository)."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

from pokemon_ai.agents.base import Agent, AgentSetup
from pokemon_ai.core.config import AppConfig
from pokemon_ai.core.event_bus import EventBus
from pokemon_ai.game.data.game_data import default_rules

BUILTIN = {
    "random": "pokemon_ai.agents.simple:RandomAgent",
    "idle": "pokemon_ai.agents.simple:IdleAgent",
}


class AgentError(ValueError):
    pass


def agent_class(spec: str) -> type[Agent]:
    """Agent class for a registry name, `package.module:Class` or `file.py:Class`."""
    spec = BUILTIN.get(spec, spec)
    module_name, separator, class_name = spec.rpartition(":")
    if not separator:
        names = ", ".join(BUILTIN)
        raise AgentError(
            f"Unknown agent: {spec} (choices: {names}, package.module:Class or file.py:Class)"
        )
    try:
        if module_name.endswith(".py"):
            module = _load_file(module_name)
        else:
            module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
    except (ImportError, AttributeError, OSError) as error:
        raise AgentError(f"Agent not found: {spec} ({error})") from None
    if not (isinstance(cls, type) and issubclass(cls, Agent)):
        raise AgentError(f"{spec} is not an Agent (pokemon_ai.agents.base.Agent)")
    return cls


def _load_file(path: str):
    """Import a module from a Python file."""
    file = Path(path).expanduser().resolve()
    if not file.exists():
        raise ImportError(f"file not found: {file}")
    name = f"pokemon_ai_agent_{file.stem}"
    if name in sys.modules:
        return sys.modules[name]
    module_spec = importlib.util.spec_from_file_location(name, file)
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[name] = module
    module_spec.loader.exec_module(module)
    return module


def make_setup(config: AppConfig, spec: str, bus: EventBus | None = None) -> AgentSetup:
    name = agent_class(spec).name  # the option section and data folder use the agent name
    return AgentSetup(
        config=config,
        options=dict(config.agents.get(name, {})),
        bus=bus,
        rules=default_rules(),
        data_dir=Path(config.run.data_dir) / name,
    )


def create_agent(config: AppConfig, spec: str | None = None, bus: EventBus | None = None) -> Agent:
    """Create the agent `spec` (default: `run.agent`) and reload what it learned before."""
    spec = spec or config.run.agent
    setup = make_setup(config, spec, bus)
    agent = agent_class(spec).create(setup)
    if setup.data_dir is not None and setup.data_dir.exists():
        agent.load(setup.data_dir)
    return agent

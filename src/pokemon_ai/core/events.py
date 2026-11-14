"""Structured events shared by the session, the agent and the interface."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    # Published by the session.
    GAME_STATE_UPDATED = "GAME_STATE_UPDATED"
    POSITION_CHANGED = "POSITION_CHANGED"
    MAP_DISCOVERED = "MAP_DISCOVERED"
    BATTLE_STARTED = "BATTLE_STARTED"
    BATTLE_ENDED = "BATTLE_ENDED"
    AGENT_STARTED = "AGENT_STARTED"
    AGENT_PAUSED = "AGENT_PAUSED"
    AGENT_RESUMED = "AGENT_RESUMED"
    AGENT_STOPPED = "AGENT_STOPPED"
    MODE_CHANGED = "MODE_CHANGED"
    STATE_SAVED = "STATE_SAVED"
    STATE_LOADED = "STATE_LOADED"
    # Optional events an agent can publish to show what it is doing.
    ACTION_SELECTED = "ACTION_SELECTED"
    GOAL_SELECTED = "GOAL_SELECTED"
    SEARCH_COMPLETED = "SEARCH_COMPLETED"  # drawn on the Map View (path and explored cells)


@dataclass(frozen=True, slots=True)
class AgentEvent:
    """Immutable message that can cross threads without sharing any state.

    The payload only holds plain data (JSON-friendly) so it can be displayed or stored.
    """

    event_type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

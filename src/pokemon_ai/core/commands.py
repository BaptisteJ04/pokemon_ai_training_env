"""Commands the interface can send to an agent (`Agent.handle`).

An agent handles the commands it understands and ignores the others. It lists them in
`Agent.capabilities`, which enables the matching buttons of the interface.
"""

from __future__ import annotations

from dataclasses import dataclass

from pokemon_ai.game.models.map import Position

NAVIGATE = "navigate"  # capability for the Navigate and Explore commands


@dataclass(frozen=True, slots=True)
class Navigate:
    """Go to a position (for example chosen on the Map View), then wait."""

    target: Position


@dataclass(frozen=True, slots=True)
class Explore:
    """Go back to exploring on its own (after `Navigate`)."""

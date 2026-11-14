"""The discovered world map: grids of visited maps, transitions and points of interest.

`WorldMap` is an immutable value built by the cartography (`game/cartography.py`). Transitions
are only known once they have been taken: nothing is deduced from game data.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pokemon_ai.game.models.map import Cell, Direction, MapGrid, Position


class TransitionKind(StrEnum):
    WARP = "WARP"  # door, stairs, mat: from one exact tile to another
    CONNECTION = "CONNECTION"  # leaving an outdoor map through its border to the next one
    OTHER = "OTHER"  # teleport, fainting, script: not a reusable path


@dataclass(frozen=True, slots=True)
class Transition:
    kind: TransitionKind
    source: Position  # start tile (the warp, or the border tile for a connection)
    destination: Position  # observed arrival tile
    direction: Direction | None = None  # exit direction (connection) or pushed direction (warp)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "source": _position_to_list(self.source),
            "destination": _position_to_list(self.destination),
            "direction": self.direction.name if self.direction is not None else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Transition:
        direction = data["direction"]
        return cls(
            kind=TransitionKind(data["kind"]),
            source=Position(*data["source"]),
            destination=Position(*data["destination"]),
            direction=Direction[direction] if direction is not None else None,
        )


class PoiKind(StrEnum):
    POKECENTER = "POKECENTER"  # entrance of a Pokemon Center (warp tile, outdoor side)
    MART = "MART"  # entrance of a shop
    GYM = "GYM"  # entrance of a gym
    NPC = "NPC"  # character (last seen position)
    ITEM = "ITEM"  # item on the ground (Poke Ball)
    OBJECT = "OBJECT"  # other still sprite (boulder, fossil, Pokedex on a table...)
    SIGN = "SIGN"  # sign
    FIXTURE = "FIXTURE"  # usable piece of scenery (PC, trash can, statue), without a sprite


@dataclass(frozen=True, slots=True)
class PointOfInterest:
    kind: PoiKind
    position: Position
    label: str = ""  # sprite (for example SPRITE_NURSE) or name of the map it serves
    frame: int = 0  # last observation
    sprite: int | None = None  # slot of the sprite on its map (NPCs, items)
    facing: Direction | None = None  # direction needed to interact (a PC: facing up)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "position": _position_to_list(self.position),
            "label": self.label,
            "frame": self.frame,
            "sprite": self.sprite,
            "facing": None if self.facing is None else self.facing.name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PointOfInterest:
        return cls(
            PoiKind(data["kind"]),
            Position(*data["position"]),
            data["label"],
            data["frame"],
            data["sprite"],
            None if data.get("facing") is None else Direction[data["facing"]],
        )


@dataclass(frozen=True)
class WorldMap:
    grids: Mapping[int, MapGrid] = field(default_factory=dict)
    transitions: tuple[Transition, ...] = ()
    pois: tuple[PointOfInterest, ...] = ()

    def grid(self, map_id: int) -> MapGrid | None:
        return self.grids.get(map_id)

    def accessible_cells(self, position: Position) -> frozenset[Cell]:
        """Known tiles reachable on foot from `position` without leaving the map."""
        grid = self.grids.get(position.map_id)
        if grid is None or not grid.in_bounds(position.x, position.y):
            return frozenset()
        reached, queue = {position.cell}, deque([position.cell])
        while queue:
            for _, target in grid.moves(*queue.popleft()):
                if target not in reached:
                    reached.add(target)
                    queue.append(target)
        return frozenset(reached)

    def frontier(self, map_id: int) -> frozenset[Cell]:
        grid = self.grids.get(map_id)
        return grid.frontier() if grid is not None else frozenset()

    def pois_of(self, kind: PoiKind, map_id: int | None = None) -> tuple[PointOfInterest, ...]:
        return tuple(
            poi
            for poi in self.pois
            if poi.kind == kind and (map_id is None or poi.position.map_id == map_id)
        )


def _position_to_list(position: Position) -> list[int]:
    return [position.map_id, position.x, position.y]

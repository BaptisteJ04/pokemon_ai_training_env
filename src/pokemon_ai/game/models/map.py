"""Positions, tile types and the grid of a map.

A `MapGrid` is immutable: the cartography builds a new version at each discovery. It only holds
what the agent has seen: tiles never observed are `UNKNOWN`. Coordinates are in tiles (x to the
right, y downwards), like the game's `wXCoord` and `wYCoord`.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import IntEnum

import numpy as np

type Cell = tuple[int, int]
type Move = tuple[int, int, Direction]  # from tile (x, y), in a direction


class Direction(IntEnum):
    """Values as stored by the game (facing direction of the player sprite)."""

    DOWN = 0
    UP = 4
    LEFT = 8
    RIGHT = 12

    @property
    def delta(self) -> Cell:
        return _DELTAS[self]

    def apply(self, x: int, y: int, steps: int = 1) -> Cell:
        dx, dy = self.delta
        return x + steps * dx, y + steps * dy


_DELTAS = {
    Direction.DOWN: (0, 1),
    Direction.UP: (0, -1),
    Direction.LEFT: (-1, 0),
    Direction.RIGHT: (1, 0),
}


@dataclass(frozen=True, slots=True)
class Position:
    map_id: int
    x: int
    y: int

    @property
    def cell(self) -> Cell:
        return self.x, self.y


class TileType(IntEnum):
    UNKNOWN = 0
    WALKABLE = 1
    BLOCKED = 2
    GRASS = 3  # walkable, with wild encounters
    WATER = 4  # only walkable by surfing
    BUILDING = 5  # reserved: the game does not tell a building wall from another obstacle
    TRANSITION = 6  # warp (door, stairs, exit mat)
    INTERACTIVE = 7  # sign: not walkable, readable by facing it
    LEDGE = 8  # ledge: not walkable, can be jumped in one direction only
    CUT_TREE = 9  # small tree: not walkable, removed with Cut (it grows back)


PASSABLE = frozenset({TileType.WALKABLE, TileType.GRASS, TileType.TRANSITION})


@dataclass(frozen=True, slots=True, eq=False)
class MapGrid:
    map_id: int
    name: str
    tileset: int
    tiles: np.ndarray  # (height, width) of TileType values, read-only
    jumps: frozenset[Move] = frozenset()  # ledge jumps: landing 2 tiles further
    blocked_moves: frozenset[Move] = frozenset()  # forbidden steps between two walkable tiles
    exits: frozenset[Move] = frozenset()  # exits through the border to a neighbouring map

    def __post_init__(self) -> None:
        if self.tiles.ndim != 2 or self.tiles.dtype != np.uint8:
            raise ValueError("tiles must be a 2D uint8 array")
        if self.tiles.flags.writeable:
            tiles = self.tiles.copy()
            tiles.flags.writeable = False
            object.__setattr__(self, "tiles", tiles)

    @classmethod
    def unknown(cls, map_id: int, name: str, tileset: int, width: int, height: int) -> MapGrid:
        return cls(map_id, name, tileset, np.zeros((height, width), dtype=np.uint8))

    @property
    def width(self) -> int:
        return self.tiles.shape[1]

    @property
    def height(self) -> int:
        return self.tiles.shape[0]

    @property
    def revealed(self) -> int:
        return int(np.count_nonzero(self.tiles))

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def tile(self, x: int, y: int) -> TileType:
        if not self.in_bounds(x, y):
            return TileType.UNKNOWN
        return TileType(int(self.tiles[y, x]))

    def is_passable(self, x: int, y: int) -> bool:
        return self.tile(x, y) in PASSABLE

    def moves(self, x: int, y: int) -> Iterator[tuple[Direction, Cell]]:
        """Possible steps from a known walkable tile: (direction, arrival tile).

        A ledge jump counts as one step: the game chains it automatically.
        """
        for direction in Direction:
            if (x, y, direction) in self.jumps:
                landing = direction.apply(x, y, 2)
                if self.is_passable(*landing):
                    yield direction, landing
                continue
            target = direction.apply(x, y)
            if self.is_passable(*target) and (x, y, direction) not in self.blocked_moves:
                yield direction, target

    def frontier(self) -> frozenset[Cell]:
        """Known walkable tiles next to an unknown tile of the map."""
        passable = np.isin(self.tiles, [int(t) for t in PASSABLE])
        unknown = self.tiles == TileType.UNKNOWN
        near_unknown = np.zeros_like(unknown)
        near_unknown[1:, :] |= unknown[:-1, :]
        near_unknown[:-1, :] |= unknown[1:, :]
        near_unknown[:, 1:] |= unknown[:, :-1]
        near_unknown[:, :-1] |= unknown[:, 1:]
        ys, xs = np.nonzero(passable & near_unknown)
        return frozenset(zip(xs.tolist(), ys.tolist(), strict=True))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MapGrid):
            return NotImplemented
        return (
            (self.map_id, self.name, self.tileset) == (other.map_id, other.name, other.tileset)
            and np.array_equal(self.tiles, other.tiles)
            and (self.jumps, self.blocked_moves, self.exits)
            == (other.jumps, other.blocked_moves, other.exits)
        )

    __hash__ = None  # type: ignore[assignment]

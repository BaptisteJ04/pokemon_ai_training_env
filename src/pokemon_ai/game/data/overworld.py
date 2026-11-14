"""Movement rules of the engine, extracted from the ROM (`assets/data/overworld.json`).

A map is a grid of blocks of 4x4 tiles, i.e. 2x2 map tiles. The engine only looks at one tile
per map tile: the lower-left one for collisions, the lower-right one for wild encounters
(`engine/battle/wild_encounters.asm`). These rules are usable by the agent: they describe the
physics of the game, not the content of the maps.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np

from pokemon_ai.game.data.game_data import DATA_DIR, _read_json
from pokemon_ai.game.models.map import Direction

OVERWORLD_TILESET = 0
SHIP_PORT_TILESET = 14
# Water tiles hard-coded in the engine (`CollisionCheckOnWater`, `TryDoWildEncounter`). Tile 32
# is not water in the Vermilion port tileset (S.S. Anne gangway).
WATER_TILE = 0x14
SHORE_TILES = (0x32, 0x48)
# Routines that check the player's facing, given by the entry argument: a PC is switched on from
# the front (from below), and the bench guy of a Pokemon Center is talked to from the side.
ORIENTED_FIXTURES = frozenset(
    {"OpenPokemonCenterPC", "BillsHousePC", "OpenRedsPC", "PrintBenchGuyText"}
)


@dataclass(frozen=True, slots=True, eq=False)
class TilesetInfo:
    id: int
    identifier: str
    blocks: np.ndarray  # (number of blocks, 4, 4): tile ids, read-only
    collision: frozenset[int]  # walkable tiles (lower-left corner of a map tile)
    counter_tiles: tuple[int, ...]  # counters: you talk to the NPCs placed behind them
    grass_tile: int | None
    water: bool  # the tileset has water (you can surf or fish there)


@dataclass(frozen=True, slots=True)
class Fixture:
    """Scenery the player can interact with (PC, trash can, statue...). It is visible on screen
    but is not a sprite: the game looks it up in a table when A is pressed."""

    map_id: int
    x: int
    y: int
    routine: str
    facing: Direction | None = None  # direction required to use it


class OverworldRules:
    def __init__(self, data: dict[str, Any]) -> None:
        self.meta: dict[str, Any] = data["meta"]
        blocksets = {
            name: np.frombuffer(bytes.fromhex(blocks), dtype=np.uint8).reshape(-1, 4, 4)
            for name, blocks in data["blocksets"].items()
        }
        self.tilesets: dict[int, TilesetInfo] = {}
        for entry in data["tilesets"]:
            self.tilesets[entry["id"]] = TilesetInfo(
                id=entry["id"],
                identifier=entry["identifier"],
                blocks=blocksets[entry["blockset"]],
                collision=frozenset(entry["collision"]),
                counter_tiles=tuple(entry["counter_tiles"]),
                grass_tile=entry["grass_tile"],
                water=entry["water"],
            )
        # (facing, tile under the player, ledge tile): a jump of 2 tiles.
        self.ledges: frozenset[tuple[int, int, int]] = frozenset(
            (facing, standing, ledge) for facing, standing, ledge in data["ledges"]
        )
        # Pairs of tiles you cannot walk between (height differences), in both directions. They
        # match the game loop `CheckForTilePairCollisions`, which sometimes reads the table with
        # an offset.
        self.blocked_pairs: dict[bool, dict[int, frozenset[tuple[int, int]]]] = {}
        for surfing, key in ((False, "land"), (True, "water")):
            by_tileset: dict[int, set[tuple[int, int]]] = {}
            for tileset, first, second in data["tile_pair_collisions"][key]:
                by_tileset.setdefault(tileset, set()).update({(first, second), (second, first)})
            self.blocked_pairs[surfing] = {t: frozenset(p) for t, p in by_tileset.items()}
        self.sprites: dict[int, str] = {s["id"]: s["identifier"] for s in data["sprites"]}
        fixtures: dict[int, list[Fixture]] = {}
        for entry in data.get("fixtures", ()):
            oriented = entry["routine"] in ORIENTED_FIXTURES
            facing = Direction(entry["argument"]) if oriented else None
            fixture = Fixture(entry["map"], entry["x"], entry["y"], entry["routine"], facing)
            fixtures.setdefault(fixture.map_id, []).append(fixture)
        self.fixtures: dict[int, tuple[Fixture, ...]] = {k: tuple(v) for k, v in fixtures.items()}

    @classmethod
    def load(cls, path: Path | None = None) -> OverworldRules:
        return cls(_read_json(path or DATA_DIR / "overworld.json"))


@cache
def default_overworld() -> OverworldRules:
    return OverworldRules.load()

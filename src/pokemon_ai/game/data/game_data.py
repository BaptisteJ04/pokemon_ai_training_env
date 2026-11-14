"""Typed access to the reference data in `assets/data`.

`GameRules` holds the engine rules (species, moves, types, items): agents may use them.
`GameCatalog` holds the map and event names: it is reserved to the state reading layer and the
`KnowledgeBase`, so the agent cannot list what it has not discovered yet.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[4] / "assets" / "data"


class GameDataError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class BaseStats:
    hp: int
    attack: int
    defense: int
    speed: int
    special: int


@dataclass(frozen=True, slots=True)
class SpeciesInfo:
    id: int  # internal index (the one stored in memory), not the Pokedex number
    dex: int
    identifier: str
    name: str
    base_stats: BaseStats
    types: tuple[int, int]
    catch_rate: int
    base_exp: int
    level1_moves: tuple[int, ...]
    growth_rate: str


@dataclass(frozen=True, slots=True)
class MoveInfo:
    id: int
    identifier: str
    name: str
    effect: int
    effect_name: str
    power: int
    type: int
    accuracy: int  # out of 255
    pp: int

    def max_pp(self, pp_ups: int) -> int:
        """Maximum PP after `pp_ups` PP Ups (each one adds 1/5 of the base PP)."""
        return self.pp + pp_ups * (self.pp // 5)


@dataclass(frozen=True, slots=True)
class ItemInfo:
    id: int
    identifier: str
    name: str
    price: int | None
    key_item: bool
    ball: bool
    move: int | None = None  # for TMs and HMs


@dataclass(frozen=True, slots=True)
class MapInfo:
    id: int
    identifier: str
    name: str
    width: int  # in blocks of 2x2 tiles
    height: int


class GameRules:
    def __init__(self, data: dict[str, Any]) -> None:
        self.meta: dict[str, Any] = data["meta"]
        self.type_names: dict[int, str] = {t["id"]: t["name"] for t in data["types"]}
        self.type_effectiveness: dict[tuple[int, int], float] = {
            (attacker, defender): multiplier / 10
            for attacker, defender, multiplier in data["type_chart"]
        }
        self.species: dict[int, SpeciesInfo] = {}
        for entry in data["species"]:
            info = SpeciesInfo(
                **{
                    **entry,
                    "base_stats": BaseStats(**entry["base_stats"]),
                    "types": tuple(entry["types"]),
                    "level1_moves": tuple(entry["level1_moves"]),
                }
            )
            self.species[info.id] = info
        # Type chart in ROM order (multiplier x 10): the engine applies it entry by entry,
        # rounding each time.
        self.type_chart: tuple[tuple[int, int, int], ...] = tuple(
            (attacker, defender, multiplier)
            for attacker, defender, multiplier in data["type_chart"]
        )
        self.moves: dict[int, MoveInfo] = {m["id"]: MoveInfo(**m) for m in data["moves"]}
        self.move_ids: dict[str, int] = {m.identifier: m.id for m in self.moves.values()}
        self.items: dict[int, ItemInfo] = {i["id"]: ItemInfo(**i) for i in data["items"]}
        self.type_ids: dict[str, int] = {t["identifier"]: t["id"] for t in data["types"]}

    @classmethod
    def load(cls, path: Path | None = None) -> GameRules:
        return cls(_read_json(path or DATA_DIR / "rules.json"))

    def effectiveness(self, move_type: int, defender_types: tuple[int, int]) -> float:
        """Type multiplier (both defender types are applied if they differ)."""
        multiplier = self.type_effectiveness.get((move_type, defender_types[0]), 1.0)
        if defender_types[1] != defender_types[0]:
            multiplier *= self.type_effectiveness.get((move_type, defender_types[1]), 1.0)
        return multiplier


class GameCatalog:
    def __init__(self, data: dict[str, Any]) -> None:
        self.meta: dict[str, Any] = data["meta"]
        self.maps: dict[int, MapInfo] = {m["id"]: MapInfo(**m) for m in data["maps"]}
        self.event_names: dict[int, str] = {index: name for name, index in data["events"].items()}

    @classmethod
    def load(cls, path: Path | None = None) -> GameCatalog:
        return cls(_read_json(path or DATA_DIR / "catalog.json"))

    def event_name(self, index: int) -> str:
        return self.event_names.get(index, f"EVENT_UNNAMED_{index:03X}")


@cache
def default_rules() -> GameRules:
    return GameRules.load()


@cache
def default_catalog() -> GameCatalog:
    return GameCatalog.load()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise GameDataError(
            f"{path} not found: the reference data must be extracted from the ROM first"
        )
    return json.loads(path.read_text(encoding="utf-8"))

"""The game state as the agent knows it.

Each section can be `Unavailable` if reading it failed or gave inconsistent data. Progress and
world only contain what the agent has discovered (see `game/knowledge.py`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from pokemon_ai.core.state import DataIssue, Maybe
from pokemon_ai.game.models.battle import BattleState
from pokemon_ai.game.models.interface import InterfaceState
from pokemon_ai.game.models.inventory import InventoryState
from pokemon_ai.game.models.map import Direction, MapGrid, Position
from pokemon_ai.game.models.pokemon import PokemonState
from pokemon_ai.game.models.world_map import WorldMap


class GameStatus(StrEnum):
    INTRO = "INTRO"  # title screen or intro: no game is running yet
    OVERWORLD = "OVERWORLD"  # outside battles (menus and dialogs: see GameState.interface)
    BATTLE = "BATTLE"


@dataclass(frozen=True, slots=True)
class PlayerState:
    name: str
    position: Position
    direction: Direction

    @property
    def current_map(self) -> int:
        return self.position.map_id


@dataclass(frozen=True, slots=True)
class ProgressState:
    badges: frozenset[int] = frozenset()
    defeated_trainers: frozenset[str] = frozenset()
    discovered_locations: frozenset[int] = frozenset()
    completed_events: frozenset[str] = frozenset()
    elite_four_progress: int = 0
    champion_defeated: bool = False
    pokedex_seen: frozenset[int] = frozenset()
    pokedex_owned: frozenset[int] = frozenset()


@dataclass(frozen=True, slots=True)
class WorldState:
    current_map: int | None
    current_map_name: str | None
    explored_maps: frozenset[int] = frozenset()
    world_map: WorldMap = field(default_factory=WorldMap)  # discovered grids, transitions, POIs

    @property
    def current_grid(self) -> MapGrid | None:
        return None if self.current_map is None else self.world_map.grid(self.current_map)


@dataclass(frozen=True, slots=True)
class GameState:
    game_status: GameStatus
    player: Maybe[PlayerState]
    party: Maybe[tuple[Maybe[PokemonState], ...]]
    inventory: Maybe[InventoryState]
    world: WorldState
    progress: ProgressState
    battle: Maybe[BattleState | None]
    frame: int
    issues: tuple[DataIssue, ...] = ()
    interface: InterfaceState = field(default_factory=InterfaceState)  # dialogs and menus

    @property
    def money(self) -> Maybe[int]:
        if isinstance(self.inventory, InventoryState):
            return self.inventory.money
        return self.inventory  # Unavailable

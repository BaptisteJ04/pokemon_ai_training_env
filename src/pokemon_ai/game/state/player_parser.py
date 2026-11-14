"""Reading the player state: name, position and facing."""

from __future__ import annotations

from pokemon_ai.game.data.charmap import decode, is_valid_name
from pokemon_ai.game.data.game_data import GameCatalog
from pokemon_ai.game.models.game_state import PlayerState
from pokemon_ai.game.models.map import Direction, Position
from pokemon_ai.game.state.common import check
from pokemon_ai.game.state.map_parser import parse_map
from pokemon_ai.game.state.memory_addresses import (
    CUR_MAP_HEIGHT,
    CUR_MAP_WIDTH,
    PLAYER_FACING,
    PLAYER_NAME,
    X_COORD,
    Y_COORD,
)
from pokemon_ai.game.state.memory_reader import MemorySnapshot


def game_started(snapshot: MemorySnapshot) -> bool:
    """True once the intro is over: the player is named and a map is loaded.

    The name is typed during the intro, before the first map is loaded: while the map
    dimensions are zero, the game has not started.
    """
    map_loaded = snapshot.u8(CUR_MAP_WIDTH) > 0 and snapshot.u8(CUR_MAP_HEIGHT) > 0
    return map_loaded and is_valid_name(snapshot.field(PLAYER_NAME))


def parse_player(snapshot: MemorySnapshot, catalog: GameCatalog) -> PlayerState:
    check(is_valid_name(snapshot.field(PLAYER_NAME)), "player name missing or invalid")
    current_map = parse_map(snapshot, catalog)
    x, y = snapshot.u8(X_COORD), snapshot.u8(Y_COORD)
    # Coordinates are in tiles; map dimensions are in blocks of 2x2 tiles.
    check(
        x < 2 * current_map.width and y < 2 * current_map.height,
        f"position ({x}, {y}) outside the map",
    )
    facing = snapshot.u8(PLAYER_FACING)
    check(facing in Direction._value2member_map_, f"unknown facing: {facing}")
    return PlayerState(
        name=decode(snapshot.field(PLAYER_NAME)),
        position=Position(current_map.id, x, y),
        direction=Direction(facing),
    )

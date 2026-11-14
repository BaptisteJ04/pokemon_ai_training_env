"""Identification and full reading of the current map.

`parse_map_view` rebuilds the tiles from `wOverworldMap` (the map blocks and their border) and
the tileset blockset, then applies the engine rules: the lower-left tile for collisions, the
lower-right tile for grass, ledges and blocking tile pairs. The `MapView` describes the whole
map, including what the player has not seen: it stays in the reading layer, and the cartography
only reveals the visible part.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from pokemon_ai.game.data.game_data import GameCatalog, MapInfo
from pokemon_ai.game.data.overworld import (
    OVERWORLD_TILESET,
    SHIP_PORT_TILESET,
    SHORE_TILES,
    WATER_TILE,
    OverworldRules,
    TilesetInfo,
)
from pokemon_ai.game.models.game_state import PlayerState
from pokemon_ai.game.models.map import Cell, Direction, Move, TileType
from pokemon_ai.game.state.common import check
from pokemon_ai.game.state.memory_addresses import (
    CUR_MAP,
    CUR_MAP_CONNECTIONS,
    CUR_MAP_HEIGHT,
    CUR_MAP_TILESET,
    CUR_MAP_WIDTH,
    MAX_SIGNS,
    MAX_WARPS,
    NUM_SIGNS,
    NUM_SPRITES,
    NUM_WARPS,
    OVERWORLD_MAP,
    SIGN_COORDS,
    SPRITE_DATA_SIZE,
    SPRITE_SLOTS,
    SPRITE_STATE_DATA_1,
    SPRITE_STATE_DATA_2,
    WARP_ENTRIES,
    WARPED_FROM_MAP,
    WARPED_FROM_WARP,
    Address,
)
from pokemon_ai.game.state.memory_reader import MemorySnapshot

MAP_BORDER_BLOCKS = 3
BORDER = 2 * MAP_BORDER_BLOCKS  # in tiles
# Visible window: 10x9 tiles, with the player on tile (4, 4) (screen tiles 8-9).
VIEW_LEFT, VIEW_RIGHT, VIEW_UP, VIEW_DOWN = 4, 5, 4, 4
SPRITE_HIDDEN = 0xFF
SPRITE_COORD_OFFSET = 4
CONNECTION_BITS = {Direction.UP: 3, Direction.DOWN: 2, Direction.LEFT: 1, Direction.RIGHT: 0}


def parse_map(snapshot: MemorySnapshot, catalog: GameCatalog) -> MapInfo:
    """Current map, with its dimensions checked against the catalog."""
    map_id = snapshot.u8(CUR_MAP)
    info = catalog.maps.get(map_id)
    check(info is not None, f"unknown map 0x{map_id:02X}")
    assert info is not None
    size = (snapshot.u8(CUR_MAP_WIDTH), snapshot.u8(CUR_MAP_HEIGHT))
    expected = (info.width, info.height)
    check(size == expected, f"dimensions {size} instead of {expected} for {info.identifier}")
    return info


@dataclass(frozen=True, slots=True)
class SpriteView:
    index: int  # slot of the sprite on the map (1 to 15)
    picture: int  # picture id (SPRITE_*)
    x: int
    y: int
    visible: bool  # shown: neither hidden by the game nor off screen


@dataclass(frozen=True, slots=True, eq=False)
class MapView:
    map_id: int
    tileset: int
    tiles: np.ndarray  # (height, width) of TileType values, the whole map
    jumps: frozenset[Move]
    blocked_moves: frozenset[Move]
    exits: frozenset[Move]
    warps: tuple[Cell, ...]  # in game order: the index is the one of `wWarpedFromWhichWarp`
    signs: tuple[Cell, ...]
    sprites: tuple[SpriteView, ...]
    viewport: tuple[int, int, int, int]  # x0, y0, x1, y1 (x1, y1 excluded), may overflow
    warped_from: tuple[int, int]  # (map, warp index) of the last warp taken

    def in_view(self, x: int, y: int) -> bool:
        x0, y0, x1, y1 = self.viewport
        return x0 <= x < x1 and y0 <= y < y1


def parse_map_view(
    snapshot: MemorySnapshot, info: MapInfo, player: PlayerState, rules: OverworldRules
) -> MapView:
    tileset = rules.tilesets.get(snapshot.u8(CUR_MAP_TILESET))
    check(tileset is not None, f"unknown tileset: {snapshot.u8(CUR_MAP_TILESET)}")
    assert tileset is not None
    stride, rows = info.width + 2 * MAP_BORDER_BLOCKS, info.height + 2 * MAP_BORDER_BLOCKS
    check(stride * rows <= OVERWORLD_MAP.size, f"map {info.identifier} is too big")
    blocks = np.frombuffer(snapshot.read(OVERWORLD_MAP.address, stride * rows), dtype=np.uint8)
    blocks = blocks.reshape(rows, stride)
    count = len(tileset.blocks)
    inside = blocks[MAP_BORDER_BLOCKS:-MAP_BORDER_BLOCKS, MAP_BORDER_BLOCKS:-MAP_BORDER_BLOCKS]
    check(int(inside.max()) < count, "block missing from the blockset")
    # The border receives a strip of the neighbouring map, numbered in that map's tileset
    # (Route 22 below Route 23, which uses the PLATEAU tileset): a block that does not exist in
    # the current tileset is replaced by block 0.
    if int(blocks.max()) >= count:
        blocks = np.where(blocks < count, blocks, 0).astype(np.uint8)

    lower_left, lower_right = cell_tiles(blocks, tileset)
    types = classify(lower_left, lower_right, tileset)
    jumps, ledges = find_jumps(lower_left, types, tileset, rules)
    types[ledges] = TileType.LEDGE
    blocked = find_blocked_moves(lower_left, types, tileset, rules)
    exits = find_exits(types, snapshot.u8(CUR_MAP_CONNECTIONS))

    inner = (slice(BORDER, BORDER + 2 * info.height), slice(BORDER, BORDER + 2 * info.width))
    tiles = types[inner].copy()
    warps = _coordinates(snapshot, WARP_ENTRIES.address, NUM_WARPS, MAX_WARPS, 4)
    signs = _coordinates(snapshot, SIGN_COORDS.address, NUM_SIGNS, MAX_SIGNS, 2)
    height, width = tiles.shape
    for cells, tile_type in ((warps, TileType.TRANSITION), (signs, TileType.INTERACTIVE)):
        for x, y in cells:
            if 0 <= x < width and 0 <= y < height:
                tiles[y, x] = tile_type
    tiles.flags.writeable = False

    x, y = player.position.x, player.position.y
    return MapView(
        map_id=info.id,
        tileset=tileset.id,
        tiles=tiles,
        jumps=_crop(jumps, width, height),
        blocked_moves=_crop(blocked, width, height),
        exits=_crop(exits, width, height),
        warps=warps,
        signs=signs,
        sprites=_sprites(snapshot),
        viewport=(x - VIEW_LEFT, y - VIEW_UP, x + VIEW_RIGHT + 1, y + VIEW_DOWN + 1),
        warped_from=(snapshot.u8(WARPED_FROM_MAP), snapshot.u8(WARPED_FROM_WARP)),
    )


def cell_tiles(blocks: np.ndarray, tileset: TilesetInfo) -> tuple[np.ndarray, np.ndarray]:
    """Lower-left and lower-right tiles of each map tile, for a grid of blocks."""
    rows, columns = blocks.shape
    tiles = tileset.blocks[blocks].transpose(0, 2, 1, 3).reshape(4 * rows, 4 * columns)
    return tiles[1::2, 0::2], tiles[1::2, 1::2]


# Tile of the small tree that Cut removes (engine/overworld/cut.asm: wTileInFrontOfPlayer, the
# lower-left tile of the faced tile), per tileset.
CUT_TREE_TILES = {0: 0x3D, 7: 0x50}  # OVERWORLD, GYM


def classify(lower_left: np.ndarray, lower_right: np.ndarray, tileset: TilesetInfo) -> np.ndarray:
    passable = np.isin(lower_left, list(tileset.collision))
    types = np.full(lower_left.shape, TileType.BLOCKED, dtype=np.uint8)
    tree = CUT_TREE_TILES.get(tileset.id)
    if tree is not None:
        types[lower_left == tree] = TileType.CUT_TREE
    if tileset.water:
        water_tiles = [WATER_TILE, *SHORE_TILES]
        if tileset.id == SHIP_PORT_TILESET:
            water_tiles.remove(SHORE_TILES[0])
        types[np.isin(lower_left, water_tiles)] = TileType.WATER
    types[passable] = TileType.WALKABLE
    if tileset.grass_tile is not None:
        types[passable & (lower_right == tileset.grass_tile)] = TileType.GRASS
    return types


def find_jumps(
    lower_left: np.ndarray, types: np.ndarray, tileset: TilesetInfo, rules: OverworldRules
) -> tuple[set[Move], np.ndarray]:
    """Ledge jumps (`HandleLedges`, only in the outdoor tileset) and the ledge tiles."""
    jumps: set[Move] = set()
    ledges = np.zeros(types.shape, dtype=bool)
    if tileset.id != OVERWORLD_TILESET:
        return jumps, ledges
    for facing, standing, ledge in rules.ledges:
        direction = Direction(facing)
        front = _shifted(lower_left, direction)
        sources = (lower_left == standing) & (front == ledge) & _passable(types)
        ys, xs = np.nonzero(sources)
        for y, x in zip(ys.tolist(), xs.tolist(), strict=True):
            jumps.add((x, y, direction))
            ledges[_front(y, x, direction)] = True
    return jumps, ledges


def find_blocked_moves(
    lower_left: np.ndarray, types: np.ndarray, tileset: TilesetInfo, rules: OverworldRules
) -> set[Move]:
    """Forbidden steps between two walkable tiles (height differences in caves and forests)."""
    pairs = rules.blocked_pairs[False].get(tileset.id)
    blocked: set[Move] = set()
    if not pairs:
        return blocked
    passable = _passable(types)
    for direction in Direction:
        front_tiles = _shifted(lower_left, direction)
        both = passable & _shifted(passable, direction)
        for standing, front in pairs:
            mask = both & (lower_left == standing) & (front_tiles == front)
            ys, xs = np.nonzero(mask)
            blocked.update((int(x), int(y), direction) for y, x in zip(ys, xs, strict=True))
    return blocked


def find_exits(types: np.ndarray, connections: int) -> set[Move]:
    """Border tiles leading to a neighbouring map: connection present, next tile walkable."""
    exits: set[Move] = set()
    passable = _passable(types)
    height, width = types.shape[0] - 2 * BORDER, types.shape[1] - 2 * BORDER
    for direction, bit in CONNECTION_BITS.items():
        if not connections >> bit & 1:
            continue
        mask = passable & _shifted(passable, direction)
        if direction == Direction.UP:
            cells = [(x, 0) for x in range(width)]
        elif direction == Direction.DOWN:
            cells = [(x, height - 1) for x in range(width)]
        elif direction == Direction.LEFT:
            cells = [(0, y) for y in range(height)]
        else:
            cells = [(width - 1, y) for y in range(height)]
        exits.update(
            (x + BORDER, y + BORDER, direction) for x, y in cells if mask[y + BORDER, x + BORDER]
        )
    return exits


def _passable(types: np.ndarray) -> np.ndarray:
    return np.isin(types, [TileType.WALKABLE, TileType.GRASS, TileType.TRANSITION])


def _shifted(grid: np.ndarray, direction: Direction) -> np.ndarray:
    """`result[y, x] = grid[y + dy, x + dx]`, the value of the neighbouring tile (0 outside)."""
    dx, dy = direction.delta
    result = np.zeros_like(grid)
    height, width = grid.shape
    result[max(0, -dy) : height - max(0, dy), max(0, -dx) : width - max(0, dx)] = grid[
        max(0, dy) : height - max(0, -dy), max(0, dx) : width - max(0, -dx)
    ]
    return result


def _front(y: int, x: int, direction: Direction) -> tuple[int, int]:
    dx, dy = direction.delta
    return y + dy, x + dx


def _crop(moves: set[Move], width: int, height: int) -> frozenset[Move]:
    """Coordinates with border -> map coordinates (sources outside the map are dropped)."""
    return frozenset(
        (x - BORDER, y - BORDER, d)
        for x, y, d in moves
        if 0 <= x - BORDER < width and 0 <= y - BORDER < height
    )


def _coordinates(
    snapshot: MemorySnapshot, address: int, count_field: Address, maximum: int, entry_size: int
) -> tuple[Cell, ...]:
    count = snapshot.u8(count_field)
    check(count <= maximum, f"{count} entries for {count_field.symbol} (max {maximum})")
    data = snapshot.read(address, entry_size * count)
    # The first two bytes of each entry are (y, x).
    return tuple((data[i + 1], data[i]) for i in range(0, len(data), entry_size))


def _sprites(snapshot: MemorySnapshot) -> tuple[SpriteView, ...]:
    count = snapshot.u8(NUM_SPRITES)
    check(count < SPRITE_SLOTS, f"{count} sprites on the map")
    sprites = []
    for index in range(1, count + 1):
        screen = snapshot.read(SPRITE_STATE_DATA_1.address + index * SPRITE_DATA_SIZE, 3)
        on_map = snapshot.read(SPRITE_STATE_DATA_2.address + index * SPRITE_DATA_SIZE, 6)
        picture = screen[0]
        sprites.append(
            SpriteView(
                index=index,
                picture=picture,
                x=on_map[5] - SPRITE_COORD_OFFSET,
                y=on_map[4] - SPRITE_COORD_OFFSET,
                visible=picture != 0 and screen[2] != SPRITE_HIDDEN,
            )
        )
    return tuple(sprites)

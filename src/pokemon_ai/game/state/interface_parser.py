"""State of the game interface: text, menus, waiting for a press, cutscenes.

Everything is read from the in-memory copy of the screen (`wTileMap`) and two control bytes:
- a down arrow at the bottom right of the text box: the game waits for A or B;
- a cursor arrow: a menu waits for a choice (the selected entry is the text to its right);
- `wJoyIgnore` not zero: the game ignores the joypad (cutscene, transition);
- `wWalkCounter` not zero: a step is in progress.
All of this is visible on screen, so the agent may use it.
"""

from __future__ import annotations

from pokemon_ai.game.models.interface import InterfaceState, MenuItem
from pokemon_ai.game.state.memory_addresses import (
    JOY_IGNORE,
    SCREEN_HEIGHT_TILES,
    SCREEN_WIDTH_TILES,
    TILE_MAP,
    WALK_COUNTER,
)
from pokemon_ai.game.state.memory_reader import MemorySnapshot
from pokemon_ai.game.state.screen_text import SCREEN_CHARS, screen_text

CURSOR = 0xED  # arrow: selected entry
INACTIVE_CURSOR = 0xEC  # hollow arrow: remembered selection of an inactive menu
WAIT_ARROW = 0xEE  # down arrow: press A or B to continue


def parse_interface(snapshot: MemorySnapshot) -> InterfaceState:
    tiles = snapshot.field(TILE_MAP)
    text = screen_text(snapshot)
    cursor: tuple[int, int] | None = None
    items: tuple[MenuItem, ...] = ()
    if CURSOR in tiles:
        row, column = divmod(tiles.index(CURSOR), SCREEN_WIDTH_TILES)
        cursor = (column, row)
        items = _menu_items(tiles, cursor)
    return InterfaceState(
        text=text.strip(),
        waiting_for_input=WAIT_ARROW in tiles[-2 * SCREEN_WIDTH_TILES :],
        cursor=cursor,
        menu_items=items,
        input_locked=snapshot.u8(JOY_IGNORE) != 0,
        walking=snapshot.u8(WALK_COUNTER) != 0,
    )


def _menu_items(tiles: bytes, cursor: tuple[int, int]) -> tuple[MenuItem, ...]:
    """Entries aligned with the cursor column: same column, text right after it.

    A tile of the cursor column is an entry if it is empty (space) or holds a cursor, and text
    follows it. Entries are one or two rows apart depending on the menu, so we keep every
    candidate row of the box that holds the cursor.
    """
    column, row = cursor
    top, bottom = _box_rows(tiles, column, row)
    items = []
    for line_row in range(top, bottom + 1):
        tile = tiles[line_row * SCREEN_WIDTH_TILES + column]
        if tile not in (CURSOR, INACTIVE_CURSOR, 0x7F):
            continue
        label = _text_after(tiles, line_row, column)
        if label:
            items.append(MenuItem(label, line_row, line_row == row))
    return tuple(items)


def _box_rows(tiles: bytes, column: int, row: int) -> tuple[int, int]:
    """Rows of the box (delimited by its borders) that holds the cursor."""
    top = row
    while top > 0 and tiles[(top - 1) * SCREEN_WIDTH_TILES + column] not in (0x79, 0x7A, 0x7B):
        top -= 1
    bottom = row
    while bottom < SCREEN_HEIGHT_TILES - 1 and tiles[
        (bottom + 1) * SCREEN_WIDTH_TILES + column
    ] not in (0x7D, 0x7A, 0x7E):
        bottom += 1
    return top, bottom


def _text_after(tiles: bytes, row: int, column: int) -> str:
    """Text to the right of `column`, up to the border of the box."""
    chars = []
    for tile in tiles[row * SCREEN_WIDTH_TILES + column + 1 : (row + 1) * SCREEN_WIDTH_TILES]:
        if tile == 0x7C:  # │
            break
        chars.append(SCREEN_CHARS.get(tile, " "))
    return "".join(chars).strip()

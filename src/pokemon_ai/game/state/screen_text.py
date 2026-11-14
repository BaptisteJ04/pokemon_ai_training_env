"""Text shown on screen, read from the in-memory copy of the tiles (`wTileMap`).

Dialog boxes and menus write character codes directly into the background tiles, so the screen
can be read without computer vision. Graphic tiles (scenery, sprites) become a space.
"""

from __future__ import annotations

from pokemon_ai.game.data.charmap import CHARMAP
from pokemon_ai.game.state.memory_addresses import (
    SCREEN_HEIGHT_TILES,
    SCREEN_WIDTH_TILES,
    TILE_MAP,
)
from pokemon_ai.game.state.memory_reader import MemorySnapshot

# Tiles 0x00-0x78 are also used for scenery, so we only keep the box borders and the colon.
# Some tiles stand for several characters ("'s", "PK"), so a line can be longer than 20.
SCREEN_CHARS = {code: char for code, char in CHARMAP.items() if code >= 0x79 or code == 0x6D}


def screen_lines(snapshot: MemorySnapshot) -> list[str]:
    tiles = snapshot.field(TILE_MAP)
    return [
        "".join(
            SCREEN_CHARS.get(tile, " ")
            for tile in tiles[row * SCREEN_WIDTH_TILES :][:SCREEN_WIDTH_TILES]
        )
        for row in range(SCREEN_HEIGHT_TILES)
    ]


def screen_text(snapshot: MemorySnapshot) -> str:
    return "\n".join(line.rstrip() for line in screen_lines(snapshot))

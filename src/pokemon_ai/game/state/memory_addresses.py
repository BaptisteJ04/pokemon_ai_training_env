"""Central table of the memory addresses of Pokemon Red (US).

Source: the pret/pokered symbols (branch `symbols`, commit bd77855a), checked against the ROM
with SHA-1 ea9bcae6... See docs/memory_mapping.md.
All addresses are in WRAM (0xC000-0xDFFF), so one snapshot is enough to read them.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Address:
    symbol: str  # pokered symbol name
    address: int
    size: int = 1
    description: str = ""


NAME_LENGTH = 11  # 10 characters + terminator
PARTY_LENGTH = 6
PARTY_MON_SIZE = 44
BATTLE_MON_SIZE = 29
BAG_CAPACITY = 20
PC_ITEM_CAPACITY = 50
SCREEN_WIDTH_TILES = 20
SCREEN_HEIGHT_TILES = 18
SPRITE_SLOTS = 16  # the player (slot 0) and up to 15 map sprites
SPRITE_DATA_SIZE = 16
MAX_WARPS = 32
MAX_SIGNS = 16

# Screen
TILE_MAP = Address("wTileMap", 0xC3A0, SCREEN_WIDTH_TILES * SCREEN_HEIGHT_TILES, "Screen tiles")
PLAYER_FACING = Address(
    "wSpritePlayerStateData1FacingDirection",
    0xC109,
    description="Player facing: 0 down, 4 up, 8 left, 12 right",
)

SPRITE_STATE_DATA_1 = Address(
    "wSpriteStateData1",
    0xC100,
    SPRITE_SLOTS * SPRITE_DATA_SIZE,
    "Sprites on screen: +0 picture (0 = none), +2 image index (FF = invisible)",
)
SPRITE_STATE_DATA_2 = Address(
    "wSpriteStateData2",
    0xC200,
    SPRITE_SLOTS * SPRITE_DATA_SIZE,
    "Sprites on the map: +4 y + 4, +5 x + 4 (in tiles)",
)
OVERWORLD_MAP = Address(
    "wOverworldMap",
    0xC6E8,
    1300,
    "Blocks of the current map, with a 3-block border (connections included)",
)

# Control
JOY_IGNORE = Address(
    "wJoyIgnore",
    0xCD6B,
    description="Buttons ignored by the game (not zero during cutscenes)",
)
WALK_COUNTER = Address(
    "wWalkCounter", 0xCFC5, description="Frames left in the current step (0 = standing still)"
)

# Battle
PLAYER_MON_NUMBER = Address("wPlayerMonNumber", 0xCC2F, description="Index in the team")
PLAYER_STAT_MODS = Address("wPlayerMonStatMods", 0xCD1A, 6, "Stat stages (7 = neutral)")
ENEMY_STAT_MODS = Address("wEnemyMonStatMods", 0xCD2E, 6, "Stat stages (7 = neutral)")
ENEMY_MON_NICK = Address("wEnemyMonNick", 0xCFDA, NAME_LENGTH)
ENEMY_MON = Address("wEnemyMon", 0xCFE5, BATTLE_MON_SIZE, "enemy battle_struct")
BATTLE_MON_NICK = Address("wBattleMonNick", 0xD009, NAME_LENGTH)
BATTLE_MON = Address("wBattleMon", 0xD014, BATTLE_MON_SIZE, "player battle_struct")
TRAINER_CLASS = Address("wTrainerClass", 0xD031)
IS_IN_BATTLE = Address("wIsInBattle", 0xD057, description="0 no, 1 wild, 2 trainer, FF lost")
CUR_OPPONENT = Address("wCurOpponent", 0xD059)
BATTLE_TYPE = Address("wBattleType", 0xD05A)
TRAINER_NO = Address("wTrainerNo", 0xD05D)
ENEMY_PARTY_COUNT = Address("wEnemyPartyCount", 0xD89C)

# Player and team
PLAYER_NAME = Address("wPlayerName", 0xD158, NAME_LENGTH)
PARTY_COUNT = Address("wPartyCount", 0xD163)
PARTY_SPECIES = Address("wPartySpecies", 0xD164, PARTY_LENGTH + 1, "List ended by FF")
PARTY_MONS = Address("wPartyMons", 0xD16B, PARTY_MON_SIZE * PARTY_LENGTH)
PARTY_MON_OT = Address("wPartyMonOT", 0xD273, NAME_LENGTH * PARTY_LENGTH)
PARTY_MON_NICKS = Address("wPartyMonNicks", 0xD2B5, NAME_LENGTH * PARTY_LENGTH)
POKEDEX_OWNED = Address("wPokedexOwned", 0xD2F7, 19, "Bitfield, bit 0 = number 1")
POKEDEX_SEEN = Address("wPokedexSeen", 0xD30A, 19, "Bitfield, bit 0 = number 1")
NUM_BAG_ITEMS = Address("wNumBagItems", 0xD31D)
BAG_ITEMS = Address("wBagItems", 0xD31E, 2 * BAG_CAPACITY + 1, "Pairs (id, quantity), FF")
PLAYER_MONEY = Address("wPlayerMoney", 0xD347, 3, "BCD big-endian")
RIVAL_NAME = Address("wRivalName", 0xD34A, NAME_LENGTH)
OBTAINED_BADGES = Address("wObtainedBadges", 0xD356, description="Bitfield, bit 0 = Boulder Badge")
PLAYER_ID = Address("wPlayerID", 0xD359, 2)

# Map
CUR_MAP = Address("wCurMap", 0xD35E)
Y_COORD = Address("wYCoord", 0xD361)
X_COORD = Address("wXCoord", 0xD362)
LAST_MAP = Address("wLastMap", 0xD365)
CUR_MAP_TILESET = Address("wCurMapTileset", 0xD367)
CUR_MAP_HEIGHT = Address("wCurMapHeight", 0xD368, description="In blocks of 2x2 tiles")
CUR_MAP_WIDTH = Address("wCurMapWidth", 0xD369, description="In blocks of 2x2 tiles")
CUR_MAP_CONNECTIONS = Address(
    "wCurMapConnections", 0xD370, description="Connections: bit 3 north, 2 south, 1 west, 0 east"
)
NUM_WARPS = Address("wNumberOfWarps", 0xD3AE)
WARP_ENTRIES = Address(
    "wWarpEntries", 0xD3AF, 4 * MAX_WARPS, "(y, x, destination warp, destination map)"
)
NUM_SIGNS = Address("wNumSigns", 0xD4B0)
SIGN_COORDS = Address("wSignCoords", 0xD4B1, 2 * MAX_SIGNS, "Signs: (y, x)")
NUM_SPRITES = Address("wNumSprites", 0xD4E1, description="Map sprites, without the player")
WARPED_FROM_WARP = Address("wWarpedFromWhichWarp", 0xD73B, description="Last warp taken")
WARPED_FROM_MAP = Address("wWarpedFromWhichMap", 0xD73C, description="Map of that warp")
NUM_BOX_ITEMS = Address("wNumBoxItems", 0xD53A, description="Items stored in the PC")
BOX_ITEMS = Address("wBoxItems", 0xD53B, 2 * PC_ITEM_CAPACITY + 1)

# Progress
EVENT_FLAGS = Address("wEventFlags", 0xD747, 0x140, "Event bitfield (2560 flags)")
PLAY_TIME_HOURS = Address("wPlayTimeHours", 0xDA41)
PLAY_TIME_MINUTES = Address("wPlayTimeMinutes", 0xDA43)
PLAY_TIME_SECONDS = Address("wPlayTimeSeconds", 0xDA44)

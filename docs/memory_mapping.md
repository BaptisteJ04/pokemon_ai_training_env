# Memory map: Pokemon Red (US)

**ROM:** Pokemon Red (USA, Europe), SHA-1 `ea9bcae617fdf159b045185467ae58b2e4a48b9a`
**Source of the addresses:** symbols of [pret/pokered](https://github.com/pret/pokered), branch `symbols`, commit `bd77855a`
**Code:** `src/pokemon_ai/game/state/memory_addresses.py` (the single source of truth)

## How the data is read

All addresses are in WRAM. The whole WRAM (8 KiB) is copied in one read, so all the values of one
observation come from the same frame, and the parsers work on that copy.

An inconsistent reading is **never** passed on: the affected section becomes
`Unavailable(reason)`. This applies to the whole team or to one Pokemon, to the player, to the
bag or to a fighter in battle.

## Addresses

| Symbol | Address | Size | Description |
|---|---|---|---|
| `wSpriteStateData1` | `0xC100` | 256 | 16 sprites on screen (0 = player): +0 picture (0 = none), +2 image index (FF = invisible) |
| `wSpritePlayerStateData1FacingDirection` | `0xC109` | 1 | Player facing: 0 down, 4 up, 8 left, 12 right |
| `wSpriteStateData2` | `0xC200` | 256 | 16 sprites on the map: +4 y + 4, +5 x + 4 (in tiles) |
| `wTileMap` | `0xC3A0` | 360 | Screen tiles, 20x18 (text can be read with the charmap) |
| `wOverworldMap` | `0xC6E8` | 1300 | Blocks of the current map, with a 3-block border (strips of neighbouring maps included) |
| `wPlayerMonNumber` | `0xCC2F` | 1 | Index in the team of the Pokemon in battle |
| `wPlayerMonStatMods` | `0xCD1A` | 6 | Stat stages Att/Def/Spe/Spc/Acc/Eva (7 = neutral) |
| `wEnemyMonStatMods` | `0xCD2E` | 6 | Same for the opponent |
| `wJoyIgnore` | `0xCD6B` | 1 | Buttons ignored (not zero during cutscenes) |
| `wWalkCounter` | `0xCFC5` | 1 | Frames left in the current step (0 = standing still) |
| `wEnemyMonNick` | `0xCFDA` | 11 | Name of the opposing Pokemon |
| `wEnemyMon` | `0xCFE5` | 29 | Enemy `battle_struct` |
| `wBattleMonNick` | `0xD009` | 11 | Name of the player's Pokemon in battle |
| `wBattleMon` | `0xD014` | 29 | Player `battle_struct` |
| `wTrainerClass` | `0xD031` | 1 | Class of the opposing trainer (25 = rival, first battle) |
| `wIsInBattle` | `0xD057` | 1 | 0 no, 1 wild, 2 trainer, FF lost |
| `wCurOpponent` | `0xD059` | 1 | Current opponent |
| `wBattleType` | `0xD05A` | 1 | Battle type (normal, Safari...) |
| `wTrainerNo` | `0xD05D` | 1 | Number of the trainer in its class |
| `wPlayerName` | `0xD158` | 11 | Player name, ended by 0x50 |
| `wPartyCount` | `0xD163` | 1 | Team size (0 to 6) |
| `wPartySpecies` | `0xD164` | 7 | Species of the team, list ended by FF |
| `wPartyMons` | `0xD16B` | 264 | 6 x `party_struct` of 44 bytes |
| `wPartyMonOT` | `0xD273` | 66 | Original trainers |
| `wPartyMonNicks` | `0xD2B5` | 66 | Nicknames |
| `wPokedexOwned` | `0xD2F7` | 19 | Bitfield, bit 0 = number 1 |
| `wPokedexSeen` | `0xD30A` | 19 | Bitfield, bit 0 = number 1 |
| `wNumBagItems` | `0xD31D` | 1 | Number of items in the bag (max 20) |
| `wBagItems` | `0xD31E` | 41 | Pairs (id, quantity), ended by FF |
| `wPlayerMoney` | `0xD347` | 3 | Money, big-endian BCD |
| `wRivalName` | `0xD34A` | 11 | Rival name |
| `wObtainedBadges` | `0xD356` | 1 | Bitfield, bit 0 = Boulder Badge |
| `wPlayerID` | `0xD359` | 2 | Trainer id |
| `wCurMap` | `0xD35E` | 1 | Current map (see `assets/data/catalog.json`) |
| `wYCoord` | `0xD361` | 1 | Row, in tiles |
| `wXCoord` | `0xD362` | 1 | Column, in tiles |
| `wLastMap` | `0xD365` | 1 | Last outdoor map |
| `wCurMapTileset` | `0xD367` | 1 | Tileset of the map |
| `wCurMapHeight` | `0xD368` | 1 | Height, in blocks of 2x2 tiles |
| `wCurMapWidth` | `0xD369` | 1 | Width, in blocks of 2x2 tiles |
| `wCurMapConnections` | `0xD370` | 1 | Connections: bit 3 north, 2 south, 1 west, 0 east |
| `wNumberOfWarps` | `0xD3AE` | 1 | Number of warps of the map (max 32) |
| `wWarpEntries` | `0xD3AF` | 128 | (y, x, destination warp, destination map); **the destination is never exposed** |
| `wNumSigns` | `0xD4B0` | 1 | Number of signs (max 16) |
| `wSignCoords` | `0xD4B1` | 32 | Signs: (y, x) |
| `wNumSprites` | `0xD4E1` | 1 | Map sprites, without the player (max 15) |
| `wNumBoxItems` | `0xD53A` | 1 | Items stored in the PC (max 50) |
| `wBoxItems` | `0xD53B` | 101 | Pairs (id, quantity), ended by FF |
| `wWarpedFromWhichWarp` | `0xD73B` | 1 | Index of the last warp taken, in its map |
| `wWarpedFromWhichMap` | `0xD73C` | 1 | Map of that warp |
| `wEventFlags` | `0xD747` | 320 | Bitfield of the 2560 event flags (**never exposed to the agent**) |
| `wEnemyPartyCount` | `0xD89C` | 1 | Size of the enemy team |
| `wPlayTimeHours` | `0xDA41` | 1 | Displayed play time (hours) |
| `wPlayTimeMinutes` | `0xDA43` | 1 | Displayed play time (minutes) |
| `wPlayTimeSeconds` | `0xDA44` | 1 | Displayed play time (seconds) |

## Structures

### `party_struct` (44 bytes)

| Offset | Size | Field | Format |
|---|---|---|---|
| 0 | 1 | Species | internal index (not the Pokedex number) |
| 1 | 2 | Current HP | big-endian |
| 3 | 1 | Level (box) | |
| 4 | 1 | Status | bits 0-2 sleep, 3 PSN, 4 BRN, 5 FRZ, 6 PAR |
| 5 | 2 | Types | type ids (`rules.json`) |
| 7 | 1 | Catch rate | |
| 8 | 4 | Moves | ids, 0 = empty slot (always at the end) |
| 12 | 2 | Original trainer id | |
| 14 | 3 | Experience | big-endian |
| 17 | 10 | Stat experience (HP, Att, Def, Spe, Spc) | 5 x 16 bits big-endian |
| 27 | 2 | DVs | Att/Def then Spe/Spc (4 bits each), HP DV derived |
| 29 | 4 | PP | bits 0-5 PP, bits 6-7 PP Ups |
| 33 | 1 | Level | |
| 34 | 10 | Stats (max HP, Att, Def, Spe, Spc) | 5 x 16 bits big-endian |

### `battle_struct` (29 bytes)

Same layout as `party_struct` up to the moves (offset 11). Then:

| Offset | Size | Field |
|---|---|---|
| 12 | 2 | DVs |
| 14 | 1 | Level |
| 15 | 10 | Stats |
| 25 | 4 | PP |

### Current map (`wOverworldMap`)

A map is a grid of blocks of 4x4 tiles, i.e. 2x2 map tiles. `wOverworldMap` holds the blocks of
the map surrounded by a border of 3 blocks, row by row, with a stride of `width + 6`. The border
holds the background block, or strips of the neighbouring maps when a connection exists. Blocks
become tiles through the blockset of the current tileset (`assets/data/overworld.json`,
extracted from the ROM).

For each map tile, the engine only looks at one tile:

| Rule | Tile tested | `pokered` source |
|---|---|---|
| Collision | lower-left corner (screen tile 8, 9 for the player) | `CheckTilePassable`, `*_Coll` lists |
| Tall grass | lower-right corner | `TryDoWildEncounter`, grass tile of the tileset |
| Water | lower-left corner: `14`, `48`, and `32` outside the Vermilion port | `CollisionCheckOnWater` |
| Ledge | tile under the player and tile in front, depending on the facing (outdoor tileset only) | `HandleLedges`, `LedgeTiles` |
| Height difference | forbidden pair (tile under the player, tile in front), in both directions | `TilePairCollisionsLand` |

The screen shows 10x9 map tiles with the player on tile (4, 4). By default the cartography only
reveals the tiles from x - 4 to x + 5 and from y - 4 to y + 4.

### Interface (dialogs, menus): `wTileMap`

Text boxes and menus write their characters into the screen tiles
(`game/state/interface_parser.py`):

| Tile | Meaning |
|---|---|
| `ED` (filled arrow) | cursor of an active menu; the selected entry is the text to its right |
| `EC` (hollow arrow) | remembered selection of an inactive menu |
| `EE` (down arrow) | bottom right of the box: the game waits for A or B |
| `79`-`7E` | box borders (they delimit the entries of a menu) |

The main battle menu is a 2x2 grid: FIGHT at (9, 14), PKMN at (15, 14), ITEM at (9, 16), RUN at
(15, 16).

## Pitfalls found

- **During the intro**, `wCurMap` already holds Red's bedroom, and the player name is typed before
  the map is loaded. A game only counts as started if the name is valid **and** the map has
  non-zero dimensions.
- **During a map change**, `wCurMap` is updated before the dimensions. Reading the player is then
  briefly `Unavailable` (an inconsistency is detected, which is intended).
- **At the start of a battle**, before the Pokemon is sent out, `wBattleMon` can hold stale data:
  that fighter is marked `Unavailable` without invalidating the whole battle.
- **`wIsInBattle = FF`** after a defeat: this is not a battle in progress.
- **Coordinates change at the end of a step** (`wWalkCounter` goes back to 0), so the window
  computed from the position never contains a tile that is not displayed yet.
- **`wDestinationWarpID` is rewritten by some scripts** (255 after the rival battle): the arrival
  tile of a warp is deduced from the observed position and the warps of the new map.
- **A sprite becomes visible a few frames after the step** that brings it on screen: the next
  observation picks it up.
- **`wWarpedFromWhichWarp` is not reset** by a connection passage: a warp is only kept if it is
  next to the last observed position.
- **The last blockset of a bank** has no end symbol: it is read up to the end of the bank
  (padding blocks that are never referenced).
- **B advances text** like A, but never restarts an interaction: A, pressed right after a box
  closes, would talk to the NPC again. The **last box** of a dialog does not show the down arrow.
- **During a cutscene, `wJoyIgnore` is not zero but the text still advances** with A or B.
- **After a map change**, the game ignores the joypad for a few dozen frames, then listens
  briefly: wait until the player keeps control for 48 frames in a row before moving.
- **A door triggers as soon as it is walked on; an exit mat only when pushing against a wall or
  the map border.** Pushing toward a walkable tile just walks.
- **B cancels an evolution:** answer A when the text talks about evolution.

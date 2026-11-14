"""Cartography: builds the `WorldMap` from successive observations.

Only the part of the map shown on screen is revealed (`viewport` mode, the default), or the
whole current map in `full_map_on_entry` mode. Warps and connections only become transitions once
they have been taken: the destination of a warp is never read from memory, it is seen on arrival.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

import numpy as np

from pokemon_ai.game.data.overworld import Fixture
from pokemon_ai.game.models.game_state import GameStatus, PlayerState
from pokemon_ai.game.models.map import PASSABLE, Cell, Direction, MapGrid, Move, Position
from pokemon_ai.game.models.world_map import (
    PoiKind,
    PointOfInterest,
    Transition,
    TransitionKind,
    WorldMap,
)
from pokemon_ai.game.state.map_parser import MapView, SpriteView
from pokemon_ai.game.state.reader import MemoryObservation

type RevealMode = Literal["viewport", "full_map_on_entry"]

MAX_TRANSIENT_READS = 4  # transient observations tolerated after a warp
BUILDING_TILESETS = {6: PoiKind.POKECENTER, 2: PoiKind.MART, 7: PoiKind.GYM}
SPRITE_POKE_BALL = 0x3D
PASSABLE_VALUES = frozenset(int(tile) for tile in PASSABLE)
FIRST_STILL_SPRITE = 0x3D  # sprites without a walking animation: items, boulders...


@dataclass(frozen=True, slots=True)
class CartographyUpdate:
    revealed_tiles: int = 0  # tiles discovered or changed
    new_transitions: tuple[Transition, ...] = ()
    new_pois: tuple[PointOfInterest, ...] = ()


class _GridBuilder:
    """Editable version of a `MapGrid`, frozen on demand (and only if it changed)."""

    def __init__(self, grid: MapGrid) -> None:
        self.map_id, self.name, self.tileset = grid.map_id, grid.name, grid.tileset
        self.tiles = grid.tiles.copy()
        self.moves = {
            "jumps": set(grid.jumps),
            "blocked_moves": set(grid.blocked_moves),
            "exits": set(grid.exits),
        }
        self._frozen: MapGrid | None = grid

    def touch(self) -> None:
        self._frozen = None

    def freeze(self) -> MapGrid:
        if self._frozen is None:
            self._frozen = MapGrid(
                self.map_id,
                self.name,
                self.tileset,
                self.tiles,
                jumps=frozenset(self.moves["jumps"]),
                blocked_moves=frozenset(self.moves["blocked_moves"]),
                exits=frozenset(self.moves["exits"]),
            )
        return self._frozen


class Cartographer:
    def __init__(
        self,
        reveal_mode: RevealMode = "viewport",
        world_map: WorldMap | None = None,
        sprite_names: Mapping[int, str] | None = None,
        fixtures: Mapping[int, tuple[Fixture, ...]] | None = None,
    ) -> None:
        self.reveal_mode = reveal_mode
        self._sprite_names = sprite_names or {}
        self._fixtures = fixtures or {}
        world_map = world_map or WorldMap()
        self._grids = {map_id: _GridBuilder(grid) for map_id, grid in world_map.grids.items()}
        self._transitions = dict.fromkeys(world_map.transitions)
        self._pois = {_poi_key(poi): poi for poi in world_map.pois}
        # Warp coordinates of each visited map, in game order. They identify the warp that was
        # taken, and are never exposed.
        self._warps: dict[int, tuple[Cell, ...]] = {}
        self._last: PlayerState | None = None
        self._transient = 0  # consecutive transient reads after a warp
        self._snapshot: WorldMap | None = world_map

    @property
    def world_map(self) -> WorldMap:
        if self._snapshot is None:
            self._snapshot = WorldMap(
                grids={map_id: builder.freeze() for map_id, builder in self._grids.items()},
                transitions=tuple(self._transitions),
                pois=tuple(self._pois.values()),
            )
        return self._snapshot

    def update(self, observation: MemoryObservation) -> CartographyUpdate:
        player, view = observation.player, observation.map_view
        if (
            observation.status != GameStatus.OVERWORLD
            or not isinstance(player, PlayerState)
            or not isinstance(view, MapView)
        ):
            return CartographyUpdate()
        last = self._last
        transition = None
        if last is not None and last.position.map_id != view.map_id:
            transition = self._detect_transition(last, player.position, view)
            if transition is None:
                # Transient read (new map, but the position, and sometimes the blocks, of the
                # old one): nothing is kept, neither passage nor tile. We try again at the next
                # observation, remembering where we came from.
                self._transient += 1
                return CartographyUpdate()
            self._transient = 0
        builder = self._grids.get(view.map_id)
        if builder is None:
            height, width = view.tiles.shape
            name = observation.map_name or f"MAP_{view.map_id:02X}"
            grid = MapGrid.unknown(view.map_id, name, view.tileset, width, height)
            builder = self._grids[view.map_id] = _GridBuilder(grid)
        self._warps[view.map_id] = view.warps

        revealed = self._reveal(builder, view)
        new_pois = self._update_sprites_and_signs(view, observation.frame)
        new_transitions: tuple[Transition, ...] = ()
        if transition is not None:
            if transition not in self._transitions:
                self._transitions[transition] = None
                new_transitions = (transition,)
            new_pois += self._building_pois(transition, observation.frame)
        self._last = player

        # Unchanged grids are reused: rebuilding the snapshot is cheap, and it must be done at
        # each observation to follow the NPCs.
        self._snapshot = None
        return CartographyUpdate(revealed, new_transitions, new_pois)

    # --- Revealing tiles ---

    def _reveal(self, builder: _GridBuilder, view: MapView) -> int:
        height, width = view.tiles.shape
        if self.reveal_mode == "full_map_on_entry":
            region = (slice(0, height), slice(0, width))
        else:
            x0, y0, x1, y1 = view.viewport
            region = (
                slice(max(0, y0), max(0, min(height, y1))),
                slice(max(0, x0), max(0, min(width, x1))),
            )
        before = builder.tiles[region].copy()
        builder.tiles[region] = view.tiles[region]
        changed = int(np.count_nonzero(before != builder.tiles[region]))

        observed = {
            "jumps": view.jumps,
            "blocked_moves": view.blocked_moves,
            "exits": view.exits,
        }
        for name, moves in observed.items():
            current = builder.moves[name]
            seen = self._seen_move
            stale = {move for move in current if seen(view, move) and move not in moves}
            fresh = {move for move in moves if seen(view, move)} - current
            current.difference_update(stale)
            current.update(fresh)
            changed += len(stale) + len(fresh)
        if changed:
            builder.touch()
        return changed

    def _seen_move(self, view: MapView, move: Move) -> bool:
        """A move is known if its start tile and its target tile have been seen."""
        if self.reveal_mode == "full_map_on_entry":
            return True
        x, y, direction = move
        return view.in_view(x, y) and view.in_view(*direction.apply(x, y))

    # --- Points of interest ---

    def _update_sprites_and_signs(self, view: MapView, frame: int) -> tuple[PointOfInterest, ...]:
        visible = {sprite.index: sprite for sprite in view.sprites if sprite.visible}
        visible = {i: s for i, s in visible.items() if view.in_view(s.x, s.y)}
        new: list[PointOfInterest] = []
        # A sprite no longer shown at its last known position is gone (item picked up, NPC
        # left): it is forgotten until it shows up again.
        for key, poi in list(self._pois.items()):
            if (
                poi.kind in _SPRITE_KINDS
                and poi.position.map_id == view.map_id
                and poi.sprite not in visible
                and view.in_view(poi.position.x, poi.position.y)
            ):
                del self._pois[key]
        for sprite in visible.values():
            poi = self._sprite_poi(view.map_id, sprite, frame)
            key = _poi_key(poi)
            if key not in self._pois:
                new.append(poi)
            self._pois[key] = poi
        for x, y in view.signs:
            if self.reveal_mode == "full_map_on_entry" or view.in_view(x, y):
                poi = PointOfInterest(PoiKind.SIGN, Position(view.map_id, x, y), frame=frame)
                if _poi_key(poi) not in self._pois:
                    self._pois[_poi_key(poi)] = poi
                    new.append(poi)
        for fixture in self._fixtures.get(view.map_id, ()):
            if self.reveal_mode == "full_map_on_entry" or view.in_view(fixture.x, fixture.y):
                position = Position(view.map_id, fixture.x, fixture.y)
                poi = PointOfInterest(
                    PoiKind.FIXTURE, position, fixture.routine, frame, facing=fixture.facing
                )
                if _poi_key(poi) not in self._pois:
                    self._pois[_poi_key(poi)] = poi
                    new.append(poi)
        return tuple(new)

    def _sprite_poi(self, map_id: int, sprite: SpriteView, frame: int) -> PointOfInterest:
        if sprite.picture == SPRITE_POKE_BALL:
            kind = PoiKind.ITEM
        elif sprite.picture >= FIRST_STILL_SPRITE:
            kind = PoiKind.OBJECT
        else:
            kind = PoiKind.NPC
        label = self._sprite_names.get(sprite.picture, f"SPRITE_{sprite.picture:02X}")
        position = Position(map_id, sprite.x, sprite.y)
        return PointOfInterest(kind, position, label, frame, sprite=sprite.index)

    def _building_pois(self, transition: Transition, frame: int) -> tuple[PointOfInterest, ...]:
        """Entrance of a Pokemon Center, shop or gym, on the outdoor side of the warp."""
        if transition.kind != TransitionKind.WARP:
            return ()
        source = self._grids[transition.source.map_id]
        destination = self._grids[transition.destination.map_id]
        for building, door, outside in (
            (destination, transition.source, source),
            (source, transition.destination, destination),
        ):
            kind = BUILDING_TILESETS.get(building.tileset)
            if kind is not None and outside.tileset not in BUILDING_TILESETS:
                poi = PointOfInterest(kind, door, building.name, frame)
                if _poi_key(poi) not in self._pois:
                    self._pois[_poi_key(poi)] = poi
                    return (poi,)
        return ()

    # --- Transitions ---

    def _detect_transition(
        self, last: PlayerState, current: Position, view: MapView
    ) -> Transition | None:
        """Identify the passage from one map to another between two observations.

        - warp: the game records the warp taken (`wWarpedFromWhichWarp`); it must be next to
          the last observed position;
        - connection: the player was at the border of the map and arrives at the opposite one;
        - otherwise: teleport, fainting or script (OTHER, not a reusable path).

        None: the observation is transient (arrival far from any destination warp).
        """
        source = last.position
        warped_map, warped_index = view.warped_from
        source_warps = self._warps.get(source.map_id, ())
        warp = None
        if warped_map == source.map_id and warped_index < len(source_warps):
            warp = source_warps[warped_index]
        edge = self._edge(last)
        if warp is not None and _distance(warp, source.cell) <= 1:
            return self._warp(Position(source.map_id, *warp), last, current, view)
        if edge is not None and _on_opposite_edge(edge, current, view):
            builder = self._grids[source.map_id]
            builder.moves["exits"].add((source.x, source.y, edge))
            builder.touch()
            return Transition(TransitionKind.CONNECTION, source, current, edge)
        if warp is not None:
            return self._warp(Position(source.map_id, *warp), last, current, view)
        return Transition(TransitionKind.OTHER, source, current)

    def _edge(self, last: PlayerState) -> Direction | None:
        grid = self._grids[last.position.map_id]
        x, y = last.position.cell
        height, width = grid.tiles.shape
        edges = [
            direction
            for direction, on_edge in (
                (Direction.UP, y == 0),
                (Direction.DOWN, y == height - 1),
                (Direction.LEFT, x == 0),
                (Direction.RIGHT, x == width - 1),
            )
            if on_edge
        ]
        if last.direction in edges:
            return last.direction
        return edges[0] if edges else None

    def _warp(
        self, source: Position, last: PlayerState, current: Position, view: MapView
    ) -> Transition | None:
        """The arrival is the warp tile next to the observed position: when leaving a building
        the game makes the player take an automatic step.

        A door triggers as soon as it is walked on; an exit mat only when pushing against a
        wall or the map border. If the player was seen on the warp, facing an obstacle, that is
        the direction to push; otherwise it stays unknown."""
        facing = None
        if last.position == source:
            x, y = last.direction.apply(source.x, source.y)
            height, width = self._grids[source.map_id].tiles.shape
            inside = 0 <= x < width and 0 <= y < height
            if not inside or self._grids[source.map_id].tiles[y, x] not in PASSABLE_VALUES:
                facing = last.direction
        nearest = min(view.warps, key=lambda warp: _distance(warp, current.cell), default=None)
        if nearest is not None and _distance(nearest, current.cell) <= 1:
            current = Position(current.map_id, *nearest)
        elif nearest is not None and self._transient < MAX_TRANSIENT_READS:
            # We always arrive on a warp or right next to it. Otherwise the position read is still
            # the one of the previous map (read while the map was loading).
            return None
        elif nearest is not None:
            current = Position(current.map_id, *nearest)  # still far: take the nearest warp
        return Transition(TransitionKind.WARP, source, current, facing)


_SPRITE_KINDS = frozenset({PoiKind.NPC, PoiKind.ITEM, PoiKind.OBJECT})


def _poi_key(poi: PointOfInterest) -> tuple[object, ...]:
    if poi.kind in _SPRITE_KINDS:
        return ("sprite", poi.position.map_id, poi.sprite)
    return (poi.kind, poi.position)


def _distance(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _on_opposite_edge(edge: Direction, current: Position, view: MapView) -> bool:
    height, width = view.tiles.shape
    return {
        Direction.UP: current.y == height - 1,
        Direction.DOWN: current.y == 0,
        Direction.LEFT: current.x == width - 1,
        Direction.RIGHT: current.x == 0,
    }[edge]

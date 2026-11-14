"""Full memory reading: assembles the parsers into a `MemoryObservation`.

A `MemoryObservation` holds raw data the agent must not see (the event flags). It never leaves
the `game` layer: the `KnowledgeBase` turns it into a `GameState`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from pokemon_ai.core.state import DataIssue, Maybe, Unavailable
from pokemon_ai.game.data.game_data import GameCatalog, GameRules
from pokemon_ai.game.data.overworld import OverworldRules, default_overworld
from pokemon_ai.game.models.battle import BattleState
from pokemon_ai.game.models.game_state import GameStatus, PlayerState
from pokemon_ai.game.models.interface import InterfaceState
from pokemon_ai.game.models.inventory import InventoryState
from pokemon_ai.game.state.battle_parser import LOST_BATTLE, parse_battle
from pokemon_ai.game.state.common import InconsistentDataError
from pokemon_ai.game.state.interface_parser import parse_interface
from pokemon_ai.game.state.inventory_parser import parse_inventory
from pokemon_ai.game.state.map_parser import MapView, parse_map, parse_map_view
from pokemon_ai.game.state.memory_addresses import (
    EVENT_FLAGS,
    IS_IN_BATTLE,
    OBTAINED_BADGES,
    POKEDEX_OWNED,
    POKEDEX_SEEN,
)
from pokemon_ai.game.state.memory_reader import MemorySnapshot, bits
from pokemon_ai.game.state.party_parser import PartySlots, parse_party
from pokemon_ai.game.state.player_parser import game_started, parse_player

NO_GAME = Unavailable("no game in progress")


@dataclass(frozen=True, slots=True)
class MemoryObservation:
    frame: int
    status: GameStatus
    player: Maybe[PlayerState]
    map_name: str | None
    party: Maybe[PartySlots]
    inventory: Maybe[InventoryState]
    battle: Maybe[BattleState | None]
    badges: frozenset[int]
    pokedex_seen: frozenset[int]
    pokedex_owned: frozenset[int]
    event_flags: frozenset[int]  # raw indices: only for the KnowledgeBase
    issues: tuple[DataIssue, ...]
    # The whole current map, outside battles: only for the cartography, which reveals just the
    # visible part. None in battle or outside a game.
    map_view: Maybe[MapView] | None = None
    interface: InterfaceState = field(default_factory=InterfaceState)  # dialogs, menus


def read_observation(
    snapshot: MemorySnapshot,
    rules: GameRules,
    catalog: GameCatalog,
    overworld: OverworldRules | None = None,
) -> MemoryObservation:
    if not game_started(snapshot):
        return MemoryObservation(
            snapshot.frame, GameStatus.INTRO, NO_GAME, None, NO_GAME, NO_GAME, NO_GAME,
            frozenset(), frozenset(), frozenset(), frozenset(), (),
            interface=parse_interface(snapshot),
        )  # fmt: skip

    issues: list[DataIssue] = []

    def guarded[T](section: str, parse: Callable[[], T]) -> Maybe[T]:
        try:
            return parse()
        except InconsistentDataError as error:
            issues.append(DataIssue(section, str(error)))
            return Unavailable(str(error))

    player = guarded("player", lambda: parse_player(snapshot, catalog))
    party = guarded("party", lambda: parse_party(snapshot, rules))
    if not isinstance(party, Unavailable):
        party, slot_issues = party
        issues.extend(DataIssue("party", issue) for issue in slot_issues)
    in_battle = snapshot.u8(IS_IN_BATTLE) not in (0, LOST_BATTLE)
    map_name = None
    map_view: Maybe[MapView] | None = None
    if isinstance(player, PlayerState):
        map_name = catalog.maps[player.position.map_id].name
        if not in_battle:
            map_view = guarded(
                "map",
                lambda: parse_map_view(
                    snapshot, parse_map(snapshot, catalog), player, overworld or default_overworld()
                ),
            )
    elif not in_battle:
        map_view = Unavailable("unreadable player")

    return MemoryObservation(
        frame=snapshot.frame,
        status=GameStatus.BATTLE if in_battle else GameStatus.OVERWORLD,
        player=player,
        map_name=map_name,
        party=party,
        inventory=guarded("inventory", lambda: parse_inventory(snapshot, rules)),
        battle=guarded("battle", lambda: parse_battle(snapshot, rules)),
        badges=frozenset(bits(snapshot.field(OBTAINED_BADGES))),
        pokedex_seen=frozenset(index + 1 for index in bits(snapshot.field(POKEDEX_SEEN))),
        pokedex_owned=frozenset(index + 1 for index in bits(snapshot.field(POKEDEX_OWNED))),
        event_flags=frozenset(bits(snapshot.field(EVENT_FLAGS))),
        issues=tuple(issues),
        map_view=map_view,
        interface=parse_interface(snapshot),
    )

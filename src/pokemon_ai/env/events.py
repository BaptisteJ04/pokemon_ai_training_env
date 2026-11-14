"""Game events, found by comparing two successive observations.

They only contain what a player sees change: a map discovered, a story event (already raised,
so already known), a badge, a key item, a captured Pokemon, a level up, a battle starting or
ending, a fully fainted team.
"""

from __future__ import annotations

from pokemon_ai.core.state import Unavailable
from pokemon_ai.env.base import GameEvent
from pokemon_ai.game.models.game_state import GameState, GameStatus
from pokemon_ai.game.queries import party

MAP_DISCOVERED = "map_discovered"
GAME_EVENT = "game_event"
BADGE = "badge"
KEY_ITEM = "key_item"
CAPTURE = "capture"
LEVEL_UP = "level_up"
BATTLE_STARTED = "battle_started"
BATTLE_ENDED = "battle_ended"
TEAM_FAINTED = "team_fainted"


def diff_events(previous: GameState | None, current: GameState) -> tuple[GameEvent, ...]:
    if previous is None:
        return ()
    events: list[GameEvent] = []

    grids = current.world.world_map.grids
    for map_id in sorted(current.world.explored_maps - previous.world.explored_maps):
        grid = grids.get(map_id)
        events.append(
            GameEvent(MAP_DISCOVERED, {"map_id": map_id, "name": grid.name if grid else None})
        )
    for name in sorted(current.progress.completed_events - previous.progress.completed_events):
        events.append(GameEvent(GAME_EVENT, {"name": name}))
    for badge in sorted(current.progress.badges - previous.progress.badges):
        events.append(GameEvent(BADGE, {"index": badge}))
    for item in sorted(set(_key_items(current)) - set(_key_items(previous))):
        events.append(GameEvent(KEY_ITEM, {"name": item}))
    for species in sorted(current.progress.pokedex_owned - previous.progress.pokedex_owned):
        events.append(GameEvent(CAPTURE, {"species": species}))

    old_team = party(previous)
    for slot, mon in enumerate(party(current)):
        if slot < len(old_team):
            old = old_team[slot]
            if mon.species_id == old.species_id and mon.level > old.level:
                data = {"slot": slot, "species": mon.species_name, "level": mon.level}
                events.append(GameEvent(LEVEL_UP, data))

    was_in_battle = previous.game_status == GameStatus.BATTLE
    is_in_battle = current.game_status == GameStatus.BATTLE
    if is_in_battle and not was_in_battle:
        events.append(GameEvent(BATTLE_STARTED, {}))
    elif was_in_battle and not is_in_battle:
        events.append(GameEvent(BATTLE_ENDED, {}))

    team = party(current)
    all_fainted = bool(team) and all(mon.current_hp == 0 for mon in team)
    if all_fainted and any(mon.current_hp for mon in old_team):
        events.append(GameEvent(TEAM_FAINTED, {}))
    return tuple(events)


def _key_items(state: GameState) -> tuple[str, ...]:
    inventory = state.inventory
    return () if isinstance(inventory, Unavailable) else inventory.key_items

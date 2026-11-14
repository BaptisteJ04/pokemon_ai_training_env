"""Knowledge firewall: what the agent has discovered, and nothing else.

The game memory holds everything (future event flags, maps never visited, where warps lead, the
opponent's moves and stats). The `KnowledgeBase` only keeps what was observed: the maps the
player has been in, the events that already happened, the discovered world map (tiles seen on
screen, transitions taken, points of interest spotted) and, in battle, what a player sees of the
opponent. The agent cannot list events that did not happen, nor learn the name of a flag before
it is raised.
"""

from __future__ import annotations

from dataclasses import dataclass

from pokemon_ai.game.battle_knowledge import BattleKnowledge
from pokemon_ai.game.cartography import Cartographer, RevealMode
from pokemon_ai.game.data.game_data import GameCatalog, GameRules, default_rules
from pokemon_ai.game.data.overworld import default_overworld
from pokemon_ai.game.models.battle import BattleState
from pokemon_ai.game.models.game_state import (
    GameState,
    GameStatus,
    PlayerState,
    ProgressState,
    WorldState,
)
from pokemon_ai.game.models.world_map import PointOfInterest, Transition, WorldMap
from pokemon_ai.game.state.reader import MemoryObservation

# Conditions for winning the game (they say nothing about how to get there).
ELITE_FOUR_EVENTS = (
    "EVENT_BEAT_LORELEIS_ROOM_TRAINER_0",
    "EVENT_BEAT_BRUNOS_ROOM_TRAINER_0",
    "EVENT_BEAT_AGATHAS_ROOM_TRAINER_0",
    "EVENT_BEAT_LANCES_ROOM_TRAINER_0",
)
CHAMPION_EVENT = "EVENT_BEAT_CHAMPION_RIVAL"
TRAINER_EVENT_PREFIX = "EVENT_BEAT_"


@dataclass(frozen=True, slots=True)
class KnowledgeUpdate:
    new_maps: tuple[int, ...] = ()
    new_events: tuple[str, ...] = ()
    revealed_tiles: int = 0
    new_transitions: tuple[Transition, ...] = ()
    new_pois: tuple[PointOfInterest, ...] = ()


class KnowledgeBase:
    def __init__(
        self,
        catalog: GameCatalog,
        reveal_mode: RevealMode = "viewport",
        world_map: WorldMap | None = None,
        rules: GameRules | None = None,
    ) -> None:
        self._catalog = catalog
        self._explored_maps: dict[int, int] = {}  # map -> frame of the first visit
        self._completed_events: dict[str, int] = {}  # event -> frame it was first seen
        overworld = default_overworld()
        self._cartographer = Cartographer(
            reveal_mode, world_map, overworld.sprites, overworld.fixtures
        )
        self._battle = BattleKnowledge(rules or default_rules())
        if world_map is not None:
            self._explored_maps.update(dict.fromkeys(world_map.grids, 0))

    @property
    def explored_maps(self) -> frozenset[int]:
        return frozenset(self._explored_maps)

    @property
    def completed_events(self) -> frozenset[str]:
        return frozenset(self._completed_events)

    @property
    def world_map(self) -> WorldMap:
        return self._cartographer.world_map

    def update(self, observation: MemoryObservation) -> KnowledgeUpdate:
        if observation.status == GameStatus.INTRO:
            return KnowledgeUpdate()
        new_maps = []
        if isinstance(observation.player, PlayerState):
            map_id = observation.player.position.map_id
            if map_id not in self._explored_maps:
                self._explored_maps[map_id] = observation.frame
                new_maps.append(map_id)
        new_events = []
        for index in sorted(observation.event_flags):
            name = self._catalog.event_name(index)
            if name not in self._completed_events:
                self._completed_events[name] = observation.frame
                new_events.append(name)
        mapped = self._cartographer.update(observation)
        self._battle.observe(observation)
        return KnowledgeUpdate(
            tuple(new_maps),
            tuple(new_events),
            mapped.revealed_tiles,
            mapped.new_transitions,
            mapped.new_pois,
        )

    def build_state(self, observation: MemoryObservation) -> GameState:
        """Build the state seen by the agent. Call `update` first, with the same observation."""
        events = self.completed_events
        progress = ProgressState(
            badges=observation.badges,
            defeated_trainers=frozenset(e for e in events if e.startswith(TRAINER_EVENT_PREFIX)),
            discovered_locations=self.explored_maps,
            completed_events=events,
            elite_four_progress=sum(event in events for event in ELITE_FOUR_EVENTS),
            champion_defeated=CHAMPION_EVENT in events,
            pokedex_seen=observation.pokedex_seen,
            pokedex_owned=observation.pokedex_owned,
        )
        player = observation.player
        current_map = player.position.map_id if isinstance(player, PlayerState) else None
        world = WorldState(
            current_map=current_map,
            current_map_name=observation.map_name,
            explored_maps=self.explored_maps,
            world_map=self.world_map,
        )
        return GameState(
            game_status=observation.status,
            player=player,
            party=observation.party,
            inventory=observation.inventory,
            world=world,
            progress=progress,
            battle=self._visible_battle(observation),
            frame=observation.frame,
            issues=observation.issues,
            interface=observation.interface,
        )

    def _visible_battle(self, observation: MemoryObservation):
        """The opponent as a player sees it (see `game/battle_knowledge.py`)."""
        battle = observation.battle
        return self._battle.visible(battle) if isinstance(battle, BattleState) else battle

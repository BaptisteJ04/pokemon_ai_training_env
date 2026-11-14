"""Game session: emulator, state reading and event publishing.

A session lives in a single thread (the agent's). It publishes events with simple data on the
bus, and exposes the state and the world map as immutable values that the interface can receive
without sharing any data.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, Protocol

from pokemon_ai.core.event_bus import EventBus
from pokemon_ai.core.events import AgentEvent, EventType
from pokemon_ai.core.state import Observation, Unavailable
from pokemon_ai.emulator.base import GameEmulator
from pokemon_ai.emulator.controls import Button, InputStep
from pokemon_ai.emulator.state_manager import SaveStateManager
from pokemon_ai.game.adapter import GameAdapter, PokemonRedAdapter
from pokemon_ai.game.knowledge import KnowledgeBase
from pokemon_ai.game.models.game_state import GameState, GameStatus, PlayerState
from pokemon_ai.game.models.world_map import WorldMap
from pokemon_ai.game.state.observer import GameObserver

logger = logging.getLogger(__name__)


class Controller(Protocol):
    """Whatever decides in autonomous mode: normally an agent (see `AgentController`)."""

    name: str

    def decide(self, state: GameState) -> Sequence[InputStep]:
        """Next inputs to play (an empty sequence waits one frame)."""
        ...


class GameSession:
    def __init__(
        self,
        emulator: GameEmulator,
        bus: EventBus,
        *,
        rom_sha1: str = "",
        reveal_mode: str = "viewport",
        observation_interval: int = 8,
        savestates: SaveStateManager | None = None,
        adapter: GameAdapter | None = None,
    ) -> None:
        self.adapter = adapter or PokemonRedAdapter()  # everything specific to the game
        self.emulator = emulator
        self.bus = bus
        self.rom_sha1 = rom_sha1
        self.observation_interval = observation_interval
        self.savestates = savestates
        self._reveal_mode = reveal_mode
        self.observer = self._new_observer()
        self.state: GameState | None = None
        self.map_version = 0  # incremented at each discovery (tiles, transitions, POIs)
        self._frames_since_observation = 0
        self._last_position: tuple[int, int, int] | None = None
        self._last_summary: dict[str, Any] | None = None
        self._in_battle = False

    @property
    def world_map(self) -> WorldMap:
        return self.observer.knowledge.world_map

    def advance(self, buttons: frozenset[Button] = frozenset(), frames: int = 1) -> None:
        """Run `frames` frames with `buttons` held, reading the state regularly."""
        self.emulator.set_held_buttons(buttons)
        self.emulator.advance(frames)
        self._frames_since_observation += frames
        if self._frames_since_observation >= self.observation_interval:
            self.observe()

    def observe(self) -> Observation[GameState]:
        observation = self.observer.observe()
        self._frames_since_observation = 0
        self.state = observation.state
        self._publish_changes(observation.state)
        return observation

    def publish(self, event_type: EventType, **payload: Any) -> None:
        self.bus.publish(AgentEvent(event_type, payload))

    def save_state(self, name: str, description: str = "") -> None:
        if self.savestates is None:
            raise RuntimeError("No savestate folder configured")
        self.savestates.save(
            name,
            self.emulator.save_state(),
            rom_sha1=self.rom_sha1,
            frame_count=self.emulator.frame_count,
            description=description,
        )
        self.publish(EventType.STATE_SAVED, name=name, frame=self.emulator.frame_count)

    def load_state(
        self, state: bytes, name: str = "", knowledge: KnowledgeBase | None = None
    ) -> None:
        """Load a savestate.

        By default the knowledge starts blank: the loaded game is another situation, and the
        agent has not seen its maps. Pass `knowledge` to keep what was discovered so far.
        """
        self.emulator.load_state(state)
        self.observer = (
            self._new_observer()
            if knowledge is None
            else self.adapter.observer(self.emulator, knowledge)
        )
        self._last_position, self._last_summary, self._in_battle = None, None, False
        self.map_version += 1
        self.publish(EventType.STATE_LOADED, name=name, frame=self.emulator.frame_count)
        self.observe()

    def _new_observer(self) -> GameObserver:
        knowledge = self.adapter.new_knowledge(self._reveal_mode)
        return self.adapter.observer(self.emulator, knowledge)

    def _publish_changes(self, state: GameState) -> None:
        update = self.observer.last_update
        if update.revealed_tiles or update.new_transitions or update.new_pois:
            self.map_version += 1
        for map_id in update.new_maps:
            grid = self.world_map.grid(map_id)
            self.publish(
                EventType.MAP_DISCOVERED,
                discovery="map",
                map_id=map_id,
                name=grid.name if grid is not None else state.world.current_map_name,
            )
        for transition in update.new_transitions:
            self.publish(EventType.MAP_DISCOVERED, discovery="transition", **transition.to_dict())
        for poi in update.new_pois:
            self.publish(EventType.MAP_DISCOVERED, discovery="poi", **poi.to_dict())

        player = state.player
        if isinstance(player, PlayerState):
            position = (player.position.map_id, player.position.x, player.position.y)
            if position != self._last_position:
                self._last_position = position
                self.publish(
                    EventType.POSITION_CHANGED,
                    map_id=position[0],
                    map_name=state.world.current_map_name,
                    x=position[1],
                    y=position[2],
                    direction=player.direction.name,
                    frame=state.frame,
                )

        in_battle = state.game_status == GameStatus.BATTLE
        if in_battle != self._in_battle:
            self._in_battle = in_battle
            if in_battle:
                self.publish(EventType.BATTLE_STARTED, **battle_summary(state))
            else:
                self.publish(EventType.BATTLE_ENDED, frame=state.frame)

        summary = summarize(state)
        if summary != self._last_summary:
            self._last_summary = summary
            self.publish(EventType.GAME_STATE_UPDATED, frame=state.frame, **summary)


def summarize(state: GameState) -> dict[str, Any]:
    """Summary of the state without position and time (published only when it changes)."""
    summary: dict[str, Any] = {"status": state.game_status.value}
    if not isinstance(state.party, Unavailable):
        summary["party"] = [
            None
            if isinstance(mon, Unavailable)
            else {
                "name": mon.nickname,
                "species": mon.species_name,
                "level": mon.level,
                "hp": mon.current_hp,
                "max_hp": mon.max_hp,
                "status": mon.status,
            }
            for mon in state.party
        ]
    if not isinstance(state.inventory, Unavailable):
        inventory = state.inventory
        summary["money"] = inventory.money
        summary["items"] = {**inventory.items, **inventory.pokeballs}
        summary["key_items"] = list(inventory.key_items)
    summary["badges"] = len(state.progress.badges)
    summary["issues"] = [f"{issue.field}: {issue.reason}" for issue in state.issues]
    return summary


def battle_summary(state: GameState) -> dict[str, Any]:
    battle = state.battle
    if battle is None or isinstance(battle, Unavailable):
        return {"frame": state.frame}
    enemy = battle.enemy
    return {
        "frame": state.frame,
        "kind": battle.kind.name,
        "enemy": None if isinstance(enemy, Unavailable) else enemy.species_name,
        "enemy_level": None if isinstance(enemy, Unavailable) else enemy.level,
    }

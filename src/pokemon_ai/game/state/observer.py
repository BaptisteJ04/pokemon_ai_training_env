"""Entry point of state reading: emulator -> `Observation[GameState]`."""

from __future__ import annotations

import logging

from pokemon_ai.core.state import DataIssue, Observation, Unavailable
from pokemon_ai.emulator.base import GameEmulator
from pokemon_ai.game.data.game_data import (
    GameCatalog,
    GameRules,
    default_catalog,
    default_rules,
)
from pokemon_ai.game.knowledge import KnowledgeBase, KnowledgeUpdate
from pokemon_ai.game.models.game_state import GameState, GameStatus
from pokemon_ai.game.state.memory_reader import MemorySnapshot
from pokemon_ai.game.state.reader import MemoryObservation, read_observation

logger = logging.getLogger(__name__)


class GameObserver:
    def __init__(
        self,
        emulator: GameEmulator,
        rules: GameRules | None = None,
        catalog: GameCatalog | None = None,
        knowledge: KnowledgeBase | None = None,
    ) -> None:
        self._emulator = emulator
        self.rules = rules or default_rules()
        self._catalog = catalog or default_catalog()
        self.knowledge = knowledge or KnowledgeBase(self._catalog)
        self.last_update = KnowledgeUpdate()
        self.last_snapshot: MemorySnapshot | None = None
        self._last_issues: frozenset[DataIssue] = frozenset()

    def observe(self) -> Observation[GameState]:
        snapshot = MemorySnapshot.capture(self._emulator)
        raw = read_observation(snapshot, self.rules, self._catalog)
        self.last_snapshot = snapshot
        # A persistent issue is only reported when it first appears.
        for issue in sorted(set(raw.issues) - self._last_issues, key=str):
            logger.warning("Inconsistent data (%s): %s", issue.field, issue.reason)
        self._last_issues = frozenset(raw.issues)
        self.last_update = self.knowledge.update(raw)
        return Observation(
            state=self.knowledge.build_state(raw),
            confidence=confidence(raw),
            source="memory",
            frame=raw.frame,
        )


def confidence(raw: MemoryObservation) -> float:
    """Share of readable sections. Outside a game (INTRO) nothing is expected: confidence 1."""
    if raw.status == GameStatus.INTRO:
        return 1.0
    sections: list[object] = [raw.player, raw.inventory, raw.battle]
    if raw.map_view is not None:
        sections.append(raw.map_view)
    sections.extend(raw.party if not isinstance(raw.party, Unavailable) else [raw.party])
    readable = sum(not isinstance(section, Unavailable) for section in sections)
    return readable / len(sections)

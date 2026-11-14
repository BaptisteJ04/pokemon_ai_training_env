"""Everything specific to one game, behind an interface.

The rest of the platform (environment, agents, interface) works with the common `GameState`
model. A `GameAdapter` says how to get it for one game: memory reading, catalog (map and event
names, only used to read the state) and engine rules (species, moves, types, items).

Pokemon Red (US) is the first implementation. Blue and Yellow share most of the engine (other
memory addresses and catalogs). Gold and Silver would need a new adapter with a different memory
reader.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pokemon_ai.emulator.base import GameEmulator
from pokemon_ai.game.data.game_data import GameCatalog, GameRules, default_catalog, default_rules
from pokemon_ai.game.knowledge import KnowledgeBase
from pokemon_ai.game.state.observer import GameObserver


class GameAdapter(ABC):
    name: str

    @abstractmethod
    def rules(self) -> GameRules: ...

    @abstractmethod
    def catalog(self) -> GameCatalog: ...

    @abstractmethod
    def new_knowledge(self, reveal_mode: str = "viewport") -> KnowledgeBase: ...

    @abstractmethod
    def observer(self, emulator: GameEmulator, knowledge: KnowledgeBase) -> GameObserver:
        """State reading (memory -> `GameState`, filtered by `knowledge`)."""


class PokemonRedAdapter(GameAdapter):
    name = "pokemon_red"

    def rules(self) -> GameRules:
        return default_rules()

    def catalog(self) -> GameCatalog:
        return default_catalog()

    def new_knowledge(self, reveal_mode: str = "viewport") -> KnowledgeBase:
        return KnowledgeBase(self.catalog(), reveal_mode, rules=self.rules())  # type: ignore[arg-type]

    def observer(self, emulator: GameEmulator, knowledge: KnowledgeBase) -> GameObserver:
        return GameObserver(emulator, self.rules(), self.catalog(), knowledge)


ADAPTERS: dict[str, type[GameAdapter]] = {"pokemon_red": PokemonRedAdapter}


def game_adapter(name: str = "pokemon_red") -> GameAdapter:
    try:
        return ADAPTERS[name]()
    except KeyError:
        raise ValueError(f"Unknown game: {name} (choices: {', '.join(ADAPTERS)})") from None

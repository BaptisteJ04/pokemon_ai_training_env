"""Simple reads of the state, shared by the game layer, the interface and agents."""

from __future__ import annotations

from pokemon_ai.core.state import Unavailable
from pokemon_ai.game.models.game_state import GameState
from pokemon_ai.game.models.pokemon import PokemonState

POTIONS = ("POTION", "SUPER_POTION", "HYPER_POTION", "MAX_POTION", "FULL_RESTORE")


def party(state: GameState) -> list[PokemonState]:
    """Readable Pokemon of the team (empty list if the team is unreadable)."""
    if isinstance(state.party, Unavailable):
        return []
    return [mon for mon in state.party if isinstance(mon, PokemonState)]

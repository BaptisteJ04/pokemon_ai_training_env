"""State of a battle in progress."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from pokemon_ai.core.state import Maybe
from pokemon_ai.game.models.move import MoveState
from pokemon_ai.game.models.pokemon import PokemonStats


class BattleKind(IntEnum):
    WILD = 1
    TRAINER = 2


@dataclass(frozen=True, slots=True)
class StatModifiers:
    """Stat stages, from -6 to +6."""

    attack: int = 0
    defense: int = 0
    speed: int = 0
    special: int = 0
    accuracy: int = 0
    evasion: int = 0


@dataclass(frozen=True, slots=True)
class BattlePokemon:
    species_id: int
    species_name: str
    nickname: str
    level: int
    current_hp: int
    max_hp: int
    status: str | None
    types: tuple[int, int]
    moves: tuple[MoveState, ...]
    stats: PokemonStats
    modifiers: StatModifiers
    sleep_turns: int = 0
    estimated: bool = False  # seen like a player sees it: estimated HP and stats, moves seen so far


@dataclass(frozen=True, slots=True)
class BattleState:
    kind: BattleKind
    player: Maybe[BattlePokemon]
    enemy: Maybe[BattlePokemon]
    player_party_index: int
    trainer_class: int | None = None
    trainer_number: int | None = None
    enemy_party_size: int | None = None
    enemy_moves_observed: int = 0  # enemy move announcements already seen (same species, level)

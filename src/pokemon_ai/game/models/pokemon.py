"""A Pokemon of the team."""

from __future__ import annotations

from dataclasses import dataclass

from pokemon_ai.game.models.move import MoveState

STATUS_NAMES = ("SLP", "PSN", "BRN", "FRZ", "PAR")


@dataclass(frozen=True, slots=True)
class PokemonStats:
    """Block of five Gen 1 values, used for stats, DVs and stat experience."""

    hp: int
    attack: int
    defense: int
    speed: int
    special: int


@dataclass(frozen=True, slots=True)
class PokemonState:
    species_id: int  # internal index of the game
    species_name: str
    nickname: str
    level: int
    current_hp: int
    max_hp: int
    experience: int
    status: str | None  # SLP, PSN, BRN, FRZ, PAR or None
    moves: tuple[MoveState, ...]
    stats: PokemonStats
    types: tuple[int, int]
    dvs: PokemonStats
    stat_exp: PokemonStats
    sleep_turns: int = 0

    @property
    def is_fainted(self) -> bool:
        return self.current_hp == 0

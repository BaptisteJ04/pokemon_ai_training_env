"""Helpers shared by the parsers: consistency checks, status, moves, stats."""

from __future__ import annotations

from pokemon_ai.game.data.game_data import GameRules, SpeciesInfo
from pokemon_ai.game.models.move import MoveState
from pokemon_ai.game.models.pokemon import STATUS_NAMES, PokemonStats
from pokemon_ai.game.state.memory_reader import u16

MAX_LEVEL = 100
MAX_EXPERIENCE = 1_250_000  # slow growth curve at level 100
MAX_STAT = 999


class InconsistentDataError(ValueError):
    """Data that was read but is inconsistent: it is marked unavailable, never passed on."""


def check(condition: bool, reason: str) -> None:
    if not condition:
        raise InconsistentDataError(reason)


def species(rules: GameRules, species_id: int) -> SpeciesInfo:
    info = rules.species.get(species_id)
    check(info is not None, f"unknown species 0x{species_id:02X}")
    assert info is not None
    return info


def parse_level(level: int) -> int:
    check(1 <= level <= MAX_LEVEL, f"level out of range: {level}")
    return level


def parse_status(byte: int) -> tuple[str | None, int]:
    """Gen 1 status byte: bits 0-2 = sleep turns, bits 3-6 = PSN, BRN, FRZ, PAR."""
    sleep_turns = byte & 0x07
    flags = [bit for bit in range(3, 7) if byte >> bit & 1]
    check(byte & 0x80 == 0, f"unknown status bit: 0x{byte:02X}")
    check(len(flags) + (sleep_turns > 0) <= 1, f"several statuses at once: 0x{byte:02X}")
    if sleep_turns:
        return STATUS_NAMES[0], sleep_turns
    if flags:
        return STATUS_NAMES[flags[0] - 2], 0
    return None, 0


def parse_moves(rules: GameRules, move_ids: bytes, pp_bytes: bytes) -> tuple[MoveState, ...]:
    """Non-empty moves in slot order. An empty slot can only come at the end."""
    moves = []
    seen_empty = False
    for move_id, pp_byte in zip(move_ids, pp_bytes, strict=True):
        if move_id == 0:
            seen_empty = True
            continue
        check(not seen_empty, "move after an empty slot")
        info = rules.moves.get(move_id)
        check(info is not None, f"unknown move {move_id}")
        assert info is not None
        pp, pp_ups = pp_byte & 0x3F, pp_byte >> 6
        max_pp = info.max_pp(pp_ups)
        check(pp <= max_pp, f"{info.identifier}: {pp} PP for a maximum of {max_pp}")
        moves.append(MoveState(move_id, info.name, pp, max_pp, pp_ups))
    return tuple(moves)


def parse_stats(data: bytes, offset: int) -> PokemonStats:
    """Five big-endian 16-bit values: max HP, Attack, Defense, Speed, Special."""
    values = [u16(data, offset + 2 * index) for index in range(5)]
    check(all(0 < value <= MAX_STAT for value in values), f"stats out of range: {values}")
    return PokemonStats(*values)


def parse_dvs(data: bytes, offset: int) -> PokemonStats:
    attack, defense = data[offset] >> 4, data[offset] & 0x0F
    speed, special = data[offset + 1] >> 4, data[offset + 1] & 0x0F
    hp = (attack & 1) << 3 | (defense & 1) << 2 | (speed & 1) << 1 | (special & 1)
    return PokemonStats(hp, attack, defense, speed, special)


def parse_hp(current: int, maximum: int) -> tuple[int, int]:
    check(0 < maximum <= MAX_STAT, f"max HP out of range: {maximum}")
    check(current <= maximum, f"HP {current} above the maximum {maximum}")
    return current, maximum


def check_types(info: SpeciesInfo, types: tuple[int, int]) -> tuple[int, int]:
    check(types == info.types, f"types {types} differ from those of {info.identifier}")
    return types

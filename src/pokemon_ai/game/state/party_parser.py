"""Reading the Pokemon team (44-byte `party_struct` per Pokemon)."""

from __future__ import annotations

from pokemon_ai.core.state import Maybe, Unavailable
from pokemon_ai.game.data.charmap import decode
from pokemon_ai.game.data.game_data import GameRules
from pokemon_ai.game.models.pokemon import PokemonState, PokemonStats
from pokemon_ai.game.state.common import (
    MAX_EXPERIENCE,
    InconsistentDataError,
    check,
    check_types,
    parse_dvs,
    parse_hp,
    parse_level,
    parse_moves,
    parse_stats,
    parse_status,
    species,
)
from pokemon_ai.game.state.memory_addresses import (
    NAME_LENGTH,
    PARTY_COUNT,
    PARTY_LENGTH,
    PARTY_MON_NICKS,
    PARTY_MON_SIZE,
    PARTY_MONS,
    PARTY_SPECIES,
)
from pokemon_ai.game.state.memory_reader import MemorySnapshot, u16, u24

PartySlots = tuple[Maybe[PokemonState], ...]


def parse_party(snapshot: MemorySnapshot, rules: GameRules) -> tuple[PartySlots, list[str]]:
    """Return the team slots and the issues found in each slot.

    Raises `InconsistentDataError` if the team itself is unreadable (size or species list).
    """
    count = snapshot.u8(PARTY_COUNT)
    check(count <= PARTY_LENGTH, f"team size out of range: {count}")
    species_list = snapshot.field(PARTY_SPECIES)
    check(species_list[count] == 0xFF, "team species list not ended by FF")

    structs = snapshot.field(PARTY_MONS)
    nicknames = snapshot.field(PARTY_MON_NICKS)
    slots: list[Maybe[PokemonState]] = []
    issues = []
    for index in range(count):
        try:
            mon = parse_party_mon(
                structs[index * PARTY_MON_SIZE :][:PARTY_MON_SIZE],
                nicknames[index * NAME_LENGTH :][:NAME_LENGTH],
                rules,
            )
            listed = species_list[index]
            check(
                mon.species_id == listed,
                f"species 0x{mon.species_id:02X} differs from list 0x{listed:02X}",
            )
            slots.append(mon)
        except InconsistentDataError as error:
            slots.append(Unavailable(str(error)))
            issues.append(f"party[{index}]: {error}")
    return tuple(slots), issues


def parse_party_mon(data: bytes, nickname: bytes, rules: GameRules) -> PokemonState:
    info = species(rules, data[0])
    current_hp, max_hp = parse_hp(u16(data, 1), u16(data, 34))
    status, sleep_turns = parse_status(data[4])
    experience = u24(data, 14)
    check(experience <= MAX_EXPERIENCE, f"experience out of range: {experience}")
    stats = parse_stats(data, 34)
    return PokemonState(
        species_id=info.id,
        species_name=info.name,
        nickname=decode(nickname),
        level=parse_level(data[33]),
        current_hp=current_hp,
        max_hp=max_hp,
        experience=experience,
        status=status,
        moves=parse_moves(rules, data[8:12], data[29:33]),
        stats=stats,
        types=check_types(info, (data[5], data[6])),
        dvs=parse_dvs(data, 27),
        stat_exp=PokemonStats(*(u16(data, 17 + 2 * index) for index in range(5))),
        sleep_turns=sleep_turns,
    )

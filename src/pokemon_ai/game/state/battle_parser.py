"""Reading the battle state (29-byte `battle_struct`)."""

from __future__ import annotations

from pokemon_ai.core.state import Maybe, Unavailable
from pokemon_ai.game.data.charmap import decode
from pokemon_ai.game.data.game_data import GameRules
from pokemon_ai.game.models.battle import BattleKind, BattlePokemon, BattleState, StatModifiers
from pokemon_ai.game.state.common import (
    InconsistentDataError,
    check,
    check_types,
    parse_hp,
    parse_level,
    parse_moves,
    parse_stats,
    parse_status,
    species,
)
from pokemon_ai.game.state.memory_addresses import (
    BATTLE_MON,
    BATTLE_MON_NICK,
    ENEMY_MON,
    ENEMY_MON_NICK,
    ENEMY_PARTY_COUNT,
    ENEMY_STAT_MODS,
    IS_IN_BATTLE,
    PARTY_LENGTH,
    PLAYER_MON_NUMBER,
    PLAYER_STAT_MODS,
    TRAINER_CLASS,
    TRAINER_NO,
    Address,
)
from pokemon_ai.game.state.memory_reader import MemorySnapshot, u16

NEUTRAL_MODIFIER = 7
LOST_BATTLE = 0xFF


def parse_battle(snapshot: MemorySnapshot, rules: GameRules) -> BattleState | None:
    """Return None outside battles. Each unreadable fighter is marked `Unavailable`."""
    in_battle = snapshot.u8(IS_IN_BATTLE)
    if in_battle in (0, LOST_BATTLE):
        return None
    check(in_battle in (BattleKind.WILD, BattleKind.TRAINER), f"wIsInBattle = 0x{in_battle:02X}")
    kind = BattleKind(in_battle)

    player_index = snapshot.u8(PLAYER_MON_NUMBER)
    check(player_index < PARTY_LENGTH, f"active Pokemon index out of range: {player_index}")
    trainer = kind == BattleKind.TRAINER
    enemy_party_size = snapshot.u8(ENEMY_PARTY_COUNT) if trainer else None
    if enemy_party_size is not None:
        check(1 <= enemy_party_size <= PARTY_LENGTH, f"enemy team of {enemy_party_size}")

    return BattleState(
        kind=kind,
        player=_combatant(snapshot, rules, BATTLE_MON, BATTLE_MON_NICK, PLAYER_STAT_MODS),
        enemy=_combatant(snapshot, rules, ENEMY_MON, ENEMY_MON_NICK, ENEMY_STAT_MODS),
        player_party_index=player_index,
        trainer_class=snapshot.u8(TRAINER_CLASS) if trainer else None,
        trainer_number=snapshot.u8(TRAINER_NO) if trainer else None,
        enemy_party_size=enemy_party_size,
    )


def _combatant(
    snapshot: MemorySnapshot,
    rules: GameRules,
    struct: Address,
    nickname: Address,
    modifiers: Address,
) -> Maybe[BattlePokemon]:
    try:
        return parse_battle_mon(
            snapshot.field(struct), snapshot.field(nickname), snapshot.field(modifiers), rules
        )
    except InconsistentDataError as error:
        # Normal at the start of a battle, before the Pokemon is sent out.
        return Unavailable(str(error))


def parse_battle_mon(data: bytes, nickname: bytes, mods: bytes, rules: GameRules) -> BattlePokemon:
    info = species(rules, data[0])
    current_hp, max_hp = parse_hp(u16(data, 1), u16(data, 15))
    status, sleep_turns = parse_status(data[4])
    check(all(1 <= value <= 13 for value in mods), f"stat stages out of range: {list(mods)}")
    return BattlePokemon(
        species_id=info.id,
        species_name=info.name,
        nickname=decode(nickname),
        level=parse_level(data[14]),
        current_hp=current_hp,
        max_hp=max_hp,
        status=status,
        types=check_types(info, (data[5], data[6])),
        moves=parse_moves(rules, data[8:12], data[25:29]),
        stats=parse_stats(data, 15),
        modifiers=StatModifiers(*(value - NEUTRAL_MODIFIER for value in mods)),
        sleep_turns=sleep_turns,
    )

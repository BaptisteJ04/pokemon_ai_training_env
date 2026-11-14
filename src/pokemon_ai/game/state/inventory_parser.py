"""Reading the bag, the PC items and the money."""

from __future__ import annotations

from pokemon_ai.game.data.game_data import GameRules
from pokemon_ai.game.models.inventory import InventoryState
from pokemon_ai.game.state.common import check
from pokemon_ai.game.state.memory_addresses import (
    BAG_CAPACITY,
    BAG_ITEMS,
    BOX_ITEMS,
    NUM_BAG_ITEMS,
    NUM_BOX_ITEMS,
    PC_ITEM_CAPACITY,
    PLAYER_MONEY,
    Address,
)
from pokemon_ai.game.state.memory_reader import MemorySnapshot, decode_bcd

MAX_MONEY = 999_999
MAX_ITEM_QUANTITY = 99


def parse_inventory(snapshot: MemorySnapshot, rules: GameRules) -> InventoryState:
    try:
        money = decode_bcd(snapshot.field(PLAYER_MONEY))
    except ValueError as error:
        check(False, f"unreadable money: {error}")
    check(money <= MAX_MONEY, f"money out of range: {money}")

    items: dict[str, int] = {}
    pokeballs: dict[str, int] = {}
    key_items: list[str] = []
    for item_id, quantity in _item_list(snapshot, NUM_BAG_ITEMS, BAG_ITEMS, BAG_CAPACITY, rules):
        info = rules.items[item_id]
        if info.key_item:
            key_items.append(info.identifier)
        target = pokeballs if info.ball else items
        if not info.key_item:
            target[info.identifier] = target.get(info.identifier, 0) + quantity

    pc_items: dict[str, int] = {}
    for item_id, quantity in _item_list(
        snapshot, NUM_BOX_ITEMS, BOX_ITEMS, PC_ITEM_CAPACITY, rules
    ):
        identifier = rules.items[item_id].identifier
        pc_items[identifier] = pc_items.get(identifier, 0) + quantity

    return InventoryState(items, pokeballs, tuple(key_items), money, pc_items)


def _item_list(
    snapshot: MemorySnapshot,
    count_field: Address,
    list_field: Address,
    capacity: int,
    rules: GameRules,
) -> list[tuple[int, int]]:
    count = snapshot.u8(count_field)
    check(count <= capacity, f"{count_field.symbol} out of range: {count}")
    data = snapshot.field(list_field)
    check(data[2 * count] == 0xFF, f"{list_field.symbol} not ended by FF")
    entries = []
    for index in range(count):
        item_id, quantity = data[2 * index], data[2 * index + 1]
        check(item_id in rules.items, f"unknown item 0x{item_id:02X}")
        check(1 <= quantity <= MAX_ITEM_QUANTITY, f"quantity out of range: {quantity}")
        entries.append((item_id, quantity))
    return entries

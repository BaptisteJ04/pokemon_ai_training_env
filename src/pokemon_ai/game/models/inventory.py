"""Bag. Items are identified by their pokered constant name (for example `POKE_BALL`)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class InventoryState:
    items: dict[str, int]
    pokeballs: dict[str, int]
    key_items: tuple[str, ...]
    money: int
    pc_items: dict[str, int] = field(default_factory=dict)

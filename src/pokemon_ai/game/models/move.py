"""A move known by a Pokemon."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MoveState:
    move_id: int
    name: str
    pp: int
    max_pp: int
    pp_ups: int = 0

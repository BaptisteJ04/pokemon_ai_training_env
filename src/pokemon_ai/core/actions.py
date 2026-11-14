"""Elementary actions of an agent: moves and buttons.

A move toward a blocked tile only turns the player. That is also how you face an NPC or a sign.
"""

from __future__ import annotations

from enum import StrEnum

from pokemon_ai.emulator.controls import Button


class Action(StrEnum):
    MOVE_UP = "MOVE_UP"
    MOVE_DOWN = "MOVE_DOWN"
    MOVE_LEFT = "MOVE_LEFT"
    MOVE_RIGHT = "MOVE_RIGHT"
    PRESS_A = "PRESS_A"
    PRESS_B = "PRESS_B"
    PRESS_START = "PRESS_START"
    PRESS_SELECT = "PRESS_SELECT"
    WAIT = "WAIT"

    @property
    def button(self) -> Button | None:
        return _BUTTONS.get(self)

    @property
    def is_move(self) -> bool:
        return self.name.startswith("MOVE_")

    @classmethod
    def move(cls, direction: str) -> Action:
        """`direction` is UP, DOWN, LEFT or RIGHT."""
        return cls(f"MOVE_{direction}")


_BUTTONS = {
    Action.MOVE_UP: Button.UP,
    Action.MOVE_DOWN: Button.DOWN,
    Action.MOVE_LEFT: Button.LEFT,
    Action.MOVE_RIGHT: Button.RIGHT,
    Action.PRESS_A: Button.A,
    Action.PRESS_B: Button.B,
    Action.PRESS_START: Button.START,
    Action.PRESS_SELECT: Button.SELECT,
}

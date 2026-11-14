"""Game Boy buttons and button sequences."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# Default durations in frames (60 frames = 1 second). A press that is too short can be ignored
# because the game only reads the joypad at certain moments.
DEFAULT_HOLD_FRAMES = 8
DEFAULT_WAIT_FRAMES = 8


class Button(StrEnum):
    A = "a"
    B = "b"
    START = "start"
    SELECT = "select"
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True, slots=True)
class InputStep:
    """Hold `button` for `hold_frames`, then release everything for `wait_frames`.

    `button=None` is a plain wait.
    """

    button: Button | None
    hold_frames: int = DEFAULT_HOLD_FRAMES
    wait_frames: int = DEFAULT_WAIT_FRAMES

    def __post_init__(self) -> None:
        if self.hold_frames < 0 or self.wait_frames < 0:
            raise ValueError("Durations cannot be negative")
        if self.button is not None and self.hold_frames == 0:
            raise ValueError("A button press must last at least one frame")

    @property
    def total_frames(self) -> int:
        return (self.hold_frames if self.button is not None else 0) + self.wait_frames


def tap(
    button: Button, hold: int = DEFAULT_HOLD_FRAMES, wait: int = DEFAULT_WAIT_FRAMES
) -> InputStep:
    return InputStep(button, hold, wait)


def wait(frames: int) -> InputStep:
    return InputStep(None, 0, frames)

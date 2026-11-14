"""What an agent can answer, and how it becomes button presses.

An agent answers with an elementary `Action` (move, button, wait) or, for finer control, with a
sequence of `InputStep` (button, hold time, wait time).

The durations are short: the end of a move or an animation is not waited for here. The agent
decides again once the game can be controlled.
"""

from __future__ import annotations

from collections.abc import Sequence

from pokemon_ai.core.actions import Action
from pokemon_ai.emulator.controls import InputStep, tap, wait

type AgentAction = Action | Sequence[InputStep]

MOVE_HOLD_FRAMES = 4  # enough to start a step; the step itself lasts 16 frames
MOVE_WAIT_FRAMES = 2
PRESS_HOLD_FRAMES = 4
PRESS_WAIT_FRAMES = 6
WAIT_FRAMES = 4


def to_inputs(action: Action) -> list[InputStep]:
    button = action.button
    if button is None:
        return [wait(WAIT_FRAMES)]
    if action.is_move:
        return [tap(button, hold=MOVE_HOLD_FRAMES, wait=MOVE_WAIT_FRAMES)]
    return [tap(button, hold=PRESS_HOLD_FRAMES, wait=PRESS_WAIT_FRAMES)]


def as_inputs(action: AgentAction) -> list[InputStep]:
    """The sequence of inputs to play for an elementary action or a button sequence."""
    if isinstance(action, Action):
        return to_inputs(action)
    return list(action)

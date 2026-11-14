"""Generic building blocks of the observed state: unavailable data, read issues, observation.

Pokemon-specific structures (GameState and its parts) live in `game/models`, so this module does
not depend on any game.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Unavailable:
    """Data that could not be read or is inconsistent. Not the same as a zero or empty value."""

    reason: str


type Maybe[T] = T | Unavailable


def is_available[T](value: Maybe[T]) -> bool:
    return not isinstance(value, Unavailable)


@dataclass(frozen=True, slots=True)
class DataIssue:
    field: str
    reason: str


@dataclass(frozen=True, slots=True)
class Observation[S]:
    """Observed state with its source, the frame number and a confidence in [0, 1]."""

    state: S
    confidence: float
    source: str
    frame: int
    timestamp: float = field(default_factory=time.time)

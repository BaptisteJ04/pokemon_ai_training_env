"""Emulator interface: the rest of the project never uses PyBoy directly."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from pokemon_ai.emulator.controls import Button

ADDRESS_SPACE = 0x10000


class GameEmulator(ABC):
    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def set_held_buttons(self, buttons: frozenset[Button]) -> None:
        """Hold exactly these buttons until the next call."""

    @abstractmethod
    def advance(self, frames: int) -> None:
        """Run `frames` frames with the current buttons held."""

    @abstractmethod
    def get_screenshot(self) -> np.ndarray:
        """Copy of the current screen as an RGB array of shape (144, 160, 3)."""

    @abstractmethod
    def get_memory(self, address: int, size: int = 1) -> bytes: ...

    @abstractmethod
    def save_state(self) -> bytes: ...

    @abstractmethod
    def load_state(self, state: bytes) -> None: ...

    @property
    @abstractmethod
    def frame_count(self) -> int:
        """Frames emulated since the start. This is our measure of game time."""

    def __enter__(self) -> GameEmulator:
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()


def check_memory_range(address: int, size: int) -> None:
    if size < 1:
        raise ValueError(f"Invalid read size: {size}")
    if address < 0 or address + size > ADDRESS_SPACE:
        raise ValueError(f"Read outside the address space: 0x{address:04X} + {size}")

"""GameEmulator implemented with PyBoy (the only module that imports PyBoy)."""

from __future__ import annotations

import io
import logging
import struct
import warnings

import numpy as np

with warnings.catch_warnings():
    # PyBoy warns that it uses the SDL2 binaries from pysdl2-dll, which is what we want.
    warnings.filterwarnings("ignore", message="Using SDL2 binaries", category=UserWarning)
    from pyboy import PyBoy

from pokemon_ai.emulator.base import GameEmulator, check_memory_range
from pokemon_ai.emulator.controls import Button
from pokemon_ai.emulator.rom import RomImage

logger = logging.getLogger(__name__)

# Header written before the PyBoy savestate. PyBoy does not restore its frame counter when
# loading a state, but we use that counter as the game clock.
STATE_HEADER = struct.Struct("<4sBQ")
STATE_MAGIC = b"PKAI"
STATE_VERSION = 1


class EmulatorNotRunningError(RuntimeError):
    pass


class PyBoyEmulator(GameEmulator):
    def __init__(
        self, rom: RomImage, *, headless: bool = True, scale: int = 3, sound: bool = False
    ) -> None:
        self.rom = rom
        self._headless = headless
        self._scale = scale
        self._sound = sound
        self._pyboy: PyBoy | None = None
        self._held: set[Button] = set()
        self._frame_count = 0

    def start(self) -> None:
        if self._pyboy is not None:
            return
        # The ROM is passed as a stream and without a RAM file: nothing is read from or written
        # to disk, and every start uses a blank cartridge.
        self._pyboy = PyBoy(
            io.BytesIO(self.rom.data),
            window="null" if self._headless else "SDL2",
            scale=self._scale,
            sound_emulated=self._sound,
            cgb=False,
            log_level="ERROR",
        )
        # No speed limit: the session loop paces the game itself.
        self._pyboy.set_emulation_speed(0)
        self._frame_count = 0
        logger.info("Emulator started: %s (SHA-1 %s)", self.rom.title, self.rom.sha1[:12])

    def stop(self) -> None:
        if self._pyboy is None:
            return
        self._pyboy.stop(save=False)
        self._pyboy = None
        self._held.clear()
        logger.info("Emulator stopped")

    def set_held_buttons(self, buttons: frozenset[Button]) -> None:
        pyboy = self._require()
        for button in self._held - buttons:
            pyboy.button_release(button.value)
        for button in buttons - self._held:
            pyboy.button_press(button.value)
        self._held = set(buttons)

    def advance(self, frames: int) -> None:
        if frames < 0:
            raise ValueError("The number of frames cannot be negative")
        if frames:
            # Only the last frame is rendered, which is PyBoy's optimization for AI use.
            self._require().tick(frames, True)
            self._frame_count += frames

    def get_screenshot(self) -> np.ndarray:
        return np.array(self._require().screen.ndarray[:, :, :3], copy=True)

    def get_memory(self, address: int, size: int = 1) -> bytes:
        check_memory_range(address, size)
        memory = self._require().memory
        return bytes(memory[address : address + size])

    def save_state(self) -> bytes:
        buffer = io.BytesIO()
        buffer.write(STATE_HEADER.pack(STATE_MAGIC, STATE_VERSION, self._frame_count))
        self._require().save_state(buffer)
        return buffer.getvalue()

    def load_state(self, state: bytes) -> None:
        pyboy = self._require()
        if len(state) < STATE_HEADER.size:
            raise ValueError("Invalid savestate: too short")
        magic, version, frame_count = STATE_HEADER.unpack_from(state)
        if magic != STATE_MAGIC or version != STATE_VERSION:
            raise ValueError("Invalid savestate: unknown header (not made by PyBoyEmulator?)")
        pyboy.load_state(io.BytesIO(state[STATE_HEADER.size :]))
        self._frame_count = frame_count
        # A savestate keeps the joypad state. A button held when it was saved would stay
        # pressed forever, so release everything.
        for button in Button:
            pyboy.button_release(button.value)
        self._held.clear()

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def _require(self) -> PyBoy:
        if self._pyboy is None:
            raise EmulatorNotRunningError("The emulator is not started (call start())")
        return self._pyboy

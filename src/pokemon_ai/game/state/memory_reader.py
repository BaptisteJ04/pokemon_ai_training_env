"""Typed reads of Game Boy memory from a snapshot of the WRAM.

The whole WRAM is copied in one read, so all the values of an observation come from the same
frame and the parsers work without touching the emulator.
"""

from __future__ import annotations

from pokemon_ai.emulator.base import GameEmulator
from pokemon_ai.game.data.charmap import decode
from pokemon_ai.game.state.memory_addresses import Address

WRAM_START = 0xC000
WRAM_SIZE = 0x2000


class MemorySnapshot:
    def __init__(self, wram: bytes, frame: int = 0) -> None:
        if len(wram) != WRAM_SIZE:
            raise ValueError(f"WRAM snapshot of {len(wram)} bytes instead of {WRAM_SIZE}")
        self.wram = wram
        self.frame = frame

    @classmethod
    def capture(cls, emulator: GameEmulator) -> MemorySnapshot:
        return cls(emulator.get_memory(WRAM_START, WRAM_SIZE), emulator.frame_count)

    def read(self, address: int, size: int = 1) -> bytes:
        offset = address - WRAM_START
        if offset < 0 or offset + size > WRAM_SIZE:
            raise ValueError(f"0x{address:04X} + {size} is outside the WRAM")
        return self.wram[offset : offset + size]

    def field(self, field: Address) -> bytes:
        return self.read(field.address, field.size)

    def u8(self, field: Address | int) -> int:
        return self.read(_address(field))[0]

    def u16(self, field: Address | int) -> int:
        """Big-endian 16-bit integer (format of HP, stats and DVs in Gen 1)."""
        return int.from_bytes(self.read(_address(field), 2), "big")

    def bcd(self, field: Address) -> int:
        return decode_bcd(self.field(field))

    def text(self, field: Address) -> str:
        return decode(self.field(field))


def _address(field: Address | int) -> int:
    return field.address if isinstance(field, Address) else field


def u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "big")


def u24(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 3], "big")


def decode_bcd(data: bytes) -> int:
    """Decode a big-endian BCD number. Raises ValueError if a digit is above 9."""
    value = 0
    for byte in data:
        high, low = byte >> 4, byte & 0x0F
        if high > 9 or low > 9:
            raise ValueError(f"Invalid BCD byte: 0x{byte:02X}")
        value = value * 100 + high * 10 + low
    return value


def bits(data: bytes) -> set[int]:
    """Indices of the bits set in a bitfield (bit 0 of byte 0 = index 0)."""
    return {
        index * 8 + bit for index, byte in enumerate(data) for bit in range(8) if byte >> bit & 1
    }

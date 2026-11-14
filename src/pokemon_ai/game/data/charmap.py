"""Character encoding of Pokemon Red (US), from `constants/charmap.asm` of pret/pokered."""

from __future__ import annotations

TERMINATOR = 0x50

CHARMAP: dict[int, str] = {
    0x4A: "PKMN",
    0x54: "POKé",
    0x5B: "PC",
    0x5C: "TM",
    0x5D: "TRAINER",
    0x5E: "ROCKET",
    0x6D: ":",
    0x70: "‘",
    0x71: "’",
    0x72: "“",
    0x73: "”",
    0x75: "…",
    0x79: "┌",
    0x7A: "─",
    0x7B: "┐",
    0x7C: "│",
    0x7D: "└",
    0x7E: "┘",
    0x7F: " ",
    0x9A: "(",
    0x9B: ")",
    0x9C: ":",
    0x9D: ";",
    0x9E: "[",
    0x9F: "]",
    0xBA: "é",
    0xBB: "'d",
    0xBC: "'l",
    0xBD: "'s",
    0xBE: "'t",
    0xBF: "'v",
    0xE0: "'",
    0xE1: "PK",
    0xE2: "MN",
    0xE3: "-",
    0xE4: "'r",
    0xE5: "'m",
    0xE6: "?",
    0xE7: "!",
    0xE8: ".",
    0xEC: "▷",
    0xED: "▶",
    0xEE: "▼",
    0xEF: "♂",
    0xF0: "¥",
    0xF1: "×",
    0xF2: ".",
    0xF3: "/",
    0xF4: ",",
    0xF5: "♀",
}
CHARMAP.update({0x80 + i: chr(ord("A") + i) for i in range(26)})
CHARMAP.update({0xA0 + i: chr(ord("a") + i) for i in range(26)})
CHARMAP.update({0xF6 + i: str(i) for i in range(10)})

# Characters a player can type in a name (naming screen).
NAME_CHARACTERS = frozenset(
    [
        *range(0x80, 0x9A),
        *range(0xA0, 0xBA),
        *(0x7F, 0x9A, 0x9B, 0x9C, 0x9D, 0x9E, 0x9F),
        *(0xE1, 0xE2, 0xE3, 0xE6, 0xE7, 0xE8, 0xEF, 0xF1, 0xF3, 0xF4, 0xF5),
        *range(0xF6, 0x100),
    ]
)


def decode(data: bytes) -> str:
    """Decode up to the 0x50 terminator (excluded). Unknown bytes become "?"."""
    chars = []
    for byte in data:
        if byte == TERMINATOR:
            break
        chars.append(CHARMAP.get(byte, "?"))
    return "".join(chars)


def is_valid_name(data: bytes, max_length: int = 10) -> bool:
    """True if `data` holds a name that can be typed: not empty and ended by 0x50."""
    try:
        end = data.index(TERMINATOR)
    except ValueError:
        return False
    return 0 < end <= max_length and all(byte in NAME_CHARACTERS for byte in data[:end])

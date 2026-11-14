"""Loading and checking the ROM.

The ROM can be a `.gb` / `.gbc` file or a `.zip` archive containing exactly one of them.
It is read in memory and never extracted to disk.
"""

from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path

ROM_EXTENSIONS = (".gb", ".gbc")
MAX_ROM_SIZE = 8 * 1024 * 1024  # the biggest Game Boy cartridge is 8 MiB
TITLE_ADDRESS = slice(0x134, 0x144)


class RomError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class RomImage:
    data: bytes
    sha1: str
    source: Path

    @property
    def title(self) -> str:
        """Title from the cartridge header (for example "POKEMON RED")."""
        raw = self.data[TITLE_ADDRESS]
        return raw.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()


def load_rom(path: Path, expected_sha1: str | None = None) -> RomImage:
    if not path.exists():
        raise RomError(f"ROM not found: {path}")
    data = _read_zip(path) if path.suffix.lower() == ".zip" else _read_file(path)
    if len(data) < TITLE_ADDRESS.stop:
        raise RomError(f"{path} is too small to be a Game Boy ROM ({len(data)} bytes)")

    sha1 = hashlib.sha1(data).hexdigest()
    if expected_sha1 is not None and sha1 != expected_sha1.lower():
        raise RomError(
            f"Unexpected ROM SHA-1: {sha1} (expected {expected_sha1}). "
            "Memory addresses depend on the exact ROM version."
        )
    return RomImage(data=data, sha1=sha1, source=path)


def _read_file(path: Path) -> bytes:
    if path.suffix.lower() not in ROM_EXTENSIONS:
        raise RomError(f"Unknown extension for {path} (expected .gb, .gbc or .zip)")
    if path.stat().st_size > MAX_ROM_SIZE:
        raise RomError(f"{path} is bigger than any Game Boy ROM")
    return path.read_bytes()


def _read_zip(path: Path) -> bytes:
    try:
        with zipfile.ZipFile(path) as archive:
            entries = [
                info
                for info in archive.infolist()
                if not info.is_dir() and info.filename.lower().endswith(ROM_EXTENSIONS)
            ]
            if len(entries) != 1:
                raise RomError(
                    f"{path} must contain exactly one .gb/.gbc ROM ({len(entries)} found)"
                )
            with archive.open(entries[0]) as handle:
                # Bounded read: the size announced by the archive is not trusted.
                data = handle.read(MAX_ROM_SIZE + 1)
    except zipfile.BadZipFile as error:
        raise RomError(f"Invalid archive {path}: {error}") from None
    if len(data) > MAX_ROM_SIZE:
        raise RomError(f"{path} is bigger than any Game Boy ROM")
    return data

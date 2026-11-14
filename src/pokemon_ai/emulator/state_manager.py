"""Named savestates on disk, each with a small JSON metadata file.

`<name>.state` comes with `<name>.json`, which records the ROM SHA-1: a savestate is only valid
for the ROM that produced it.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

# A name may contain one folder level, e.g. "reference/pallet_town".
NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*(/[A-Za-z0-9][A-Za-z0-9_-]*)?$")


class SaveStateError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class SaveStateInfo:
    name: str
    rom_sha1: str
    frame_count: int
    description: str = ""
    created_at: float = field(default_factory=time.time)


class SaveStateManager:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def save(
        self,
        name: str,
        state: bytes,
        *,
        rom_sha1: str,
        frame_count: int,
        description: str = "",
    ) -> SaveStateInfo:
        state_path, meta_path = self._paths(name)
        info = SaveStateInfo(name, rom_sha1, frame_count, description)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_bytes(state)
        meta_path.write_text(json.dumps(asdict(info), indent=2), encoding="utf-8")
        return info

    def load(self, name: str, *, rom_sha1: str | None = None) -> bytes:
        """Read a savestate. If `rom_sha1` is given, refuse a state made by another ROM."""
        state_path, _ = self._paths(name)
        if not state_path.exists():
            raise SaveStateError(f"Savestate not found: {state_path}")
        info = self.info(name)
        if rom_sha1 is not None and info.rom_sha1 != rom_sha1:
            raise SaveStateError(
                f"Savestate '{name}' was made by another ROM "
                f"({info.rom_sha1[:12]} instead of {rom_sha1[:12]})"
            )
        return state_path.read_bytes()

    def info(self, name: str) -> SaveStateInfo:
        _, meta_path = self._paths(name)
        if not meta_path.exists():
            raise SaveStateError(f"No metadata for savestate '{name}'")
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            fields = {key: data[key] for key in SaveStateInfo.__dataclass_fields__ if key in data}
            return SaveStateInfo(**fields)
        except (json.JSONDecodeError, TypeError) as error:
            raise SaveStateError(f"Invalid metadata for '{name}': {error}") from None

    def list(self) -> list[SaveStateInfo]:
        if not self.directory.exists():
            return []
        names = [
            path.relative_to(self.directory).with_suffix("").as_posix()
            for path in sorted(self.directory.rglob("*.state"))
        ]
        return [self.info(name) for name in names if self._paths(name)[1].exists()]

    def _paths(self, name: str) -> tuple[Path, Path]:
        if not NAME_PATTERN.match(name):
            raise SaveStateError(f"Invalid savestate name '{name}' (letters, digits, _ and - only)")
        return self.directory / f"{name}.state", self.directory / f"{name}.json"

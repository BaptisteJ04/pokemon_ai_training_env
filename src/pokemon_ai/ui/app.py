"""Start the graphical interface."""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from pokemon_ai.core.config import AppConfig
from pokemon_ai.emulator.pyboy_adapter import PyBoyEmulator
from pokemon_ai.emulator.rom import load_rom
from pokemon_ai.runtime.controllers import make_controller
from pokemon_ai.runtime.loop import Mode
from pokemon_ai.runtime.savestates import savestate_manager
from pokemon_ai.ui.controllers.session_controller import SessionController
from pokemon_ai.ui.main_window import MainWindow


def choose_platform() -> None:
    """On Wayland, use XWayland (xcb) unless QT_QPA_PLATFORM is set.

    The Qt 6.12 Wayland plugin reads a GNOME key that Ubuntu 22.04 does not have
    (`org.gnome.settings-daemon.plugins.xsettings antialiasing`), and GLib then kills the
    process at startup.
    """
    if "QT_QPA_PLATFORM" not in os.environ and os.environ.get("XDG_SESSION_TYPE") == "wayland":
        os.environ["QT_QPA_PLATFORM"] = "xcb"


def run_app(
    config: AppConfig,
    *,
    initial_state: str | None = None,
    autonomous: bool = False,
    argv: Sequence[str] | None = None,
) -> int:
    """`initial_state` is a savestate name (otherwise the game starts cold)."""
    choose_platform()
    app = QApplication.instance() or QApplication(list(argv or sys.argv[:1]))
    rom = load_rom(config.emulator.rom_path, config.emulator.rom_sha1)
    savestates = savestate_manager(config)
    session = SessionController(
        config,
        # The interface draws the screen itself: PyBoy runs without a window, and the session
        # loop sets the speed.
        lambda: PyBoyEmulator(rom, headless=True, sound=config.emulator.sound),
        lambda bus: make_controller(config, bus=bus),
        rom_sha1=rom.sha1,
        savestates=savestates,
    )
    window = MainWindow(config, session, savestates)
    window.resize(1400, 950)
    window.show()
    if autonomous:
        window.set_mode(Mode.AUTONOMOUS)
    if initial_state is not None:
        window.load_named_state(initial_state)
    else:
        window.start()
    return app.exec()

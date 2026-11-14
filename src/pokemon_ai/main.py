"""Command-line entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from pokemon_ai import __version__
from pokemon_ai.agents.registry import BUILTIN, AgentError, agent_class
from pokemon_ai.core.config import DEFAULT_CONFIG_DIR, ConfigError, dump_config, load_config
from pokemon_ai.core.logging_setup import setup_logging

logger = logging.getLogger("pokemon_ai")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pokemon-ai", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=DEFAULT_CONFIG_DIR,
        help="folder with default.yaml and emulator.yaml",
    )
    parser.add_argument(
        "--config",
        type=Path,
        action="append",
        default=[],
        metavar="FILE",
        help="extra YAML file that overrides the configuration (can be repeated)",
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        dest="overrides",
        help="single override, e.g. emulator.speed=2 (can be repeated)",
    )
    parser.add_argument("--rom", type=Path, help="path of the ROM (shortcut for emulator.rom_path)")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="run without the interface, in autonomous mode at unlimited speed",
    )
    parser.add_argument(
        "--state",
        metavar="NAME",
        help="savestate to start from, in the savestate folder (e.g. my_state)",
    )
    parser.add_argument(
        "--agent",
        metavar="AGENT",
        help=f"agent of autonomous mode: {', '.join(BUILTIN)}, package.module:Class or "
        "file.py:Class (default: run.agent of the configuration)",
    )
    parser.add_argument(
        "--autonomous",
        action="store_true",
        help="interface: start directly in autonomous mode",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=3600,
        help="headless: frames to play (default 3600, one minute of game; 0 = no limit)",
    )
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    parser.add_argument(
        "--print-config", action="store_true", help="print the resolved configuration and exit"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    overrides = list(args.overrides)
    if args.rom is not None:
        overrides.append(f"emulator.rom_path={args.rom}")
    if args.headless:
        overrides.append("emulator.headless=true")
    if args.log_level is not None:
        overrides.append(f"logging.level={args.log_level}")
    if args.agent is not None:
        overrides.append(f"run.agent={args.agent}")

    try:
        config = load_config(args.config_dir, args.config, overrides)
        agent_class(config.run.agent)
    except (ConfigError, AgentError) as error:
        print(error, file=sys.stderr)
        return 2

    if args.print_config:
        print(dump_config(config), end="")
        return 0

    setup_logging(config.logging)
    logger.info("pokemon-ai %s, agent %s", __version__, config.run.agent)
    if config.emulator.headless:
        from pokemon_ai.runtime.headless import run_headless

        status = run_headless(config, frames=args.frames or None, initial_state=args.state)
        print(f"Run finished: {status}")
        return 0 if status == "completed" else 1

    from pokemon_ai.ui.app import run_app  # imported here so Qt is only loaded with the interface

    return run_app(config, initial_state=args.state, autonomous=args.autonomous)


if __name__ == "__main__":
    sys.exit(main())

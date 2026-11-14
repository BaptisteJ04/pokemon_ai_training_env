"""Logging setup: console output and an optional log file."""

from __future__ import annotations

import logging

from pokemon_ai.core.config import LoggingConfig

TEXT_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def setup_logging(config: LoggingConfig) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if config.file is not None:
        config.file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(config.file, encoding="utf-8"))
    for handler in handlers:
        handler.setFormatter(logging.Formatter(TEXT_FORMAT))
    logging.basicConfig(level=config.level, handlers=handlers, force=True)

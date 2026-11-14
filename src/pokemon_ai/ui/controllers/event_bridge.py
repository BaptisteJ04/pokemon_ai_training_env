"""Bridges to Qt: bus events and log messages, relayed as signals.

Bus handlers are called in the thread that publishes (the agent's). The bridge emits a Qt signal
from that thread. Since the bridge lives in the interface thread, Qt queues the call and the slot
runs in the interface thread. No data is shared.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from pokemon_ai.core.event_bus import EventBus
from pokemon_ai.core.events import AgentEvent


class EventBridge(QObject):
    event_received = Signal(object)  # AgentEvent

    def __init__(self, bus: EventBus, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._bus = bus
        self._subscription: int | None = bus.subscribe(self._relay)

    def close(self) -> None:
        if self._subscription is not None:
            self._bus.unsubscribe(self._subscription)
            self._subscription = None

    def _relay(self, event: AgentEvent) -> None:
        self.event_received.emit(event)


class LogBridge(QObject):
    """Logging handler that sends every message to the interface (log view)."""

    record_received = Signal(str, str, float)  # level, message, timestamp

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        bridge = self

        class _Handler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                bridge.record_received.emit(record.levelname, self.format(record), record.created)

        self.handler = _Handler()
        self.handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))

    def install(self, logger_name: str = "pokemon_ai", level: int = logging.INFO) -> None:
        self.handler.setLevel(level)
        logging.getLogger(logger_name).addHandler(self.handler)

    def uninstall(self, logger_name: str = "pokemon_ai") -> None:
        logging.getLogger(logger_name).removeHandler(self.handler)

"""Thread-safe publish/subscribe event bus, independent of Qt.

Handlers are called synchronously in the thread that publishes. A handler that lives in another
thread (the interface) must hand the event over in a thread-safe way, for example with a Qt Signal.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterable

from pokemon_ai.core.events import AgentEvent, EventType

logger = logging.getLogger(__name__)

EventHandler = Callable[[AgentEvent], None]


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._handlers: dict[int, tuple[EventHandler, frozenset[EventType] | None]] = {}
        self._next_id = 0

    def subscribe(
        self, handler: EventHandler, event_types: Iterable[EventType] | None = None
    ) -> int:
        """Call `handler` for the given event types (all of them if `None`). Returns an id."""
        types = frozenset(event_types) if event_types is not None else None
        with self._lock:
            subscription_id = self._next_id
            self._next_id += 1
            self._handlers[subscription_id] = (handler, types)
        return subscription_id

    def unsubscribe(self, subscription_id: int) -> None:
        with self._lock:
            self._handlers.pop(subscription_id, None)

    def publish(self, event: AgentEvent) -> None:
        with self._lock:
            handlers = list(self._handlers.values())
        for handler, types in handlers:
            if types is not None and event.event_type not in types:
                continue
            try:
                handler(event)
            except Exception:
                # A broken handler must not stop the agent or the other handlers.
                logger.exception("Error in an event handler for %s", event.event_type)

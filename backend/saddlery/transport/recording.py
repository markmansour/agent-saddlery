"""Sinks that record emitted events — for tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from saddlery.transport.base import EventSink

if TYPE_CHECKING:
    from saddlery.events import Event
    from saddlery.transport.agui import AgUiEvent, AgUiEventSink


class RecordingSink(EventSink):
    """Records internal events."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    async def emit(self, event: Event) -> None:
        self.events.append(event)


class AgUiRecordingSink:
    """Records AG-UI events — implements AgUiEventSink."""

    def __init__(self) -> None:
        self.events: list[AgUiEvent] = []

    async def emit(self, event: AgUiEvent) -> None:
        self.events.append(event)


class LoggingAgUiSink:
    """Logs AG-UI wire events as structured data, then emits to wrapped sink."""

    def __init__(self, sink: AgUiEventSink) -> None:
        self._sink = sink
        self._log = structlog.get_logger()

    async def emit(self, event: AgUiEvent) -> None:
        # Info level for lifecycle events, debug for content
        level = "info" if event.type in ("RUN_START", "RUN_FINISH") else "debug"
        self._log.log(level, "agui_event_emitted", agui_type=event.type, event=event.model_dump())
        await self._sink.emit(event)

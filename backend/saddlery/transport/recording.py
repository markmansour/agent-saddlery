"""Sinks that record emitted events — for tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from saddlery.transport.base import EventSink

if TYPE_CHECKING:
    from saddlery.events import Event
    from saddlery.transport.agui import AgUiEvent


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

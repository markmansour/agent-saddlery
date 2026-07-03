"""A sink that records emitted events — for tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from saddlery.transport.base import EventSink

if TYPE_CHECKING:
    from saddlery.events import Event


class RecordingSink(EventSink):
    def __init__(self) -> None:
        self.events: list[Event] = []

    async def emit(self, event: Event) -> None:
        self.events.append(event)

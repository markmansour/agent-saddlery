"""A sink that records emitted events — for tests."""

from __future__ import annotations

from saddlery.events import BaseEvent


class RecordingSink:
    def __init__(self) -> None:
        self.events: list[BaseEvent] = []

    async def emit(self, event: BaseEvent) -> None:
        self.events.append(event)

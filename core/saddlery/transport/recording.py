"""A sink that records emitted events — for tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from saddlery.events import BaseEvent


class RecordingSink:
    def __init__(self) -> None:
        self.events: list[BaseEvent] = []

    async def emit(self, event: BaseEvent) -> None:
        self.events.append(event)

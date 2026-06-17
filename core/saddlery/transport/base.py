"""EventSink — the outbound transport seam (core -> consumer)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from saddlery.events import BaseEvent


@runtime_checkable
class EventSink(Protocol):
    async def emit(self, event: BaseEvent) -> None: ...

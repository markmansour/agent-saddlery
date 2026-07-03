"""EventSink — the outbound transport seam (core -> consumer)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from saddlery.events import Event


@runtime_checkable
class EventSink(Protocol):
    async def emit(self, event: Event) -> None: ...

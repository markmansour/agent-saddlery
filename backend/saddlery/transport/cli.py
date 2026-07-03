"""Sinks that consume internal events and present them to consumers."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, TextIO

from saddlery.events import AssistantMessageDelta, ErrorEvent, Event, RunFinished, RunStarted
from saddlery.transport.base import EventSink

if TYPE_CHECKING:
    from saddlery.transport.agui import AgUiEventSink


class CliSink(EventSink):
    """Streams assistant text to a terminal."""

    def __init__(self, out: TextIO = sys.stdout) -> None:
        self._out = out

    async def emit(self, event: Event) -> None:
        if isinstance(event, AssistantMessageDelta):
            self._out.write(event.text)
            self._out.flush()
        elif isinstance(event, ErrorEvent):
            self._out.write(f"\n[error] {event.message}\n")
            self._out.flush()
        elif isinstance(event, RunFinished):
            self._out.write("\n")
            self._out.flush()


class AgUiSink(EventSink):
    """Translates internal events to AG-UI wire format for frontend consumption."""

    def __init__(self, consumer: AgUiEventSink) -> None:
        """
        Args:
            consumer: A sink that receives AG-UI events (implements AgUiEventSink).
        """
        self._consumer = consumer

    async def emit(self, event: Event) -> None:
        from saddlery.transport.agui import (
            ErrorEvent as AgUiErrorEvent,
        )
        from saddlery.transport.agui import (
            RunFinishEvent,
            RunStartEvent,
            TextMessageContentEvent,
        )

        if isinstance(event, RunStarted):
            await self._consumer.emit(RunStartEvent())  # type: ignore[arg-type]
        elif isinstance(event, AssistantMessageDelta):
            await self._consumer.emit(TextMessageContentEvent(content=event.text))  # type: ignore[arg-type]
        elif isinstance(event, ErrorEvent):
            await self._consumer.emit(AgUiErrorEvent(message=event.message))  # type: ignore[arg-type]
        elif isinstance(event, RunFinished):
            await self._consumer.emit(RunFinishEvent())  # type: ignore[arg-type]

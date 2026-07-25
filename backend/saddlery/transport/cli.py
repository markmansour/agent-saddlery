"""Sinks that consume internal events and present them to consumers."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, TextIO

import structlog

from saddlery.events import (
    AssistantMessageDelta,
    ErrorEvent,
    Event,
    RunFinished,
    RunStarted,
    ToolCall,
    ToolResult,
)
from saddlery.transport.base import EventSink

if TYPE_CHECKING:
    from saddlery.transport.agui import AgUiEventSink


class CliSink(EventSink):
    """Outputs events as JSON to stdout for TUI/frontend consumption."""

    def __init__(self, out: TextIO = sys.stdout) -> None:
        self._out = out

    async def emit(self, event: Event) -> None:
        import json

        # Output all events as JSON in AG-UI format
        output = {
            "event_type": event.type,
            "event_data": event.model_dump(mode="json"),
        }
        self._out.write(json.dumps(output) + "\n")
        self._out.flush()


class LoggingSink(EventSink):
    """Logs internal events as structured data, then emits to wrapped sink."""

    def __init__(self, sink: EventSink) -> None:
        self._sink = sink
        self._log = structlog.get_logger()

    async def emit(self, event: Event) -> None:
        # Log events: info for lifecycle, tool calls (important), debug for content
        if event.type in ("run_started", "run_finished"):
            self._log.info("event", event_type=event.type, event_data=event.model_dump())
        elif isinstance(event, ToolCall):
            self._log.info(
                "event",
                event_type="tool_call",
                tool_call_id=event.tool_call_id,
                tool_name=event.tool_name,
                arguments=event.arguments,
            )
        elif isinstance(event, ToolResult):
            self._log.info(
                "event",
                event_type="tool_result",
                tool_call_id=event.tool_call_id,
                is_error=event.is_error,
                content_length=len(event.content),
                content_preview=event.content[:100] if not event.is_error else event.content,
                source=event.source,
            )
        else:
            self._log.debug("event", event_type=event.type, event_data=event.model_dump())
        await self._sink.emit(event)


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

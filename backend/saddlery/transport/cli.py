"""A sink that streams assistant text to a terminal."""

from __future__ import annotations

import sys
from typing import TextIO

from saddlery.events import AssistantMessageDelta, ErrorEvent, Event, RunFinished
from saddlery.transport.base import EventSink


class CliSink(EventSink):
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

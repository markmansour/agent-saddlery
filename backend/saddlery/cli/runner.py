"""Serializes agent turns for one session.

The permission policy's taint fold ("a ToolResult since the last UserMessage") is only sound
if user messages and runs never overlap, so a message that arrives mid-run is queued and
appended to the event log only when its run starts.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from saddlery.events import UserMessage

if TYPE_CHECKING:
    from saddlery.agent import Agent
    from saddlery.session import Session
    from saddlery.transport.base import EventSink


class SessionRunner:
    def __init__(self, agent: Agent, session: Session, sink: EventSink) -> None:
        self._agent = agent
        self._session = session
        self._sink = sink
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker: asyncio.Task | None = None

    def submit(self, text: str) -> None:
        self._queue.put_nowait(text)
        if self._worker is None or self._worker.done():
            self._worker = asyncio.ensure_future(self._work())

    async def wait(self) -> None:
        if self._worker is not None:
            await self._worker

    async def _work(self) -> None:
        while not self._queue.empty():
            text = self._queue.get_nowait()
            self._session.append(
                UserMessage(
                    session_id=self._session.session_id,
                    principal=self._session.principal,
                    content=text,
                )
            )
            await self._agent.run(self._session, self._sink)

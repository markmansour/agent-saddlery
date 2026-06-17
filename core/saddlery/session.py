"""Session = an append-only event log + a pure fold to the LLM message list.

The event log is the source of truth. `SessionStore` is the persistence seam; the
in-memory implementation here is replaced by a SQLite store at slice 0.8 without
changing the fold (the fold *is* replay).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from saddlery.events import AssistantMessage, BaseEvent, UserMessage
from saddlery.messages import Message


class Session:
    def __init__(self, session_id: str, principal: str) -> None:
        self.session_id = session_id
        self.principal = principal
        self._events: list[BaseEvent] = []

    @property
    def events(self) -> list[BaseEvent]:
        return list(self._events)

    def append(self, event: BaseEvent) -> None:
        self._events.append(event)

    def to_messages(self) -> list[Message]:
        messages: list[Message] = []
        for event in self._events:
            if isinstance(event, UserMessage):
                messages.append(Message(role="user", content=event.content))
            elif isinstance(event, AssistantMessage):
                messages.append(Message(role="assistant", content=event.content))
        return messages


@runtime_checkable
class SessionStore(Protocol):
    async def get_or_create(self, session_id: str, principal: str) -> Session: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    async def get_or_create(self, session_id: str, principal: str) -> Session:
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id, principal)
        return self._sessions[session_id]

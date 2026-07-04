"""The Agent: an immutable config + the run() loop over the event stream."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from saddlery.events import (
    AssistantMessage,
    AssistantMessageDelta,
    ErrorEvent,
    Event,
    RunFinished,
    RunStarted,
)
from saddlery.llm.base import TextDelta
from saddlery.messages import Message

if TYPE_CHECKING:
    from saddlery.llm.base import LLMProvider
    from saddlery.session import Session
    from saddlery.transport.base import EventSink

DEFAULT_MODEL = "claude-haiku-4-5"


@dataclass(frozen=True)
class Agent:
    provider: LLMProvider
    system_prompt: str = "You are a helpful assistant."
    model: str = DEFAULT_MODEL

    async def run(self, session: Session, sink: EventSink) -> None:
        sid = session.session_id
        principal = session.principal

        async def emit(event: Event) -> None:
            session.append(event)
            await sink.emit(event)

        await emit(RunStarted(session_id=sid, principal=principal))
        messages = [
            Message(role="system", content=self.system_prompt),
            *session.to_messages(),
        ]
        parts: list[str] = []
        try:
            async for delta in self.provider.stream(messages, model=self.model):
                if isinstance(delta, TextDelta):
                    parts.append(delta.text)
                    await emit(
                        AssistantMessageDelta(session_id=sid, principal=principal, text=delta.text)
                    )
            await emit(
                AssistantMessage(session_id=sid, principal=principal, content="".join(parts))
            )
        except Exception as exc:  # broad on purpose: failures are recorded as events, not raised
            await emit(
                ErrorEvent(
                    session_id=sid,
                    principal=principal,
                    message=f"{type(exc).__name__}: {exc}",
                )
            )
        finally:
            await emit(RunFinished(session_id=sid, principal=principal))

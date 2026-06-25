"""The Agent: an immutable config + the run() loop over the event stream."""

from __future__ import annotations

from dataclasses import dataclass

from saddlery.events import (
    AssistantMessage,
    AssistantMessageDelta,
    BaseEvent,
    ErrorEvent,
    RunFinished,
    RunStarted,
)
from saddlery.llm.base import LLMProvider
from saddlery.messages import Message
from saddlery.session import Session
from saddlery.transport.base import EventSink

DEFAULT_MODEL = "claude-haiku-4-5"


@dataclass(frozen=True)
class Agent:
    provider: LLMProvider
    system_prompt: str = "You are a helpful assistant."
    model: str = DEFAULT_MODEL

    async def run(self, session: Session, sink: EventSink) -> None:
        meta = {"session_id": session.session_id, "principal": session.principal}

        async def emit(event: BaseEvent) -> None:
            session.append(event)
            await sink.emit(event)

        await emit(RunStarted(**meta))
        messages = [
            Message(role="system", content=self.system_prompt),
            *session.to_messages(),
        ]
        parts: list[str] = []
        try:
            async for delta in self.provider.stream(messages, model=self.model):
                parts.append(delta.text)
                await emit(AssistantMessageDelta(text=delta.text, **meta))
            await emit(AssistantMessage(content="".join(parts), **meta))
        except Exception as exc:
            await emit(ErrorEvent(message=f"{type(exc).__name__}: {exc}", **meta))
        finally:
            await emit(RunFinished(**meta))

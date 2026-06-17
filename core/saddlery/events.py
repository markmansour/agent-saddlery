"""Typed, append-only events — the canonical source of truth for a session."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


def _new_id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BaseEvent(BaseModel):
    id: str = Field(default_factory=_new_id)
    session_id: str
    principal: str
    timestamp: datetime = Field(default_factory=_now)


class UserMessage(BaseEvent):
    type: Literal["user_message"] = "user_message"
    content: str


class RunStarted(BaseEvent):
    type: Literal["run_started"] = "run_started"


class AssistantMessageDelta(BaseEvent):
    type: Literal["assistant_message_delta"] = "assistant_message_delta"
    text: str


class AssistantMessage(BaseEvent):
    type: Literal["assistant_message"] = "assistant_message"
    content: str


class RunFinished(BaseEvent):
    type: Literal["run_finished"] = "run_finished"


class ErrorEvent(BaseEvent):
    type: Literal["error"] = "error"
    message: str


Event = Annotated[
    Union[
        UserMessage,
        RunStarted,
        AssistantMessageDelta,
        AssistantMessage,
        RunFinished,
        ErrorEvent,
    ],
    Field(discriminator="type"),
]

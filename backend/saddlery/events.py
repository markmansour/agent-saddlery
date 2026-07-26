"""Typed, append-only events — the canonical source of truth for a session."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


def _new_id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)  # noqa: UP017


class BaseEvent(BaseModel):
    """Immutable base for all events — append-only, never mutated after construction."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=_new_id)
    session_id: str
    principal: str
    timestamp: datetime = Field(default_factory=_now)


class SessionStarted(BaseEvent):
    type: Literal["session_started"] = "session_started"


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


class ToolCall(BaseEvent):
    type: Literal["tool_call"] = "tool_call"
    tool_call_id: str
    tool_name: str
    arguments: dict


class ToolResult(BaseEvent):
    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    content: str
    is_error: bool = False
    source: Literal["untrusted"] = "untrusted"


class PermissionRequest(BaseEvent):
    type: Literal["permission_request"] = "permission_request"
    tool_call_id: str
    tool_name: str
    arguments: dict


class PermissionDecision(BaseEvent):
    type: Literal["permission_decision"] = "permission_decision"
    tool_call_id: str
    decision: Literal["allow", "deny"]


class ErrorEvent(BaseEvent):
    type: Literal["error"] = "error"
    message: str


Event = Annotated[
    SessionStarted
    | UserMessage
    | RunStarted
    | AssistantMessageDelta
    | AssistantMessage
    | ToolCall
    | ToolResult
    | PermissionRequest
    | PermissionDecision
    | RunFinished
    | ErrorEvent,
    Field(discriminator="type"),
]

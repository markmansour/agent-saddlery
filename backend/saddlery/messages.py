"""Provider-neutral conversation currency derived from the event log."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ToolUseBlock(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict


class ToolResultBlock(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str
    is_error: bool = False


ContentBlock = Annotated[
    TextBlock | ToolUseBlock | ToolResultBlock,
    Field(discriminator="type"),
]

Role = Literal["system", "user", "assistant"]


class Message(BaseModel):
    role: Role
    content: str | list[ContentBlock]

"""The LLMProvider seam. Pluggability lives here, not in any one vendor SDK."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from saddlery.messages import Message


class TextDelta(BaseModel):
    text: str


class ToolCallDelta(BaseModel):
    id: str  # Anthropic's tool_use.id — correlates call ↔ result
    name: str  # tool name
    input: dict  # parsed tool input/arguments (not raw JSON string)


# Union grows later (Stop/Usage). ToolCallDelta added in MM-8 step 5.
ProviderDelta = TextDelta | ToolCallDelta


@runtime_checkable
class LLMProvider(Protocol):
    def stream(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: list[dict] | None = None,
    ) -> AsyncIterator[ProviderDelta]: ...

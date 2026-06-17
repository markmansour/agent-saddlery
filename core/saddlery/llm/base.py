"""The LLMProvider seam. Pluggability lives here, not in any one vendor SDK."""

from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from pydantic import BaseModel

from saddlery.messages import Message


class TextDelta(BaseModel):
    text: str


# Union grows later (ToolCallDelta, Stop/Usage). Kept as one type for 0.1.
ProviderDelta = TextDelta


@runtime_checkable
class LLMProvider(Protocol):
    def stream(
        self, messages: list[Message], *, model: str
    ) -> AsyncIterator[ProviderDelta]: ...

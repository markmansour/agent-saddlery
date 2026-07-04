"""A scripted provider for testing the agent loop without a network."""

from __future__ import annotations

from typing import TYPE_CHECKING

from saddlery.llm.base import LLMProvider, ProviderDelta, TextDelta, ToolCallDelta

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from saddlery.messages import Message


class FakeProvider(LLMProvider):
    def __init__(
        self,
        chunks: list[str],
        *,
        error: Exception | None = None,
        tool_calls: list[ToolCallDelta] | None = None,
    ) -> None:
        self._chunks = chunks
        self._error = error
        self._tool_calls = tool_calls or []
        self._call_count = 0

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str = "fake",
        tools: list[dict] | None = None,
    ) -> AsyncIterator[ProviderDelta]:
        self._call_count += 1

        # First call with tool_calls scripted: emit tools and return
        if self._call_count == 1 and self._tool_calls:
            for tc in self._tool_calls:
                yield tc
            return

        # Normal path: emit text chunks
        for chunk in self._chunks:
            yield TextDelta(text=chunk)
        if self._error is not None:
            raise self._error

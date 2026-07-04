"""A scripted provider for testing the agent loop without a network."""

from __future__ import annotations

from typing import TYPE_CHECKING

from saddlery.llm.base import LLMProvider, ProviderDelta, TextDelta

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from saddlery.messages import Message


class FakeProvider(LLMProvider):
    def __init__(self, chunks: list[str], *, error: Exception | None = None) -> None:
        self._chunks = chunks
        self._error = error

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str = "fake",
        tools: list[dict] | None = None,
    ) -> AsyncIterator[ProviderDelta]:
        for chunk in self._chunks:
            yield TextDelta(text=chunk)
        if self._error is not None:
            raise self._error

"""A scripted provider for testing the agent loop without a network."""

from __future__ import annotations

from collections.abc import AsyncIterator

from saddlery.llm.base import ProviderDelta, TextDelta
from saddlery.messages import Message


class FakeProvider:
    def __init__(self, chunks: list[str], *, error: Exception | None = None) -> None:
        self._chunks = chunks
        self._error = error

    async def stream(
        self, messages: list[Message], *, model: str = "fake"
    ) -> AsyncIterator[ProviderDelta]:
        for chunk in self._chunks:
            yield TextDelta(text=chunk)
        if self._error is not None:
            raise self._error

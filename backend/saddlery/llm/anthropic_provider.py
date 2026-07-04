"""Native Anthropic provider. Default model is cheap Haiku for testing.

Keeps Claude-native features available (prompt caching, adaptive thinking) for
thinking-capable models; Haiku 4.5 supports neither, so neither is set here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import anthropic

from saddlery.llm.base import LLMProvider, ProviderDelta, TextDelta

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from saddlery.messages import Message


def _content_for_wire(content: str | list) -> str | list[dict]:
    """Serialize message content for the Anthropic wire format.

    Anthropic's API accepts both plain strings and lists of content blocks.
    """
    if isinstance(content, str):
        return content
    return [block.model_dump(mode="json") for block in content]


def split_system(messages: list[Message]) -> tuple[str | None, list[dict]]:
    """Separate system messages (Anthropic's `system` param) from the conversation."""
    system_parts = [
        m.content for m in messages if m.role == "system" and isinstance(m.content, str)
    ]
    convo = [
        {"role": m.role, "content": _content_for_wire(m.content)}
        for m in messages
        if m.role != "system"
    ]
    system = "\n\n".join(system_parts) if system_parts else None
    return system, convo


class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        client: anthropic.AsyncAnthropic | None = None,
        *,
        max_tokens: int = 1024,
    ) -> None:
        self._client = client or anthropic.AsyncAnthropic()
        self._max_tokens = max_tokens

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: list[dict] | None = None,
    ) -> AsyncIterator[ProviderDelta]:
        system, convo = split_system(messages)
        kwargs: dict = {"model": model, "max_tokens": self._max_tokens, "messages": convo}
        if system is not None:
            kwargs["system"] = system
        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield TextDelta(text=text)

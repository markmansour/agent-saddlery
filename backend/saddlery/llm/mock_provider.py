"""Mock LLM provider for testing and demos — responds without API calls."""

from __future__ import annotations

from typing import TYPE_CHECKING

from saddlery.llm.base import LLMProvider, ProviderDelta, TextDelta

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from saddlery.messages import Message


class MockLMProvider(LLMProvider):
    """Mock provider that returns canned responses for testing."""

    def __init__(self, response: str = "I'm a mock assistant. This is a demo response."):
        self.response = response
        self.call_count = 0

    async def stream(self, messages: list[Message], *, model: str) -> AsyncIterator[ProviderDelta]:
        """Stream a mock response (Protocol method name is 'stream', not 'stream_completion')."""
        self.call_count += 1

        # Extract the user's message for a more contextual response
        last_user_msg_str = None
        for msg in reversed(messages):
            if msg.role == "user" and isinstance(msg.content, str):
                last_user_msg_str = msg.content
                break

        # Generate context-aware responses
        if last_user_msg_str:
            if "2+2" in last_user_msg_str or "plus" in last_user_msg_str:
                response = "2 + 2 = 4"
            elif "hello" in last_user_msg_str.lower():
                response = "Hello! I'm a mock assistant. How can I help you?"
            elif "time" in last_user_msg_str.lower():
                response = (
                    "I don't have access to real-time information, but I can help with questions!"
                )
            else:
                response = (
                    f"You said: '{last_user_msg_str}'\n\n"
                    "I'm a mock assistant in test mode. In production, I would call Claude!"
                )
        else:
            response = self.response

        # Stream the response one character at a time
        for char in response:
            yield TextDelta(text=char)

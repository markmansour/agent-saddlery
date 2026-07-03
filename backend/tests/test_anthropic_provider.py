import os

import pytest

from saddlery.llm.anthropic_provider import AnthropicProvider, split_system
from saddlery.messages import Message


def test_split_system_extracts_system_and_keeps_conversation():
    msgs = [
        Message(role="system", content="be terse"),
        Message(role="user", content="hi"),
        Message(role="assistant", content="hello"),
    ]
    system, convo = split_system(msgs)
    assert system == "be terse"
    assert convo == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]


def test_split_system_returns_none_when_no_system():
    system, convo = split_system([Message(role="user", content="hi")])
    assert system is None
    assert convo == [{"role": "user", "content": "hi"}]


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no ANTHROPIC_API_KEY")
async def test_anthropic_provider_streams_live():
    provider = AnthropicProvider()
    chunks = [
        d.text
        async for d in provider.stream(
            [Message(role="user", content="Reply with exactly the word: pong")],
            model="claude-haiku-4-5",
        )
    ]
    assert "".join(chunks).strip() != ""

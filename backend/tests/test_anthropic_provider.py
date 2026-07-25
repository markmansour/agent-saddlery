import os

import pytest

from saddlery.llm.anthropic_provider import AnthropicProvider, split_system
from saddlery.llm.base import TextDelta, ToolCallDelta
from saddlery.messages import Message, ToolUseBlock


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


def test_split_system_handles_block_list_content():
    """Verify split_system serializes block-list Message content correctly."""
    messages = [
        Message(role="system", content="You are helpful."),
        Message(
            role="assistant",
            content=[ToolUseBlock(id="t1", name="read_file", input={"path": "foo.txt"})],
        ),
    ]
    system, convo = split_system(messages)

    assert system == "You are helpful."
    assert len(convo) == 1
    assert convo[0]["role"] == "assistant"
    # content should be serialized to a list of dicts
    assert isinstance(convo[0]["content"], list)
    assert convo[0]["content"][0]["type"] == "tool_use"


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no ANTHROPIC_API_KEY")
async def test_anthropic_provider_streams_live():
    provider = AnthropicProvider()
    chunks = [
        d.text
        async for d in provider.stream(
            [Message(role="user", content="Reply with exactly the word: pong")],
            model="claude-haiku-4-5",
        )
        if isinstance(d, TextDelta)
    ]
    assert "".join(chunks).strip() != ""


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no ANTHROPIC_API_KEY")
async def test_anthropic_provider_emits_tool_call_on_real_api(tmp_path):
    """Live test: verify ToolCallDelta is emitted for a real tool-use call."""
    # Create a temp file to read
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello from the file")

    # Define a tool schema asking Claude to call it
    tools = [
        {
            "name": "read_file",
            "description": "Read a text file",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        }
    ]

    # Ask Claude to read the file
    provider = AnthropicProvider()
    messages = [
        Message(
            role="user",
            content=f"Please call read_file with path={test_file}",
        )
    ]

    # Collect all deltas
    deltas = [d async for d in provider.stream(messages, model="claude-haiku-4-5", tools=tools)]

    # Verify at least one ToolCallDelta was emitted
    tool_call_deltas = [d for d in deltas if isinstance(d, ToolCallDelta)]
    assert len(tool_call_deltas) >= 1
    assert tool_call_deltas[0].name == "read_file"
    # input should be a dict with the path argument
    assert isinstance(tool_call_deltas[0].input, dict)

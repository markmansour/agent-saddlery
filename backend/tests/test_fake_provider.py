import pytest

from saddlery.llm.base import TextDelta, ToolCallDelta
from saddlery.llm.fake import FakeProvider
from saddlery.messages import Message


async def test_fake_provider_yields_text_deltas():
    provider = FakeProvider(["Hel", "lo"])
    out = [
        d.text
        async for d in provider.stream([Message(role="user", content="hi")], model="x")
        if isinstance(d, TextDelta)
    ]
    assert out == ["Hel", "lo"]


async def test_fake_provider_raises_after_chunks():
    provider = FakeProvider(["a"], error=RuntimeError("boom"))
    collected = []
    with pytest.raises(RuntimeError, match="boom"):
        async for delta in provider.stream([], model="x"):
            if isinstance(delta, TextDelta):
                collected.append(delta.text)
    assert collected == ["a"]


async def test_fake_provider_emits_tool_calls_on_first_call():
    """First call with tool_calls yields them; subsequent calls yield chunks."""
    fake = FakeProvider(
        chunks=["Here's the result"],
        tool_calls=[ToolCallDelta(id="t1", name="read_file", input={"path": "foo.txt"})],
    )

    # First call: tool_calls
    deltas1 = [d async for d in fake.stream([], model="fake")]
    assert len(deltas1) == 1
    assert isinstance(deltas1[0], ToolCallDelta)
    assert deltas1[0].id == "t1"
    assert deltas1[0].name == "read_file"
    assert deltas1[0].input == {"path": "foo.txt"}

    # Second call: text chunks
    deltas2 = [d async for d in fake.stream([], model="fake")]
    assert len(deltas2) == 1
    assert isinstance(deltas2[0], TextDelta)
    assert deltas2[0].text == "Here's the result"


async def test_fake_provider_multiple_tool_calls_on_first_call():
    """First call can emit multiple tool calls in sequence."""
    fake = FakeProvider(
        chunks=["Done"],
        tool_calls=[
            ToolCallDelta(id="t1", name="read_file", input={"path": "a.txt"}),
            ToolCallDelta(id="t2", name="read_file", input={"path": "b.txt"}),
        ],
    )

    deltas = [d async for d in fake.stream([], model="fake")]
    assert len(deltas) == 2
    assert all(isinstance(d, ToolCallDelta) for d in deltas)
    ids = [d.id for d in deltas if isinstance(d, ToolCallDelta)]
    assert ids == ["t1", "t2"]


async def test_fake_provider_no_tool_calls_falls_through_to_chunks():
    """With no tool_calls, FakeProvider works normally (backwards compatible)."""
    fake = FakeProvider(chunks=["Normal", "response"])

    deltas = [d async for d in fake.stream([], model="fake")]
    assert len(deltas) == 2
    assert all(isinstance(d, TextDelta) for d in deltas)
    texts = [d.text for d in deltas if isinstance(d, TextDelta)]
    assert texts == ["Normal", "response"]


async def test_fake_provider_empty_tool_calls_list_falls_through():
    """Empty tool_calls list is treated as no scripting."""
    fake = FakeProvider(chunks=["Text"], tool_calls=[])

    deltas = [d async for d in fake.stream([], model="fake")]
    assert len(deltas) == 1
    assert isinstance(deltas[0], TextDelta)
    assert deltas[0].text == "Text"


async def test_fake_provider_tool_call_then_error_on_second_call():
    """Tool call on first turn, then error on second call."""
    fake = FakeProvider(
        chunks=["Should not be yielded"],
        error=RuntimeError("boom"),
        tool_calls=[ToolCallDelta(id="t1", name="test", input={})],
    )

    # First call: tool call
    deltas1 = [d async for d in fake.stream([], model="fake")]
    assert len(deltas1) == 1
    assert isinstance(deltas1[0], ToolCallDelta)

    # Second call: error
    with pytest.raises(RuntimeError, match="boom"):
        async for _ in fake.stream([], model="fake"):
            pass


async def test_fake_provider_tool_call_with_complex_input():
    """Tool calls with nested/complex input are preserved."""
    complex_input = {
        "path": "/foo/bar",
        "options": {"recursive": True, "depth": 5},
        "filter": ["*.txt", "*.md"],
    }
    fake = FakeProvider(
        chunks=[],
        tool_calls=[ToolCallDelta(id="t1", name="list_files", input=complex_input)],
    )

    deltas = [d async for d in fake.stream([], model="fake")]
    assert len(deltas) == 1
    assert isinstance(deltas[0], ToolCallDelta)
    assert deltas[0].input == complex_input

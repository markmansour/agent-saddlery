from saddlery.agent import Agent
from saddlery.events import UserMessage
from saddlery.llm.base import ToolCallDelta
from saddlery.llm.fake import FakeProvider
from saddlery.session import Session
from saddlery.tools.base import ToolExecutionResult
from saddlery.tools.registry import ToolRegistry
from saddlery.transport.recording import RecordingSink


def _session_with_user(text: str) -> Session:
    s = Session(session_id="s1", principal="local")
    s.append(UserMessage(session_id="s1", principal="local", content=text))
    return s


class _StubTool:
    """A simple test tool that returns a fixed response."""

    def __init__(
        self,
        name: str = "test_tool",
        response: str = "success",
        is_error: bool = False,
    ) -> None:
        self.name = name
        self.description = f"Test tool: {name}"
        self.input_schema = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }
        self._response = response
        self._is_error = is_error

    async def call(self, arguments: dict) -> ToolExecutionResult:
        return ToolExecutionResult(self._response, is_error=self._is_error)


async def test_run_emits_ordered_events_and_final_message():
    session = _session_with_user("hello")
    sink = RecordingSink()
    agent = Agent(provider=FakeProvider(["Hel", "lo"]))

    await agent.run(session, sink)

    assert [e.type for e in sink.events] == [
        "run_started",
        "assistant_message_delta",
        "assistant_message_delta",
        "assistant_message",
        "run_finished",
    ]
    final = next(e for e in sink.events if e.type == "assistant_message")
    assert final.content == "Hello"
    # Events were also appended to the session log (source of truth).
    assert [e.type for e in session.events][0] == "user_message"
    assert session.events[-1].type == "run_finished"


async def test_run_records_error_and_still_finishes():
    session = _session_with_user("x")
    sink = RecordingSink()
    agent = Agent(provider=FakeProvider([], error=RuntimeError("boom")))

    await agent.run(session, sink)

    types = [e.type for e in sink.events]
    assert "error" in types
    assert types[-1] == "run_finished"
    err = next(e for e in sink.events if e.type == "error")
    assert "boom" in err.message


async def test_run_executes_tool_call_round_trip():
    """Full round-trip: text + tool call, execute tool, loop back for more text."""
    session = _session_with_user("call a tool")
    sink = RecordingSink()
    stub_tool = _StubTool(name="get_info", response="file contents")
    tools = ToolRegistry([stub_tool])

    # First call: emit a tool call. Second call (after tool result added to session):
    # emit text, then no more tool calls (done).
    fake = FakeProvider(
        chunks=["Response text"],
        tool_calls=[ToolCallDelta(id="call-1", name="get_info", input={"query": "test"})],
    )
    agent = Agent(provider=fake, tools=tools)

    await agent.run(session, sink)

    # Expected sequence:
    # run_started
    # tool_call (for the tool call in first iteration)
    # tool_result (result of executing get_info)
    # assistant_message_delta (from second iteration)
    # assistant_message (final message from second iteration)
    # run_finished
    types = [e.type for e in sink.events]
    assert types == [
        "run_started",
        "tool_call",
        "tool_result",
        "assistant_message_delta",
        "assistant_message",
        "run_finished",
    ]

    # Verify tool_call_id correlation
    tool_call_event = next(e for e in sink.events if e.type == "tool_call")
    assert tool_call_event.tool_call_id == "call-1"
    assert tool_call_event.tool_name == "get_info"
    assert tool_call_event.arguments == {"query": "test"}

    tool_result_event = next(e for e in sink.events if e.type == "tool_result")
    assert tool_result_event.tool_call_id == "call-1"
    assert tool_result_event.content == "file contents"
    assert tool_result_event.is_error is False
    assert tool_result_event.source == "untrusted"

    # Verify the final response text
    final_msg = next(e for e in sink.events if e.type == "assistant_message")
    assert final_msg.content == "Response text"


async def test_run_unknown_tool_name_produces_error_result():
    """If provider emits a tool call for non-existent tool, result is error."""
    session = _session_with_user("call unknown tool")
    sink = RecordingSink()
    tools = ToolRegistry([])  # No tools registered

    fake = FakeProvider(
        chunks=[],  # No text on first call
        tool_calls=[ToolCallDelta(id="call-2", name="nonexistent", input={"x": 1})],
    )
    agent = Agent(provider=fake, tools=tools)

    await agent.run(session, sink)

    # Should still complete: run_started, tool_call, tool_result (error), run_finished
    types = [e.type for e in sink.events]
    assert types[0] == "run_started"
    assert types[-1] == "run_finished"

    tool_result_event = next(e for e in sink.events if e.type == "tool_result")
    assert tool_result_event.tool_call_id == "call-2"
    assert "unknown tool 'nonexistent'" in tool_result_event.content
    assert tool_result_event.is_error is True


async def test_run_max_tool_iterations_exceeded():
    """Agent detects infinite loop and emits ErrorEvent, still finishes gracefully."""
    session = _session_with_user("infinite loop test")
    sink = RecordingSink()
    tools = ToolRegistry([_StubTool()])

    # This provider always emits a tool call (never text), forcing infinite loop
    class InfiniteToolProvider:
        async def stream(self, messages, *, model, tools=None):
            yield ToolCallDelta(id="call-3", name="test_tool", input={})

    fake = InfiniteToolProvider()
    agent = Agent(provider=fake, tools=tools, max_tool_iterations=3)

    await agent.run(session, sink)

    types = [e.type for e in sink.events]
    # Should have: run_started, then N iterations of (tool_call, tool_result),
    # then error_event for exceeding iterations, then run_finished
    assert types[0] == "run_started"
    assert types[-1] == "run_finished"
    assert "error" in types

    error_event = next(e for e in sink.events if e.type == "error")
    assert "Exceeded max_tool_iterations (3)" in error_event.message

    # Verify loop ran max_tool_iterations times
    tool_call_count = sum(1 for e in sink.events if e.type == "tool_call")
    assert tool_call_count == 3

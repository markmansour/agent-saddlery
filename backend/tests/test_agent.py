import asyncio
from typing import ClassVar

from saddlery.agent import Agent
from saddlery.events import ToolResult, UserMessage
from saddlery.llm.base import TextDelta, ToolCallDelta
from saddlery.llm.fake import FakeProvider
from saddlery.permissions.gate import PermissionGate
from saddlery.session import Session
from saddlery.tools.base import Capability, ResourceError, ToolExecutionResult
from saddlery.tools.registry import ToolRegistry
from saddlery.transport.recording import RecordingSink


def _session_with_user(text: str) -> Session:
    s = Session(session_id="s1", principal="local")
    s.append(UserMessage(session_id="s1", principal="local", content=text))
    return s


class _PolicyStub:
    """Capability/resource/detail members every stub tool needs."""

    capability: Capability = "write"

    def resource(self, arguments: dict) -> tuple[str, ...]:
        return ("stub",)

    def detail(self, arguments: dict) -> object | None:
        return None


class _StubTool(_PolicyStub):
    """A simple test tool that returns a fixed response."""

    def __init__(
        self,
        name: str = "test_tool",
        response: str = "success",
        is_error: bool = False,
        capability: Capability = "write",
        resource: tuple[str, ...] = ("stub",),
    ) -> None:
        self.name = name
        self.capability = capability
        self._resource = resource
        self.description = f"Test tool: {name}"
        self.input_schema = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }
        self._response = response
        self._is_error = is_error

    def resource(self, arguments: dict) -> tuple[str, ...]:
        return self._resource

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


async def test_run_denied_tool_call_short_circuits_without_calling_tool():
    """A gate that denies a tool never calls tool.call(); ToolResult reflects the denial."""
    session = _session_with_user("call a tool")
    sink = RecordingSink()

    class _RaisingTool(_PolicyStub):
        """A tool that would fail the test if call() were ever invoked."""

        name: ClassVar[str] = "get_info"
        description: ClassVar[str] = "test"
        input_schema: ClassVar[dict] = {"type": "object", "properties": {}}

        async def call(self, arguments: dict) -> ToolExecutionResult:
            raise AssertionError("call() should not have been invoked for a denied tool")

    tools = ToolRegistry([_RaisingTool()])
    gate = PermissionGate(allow=set(), deny={"get_info"})

    fake = FakeProvider(
        chunks=["done"],
        tool_calls=[ToolCallDelta(id="call-1", name="get_info", input={"query": "x"})],
    )
    agent = Agent(provider=fake, tools=tools, permission_gate=gate)

    await agent.run(session, sink)

    tool_result_event = next(e for e in sink.events if e.type == "tool_result")
    assert tool_result_event.tool_call_id == "call-1"
    assert tool_result_event.is_error is True
    assert "denied" in tool_result_event.content.lower()


async def test_run_allowed_tool_call_executes_normally():
    """A gate that allows a tool proceeds to call tool.call() as before."""
    session = _session_with_user("call a tool")
    sink = RecordingSink()
    stub_tool = _StubTool(name="get_info", response="file contents")
    tools = ToolRegistry([stub_tool])
    gate = PermissionGate(allow={"get_info"}, deny=set())

    fake = FakeProvider(
        chunks=["Response text"],
        tool_calls=[ToolCallDelta(id="call-1", name="get_info", input={"query": "test"})],
    )
    agent = Agent(provider=fake, tools=tools, permission_gate=gate)

    await agent.run(session, sink)

    tool_result_event = next(e for e in sink.events if e.type == "tool_result")
    assert tool_result_event.content == "file contents"
    assert tool_result_event.is_error is False


async def test_run_without_permission_gate_behaves_as_before():
    """Agent without permission_gate (the default) is unaffected — existing behavior."""
    session = _session_with_user("call a tool")
    sink = RecordingSink()
    stub_tool = _StubTool(name="get_info", response="file contents")
    tools = ToolRegistry([stub_tool])

    fake = FakeProvider(
        chunks=["Response text"],
        tool_calls=[ToolCallDelta(id="call-1", name="get_info", input={"query": "test"})],
    )
    agent = Agent(provider=fake, tools=tools)  # no permission_gate

    await agent.run(session, sink)

    tool_result_event = next(e for e in sink.events if e.type == "tool_result")
    assert tool_result_event.content == "file contents"
    assert tool_result_event.is_error is False


async def test_run_ask_decision_suspends_until_resolved():
    """A gate that returns 'ask' suspends the run; resolve_permission() lets it continue."""
    session = _session_with_user("call a tool")
    sink = RecordingSink()
    stub_tool = _StubTool(name="write_file", response="wrote it")
    tools = ToolRegistry([stub_tool])
    gate = PermissionGate(allow=set(), deny=set())  # unlisted -> ask

    fake = FakeProvider(
        chunks=["Response text"],
        tool_calls=[ToolCallDelta(id="call-1", name="write_file", input={"path": "x"})],
    )
    agent = Agent(provider=fake, tools=tools, permission_gate=gate)

    run_task = asyncio.ensure_future(agent.run(session, sink))

    # Give the run loop a chance to reach the ask-suspend point.
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    request_event = next(e for e in sink.events if e.type == "permission_request")
    assert request_event.tool_call_id == "call-1"
    assert request_event.tool_name == "write_file"
    assert not run_task.done()  # still suspended, waiting for a decision

    await agent.resolve_permission("call-1", "allow")
    await run_task

    tool_result_event = next(e for e in sink.events if e.type == "tool_result")
    assert tool_result_event.content == "wrote it"
    assert tool_result_event.is_error is False

    decision_event = next(e for e in sink.events if e.type == "permission_decision")
    assert decision_event.tool_call_id == "call-1"
    assert decision_event.decision == "allow"


async def test_run_ask_deny_produces_error_result_without_calling_tool():
    """Denying via resolve_permission() short-circuits to an error ToolResult."""
    session = _session_with_user("call a tool")
    sink = RecordingSink()

    class _RaisingTool(_PolicyStub):
        name: ClassVar[str] = "write_file"
        description: ClassVar[str] = "test"
        input_schema: ClassVar[dict] = {"type": "object", "properties": {}}

        async def call(self, arguments: dict) -> ToolExecutionResult:
            raise AssertionError("call() should not have been invoked for a denied tool")

    tools = ToolRegistry([_RaisingTool()])
    gate = PermissionGate(allow=set(), deny=set())  # unlisted -> ask

    fake = FakeProvider(
        chunks=["done"],
        tool_calls=[ToolCallDelta(id="call-2", name="write_file", input={"path": "x"})],
    )
    agent = Agent(provider=fake, tools=tools, permission_gate=gate)

    run_task = asyncio.ensure_future(agent.run(session, sink))
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    await agent.resolve_permission("call-2", "deny")
    await run_task

    tool_result_event = next(e for e in sink.events if e.type == "tool_result")
    assert tool_result_event.is_error is True
    assert "denied" in tool_result_event.content.lower()


async def test_run_remembers_ask_decision_for_second_call_in_same_run():
    """After one 'allow' decision, a second call to the same tool in a later iteration
    does not ask again (PermissionGate.remember() was invoked)."""
    session = _session_with_user("call a tool twice")
    sink = RecordingSink()
    stub_tool = _StubTool(name="write_file", response="ok")
    tools = ToolRegistry([stub_tool])
    gate = PermissionGate(allow=set(), deny=set())

    class TwoRoundProvider:
        """Emits a tool call for two iterations, then text — matches FakeProvider's shape."""

        def __init__(self) -> None:
            self._call_count = 0

        async def stream(self, messages, *, model, tools=None):
            self._call_count += 1
            if self._call_count <= 2:
                yield ToolCallDelta(
                    id=f"call-{self._call_count}", name="write_file", input={"path": "x"}
                )
            else:
                yield TextDelta(text="done")

    agent = Agent(provider=TwoRoundProvider(), tools=tools, permission_gate=gate)

    run_task = asyncio.ensure_future(agent.run(session, sink))
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    await agent.resolve_permission("call-1", "allow")

    # Give the loop time to advance to the second tool call before asserting no second ask.
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    await run_task

    request_events = [e for e in sink.events if e.type == "permission_request"]
    assert len(request_events) == 1  # only asked once, second call was remembered


async def test_permission_request_carries_capability_resource_and_taint():
    session = _session_with_user("write it")
    sink = RecordingSink()
    tool = _StubTool(name="write_file", response="ok", resource=("out.txt",))
    agent = Agent(
        provider=FakeProvider(
            chunks=["done"],
            tool_calls=[ToolCallDelta(id="c1", name="write_file", input={"path": "out.txt"})],
        ),
        tools=ToolRegistry([tool]),
        permission_gate=PermissionGate(),
    )

    run_task = asyncio.ensure_future(agent.run(session, sink))
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    request_event = next(e for e in sink.events if e.type == "permission_request")
    assert request_event.capability == "write"
    assert request_event.resource == ["out.txt"]
    assert request_event.tainted is False
    await agent.resolve_permission("c1", "allow")
    await run_task


async def test_allowlisted_write_asks_when_a_tool_result_precedes_it():
    session = _session_with_user("fix it")
    session.append(ToolResult(session_id="s1", principal="local", tool_call_id="old", content="x"))
    sink = RecordingSink()
    tool = _StubTool(name="write_file", response="ok")
    agent = Agent(
        provider=FakeProvider(
            chunks=["done"],
            tool_calls=[ToolCallDelta(id="c1", name="write_file", input={"path": "p"})],
        ),
        tools=ToolRegistry([tool]),
        permission_gate=PermissionGate(allow={"write_file"}),
    )

    run_task = asyncio.ensure_future(agent.run(session, sink))
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    request_event = next(e for e in sink.events if e.type == "permission_request")
    assert request_event.tainted is True
    await agent.resolve_permission("c1", "deny")
    await run_task


async def test_invalid_resource_becomes_an_error_result_without_calling_the_tool():
    class _BadResource(_PolicyStub):
        name = "write_file"
        description = "d"
        input_schema: ClassVar[dict] = {"type": "object", "properties": {}}

        def resource(self, arguments):
            raise ResourceError("escapes root")

        async def call(self, arguments):
            raise AssertionError("must not run")

    session = _session_with_user("go")
    sink = RecordingSink()
    agent = Agent(
        provider=FakeProvider(
            chunks=["done"],
            tool_calls=[ToolCallDelta(id="c1", name="write_file", input={"path": "../x"})],
        ),
        tools=ToolRegistry([_BadResource()]),
        permission_gate=PermissionGate(allow={"write_file"}),
    )

    await agent.run(session, sink)

    result = next(e for e in sink.events if e.type == "tool_result")
    assert result.is_error is True
    assert "Invalid arguments" in result.content


async def test_target_changing_after_approval_blocks_the_call():
    class _Shifty(_PolicyStub):
        name = "write_file"
        description = "d"
        input_schema: ClassVar[dict] = {"type": "object", "properties": {}}

        def __init__(self):
            self.resources = [("approved.txt",), ("elsewhere.txt",)]

        def resource(self, arguments):
            return self.resources.pop(0)

        async def call(self, arguments):
            raise AssertionError("must not run")

    session = _session_with_user("go")
    sink = RecordingSink()
    agent = Agent(
        provider=FakeProvider(
            chunks=["done"],
            tool_calls=[ToolCallDelta(id="c1", name="write_file", input={"path": "p"})],
        ),
        tools=ToolRegistry([_Shifty()]),
        permission_gate=PermissionGate(allow={"write_file"}),
    )

    await agent.run(session, sink)

    result = next(e for e in sink.events if e.type == "tool_result")
    assert result.is_error is True
    assert "changed after approval" in result.content


async def test_rejected_shell_command_reports_why():
    from saddlery.permissions.shell import classify

    class _Shell(_PolicyStub):
        name = "shell"
        capability: Capability = "exec"
        description = "d"
        input_schema: ClassVar[dict] = {"type": "object", "properties": {}}

        def resource(self, arguments):
            return classify(arguments["command"]).argv or ()

        def detail(self, arguments):
            return classify(arguments["command"])

        async def call(self, arguments):
            raise AssertionError("must not run")

    session = _session_with_user("go")
    sink = RecordingSink()
    agent = Agent(
        provider=FakeProvider(
            chunks=["done"],
            tool_calls=[ToolCallDelta(id="c1", name="shell", input={"command": "ls; id"})],
        ),
        tools=ToolRegistry([_Shell()]),
        permission_gate=PermissionGate(allow={"shell"}),
    )

    await agent.run(session, sink)

    result = next(e for e in sink.events if e.type == "tool_result")
    assert result.is_error is True
    assert "Run each command separately" in result.content


async def test_unexpected_gate_decision_does_not_run_the_tool():
    class _OddGate(PermissionGate):
        async def check(self, request):  # type: ignore[override]
            return "Allow"

    class _Raising(_PolicyStub):
        name = "write_file"
        description = "d"
        input_schema: ClassVar[dict] = {"type": "object", "properties": {}}

        async def call(self, arguments):
            raise AssertionError("must not run")

    session = _session_with_user("go")
    sink = RecordingSink()
    agent = Agent(
        provider=FakeProvider(
            chunks=["done"],
            tool_calls=[ToolCallDelta(id="c1", name="write_file", input={"path": "p"})],
        ),
        tools=ToolRegistry([_Raising()]),
        permission_gate=_OddGate(),
    )

    await agent.run(session, sink)

    result = next(e for e in sink.events if e.type == "tool_result")
    assert result.is_error is True
    assert "denied" in result.content.lower()


async def test_nul_byte_path_becomes_an_error_result_not_an_orphan_tool_call(tmp_path):
    from saddlery.tools.write_file import FileWriteTool

    session = _session_with_user("go")
    sink = RecordingSink()
    agent = Agent(
        provider=FakeProvider(
            chunks=["done"],
            tool_calls=[ToolCallDelta(id="c1", name="write_file", input={"path": "a\x00b"})],
        ),
        tools=ToolRegistry([FileWriteTool(tmp_path)]),
        permission_gate=PermissionGate(allow={"write_file"}),
    )

    await agent.run(session, sink)

    assert not any(e.type == "error" for e in sink.events)
    result = next(e for e in sink.events if e.type == "tool_result")
    assert result.tool_call_id == "c1"
    assert result.is_error is True
    assert "Invalid arguments" in result.content

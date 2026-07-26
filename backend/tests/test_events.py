from pydantic import TypeAdapter

from saddlery.events import (
    AssistantMessage,
    Event,
    RunStarted,
    ToolCall,
    ToolResult,
    UserMessage,
)


def test_event_has_identity_and_metadata():
    e = UserMessage(session_id="s1", principal="local", content="hi")
    assert e.type == "user_message"
    assert e.id  # auto-generated
    assert e.timestamp is not None
    assert e.session_id == "s1"
    assert e.principal == "local"


def test_event_json_roundtrip_via_discriminated_union():
    original = AssistantMessage(session_id="s1", principal="local", content="hello there")
    data = original.model_dump_json()
    parsed = TypeAdapter(Event).validate_json(data)
    assert isinstance(parsed, AssistantMessage)
    assert parsed.content == "hello there"


def test_run_started_is_distinct_type():
    assert RunStarted(session_id="s", principal="p").type == "run_started"


def test_tool_call_event():
    e = ToolCall(
        session_id="s1",
        principal="local",
        tool_call_id="t1",
        tool_name="read_file",
        arguments={"path": "foo.txt"},
    )
    assert e.type == "tool_call"
    assert e.tool_call_id == "t1"
    assert e.tool_name == "read_file"
    assert e.id  # auto-generated
    assert e.timestamp is not None


def test_tool_result_event_has_untrusted_source_by_default():
    e = ToolResult(
        session_id="s1",
        principal="local",
        tool_call_id="t1",
        content="file contents",
    )
    assert e.type == "tool_result"
    assert e.source == "untrusted"
    assert e.is_error is False


def test_tool_result_error_case():
    e = ToolResult(
        session_id="s1",
        principal="local",
        tool_call_id="t1",
        content="File not found",
        is_error=True,
    )
    assert e.is_error is True
    assert e.source == "untrusted"


def test_tool_call_json_roundtrip():
    original = ToolCall(
        session_id="s1",
        principal="local",
        tool_call_id="t1",
        tool_name="read_file",
        arguments={"path": "foo.txt"},
    )
    data = original.model_dump_json()
    parsed = TypeAdapter(Event).validate_json(data)
    assert isinstance(parsed, ToolCall)
    assert parsed.tool_call_id == "t1"
    assert parsed.arguments == {"path": "foo.txt"}


def test_tool_result_json_roundtrip():
    original = ToolResult(
        session_id="s1",
        principal="local",
        tool_call_id="t1",
        content="file contents",
        is_error=False,
    )
    data = original.model_dump_json()
    parsed = TypeAdapter(Event).validate_json(data)
    assert isinstance(parsed, ToolResult)
    assert parsed.source == "untrusted"
    assert parsed.is_error is False

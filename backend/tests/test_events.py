from pydantic import TypeAdapter

from saddlery.events import (
    AssistantMessage,
    Event,
    RunStarted,
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

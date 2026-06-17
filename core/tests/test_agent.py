from saddlery.agent import Agent
from saddlery.events import UserMessage
from saddlery.llm.fake import FakeProvider
from saddlery.session import Session
from saddlery.transport.recording import RecordingSink


def _session_with_user(text: str) -> Session:
    s = Session(session_id="s1", principal="local")
    s.append(UserMessage(session_id="s1", principal="local", content=text))
    return s


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

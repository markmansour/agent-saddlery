"""SessionRunner serializes turns: a message sent mid-run is queued, not interleaved."""

from __future__ import annotations

from saddlery.agent import Agent
from saddlery.cli.runner import SessionRunner
from saddlery.llm.fake import FakeProvider
from saddlery.session import Session
from saddlery.transport.recording import RecordingSink


def _types(session):
    return [e.type for e in session.events]


async def test_second_message_is_appended_only_after_the_first_run_finishes():
    session = Session(session_id="s1", principal="local")
    sink = RecordingSink()
    runner = SessionRunner(Agent(provider=FakeProvider(["ok"])), session, sink)

    runner.submit("one")
    runner.submit("two")  # sent while "one" is still pending or running
    await runner.wait()

    types = _types(session)
    assert types.count("user_message") == 2
    first_finish = types.index("run_finished")
    second_user = [i for i, t in enumerate(types) if t == "user_message"][1]
    assert second_user > first_finish


async def test_messages_run_in_submission_order():
    session = Session(session_id="s1", principal="local")
    runner = SessionRunner(Agent(provider=FakeProvider(["ok"])), session, RecordingSink())

    runner.submit("first")
    runner.submit("second")
    runner.submit("third")
    await runner.wait()

    user_texts = [e.content for e in session.events if e.type == "user_message"]
    assert user_texts == ["first", "second", "third"]


async def test_runner_restarts_after_going_idle():
    session = Session(session_id="s1", principal="local")
    runner = SessionRunner(Agent(provider=FakeProvider(["ok"])), session, RecordingSink())

    runner.submit("one")
    await runner.wait()
    runner.submit("two")
    await runner.wait()

    assert [e.content for e in session.events if e.type == "user_message"] == ["one", "two"]


async def test_wait_with_nothing_submitted_returns():
    session = Session(session_id="s1", principal="local")
    runner = SessionRunner(Agent(provider=FakeProvider([])), session, RecordingSink())
    await runner.wait()

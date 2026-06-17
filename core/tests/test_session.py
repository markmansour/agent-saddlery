import pytest  # noqa: F401

from saddlery.events import (
    AssistantMessage,
    AssistantMessageDelta,
    RunStarted,
    UserMessage,
)
from saddlery.session import InMemorySessionStore, Session


def _user(s, text):
    s.append(UserMessage(session_id=s.session_id, principal=s.principal, content=text))


def test_to_messages_folds_user_and_final_assistant_only():
    s = Session(session_id="s1", principal="local")
    _user(s, "hello")
    s.append(RunStarted(session_id="s1", principal="local"))
    s.append(AssistantMessageDelta(session_id="s1", principal="local", text="hi "))
    s.append(AssistantMessageDelta(session_id="s1", principal="local", text="there"))
    s.append(AssistantMessage(session_id="s1", principal="local", content="hi there"))

    msgs = s.to_messages()

    assert [(m.role, m.content) for m in msgs] == [
        ("user", "hello"),
        ("assistant", "hi there"),
    ]


def test_events_are_appended_in_order():
    s = Session(session_id="s1", principal="local")
    _user(s, "a")
    _user(s, "b")
    assert [e.content for e in s.events] == ["a", "b"]


async def test_store_get_or_create_returns_same_session():
    store = InMemorySessionStore()
    a = await store.get_or_create("s1", "local")
    b = await store.get_or_create("s1", "local")
    assert a is b
    assert a.session_id == "s1"
    assert a.principal == "local"

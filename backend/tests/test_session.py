from saddlery.events import (
    AssistantMessage,
    AssistantMessageDelta,
    RunStarted,
    ToolCall,
    ToolResult,
    UserMessage,
)
from saddlery.messages import ToolResultBlock, ToolUseBlock
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
    assert [e.content for e in s.events if isinstance(e, UserMessage)] == ["a", "b"]


def test_to_messages_folds_tool_call_and_result():
    s = Session(session_id="s1", principal="local")
    _user(s, "read foo.txt")
    s.append(
        ToolCall(
            session_id="s1",
            principal="local",
            tool_call_id="t1",
            tool_name="read_file",
            arguments={"path": "foo.txt"},
        )
    )
    s.append(
        ToolResult(
            session_id="s1",
            principal="local",
            tool_call_id="t1",
            content="file contents",
        )
    )
    s.append(AssistantMessage(session_id="s1", principal="local", content="here it is"))

    msgs = s.to_messages()

    assert len(msgs) == 4
    assert msgs[0].role == "user"
    assert msgs[0].content == "read foo.txt"

    assert msgs[1].role == "assistant"
    assert isinstance(msgs[1].content, list)
    assert len(msgs[1].content) == 1
    assert isinstance(msgs[1].content[0], ToolUseBlock)
    assert msgs[1].content[0].id == "t1"
    assert msgs[1].content[0].name == "read_file"

    assert msgs[2].role == "user"
    assert isinstance(msgs[2].content, list)
    assert len(msgs[2].content) == 1
    assert isinstance(msgs[2].content[0], ToolResultBlock)
    assert msgs[2].content[0].tool_use_id == "t1"
    assert msgs[2].content[0].content == "file contents"
    assert msgs[2].content[0].is_error is False

    assert msgs[3].role == "assistant"
    assert msgs[3].content == "here it is"


async def test_store_get_or_create_returns_same_session():
    store = InMemorySessionStore()
    a = await store.get_or_create("s1", "local")
    b = await store.get_or_create("s1", "local")
    assert a is b
    assert a.session_id == "s1"
    assert a.principal == "local"

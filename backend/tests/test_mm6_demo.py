"""MM-6 Demo: Inspect AG-UI event stream for one turn.

This test demonstrates:
1. Internal events are emitted (UserMessage → AssistantMessageDelta* → RunFinished)
2. Tokens arrive as TEXT_MESSAGE_CONTENT events
3. Lifecycle is properly bracketed by RUN_START/RUN_FINISH
"""

from saddlery.agent import Agent
from saddlery.events import UserMessage
from saddlery.llm.fake import FakeProvider
from saddlery.session import Session
from saddlery.transport.cli import AgUiSink
from saddlery.transport.recording import AgUiRecordingSink


async def test_mm6_demo_ag_ui_event_stream():
    """Demo: one turn with AG-UI emission — tokens stream as TEXT_MESSAGE_CONTENT."""

    # Setup: session with one user message
    session = Session(session_id="s1", principal="local")
    session.append(UserMessage(session_id="s1", principal="local", content="hello"))

    # Run the agent with AgUiSink wrapping an AgUiRecordingSink to collect AG-UI events
    agui_recorder = AgUiRecordingSink()
    agui_sink = AgUiSink(agui_recorder)
    agent = Agent(provider=FakeProvider(["Hello", " ", "world", "!"]))

    await agent.run(session, agui_sink)

    # Inspect the AG-UI event stream
    agui_events = agui_recorder.events
    print("\n=== AG-UI Event Stream (MM-6 Demo) ===\n")
    for i, event in enumerate(agui_events, 1):
        event_type = event.type
        details = ""
        if hasattr(event, "content"):
            details = f" — content: {event.content!r}"
        elif hasattr(event, "message"):
            details = f" — message: {event.message!r}"
        print(f"{i}. {event_type}{details}")

    # Verify the event sequence
    types = [e.type for e in agui_events]
    print(f"\nEvent sequence: {' → '.join(types)}\n")

    # Assertions (done-check criteria from MM-6)
    assert types[0] == "RUN_START", "Run must start with RUN_START"
    assert types[-1] == "RUN_FINISH", "Run must end with RUN_FINISH"

    # Tokens between lifecycle events
    text_content = [e for e in agui_events if e.type == "TEXT_MESSAGE_CONTENT"]
    assert len(text_content) == 4, "Should have 4 text chunks"
    assert "".join(e.content for e in text_content) == "Hello world!", "Tokens should reassemble"

    print("✓ Tokens arrive as TEXT_MESSAGE_CONTENT, bracketed by run lifecycle")
    print("✓ 4 chunks stream in order: 'Hello' + ' ' + 'world' + '!'")
    print("✓ Lifecycle bracket: RUN_START → [TEXT_MESSAGE_CONTENT x 4] → RUN_FINISH")

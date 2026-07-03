"""Test AG-UI event translation."""

from saddlery.events import AssistantMessageDelta, RunFinished, RunStarted, UserMessage
from saddlery.events import ErrorEvent as InternalErrorEvent
from saddlery.transport.agui import ErrorEvent as AgUiErrorEvent
from saddlery.transport.agui import RunFinishEvent, RunStartEvent, TextMessageContentEvent
from saddlery.transport.cli import AgUiSink
from saddlery.transport.recording import AgUiRecordingSink


async def test_agui_sink_translates_run_lifecycle():
    """RUN_START and RUN_FINISH events bracket a run."""
    internal_events = [
        RunStarted(session_id="s1", principal="local"),
        RunFinished(session_id="s1", principal="local"),
    ]

    consumer = AgUiRecordingSink()
    sink = AgUiSink(consumer)

    for event in internal_events:
        await sink.emit(event)

    assert len(consumer.events) == 2
    assert isinstance(consumer.events[0], RunStartEvent)
    assert isinstance(consumer.events[1], RunFinishEvent)


async def test_agui_sink_translates_text_deltas():
    """Assistant deltas become TEXT_MESSAGE_CONTENT events."""
    deltas = [
        AssistantMessageDelta(session_id="s1", principal="local", text="Hel"),
        AssistantMessageDelta(session_id="s1", principal="local", text="lo"),
    ]

    consumer = AgUiRecordingSink()
    sink = AgUiSink(consumer)

    for delta in deltas:
        await sink.emit(delta)

    assert len(consumer.events) == 2
    assert all(isinstance(e, TextMessageContentEvent) for e in consumer.events)
    assert isinstance(consumer.events[0], TextMessageContentEvent)
    assert isinstance(consumer.events[1], TextMessageContentEvent)
    assert consumer.events[0].content == "Hel"
    assert consumer.events[1].content == "lo"


async def test_agui_sink_translates_errors():
    """Errors map to ERROR events."""
    error = InternalErrorEvent(session_id="s1", principal="local", message="boom")

    consumer = AgUiRecordingSink()
    sink = AgUiSink(consumer)

    await sink.emit(error)

    assert len(consumer.events) == 1
    assert isinstance(consumer.events[0], AgUiErrorEvent)
    assert consumer.events[0].message == "boom"


async def test_agui_sink_brackets_tokens_with_lifecycle():
    """Text tokens are bracketed by RUN_START and RUN_FINISH."""
    events = [
        RunStarted(session_id="s1", principal="local"),
        AssistantMessageDelta(session_id="s1", principal="local", text="Hello"),
        RunFinished(session_id="s1", principal="local"),
    ]

    consumer = AgUiRecordingSink()
    sink = AgUiSink(consumer)

    for event in events:
        await sink.emit(event)

    types = [type(e).__name__ for e in consumer.events]
    assert types == ["RunStartEvent", "TextMessageContentEvent", "RunFinishEvent"]


async def test_agui_sink_ignores_other_events():
    """Non-mapped events (e.g., UserMessage) are ignored silently."""
    events = [
        UserMessage(session_id="s1", principal="local", content="hi"),
        RunStarted(session_id="s1", principal="local"),
        RunFinished(session_id="s1", principal="local"),
    ]

    consumer = AgUiRecordingSink()
    sink = AgUiSink(consumer)

    for event in events:
        await sink.emit(event)

    # Only lifecycle events are emitted; UserMessage is ignored
    assert len(consumer.events) == 2
    assert isinstance(consumer.events[0], RunStartEvent)
    assert isinstance(consumer.events[1], RunFinishEvent)

import io
import json

from saddlery.events import AssistantMessageDelta, ErrorEvent, RunFinished
from saddlery.transport.cli import CliSink
from saddlery.transport.recording import RecordingSink


async def test_recording_sink_collects_events():
    sink = RecordingSink()
    e = RunFinished(session_id="s", principal="p")
    await sink.emit(e)
    assert sink.events == [e]


async def test_cli_sink_writes_events_as_json_lines():
    buf = io.StringIO()
    sink = CliSink(out=buf)
    await sink.emit(AssistantMessageDelta(session_id="s", principal="p", text="hi"))
    await sink.emit(RunFinished(session_id="s", principal="p"))

    lines = buf.getvalue().splitlines()
    assert len(lines) == 2

    delta_line = json.loads(lines[0])
    assert delta_line["event_type"] == "assistant_message_delta"
    assert delta_line["event_data"]["text"] == "hi"

    finished_line = json.loads(lines[1])
    assert finished_line["event_type"] == "run_finished"


async def test_cli_sink_renders_errors():
    buf = io.StringIO()
    sink = CliSink(out=buf)
    await sink.emit(ErrorEvent(session_id="s", principal="p", message="RuntimeError: boom"))
    assert "boom" in buf.getvalue()

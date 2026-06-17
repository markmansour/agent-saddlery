import io

from saddlery.events import AssistantMessageDelta, ErrorEvent, RunFinished
from saddlery.transport.cli import CliSink
from saddlery.transport.recording import RecordingSink


async def test_recording_sink_collects_events():
    sink = RecordingSink()
    e = RunFinished(session_id="s", principal="p")
    await sink.emit(e)
    assert sink.events == [e]


async def test_cli_sink_writes_delta_text_then_newline_on_finish():
    buf = io.StringIO()
    sink = CliSink(out=buf)
    await sink.emit(AssistantMessageDelta(session_id="s", principal="p", text="hi"))
    await sink.emit(RunFinished(session_id="s", principal="p"))
    assert buf.getvalue() == "hi\n"


async def test_cli_sink_renders_errors():
    buf = io.StringIO()
    sink = CliSink(out=buf)
    await sink.emit(ErrorEvent(session_id="s", principal="p", message="RuntimeError: boom"))
    assert "boom" in buf.getvalue()

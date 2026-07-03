"""Transport layer: EventSink protocol and implementations."""

from saddlery.transport.agui import (
    AgUiEvent,
    AgUiEventSink,
    RunFinishEvent,
    RunStartEvent,
    TextMessageContentEvent,
)
from saddlery.transport.agui import (
    ErrorEvent as AgUiErrorEvent,
)
from saddlery.transport.base import EventSink
from saddlery.transport.cli import AgUiSink, CliSink, LoggingSink
from saddlery.transport.recording import (
    AgUiRecordingSink,
    LoggingAgUiSink,
    RecordingSink,
)

__all__ = [
    "AgUiErrorEvent",
    "AgUiEvent",
    "AgUiEventSink",
    "AgUiRecordingSink",
    "AgUiSink",
    "CliSink",
    "EventSink",
    "LoggingAgUiSink",
    "LoggingSink",
    "RecordingSink",
    "RunFinishEvent",
    "RunStartEvent",
    "TextMessageContentEvent",
]

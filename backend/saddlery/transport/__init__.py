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
from saddlery.transport.cli import AgUiSink, CliSink
from saddlery.transport.recording import AgUiRecordingSink, RecordingSink

__all__ = [
    "AgUiErrorEvent",
    "AgUiEvent",
    "AgUiEventSink",
    "AgUiRecordingSink",
    "AgUiSink",
    "CliSink",
    "EventSink",
    "RecordingSink",
    "RunFinishEvent",
    "RunStartEvent",
    "TextMessageContentEvent",
]

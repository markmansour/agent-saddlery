"""AG-UI — Agent User Interaction protocol events (wire format).

Maps internal events onto the standard AG-UI event stream for frontend consumption.
Reference: https://docs.ag-ui.com/introduction
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class BaseAgUiEvent(BaseModel):
    """Base for all AG-UI wire events."""

    model_config = ConfigDict(frozen=True)

    type: str


class RunStartEvent(BaseAgUiEvent):
    """Signals the start of an agent run."""

    type: Literal["RUN_START"] = "RUN_START"


class RunFinishEvent(BaseAgUiEvent):
    """Signals the end of an agent run."""

    type: Literal["RUN_FINISH"] = "RUN_FINISH"


class TextMessageContentEvent(BaseAgUiEvent):
    """A chunk of text content (token) from an assistant message."""

    type: Literal["TEXT_MESSAGE_CONTENT"] = "TEXT_MESSAGE_CONTENT"
    content: str


class StateDeltaEvent(BaseAgUiEvent):
    """Incremental state change (reserved for later phases)."""

    type: Literal["STATE_DELTA"] = "STATE_DELTA"
    state: dict[str, Any]


class ErrorEvent(BaseAgUiEvent):
    """Error during execution."""

    type: Literal["ERROR"] = "ERROR"
    message: str


AgUiEvent = Annotated[
    RunStartEvent | RunFinishEvent | TextMessageContentEvent | StateDeltaEvent | ErrorEvent,
    Field(discriminator="type"),
]


@runtime_checkable
class AgUiEventSink(Protocol):
    """Sink for AG-UI events (wire format)."""

    async def emit(self, event: AgUiEvent) -> None: ...

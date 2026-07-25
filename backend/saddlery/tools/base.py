"""The Tool seam — pluggability for tool-calling support."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class ToolExecutionResult:
    """Outcome of a single tool call — never raises; failures are data."""

    __slots__ = ("content", "is_error")

    def __init__(self, content: str, *, is_error: bool = False) -> None:
        self.content = content
        self.is_error = is_error


@runtime_checkable
class Tool(Protocol):
    """Mirrors MCP's tool shape: schema (name/description/input_schema) + call().

    input_schema is a JSON Schema object (MCP's inputSchema, snake_case on our side).
    """

    name: str
    description: str
    input_schema: dict

    async def call(self, arguments: dict) -> ToolExecutionResult: ...

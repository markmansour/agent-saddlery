"""The Tool seam — pluggability for tool-calling support."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

Capability = Literal["read", "write", "exec", "network"]
CAPABILITIES: frozenset[str] = frozenset({"read", "write", "exec", "network"})


class ResourceError(ValueError):
    """The tool's arguments do not name a valid resource (bad type, escapes the root)."""


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
    capability classifies the tool's side effects for the permission policy.
    """

    name: str
    description: str
    input_schema: dict
    capability: Capability

    async def call(self, arguments: dict) -> ToolExecutionResult: ...

    def resource(self, arguments: dict) -> tuple[str, ...]:
        """Name what this call acts on, as normalized tokens. Raise ResourceError if invalid."""
        ...

    def detail(self, arguments: dict) -> object | None:
        """Optional structured classification passed to the permission policy."""
        return None

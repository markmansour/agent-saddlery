"""Tool registry — lookup and discovery."""

from __future__ import annotations

from typing import TYPE_CHECKING

from saddlery.tools.base import CAPABILITIES

if TYPE_CHECKING:
    from saddlery.tools.base import Tool


class ToolRegistry:
    """Registry for tools, supporting lookup and schema export."""

    def __init__(self, tools: list[Tool]) -> None:
        for tool in tools:
            capability = getattr(tool, "capability", None)
            if capability not in CAPABILITIES:
                raise ValueError(
                    f"Tool {tool.name!r} must declare a capability in "
                    f"{sorted(CAPABILITIES)}, got {capability!r}"
                )
        self._tools = {tool.name: tool for tool in tools}

    def names(self) -> list[str]:
        """Registered tool names."""
        return list(self._tools)

    def get(self, name: str) -> Tool | None:
        """Look up a tool by name."""
        return self._tools.get(name)

    def specs(self) -> list[dict]:
        """Return Anthropic-shaped tool specs for the tools=[...] API parameter.

        Each spec is {"name", "description", "input_schema"}.
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in self._tools.values()
        ]

"""The PermissionGate seam — hooks -> deny -> allow -> ask evaluation order.

Mirrors ToolRegistry: constructed once in build_agent(), called from Agent.run()
between emitting ToolCall and invoking tool.call().
"""

from __future__ import annotations

from typing import Literal

Decision = Literal["allow", "deny", "ask"]


class PermissionGate:
    def __init__(
        self,
        *,
        allow: set[str],
        deny: set[str],
    ) -> None:
        self._allow = allow
        self._deny = deny

    async def check(self, tool_name: str, arguments: dict, principal: str) -> Decision:
        if tool_name in self._deny:
            return "deny"
        if tool_name in self._allow:
            return "allow"
        return "ask"

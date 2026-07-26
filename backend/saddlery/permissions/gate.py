"""The PermissionGate seam — hooks -> deny -> allow -> ask evaluation order.

Mirrors ToolRegistry: constructed once in build_agent(), called from Agent.run()
between emitting ToolCall and invoking tool.call().
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

Decision = Literal["allow", "deny", "ask"]
HookResult = Literal["allow", "deny", "ask", "pass"]
Hook = Callable[[str, dict, str], HookResult]


class PermissionGate:
    def __init__(
        self,
        *,
        allow: set[str],
        deny: set[str],
        hooks: list[Hook] | None = None,
    ) -> None:
        self._allow = allow
        self._deny = deny
        self._hooks = hooks or []

    async def check(self, tool_name: str, arguments: dict, principal: str) -> Decision:
        for hook in self._hooks:
            result = hook(tool_name, arguments, principal)
            if result != "pass":
                return result

        if tool_name in self._deny:
            return "deny"
        if tool_name in self._allow:
            return "allow"
        return "ask"

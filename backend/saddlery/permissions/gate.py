"""The PermissionGate seam: deny → hooks → remembered → allow → class default → ask.

Mirrors ToolRegistry: constructed once in build_agent(), called from Agent.run() between
emitting ToolCall and invoking tool.call(). Policy lives here; the TUI only renders prompts.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from saddlery.permissions.rules import Rule, as_rule
from saddlery.permissions.shell import ShellCommand, deny_candidates
from saddlery.tools.paths import fold

if TYPE_CHECKING:
    from collections.abc import Iterable

    from saddlery.tools.base import Capability

Decision = Literal["allow", "deny", "ask"]
HookResult = Literal["allow", "deny", "ask", "pass"]


@dataclass(frozen=True, eq=False)
class PolicyRequest:
    """Everything policy may use to decide one tool call. Built by Agent.run()."""

    tool_name: str
    arguments: dict
    principal: str
    capability: Capability
    resource: tuple[str, ...]
    tainted: bool
    detail: object | None = None


Hook = Callable[[PolicyRequest], HookResult]

_REMEMBERED_CLASSES = frozenset({"write"})


class PermissionGate:
    def __init__(
        self,
        *,
        allow: Iterable[str | Rule] = (),
        deny: Iterable[str | Rule] = (),
        hooks: list[Hook] | None = None,
    ) -> None:
        self._allow = [as_rule(item) for item in allow]
        self._deny = [as_rule(item) for item in deny]
        self._hooks = hooks or []
        self._remembered: dict[tuple[str, str, tuple[str, ...]], Literal["allow", "deny"]] = {}

    def remember(self, request: PolicyRequest, decision: Literal["allow", "deny"]) -> None:
        if request.capability not in _REMEMBERED_CLASSES:
            return
        self._remembered[self._key(request)] = decision

    async def check(self, request: PolicyRequest) -> Decision:
        if self._is_rejected(request) or self._is_denied(request):
            return "deny"

        for hook in self._hooks:
            result = hook(request)
            if result != "pass":
                return result

        remembered = self._remembered.get(self._key(request))
        if remembered is not None:
            return remembered

        if any(rule.matches(request.tool_name, request.resource) for rule in self._allow):
            if request.tainted and request.capability != "read":
                return "ask"
            return "allow"

        return "allow" if request.capability == "read" else "ask"

    @staticmethod
    def _key(request: PolicyRequest) -> tuple[str, str, tuple[str, ...]]:
        return (request.principal, request.tool_name, tuple(fold(t) for t in request.resource))

    @staticmethod
    def _is_rejected(request: PolicyRequest) -> bool:
        return isinstance(request.detail, ShellCommand) and request.detail.kind == "rejected"

    def _is_denied(self, request: PolicyRequest) -> bool:
        candidates = [request.resource]
        if isinstance(request.detail, ShellCommand):
            candidates.extend(deny_candidates(request.detail))
        return any(
            rule.matches(request.tool_name, candidate)
            for rule in self._deny
            for candidate in candidates
        )

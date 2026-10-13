"""Permission rules: a tool plus an optional token prefix of the call's resource."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from saddlery.tools.paths import fold

#: Tools whose resource tokens are path components (matched case-insensitively, like macOS).
PATH_TOOLS = frozenset({"read_file", "write_file"})

Role = Literal["allow", "deny"]


@dataclass(frozen=True)
class Rule:
    tool: str
    match: tuple[str, ...] = ()

    def matches(self, tool_name: str, resource: tuple[str, ...], *, role: Role) -> bool:
        """Token-prefix match. Deny rules and path-tool allow rules fold NFC + case (deny
        widens, which fails closed; paths follow the case-insensitive filesystem). Any other
        allow rule compares exactly, so allowing `-d` never allows `-D`."""
        if tool_name != self.tool:
            return False
        if role == "deny" or self.tool in PATH_TOOLS:
            prefix = tuple(fold(token) for token in self.match)
            tokens = tuple(fold(token) for token in resource)
        else:
            prefix, tokens = self.match, tuple(resource)
        return tokens[: len(prefix)] == prefix


def as_rule(item: str | Rule) -> Rule:
    return item if isinstance(item, Rule) else Rule(item)

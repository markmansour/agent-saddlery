"""Permission rules: a tool plus an optional token prefix of the call's resource."""

from __future__ import annotations

from dataclasses import dataclass

from saddlery.tools.paths import fold


@dataclass(frozen=True)
class Rule:
    tool: str
    match: tuple[str, ...] = ()

    def matches(self, tool_name: str, resource: tuple[str, ...]) -> bool:
        if tool_name != self.tool:
            return False
        prefix = tuple(fold(token) for token in self.match)
        folded = tuple(fold(token) for token in resource)
        return folded[: len(prefix)] == prefix


def as_rule(item: str | Rule) -> Rule:
    return item if isinstance(item, Rule) else Rule(item)

"""Loads and validates the project-level permission rules (.saddlery/permissions.json)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

from saddlery.permissions.rules import PATH_TOOLS, Rule
from saddlery.tools.paths import fold

if TYPE_CHECKING:
    from collections.abc import Collection
    from pathlib import Path

#: Single-token shell allow rules for these run arbitrary programs; they need an explicit opt-in.
BROAD_EXECUTORS = frozenset(
    {
        "bash", "sh", "zsh", "python", "python3", "node", "ruby", "perl",
        "env", "xargs", "find", "sudo", "awk", "make", "npm",
    }
)  # fmt: skip

_TOP_LEVEL_KEYS = {"allow", "deny"}
_RULE_KEYS = {"tool", "match", "unsafe_broad_allow"}


class ConfigError(Exception):
    """The permissions file is malformed. Startup must fail rather than drop rules."""


@dataclass(frozen=True)
class PermissionConfig:
    allow: tuple[Rule, ...] = ()
    deny: tuple[Rule, ...] = ()


def load_permission_config(
    path: Path, *, known_tools: Collection[str] | None = None
) -> PermissionConfig:
    """Load rules from path. A missing file is the empty config; anything malformed raises."""
    if not path.exists():
        if path.is_symlink():
            raise ConfigError(f"{path}: broken symlink (its target does not exist)")
        return PermissionConfig()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"{path}: cannot read: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise ConfigError(f"{path}: not valid UTF-8: {exc}") from exc
    try:
        data = json.loads(text, object_pairs_hook=_no_duplicates)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path}: invalid JSON: {exc}") from exc
    except ConfigError as exc:
        raise ConfigError(f"{path}: {exc}") from None
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be an object")
    unknown = set(data) - _TOP_LEVEL_KEYS
    if unknown:
        raise ConfigError(f"{path}: unknown keys {sorted(unknown)}")
    return PermissionConfig(
        allow=_parse_rules(data.get("allow", []), "allow", path, known_tools),
        deny=_parse_rules(data.get("deny", []), "deny", path, known_tools),
    )


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """json object hook: a duplicate key would silently drop rules, so reject it."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError(f"duplicate key {key!r}")
        result[key] = value
    return result


def _parse_rules(
    items: Any, kind: str, path: Path, known_tools: Collection[str] | None
) -> tuple[Rule, ...]:
    if not isinstance(items, list):
        raise ConfigError(f"{path}: '{kind}' must be a list")
    return tuple(_parse_rule(item, kind, path, known_tools) for item in items)


def _parse_rule(item: Any, kind: str, path: Path, known_tools: Collection[str] | None) -> Rule:
    where = f"{path}: {kind} rule {item!r}"
    if isinstance(item, str):
        tool, match, opted_in = item, (), False
    elif isinstance(item, dict):
        unknown = set(item) - _RULE_KEYS
        if unknown:
            raise ConfigError(f"{where}: unknown keys {sorted(unknown)}")
        tool = item.get("tool")
        raw_match = item.get("match", [])
        opted_in = item.get("unsafe_broad_allow", False)
        if not isinstance(raw_match, list):
            raise ConfigError(f"{where}: 'match' must be a list")
        if "match" in item and not raw_match:
            raise ConfigError(f"{where}: 'match' must not be empty")
        match = tuple(raw_match)
    else:
        raise ConfigError(f"{where}: a rule is a tool name or an object")
    if not isinstance(tool, str) or not tool:
        raise ConfigError(f"{where}: 'tool' must be a non-empty string")
    if known_tools is not None and tool not in known_tools:
        raise ConfigError(f"{where}: unknown tool {tool!r}")
    for token in match:
        if not isinstance(token, str) or not token:
            raise ConfigError(f"{where}: match tokens must be non-empty strings")
        if tool in PATH_TOOLS and ("/" in token or token in {".", ".."}):
            raise ConfigError(f"{where}: path tokens may not contain '/' or be '.' or '..'")
    if (
        kind == "allow"
        and tool == "shell"
        and len(match) == 1
        and fold(match[0]) in BROAD_EXECUTORS
    ):
        if opted_in is not True:
            raise ConfigError(
                f"{where}: allowing every '{match[0]}' command runs arbitrary programs; "
                'set "unsafe_broad_allow": true to accept that'
            )
        structlog.get_logger().warning("unsafe_broad_allow", tool=tool, match=list(match))
    return Rule(tool, match)

"""Loads the project-level permission allow/deny config from .saddlery/permissions.json."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(".saddlery/permissions.json")


def load_permission_config(path: Path | None = None) -> tuple[set[str], set[str]]:
    """Load {"allow": [...], "deny": [...]} from path (default .saddlery/permissions.json).

    Missing file, missing keys, or malformed JSON all default to empty sets — an unlisted
    tool falls through to the 'ask' stage of PermissionGate.check(), which is the safe
    default. A hand-edited config with a syntax error should not crash the CLI at startup.
    """
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return set(), set()

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set(), set()

    allow = set(data.get("allow", []))
    deny = set(data.get("deny", []))
    return allow, deny

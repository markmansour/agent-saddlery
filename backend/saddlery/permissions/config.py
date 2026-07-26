"""Loads the project-level permission allow/deny config from .saddlery/permissions.json."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(".saddlery/permissions.json")


def load_permission_config(path: Path | None = None) -> tuple[set[str], set[str]]:
    """Load {"allow": [...], "deny": [...]} from path (default .saddlery/permissions.json).

    Missing file or missing keys default to empty sets — an unlisted tool falls through
    to the 'ask' stage of PermissionGate.check(), which is the safe default.
    """
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return set(), set()

    data = json.loads(config_path.read_text(encoding="utf-8"))
    allow = set(data.get("allow", []))
    deny = set(data.get("deny", []))
    return allow, deny

"""Input handling — reads user messages from stdin (JSON or line-based)."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def parse_input_line(line: str) -> tuple[str, dict] | None:
    """Parse one JSON-lines wire-protocol message.

    Returns (event_type, payload) for a recognized message, or None for a blank line,
    malformed JSON, an unrecognized type, or a user_message with empty content.
    """
    stripped = line.strip()
    if not stripped:
        return None

    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError:
        return None

    event_type = obj.get("type")
    if event_type == "user_message":
        content = obj.get("content", "").strip()
        if not content:
            return None
        return ("user_message", {"content": content})
    if event_type == "permission_decision":
        return (
            "permission_decision",
            {"tool_call_id": obj.get("tool_call_id"), "decision": obj.get("decision")},
        )
    return None


async def read_input_lines() -> AsyncIterator[tuple[str, dict]]:
    """Read wire-protocol lines from stdin as JSON objects.

    Yields (event_type, payload) tuples — "user_message" with {"content": str}, or
    "permission_decision" with {"tool_call_id": str, "decision": str}. Blank lines,
    malformed JSON, and unrecognized types are silently skipped (the TUI may retry).
    """
    loop = __import__("asyncio").get_running_loop()
    while True:
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:  # EOF
                break
            parsed = parse_input_line(line)
            if parsed is not None:
                yield parsed
        except Exception:
            # Any other error (pipe broken, etc.), stop gracefully
            break


async def read_user_messages_interactive() -> AsyncIterator[str]:
    """Read user messages interactively from terminal (original Phase 0.1 behavior).

    Yields:
        User message content strings.
    """
    loop = __import__("asyncio").get_running_loop()
    while True:
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:  # EOF (Ctrl-D)
                break
            text = line.strip()
            if text:
                yield text
        except Exception:
            break

"""Input handling — reads user messages from stdin (JSON or line-based)."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


async def read_user_messages_json() -> AsyncIterator[str]:
    """Read user messages from stdin as JSON objects.

    Expected format (one per line):
        {"type": "user_message", "content": "hello"}

    Yields:
        User message content strings.
    """
    loop = __import__("asyncio").get_running_loop()
    while True:
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:  # EOF
                break
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("type") == "user_message":
                content = obj.get("content", "").strip()
                if content:
                    yield content
        except json.JSONDecodeError:
            # Silently skip malformed JSON; TUI will retry
            pass
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

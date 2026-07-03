#!/usr/bin/env python3
"""Quick demo: run the echo loop with structured logging visible.

Usage:
    # Dev mode (colored console):
    python demo_with_logging.py

    # Prod mode (JSON):
    SADDLERY_LOG_FORMAT=json python demo_with_logging.py

Then type messages and see all events logged.
"""

import asyncio
import os
import sys

# Set log format from env (default: dev)
os.environ.setdefault("SADDLERY_LOG_FORMAT", "dev")

import structlog

from saddlery.agent import Agent
from saddlery.events import UserMessage
from saddlery.llm.fake import FakeProvider
from saddlery.logging import configure_logging
from saddlery.session import Session
from saddlery.transport.cli import CliSink, LoggingSink


def build_agent() -> Agent:
    """Build agent with fake provider for demo (no API calls)."""
    return Agent(provider=FakeProvider(["Hello", " ", "world", "!"]))


async def main() -> None:
    configure_logging()
    log = structlog.get_logger()

    print("\n" + "=" * 70)
    print("Agent Saddlery Demo — Events logged below")
    print("=" * 70)
    print("\nType messages and watch events stream:")
    print("  - INFO level: lifecycle (session start/finish, run start/finish)")
    print("  - DEBUG level: content (message deltas)")
    print("\nCtrl-D to exit.\n")

    principal = "demo-user"
    session = Session(session_id="demo-001", principal=principal)

    log.info("session_started", session_id=session.session_id, principal=principal)

    agent = build_agent()
    sink = LoggingSink(CliSink())

    loop = asyncio.get_running_loop()
    try:
        while True:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            text = line.strip()
            if not text:
                continue

            session.append(
                UserMessage(session_id=session.session_id, principal=principal, content=text)
            )
            await agent.run(session, sink)

    finally:
        log.info(
            "session_finished",
            session_id=session.session_id,
            event_count=len(session.events),
        )
        print("\n" + "=" * 70)
        print("Session finished. Check logs above for event flow.")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

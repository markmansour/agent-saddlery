"""CLI entrypoint for the 0.1 echo loop."""

from __future__ import annotations

import asyncio
import sys
import uuid

import structlog

from saddlery.agent import Agent
from saddlery.events import UserMessage
from saddlery.llm.anthropic_provider import AnthropicProvider
from saddlery.logging import configure_logging
from saddlery.session import Session
from saddlery.transport.cli import CliSink, LoggingSink


def build_agent() -> Agent:
    return Agent(provider=AnthropicProvider())


async def _amain() -> int:
    configure_logging()
    log = structlog.get_logger()

    principal = "local"
    session = Session(session_id=uuid.uuid4().hex, principal=principal)

    log.info("session_started", session_id=session.session_id, principal=principal)

    agent = build_agent()
    sink = LoggingSink(CliSink())

    print("Agent Saddlery — 0.1 echo loop. Type a message; Ctrl-D to exit.")
    loop = asyncio.get_running_loop()
    try:
        while True:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:  # EOF (Ctrl-D)
                break
            text = line.strip()
            if not text:
                continue
            session.append(
                UserMessage(session_id=session.session_id, principal=principal, content=text)
            )
            await agent.run(session, sink)
    finally:
        log.info("session_finished", session_id=session.session_id, event_count=len(session.events))

    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_amain()))

"""CLI entrypoint for the 0.1 echo loop."""

from __future__ import annotations

import asyncio
import sys
import uuid

from saddlery.agent import Agent
from saddlery.events import UserMessage
from saddlery.llm.anthropic_provider import AnthropicProvider
from saddlery.session import Session
from saddlery.transport.cli import CliSink


def build_agent() -> Agent:
    return Agent(provider=AnthropicProvider())


async def _amain() -> int:
    principal = "local"
    session = Session(session_id=uuid.uuid4().hex, principal=principal)
    agent = build_agent()
    sink = CliSink()
    print("Agent Saddlery — 0.1 echo loop. Type a message; Ctrl-D to exit.")
    loop = asyncio.get_running_loop()
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
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_amain()))

"""CLI entrypoint for the 0.1 echo loop and 0.3 TUI bridge."""

from __future__ import annotations

import asyncio
import os
import sys
import uuid

import structlog
from dotenv import load_dotenv

from saddlery.agent import Agent
from saddlery.cli.input import read_user_messages_interactive, read_user_messages_json
from saddlery.events import UserMessage
from saddlery.llm.anthropic_provider import AnthropicProvider
from saddlery.llm.mock_provider import MockLMProvider
from saddlery.logging import configure_logging
from saddlery.session import Session
from saddlery.tools.read_file import FileReadTool
from saddlery.tools.registry import ToolRegistry
from saddlery.transport.cli import CliSink, LoggingSink


def build_agent() -> Agent:
    # Load the repo-root .env (shared with the TUI) without overriding vars already set
    # in the environment (e.g. by the TUI, which loads it too and passes it to this
    # subprocess — an explicit shell export should still win over the file).
    load_dotenv(override=False)

    # Use mock provider if no API key or if --test-mode is set
    test_mode_flag = "--test-mode" in sys.argv
    has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    use_mock = test_mode_flag or not has_api_key
    if use_mock:
        structlog.get_logger().warning(
            "using_mock_provider",
            reason="--test-mode flag set" if test_mode_flag else "ANTHROPIC_API_KEY not set",
        )
    provider = MockLMProvider() if use_mock else AnthropicProvider()
    return Agent(provider=provider, tools=ToolRegistry([FileReadTool()]))


def _use_json_input() -> bool:
    """Check if we should read input as JSON (for TUI subprocess mode)."""
    return "--json-input" in sys.argv


async def _amain() -> int:
    configure_logging()
    log = structlog.get_logger()

    principal = "local"
    session = Session(session_id=uuid.uuid4().hex, principal=principal)

    agent = build_agent()
    sink = LoggingSink(CliSink())

    # Emit session started event
    from saddlery.events import SessionStarted

    await sink.emit(SessionStarted(session_id=session.session_id, principal=principal))
    log.info("session_started", session_id=session.session_id, principal=principal)

    # Determine input mode: JSON (for TUI) or interactive (for CLI)
    use_json = _use_json_input()
    if use_json:
        input_reader = read_user_messages_json()
    else:
        print("Agent Saddlery — 0.1 echo loop. Type a message; Ctrl-D to exit.")
        input_reader = read_user_messages_interactive()

    try:
        async for text in input_reader:
            session.append(
                UserMessage(session_id=session.session_id, principal=principal, content=text)
            )
            await agent.run(session, sink)
    finally:
        log.info("session_finished", session_id=session.session_id, event_count=len(session.events))

    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_amain()))


if __name__ == "__main__":
    main()

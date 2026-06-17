# 0.1 Echo Loop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A runnable streaming chat echo loop — type a message in a CLI, get a streamed reply — built on the Phase 0 core seams.

**Architecture:** Hand-rolled asyncio core. An append-only event log is the source of truth; a pure `to_messages()` fold derives the LLM message list. An `Agent.run()` loop calls an `LLMProvider` (native Anthropic) and appends streamed deltas as events, emitting each to an `EventSink` (CLI). `principal` is threaded through every session and event for future tenancy. Seams (`LLMProvider`, `SessionStore`, `EventSink`) make later slices fill-ins, not rewrites.

**Tech Stack:** Python 3.12, [uv](https://docs.astral.sh/uv/), [Pydantic v2](https://docs.pydantic.dev/), [anthropic](https://github.com/anthropics/anthropic-sdk-python) SDK, [pytest](https://docs.pytest.org/) + [pytest-asyncio](https://pytest-asyncio.readthedocs.io/), [ruff](https://docs.astral.sh/ruff/).

**Spec:** [`docs/specs/2026-06-16-phase0-core-design.md`](../specs/2026-06-16-phase0-core-design.md) · **Linear:** [MAR-5](https://linear.app/mark-mansour/issue/MAR-5)

**Branch:** work on `mark/mar-5-01-echo-loop` (the Linear-suggested branch name), not `main`.

---

## File structure

All Python lives under `core/` (the monorepo's Python project; TS frontends arrive at 0.3 under `frontends/`).

| File | Responsibility |
|---|---|
| `core/pyproject.toml` | Project metadata, deps, console script, pytest/ruff config |
| `core/saddlery/messages.py` | `Message` (role + content) — provider-neutral conversation currency |
| `core/saddlery/events.py` | The six event types + discriminated `Event` union |
| `core/saddlery/session.py` | `Session` (event log + `to_messages()` fold) + `SessionStore` seam |
| `core/saddlery/llm/base.py` | `LLMProvider` protocol + `TextDelta`/`ProviderDelta` |
| `core/saddlery/llm/fake.py` | `FakeProvider` test double |
| `core/saddlery/llm/anthropic_provider.py` | `AnthropicProvider` (native SDK) + `split_system` helper |
| `core/saddlery/transport/base.py` | `EventSink` protocol |
| `core/saddlery/transport/recording.py` | `RecordingSink` test double |
| `core/saddlery/transport/cli.py` | `CliSink` — prints deltas live |
| `core/saddlery/agent.py` | `Agent` (immutable) + `run()` loop |
| `core/saddlery/cli/main.py` | CLI entrypoint (the demo) |
| `core/saddlery/tools/__init__.py`, `core/saddlery/runtime/__init__.py` | Empty seam placeholders (filled at 0.4+) |
| `core/tests/…` | Tests mirroring the modules above |

---

## Task 1: Scaffold the Python project

**Files:**
- Create: `core/pyproject.toml`, `core/saddlery/__init__.py`, `core/saddlery/llm/__init__.py`, `core/saddlery/transport/__init__.py`, `core/saddlery/cli/__init__.py`, `core/saddlery/tools/__init__.py`, `core/saddlery/runtime/__init__.py`, `core/tests/__init__.py`

- [ ] **Step 1: Create `core/pyproject.toml`**

```toml
[project]
name = "saddlery"
version = "0.0.1"
description = "Agent Saddlery core — a general-purpose agent harness"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.7",
    "anthropic>=0.49",
]

[project.scripts]
saddlery = "saddlery.cli.main:main"

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.24",
    "ruff>=0.6",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["saddlery"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
```

- [ ] **Step 2: Create the package + seam placeholders**

`core/saddlery/__init__.py`:
```python
"""Agent Saddlery core."""
```

`core/saddlery/tools/__init__.py`:
```python
"""Seam placeholder for tools — filled at slice 0.4. Intentionally empty for 0.1."""
```

`core/saddlery/runtime/__init__.py`:
```python
"""Seam placeholder for the execution runtime — filled later. Intentionally empty for 0.1."""
```

Create empty `core/saddlery/llm/__init__.py`, `core/saddlery/transport/__init__.py`, `core/saddlery/cli/__init__.py`, `core/tests/__init__.py` (each containing a single line: `""" """`).

- [ ] **Step 3: Install and verify the toolchain**

Run: `cd core && uv sync`
Expected: creates `.venv`, installs pydantic, anthropic, pytest, pytest-asyncio, ruff; exits 0.

Run: `cd core && uv run pytest -q`
Expected: `no tests ran` (exit code 5 is fine — no tests yet).

Run: `cd core && uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add core/pyproject.toml core/saddlery core/tests
git commit -m "chore(core): scaffold saddlery python project (uv, pydantic, anthropic, pytest)"
```

---

## Task 2: Event models

**Files:**
- Create: `core/saddlery/events.py`
- Test: `core/tests/test_events.py`

- [ ] **Step 1: Write the failing test**

`core/tests/test_events.py`:
```python
from pydantic import TypeAdapter

from saddlery.events import (
    AssistantMessage,
    Event,
    RunStarted,
    UserMessage,
)


def test_event_has_identity_and_metadata():
    e = UserMessage(session_id="s1", principal="local", content="hi")
    assert e.type == "user_message"
    assert e.id  # auto-generated
    assert e.timestamp is not None
    assert e.session_id == "s1"
    assert e.principal == "local"


def test_event_json_roundtrip_via_discriminated_union():
    original = AssistantMessage(session_id="s1", principal="local", content="hello there")
    data = original.model_dump_json()
    parsed = TypeAdapter(Event).validate_json(data)
    assert isinstance(parsed, AssistantMessage)
    assert parsed.content == "hello there"


def test_run_started_is_distinct_type():
    assert RunStarted(session_id="s", principal="p").type == "run_started"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd core && uv run pytest tests/test_events.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'saddlery.events'`.

- [ ] **Step 3: Write the implementation**

`core/saddlery/events.py`:
```python
"""Typed, append-only events — the canonical source of truth for a session."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


def _new_id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BaseEvent(BaseModel):
    id: str = Field(default_factory=_new_id)
    session_id: str
    principal: str
    timestamp: datetime = Field(default_factory=_now)


class UserMessage(BaseEvent):
    type: Literal["user_message"] = "user_message"
    content: str


class RunStarted(BaseEvent):
    type: Literal["run_started"] = "run_started"


class AssistantMessageDelta(BaseEvent):
    type: Literal["assistant_message_delta"] = "assistant_message_delta"
    text: str


class AssistantMessage(BaseEvent):
    type: Literal["assistant_message"] = "assistant_message"
    content: str


class RunFinished(BaseEvent):
    type: Literal["run_finished"] = "run_finished"


class ErrorEvent(BaseEvent):
    type: Literal["error"] = "error"
    message: str


Event = Annotated[
    Union[
        UserMessage,
        RunStarted,
        AssistantMessageDelta,
        AssistantMessage,
        RunFinished,
        ErrorEvent,
    ],
    Field(discriminator="type"),
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd core && uv run pytest tests/test_events.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add core/saddlery/events.py core/tests/test_events.py
git commit -m "feat(core): add typed event models with discriminated union"
```

---

## Task 3: Message model + Session fold + SessionStore

**Files:**
- Create: `core/saddlery/messages.py`, `core/saddlery/session.py`
- Test: `core/tests/test_session.py`

- [ ] **Step 1: Write the failing test**

`core/tests/test_session.py`:
```python
import pytest

from saddlery.events import (
    AssistantMessage,
    AssistantMessageDelta,
    RunStarted,
    UserMessage,
)
from saddlery.session import InMemorySessionStore, Session


def _user(s, text):
    s.append(UserMessage(session_id=s.session_id, principal=s.principal, content=text))


def test_to_messages_folds_user_and_final_assistant_only():
    s = Session(session_id="s1", principal="local")
    _user(s, "hello")
    s.append(RunStarted(session_id="s1", principal="local"))
    s.append(AssistantMessageDelta(session_id="s1", principal="local", text="hi "))
    s.append(AssistantMessageDelta(session_id="s1", principal="local", text="there"))
    s.append(AssistantMessage(session_id="s1", principal="local", content="hi there"))

    msgs = s.to_messages()

    assert [(m.role, m.content) for m in msgs] == [
        ("user", "hello"),
        ("assistant", "hi there"),
    ]


def test_events_are_appended_in_order():
    s = Session(session_id="s1", principal="local")
    _user(s, "a")
    _user(s, "b")
    assert [e.content for e in s.events] == ["a", "b"]


async def test_store_get_or_create_returns_same_session():
    store = InMemorySessionStore()
    a = await store.get_or_create("s1", "local")
    b = await store.get_or_create("s1", "local")
    assert a is b
    assert a.session_id == "s1"
    assert a.principal == "local"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd core && uv run pytest tests/test_session.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'saddlery.session'`.

- [ ] **Step 3: Write the implementations**

`core/saddlery/messages.py`:
```python
"""Provider-neutral conversation currency derived from the event log."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Role = Literal["system", "user", "assistant"]


class Message(BaseModel):
    role: Role
    content: str
```

`core/saddlery/session.py`:
```python
"""Session = an append-only event log + a pure fold to the LLM message list.

The event log is the source of truth. `SessionStore` is the persistence seam; the
in-memory implementation here is replaced by a SQLite store at slice 0.8 without
changing the fold (the fold *is* replay).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from saddlery.events import AssistantMessage, BaseEvent, UserMessage
from saddlery.messages import Message


class Session:
    def __init__(self, session_id: str, principal: str) -> None:
        self.session_id = session_id
        self.principal = principal
        self._events: list[BaseEvent] = []

    @property
    def events(self) -> list[BaseEvent]:
        return list(self._events)

    def append(self, event: BaseEvent) -> None:
        self._events.append(event)

    def to_messages(self) -> list[Message]:
        messages: list[Message] = []
        for event in self._events:
            if isinstance(event, UserMessage):
                messages.append(Message(role="user", content=event.content))
            elif isinstance(event, AssistantMessage):
                messages.append(Message(role="assistant", content=event.content))
        return messages


@runtime_checkable
class SessionStore(Protocol):
    async def get_or_create(self, session_id: str, principal: str) -> Session: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    async def get_or_create(self, session_id: str, principal: str) -> Session:
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id, principal)
        return self._sessions[session_id]
```

> Note: the spec named the store `load`/`append`; here it is `get_or_create` because 0.1
> keeps the in-memory `Session` as the mutable log. The persistence-style `append` write-path
> lands with the SQLite store at 0.8 (spec §11). Documented deviation, not a gap.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd core && uv run pytest tests/test_session.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add core/saddlery/messages.py core/saddlery/session.py core/tests/test_session.py
git commit -m "feat(core): add Message, Session fold, and in-memory SessionStore seam"
```

---

## Task 4: LLM provider seam + FakeProvider

**Files:**
- Create: `core/saddlery/llm/base.py`, `core/saddlery/llm/fake.py`
- Test: `core/tests/test_fake_provider.py`

- [ ] **Step 1: Write the failing test**

`core/tests/test_fake_provider.py`:
```python
import pytest

from saddlery.llm.fake import FakeProvider
from saddlery.messages import Message


async def test_fake_provider_yields_text_deltas():
    provider = FakeProvider(["Hel", "lo"])
    out = [d.text async for d in provider.stream([Message(role="user", content="hi")], model="x")]
    assert out == ["Hel", "lo"]


async def test_fake_provider_raises_after_chunks():
    provider = FakeProvider(["a"], error=RuntimeError("boom"))
    collected = []
    with pytest.raises(RuntimeError, match="boom"):
        async for delta in provider.stream([], model="x"):
            collected.append(delta.text)
    assert collected == ["a"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd core && uv run pytest tests/test_fake_provider.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'saddlery.llm.fake'`.

- [ ] **Step 3: Write the implementations**

`core/saddlery/llm/base.py`:
```python
"""The LLMProvider seam. Pluggability lives here, not in any one vendor SDK."""

from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from pydantic import BaseModel

from saddlery.messages import Message


class TextDelta(BaseModel):
    text: str


# Union grows later (ToolCallDelta, Stop/Usage). Kept as one type for 0.1.
ProviderDelta = TextDelta


@runtime_checkable
class LLMProvider(Protocol):
    def stream(
        self, messages: list[Message], *, model: str
    ) -> AsyncIterator[ProviderDelta]: ...
```

`core/saddlery/llm/fake.py`:
```python
"""A scripted provider for testing the agent loop without a network."""

from __future__ import annotations

from typing import AsyncIterator

from saddlery.llm.base import ProviderDelta, TextDelta
from saddlery.messages import Message


class FakeProvider:
    def __init__(self, chunks: list[str], *, error: Exception | None = None) -> None:
        self._chunks = chunks
        self._error = error

    async def stream(
        self, messages: list[Message], *, model: str = "fake"
    ) -> AsyncIterator[ProviderDelta]:
        for chunk in self._chunks:
            yield TextDelta(text=chunk)
        if self._error is not None:
            raise self._error
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd core && uv run pytest tests/test_fake_provider.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add core/saddlery/llm/base.py core/saddlery/llm/fake.py core/tests/test_fake_provider.py
git commit -m "feat(core): add LLMProvider seam and FakeProvider test double"
```

---

## Task 5: EventSink + RecordingSink + CliSink

**Files:**
- Create: `core/saddlery/transport/base.py`, `core/saddlery/transport/recording.py`, `core/saddlery/transport/cli.py`
- Test: `core/tests/test_sinks.py`

- [ ] **Step 1: Write the failing test**

`core/tests/test_sinks.py`:
```python
import io

from saddlery.events import AssistantMessageDelta, ErrorEvent, RunFinished
from saddlery.transport.cli import CliSink
from saddlery.transport.recording import RecordingSink


async def test_recording_sink_collects_events():
    sink = RecordingSink()
    e = RunFinished(session_id="s", principal="p")
    await sink.emit(e)
    assert sink.events == [e]


async def test_cli_sink_writes_delta_text_then_newline_on_finish():
    buf = io.StringIO()
    sink = CliSink(out=buf)
    await sink.emit(AssistantMessageDelta(session_id="s", principal="p", text="hi"))
    await sink.emit(RunFinished(session_id="s", principal="p"))
    assert buf.getvalue() == "hi\n"


async def test_cli_sink_renders_errors():
    buf = io.StringIO()
    sink = CliSink(out=buf)
    await sink.emit(ErrorEvent(session_id="s", principal="p", message="RuntimeError: boom"))
    assert "boom" in buf.getvalue()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd core && uv run pytest tests/test_sinks.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'saddlery.transport.cli'`.

- [ ] **Step 3: Write the implementations**

`core/saddlery/transport/base.py`:
```python
"""EventSink — the outbound transport seam (core -> consumer)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from saddlery.events import BaseEvent


@runtime_checkable
class EventSink(Protocol):
    async def emit(self, event: BaseEvent) -> None: ...
```

`core/saddlery/transport/recording.py`:
```python
"""A sink that records emitted events — for tests."""

from __future__ import annotations

from saddlery.events import BaseEvent


class RecordingSink:
    def __init__(self) -> None:
        self.events: list[BaseEvent] = []

    async def emit(self, event: BaseEvent) -> None:
        self.events.append(event)
```

`core/saddlery/transport/cli.py`:
```python
"""A sink that streams assistant text to a terminal."""

from __future__ import annotations

import sys
from typing import TextIO

from saddlery.events import AssistantMessageDelta, BaseEvent, ErrorEvent, RunFinished


class CliSink:
    def __init__(self, out: TextIO = sys.stdout) -> None:
        self._out = out

    async def emit(self, event: BaseEvent) -> None:
        if isinstance(event, AssistantMessageDelta):
            self._out.write(event.text)
            self._out.flush()
        elif isinstance(event, ErrorEvent):
            self._out.write(f"\n[error] {event.message}\n")
            self._out.flush()
        elif isinstance(event, RunFinished):
            self._out.write("\n")
            self._out.flush()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd core && uv run pytest tests/test_sinks.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add core/saddlery/transport core/tests/test_sinks.py
git commit -m "feat(core): add EventSink seam with RecordingSink and CliSink"
```

---

## Task 6: Agent.run loop

**Files:**
- Create: `core/saddlery/agent.py`
- Test: `core/tests/test_agent.py`

- [ ] **Step 1: Write the failing test**

`core/tests/test_agent.py`:
```python
from saddlery.agent import Agent
from saddlery.events import UserMessage
from saddlery.llm.fake import FakeProvider
from saddlery.session import Session
from saddlery.transport.recording import RecordingSink


def _session_with_user(text: str) -> Session:
    s = Session(session_id="s1", principal="local")
    s.append(UserMessage(session_id="s1", principal="local", content=text))
    return s


async def test_run_emits_ordered_events_and_final_message():
    session = _session_with_user("hello")
    sink = RecordingSink()
    agent = Agent(provider=FakeProvider(["Hel", "lo"]))

    await agent.run(session, sink)

    assert [e.type for e in sink.events] == [
        "run_started",
        "assistant_message_delta",
        "assistant_message_delta",
        "assistant_message",
        "run_finished",
    ]
    final = next(e for e in sink.events if e.type == "assistant_message")
    assert final.content == "Hello"
    # Events were also appended to the session log (source of truth).
    assert [e.type for e in session.events][0] == "user_message"
    assert session.events[-1].type == "run_finished"


async def test_run_records_error_and_still_finishes():
    session = _session_with_user("x")
    sink = RecordingSink()
    agent = Agent(provider=FakeProvider([], error=RuntimeError("boom")))

    await agent.run(session, sink)

    types = [e.type for e in sink.events]
    assert "error" in types
    assert types[-1] == "run_finished"
    err = next(e for e in sink.events if e.type == "error")
    assert "boom" in err.message
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd core && uv run pytest tests/test_agent.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'saddlery.agent'`.

- [ ] **Step 3: Write the implementation**

`core/saddlery/agent.py`:
```python
"""The Agent: an immutable config + the run() loop over the event stream."""

from __future__ import annotations

from dataclasses import dataclass

from saddlery.events import (
    AssistantMessage,
    AssistantMessageDelta,
    BaseEvent,
    ErrorEvent,
    RunFinished,
    RunStarted,
)
from saddlery.llm.base import LLMProvider
from saddlery.messages import Message
from saddlery.session import Session
from saddlery.transport.base import EventSink

DEFAULT_MODEL = "claude-haiku-4-5"


@dataclass(frozen=True)
class Agent:
    provider: LLMProvider
    system_prompt: str = "You are a helpful assistant."
    model: str = DEFAULT_MODEL

    async def run(self, session: Session, sink: EventSink) -> None:
        meta = {"session_id": session.session_id, "principal": session.principal}

        async def emit(event: BaseEvent) -> None:
            session.append(event)
            await sink.emit(event)

        await emit(RunStarted(**meta))
        messages = [
            Message(role="system", content=self.system_prompt),
            *session.to_messages(),
        ]
        parts: list[str] = []
        try:
            async for delta in self.provider.stream(messages, model=self.model):
                parts.append(delta.text)
                await emit(AssistantMessageDelta(text=delta.text, **meta))
            await emit(AssistantMessage(content="".join(parts), **meta))
        except Exception as exc:  # noqa: BLE001 - failures are recorded as events
            await emit(ErrorEvent(message=f"{type(exc).__name__}: {exc}", **meta))
        finally:
            await emit(RunFinished(**meta))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd core && uv run pytest tests/test_agent.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add core/saddlery/agent.py core/tests/test_agent.py
git commit -m "feat(core): add Agent.run event loop with error invariant"
```

---

## Task 7: AnthropicProvider

**Files:**
- Create: `core/saddlery/llm/anthropic_provider.py`
- Test: `core/tests/test_anthropic_provider.py`

- [ ] **Step 1: Write the failing test (pure helper + gated live smoke)**

`core/tests/test_anthropic_provider.py`:
```python
import os

import pytest

from saddlery.llm.anthropic_provider import AnthropicProvider, split_system
from saddlery.messages import Message


def test_split_system_extracts_system_and_keeps_conversation():
    msgs = [
        Message(role="system", content="be terse"),
        Message(role="user", content="hi"),
        Message(role="assistant", content="hello"),
    ]
    system, convo = split_system(msgs)
    assert system == "be terse"
    assert convo == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]


def test_split_system_returns_none_when_no_system():
    system, convo = split_system([Message(role="user", content="hi")])
    assert system is None
    assert convo == [{"role": "user", "content": "hi"}]


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no ANTHROPIC_API_KEY")
async def test_anthropic_provider_streams_live():
    provider = AnthropicProvider()
    chunks = [
        d.text
        async for d in provider.stream(
            [Message(role="user", content="Reply with exactly the word: pong")],
            model="claude-haiku-4-5",
        )
    ]
    assert "".join(chunks).strip() != ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd core && uv run pytest tests/test_anthropic_provider.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'saddlery.llm.anthropic_provider'`.

- [ ] **Step 3: Write the implementation**

`core/saddlery/llm/anthropic_provider.py`:
```python
"""Native Anthropic provider. Default model is cheap Haiku for testing.

Keeps Claude-native features available (prompt caching, adaptive thinking) for
thinking-capable models; Haiku 4.5 supports neither, so neither is set here.
"""

from __future__ import annotations

from typing import AsyncIterator

import anthropic

from saddlery.llm.base import ProviderDelta, TextDelta
from saddlery.messages import Message


def split_system(messages: list[Message]) -> tuple[str | None, list[dict]]:
    """Separate system messages (Anthropic's `system` param) from the conversation."""
    system_parts = [m.content for m in messages if m.role == "system"]
    convo = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
    system = "\n\n".join(system_parts) if system_parts else None
    return system, convo


class AnthropicProvider:
    def __init__(
        self,
        client: anthropic.AsyncAnthropic | None = None,
        *,
        max_tokens: int = 1024,
    ) -> None:
        self._client = client or anthropic.AsyncAnthropic()
        self._max_tokens = max_tokens

    async def stream(
        self, messages: list[Message], *, model: str
    ) -> AsyncIterator[ProviderDelta]:
        system, convo = split_system(messages)
        kwargs: dict = {"model": model, "max_tokens": self._max_tokens, "messages": convo}
        if system is not None:
            kwargs["system"] = system
        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield TextDelta(text=text)
```

- [ ] **Step 4: Run tests to verify the pure tests pass and the live test is skipped**

Run: `cd core && uv run pytest tests/test_anthropic_provider.py -q`
Expected: PASS for the two `split_system` tests; the live test shows `s` (skipped) when `ANTHROPIC_API_KEY` is unset.

Run (optional, real network): `cd core && ANTHROPIC_API_KEY=sk-... uv run pytest tests/test_anthropic_provider.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add core/saddlery/llm/anthropic_provider.py core/tests/test_anthropic_provider.py
git commit -m "feat(core): add native AnthropicProvider with split_system helper"
```

---

## Task 8: CLI entrypoint (the demo)

**Files:**
- Create: `core/saddlery/cli/main.py`
- Test: `core/tests/test_cli_wiring.py`

- [ ] **Step 1: Write the failing test (wiring is importable + builds an Agent)**

`core/tests/test_cli_wiring.py` (sets a dummy key so `anthropic.AsyncAnthropic()` constructs offline — construction makes no network call):
```python
from saddlery.agent import Agent
from saddlery.cli.main import build_agent


def test_build_agent_returns_agent_with_default_model(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    agent = build_agent()
    assert isinstance(agent, Agent)
    assert agent.model == "claude-haiku-4-5"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd core && uv run pytest tests/test_cli_wiring.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'saddlery.cli.main'`.

- [ ] **Step 3: Write the implementation**

`core/saddlery/cli/main.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd core && uv run pytest tests/test_cli_wiring.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Manual end-to-end verification (the MAR-5 demo)**

Run: `cd core && ANTHROPIC_API_KEY=sk-... uv run saddlery`
Then type: `Say hello in five words.` and press Enter.
Expected: a streamed assistant reply appears token-by-token, then a newline; prompt returns for the next line; Ctrl-D exits.

- [ ] **Step 6: Commit**

```bash
git add core/saddlery/cli/main.py core/tests/test_cli_wiring.py
git commit -m "feat(core): add CLI echo-loop entrypoint (saddlery)"
```

---

## Task 9: Full-suite green, lint, and wrap-up

**Files:**
- Modify: `CHANGELOG.md`, `README.md`

- [ ] **Step 1: Run the whole suite and linter**

Run: `cd core && uv run pytest -q`
Expected: all tests pass (the one live Anthropic test skipped without a key).

Run: `cd core && uv run ruff check .`
Expected: `All checks passed!` (fix any reported issues, then re-run).

- [ ] **Step 2: Update `CHANGELOG.md`** — add under `### 2026-06-16` → `#### Added`:

```markdown
- **0.1 echo loop core** (`core/saddlery/`): event models, `Session` + `to_messages()` fold,
  `LLMProvider` seam + native `AnthropicProvider`, `EventSink` (`CliSink`), `Agent.run()` loop,
  and the `saddlery` CLI. First runnable artifact ([MAR-5](https://linear.app/mark-mansour/issue/MAR-5)).
```

- [ ] **Step 3: Update `README.md` status line** to:

```markdown
> Status: **Phase 0 in progress — 0.1 echo loop implemented.** Run `cd core && uv run saddlery`
> (needs `ANTHROPIC_API_KEY`).
```

- [ ] **Step 4: Commit and push the branch**

```bash
git add CHANGELOG.md README.md
git commit -m "docs: record 0.1 echo loop in changelog and readme"
git push -u origin mark/mar-5-01-echo-loop
```

- [ ] **Step 5: Update Linear** — set [MAR-5](https://linear.app/mark-mansour/issue/MAR-5) to **Done** (or open a PR from the branch and set MAR-5 to **In Review**). Add a devlog entry `research/devlog/2026-06-16-0.1-echo-loop.md` capturing decisions/dead-ends/learnings (skeleton in `research/devlog/README.md`); prompt Mark for his own reflections.

---

## Self-review notes

- **Spec coverage:** events (§5) → Task 2; session + fold + store (§5/§6) → Task 3; `LLMProvider` + `AnthropicProvider` + `FakeProvider` (§5/§6/§9) → Tasks 4, 7; `EventSink`/`CliSink`/`RecordingSink` (§5/§9) → Task 5; `Agent.run` + error invariant (§5/§7/§8) → Task 6; CLI demo (§7/§10) → Task 8; `principal` threaded throughout (§2) → events carry it, Agent passes it via `meta`; testing strategy (§9) → fold/loop/smoke tests present.
- **Deviations (documented):** `SessionStore` exposes `get_or_create` rather than spec's `load`/`append` (persistence write-path is a 0.8 concern); `LLMProvider.stream` gains a `model` kwarg so the model stays configurable on the `Agent` (spec §3).
- **Type consistency:** `UserMessage.content`, `AssistantMessage.content`, `AssistantMessageDelta.text`, `ErrorEvent.message`; `Message(role, content)`; `provider.stream(messages, *, model)`; `Agent(provider, system_prompt, model)`; `Session(session_id, principal)` — used identically across all tasks.

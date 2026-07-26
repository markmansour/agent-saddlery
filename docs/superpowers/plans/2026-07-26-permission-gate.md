# MM-9 Permission Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a permission gate (hooks → deny → allow → ask, deny wins) to the tool-execution
path, with a new `FileWriteTool` as the first gated tool and an "ask" round-trip rendered in the
TUI.

**Architecture:** A new `PermissionGate` seam (mirroring `ToolRegistry`) sits between `ToolCall`
emission and `tool.call()` inside `Agent.run()`. Two new events, `PermissionRequest` and
`PermissionDecision`, extend the existing JSON-lines stdin/stdout wire protocol so the backend can
suspend a run (via an `asyncio.Future`) and the TUI can answer it, reusing the channel user
messages already flow through.

**Tech Stack:** Python 3.12 (backend, `saddlery` package, pydantic events, `asyncio`), TypeScript
+ Ink (TUI), pytest + pytest-asyncio (`asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed).

## Global Constraints

- Every `Tool.call()` implementation never raises — all failures become
  `ToolExecutionResult(is_error=True)` (see `backend/saddlery/tools/base.py`).
- All events are pydantic `BaseModel` subclasses of `BaseEvent`, frozen, with a `Literal["..."]`
  `type` discriminator field, added to the `Event` union in `backend/saddlery/events.py`.
- Seams (`ToolRegistry`, `LLMProvider`, `EventSink`) are `Protocol`-based or plain classes
  constructed once in `build_agent()` — follow that shape for `PermissionGate`.
- Run `cd backend && uv run ruff format . && uv run ruff check . && uv run ty check` before every
  commit (matches pre-commit hooks already configured in this repo).
- Run `cd backend && uv run pytest tests/ -q` after every task — full suite must stay green (one
  pre-existing unrelated flake was fixed in MM-8's cleanup; there should be zero failures now).
- TUI changes: `cd frontend/tui && npm run test:run && npm run type-check && npm run lint`.

---

### Task 1: `PermissionRequest` / `PermissionDecision` events

**Files:**
- Modify: `backend/saddlery/events.py` (add two classes + extend the `Event` union)
- Test: `backend/tests/test_events.py`

**Interfaces:**
- Produces: `PermissionRequest(BaseEvent)` with fields `tool_call_id: str`, `tool_name: str`,
  `arguments: dict`, `type: Literal["permission_request"] = "permission_request"`.
- Produces: `PermissionDecision(BaseEvent)` with fields `tool_call_id: str`,
  `decision: Literal["allow", "deny"]`, `type: Literal["permission_decision"] = "permission_decision"`.
- Both join the `Event` discriminated union in the same file.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_events.py` (check the existing file first for the exact import/style
used for `ToolCall`/`ToolResult` tests — mirror that pattern). Example test body:

```python
def test_permission_request_round_trips_through_json():
    event = PermissionRequest(
        session_id="s1",
        principal="local",
        tool_call_id="call-1",
        tool_name="write_file",
        arguments={"path": "out.txt", "content": "hi"},
    )
    dumped = event.model_dump(mode="json")
    assert dumped["type"] == "permission_request"
    assert dumped["tool_call_id"] == "call-1"
    assert dumped["tool_name"] == "write_file"
    assert dumped["arguments"] == {"path": "out.txt", "content": "hi"}


def test_permission_decision_round_trips_through_json():
    event = PermissionDecision(
        session_id="s1",
        principal="local",
        tool_call_id="call-1",
        decision="allow",
    )
    dumped = event.model_dump(mode="json")
    assert dumped["type"] == "permission_decision"
    assert dumped["tool_call_id"] == "call-1"
    assert dumped["decision"] == "allow"


def test_permission_events_are_frozen():
    event = PermissionRequest(
        session_id="s1", principal="local", tool_call_id="c1", tool_name="x", arguments={}
    )
    with pytest.raises(ValidationError):
        event.tool_call_id = "changed"
```

Add the necessary imports at the top of the test file: `from saddlery.events import (...,
PermissionRequest, PermissionDecision)`, plus `import pytest` and
`from pydantic import ValidationError` if not already imported (check the file first — it likely
already imports `pytest` for other frozen-event tests on `ToolCall`/`ToolResult`).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_events.py -k permission -v`
Expected: FAIL with `ImportError: cannot import name 'PermissionRequest'`

- [ ] **Step 3: Write minimal implementation**

In `backend/saddlery/events.py`, add after the existing `ToolResult` class (before `ErrorEvent`):

```python
class PermissionRequest(BaseEvent):
    type: Literal["permission_request"] = "permission_request"
    tool_call_id: str
    tool_name: str
    arguments: dict


class PermissionDecision(BaseEvent):
    type: Literal["permission_decision"] = "permission_decision"
    tool_call_id: str
    decision: Literal["allow", "deny"]
```

Then update the `Event` union at the bottom of the file to include both new classes:

```python
Event = Annotated[
    SessionStarted
    | UserMessage
    | RunStarted
    | AssistantMessageDelta
    | AssistantMessage
    | ToolCall
    | ToolResult
    | PermissionRequest
    | PermissionDecision
    | RunFinished
    | ErrorEvent,
    Field(discriminator="type"),
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_events.py -v`
Expected: PASS (all tests in the file, not just the new ones — confirms the union edit didn't
break existing discriminator behavior)

- [ ] **Step 5: Lint, format, type-check**

Run: `cd backend && uv run ruff format . && uv run ruff check . && uv run ty check`
Expected: all three report no issues

- [ ] **Step 6: Commit**

```bash
cd /Users/markmansour/Documents/Code/agent-saddlery
git add backend/saddlery/events.py backend/tests/test_events.py
git commit -m "feat(events): add PermissionRequest and PermissionDecision event types"
```

---

### Task 2: `PermissionGate` — deny/allow/ask pipeline (no hooks yet)

**Files:**
- Create: `backend/saddlery/permissions/__init__.py` (empty, matches `tools/__init__.py` pattern)
- Create: `backend/saddlery/permissions/gate.py`
- Test: `backend/tests/test_permission_gate.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `Decision = Literal["allow", "deny", "ask"]`; `PermissionGate.__init__(self, *, allow:
  set[str], deny: set[str], hooks: list[Hook] | None = None) -> None`; `async def
  check(self, tool_name: str, arguments: dict, principal: str) -> Decision`. (`hooks` param and
  its type are introduced fully in Task 3; this task builds the class with an empty default so
  Task 3 only adds behavior, not a new constructor shape.)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_permission_gate.py`:

```python
"""Tests for PermissionGate: deny/allow/ask evaluation order."""

from __future__ import annotations

from saddlery.permissions.gate import PermissionGate


async def test_deny_wins_even_when_also_allowed():
    """Deny always wins, even if the same tool is also in the allow set."""
    gate = PermissionGate(allow={"write_file"}, deny={"write_file"})
    decision = await gate.check("write_file", {}, "local")
    assert decision == "deny"


async def test_allow_list_resolves_to_allow():
    gate = PermissionGate(allow={"read_file"}, deny=set())
    decision = await gate.check("read_file", {}, "local")
    assert decision == "allow"


async def test_unlisted_tool_falls_through_to_ask():
    gate = PermissionGate(allow=set(), deny=set())
    decision = await gate.check("write_file", {}, "local")
    assert decision == "ask"


async def test_deny_list_resolves_to_deny():
    gate = PermissionGate(allow=set(), deny={"shell"})
    decision = await gate.check("shell", {}, "local")
    assert decision == "deny"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_permission_gate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'saddlery.permissions'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/saddlery/permissions/__init__.py`:

```python
"""Permission gate seam — allow/deny/ask evaluation for tool execution."""
```

Create `backend/saddlery/permissions/gate.py`:

```python
"""The PermissionGate seam — hooks -> deny -> allow -> ask evaluation order.

Mirrors ToolRegistry: constructed once in build_agent(), called from Agent.run()
between emitting ToolCall and invoking tool.call().
"""

from __future__ import annotations

from typing import Literal

Decision = Literal["allow", "deny", "ask"]


class PermissionGate:
    def __init__(
        self,
        *,
        allow: set[str],
        deny: set[str],
    ) -> None:
        self._allow = allow
        self._deny = deny

    async def check(self, tool_name: str, arguments: dict, principal: str) -> Decision:
        if tool_name in self._deny:
            return "deny"
        if tool_name in self._allow:
            return "allow"
        return "ask"
```

Note: `arguments` and `principal` parameters are unused in this task's implementation (per-tool
granularity only, per the design spec) but are part of the permanent signature — Task 3 (hooks)
and Task 4 (per-session memory) both need them, so the signature is right from the start even
though the body doesn't use them yet.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_permission_gate.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Lint, format, type-check**

Run: `cd backend && uv run ruff format . && uv run ruff check . && uv run ty check`

Note: `ty`/`ruff` may flag unused parameters `arguments` and `principal` in `check()`. If so, this
is expected and acceptable — do not suppress with `# noqa` or rename with a leading underscore;
they are part of the stable public signature that Tasks 3–4 use for real. If `ruff` specifically
errors (not just warns) on unused arguments in a way that fails `ruff check`, check
`backend/pyproject.toml`'s `[tool.ruff.lint]` section for the exact rule codes enabled — ARG
rules are not in this project's ruleset (`E,F,I,B,UP,SIM,C4,ASYNC,PT,BLE,RUF` per MM-14), so no
action should be needed.

- [ ] **Step 6: Commit**

```bash
cd /Users/markmansour/Documents/Code/agent-saddlery
git add backend/saddlery/permissions/ backend/tests/test_permission_gate.py
git commit -m "feat(permissions): add PermissionGate with deny/allow/ask evaluation"
```

---

### Task 3: Hooks seam on `PermissionGate`

**Files:**
- Modify: `backend/saddlery/permissions/gate.py`
- Test: `backend/tests/test_permission_gate.py` (add to existing file)

**Interfaces:**
- Consumes: `PermissionGate` from Task 2.
- Produces: `HookResult = Literal["allow", "deny", "ask", "pass"]`; `Hook = Callable[[str, dict,
  str], HookResult]`; `PermissionGate.__init__(self, *, allow: set[str], deny: set[str], hooks:
  list[Hook] | None = None) -> None` (adds the `hooks` parameter, defaulting to `None` so Task 2's
  tests and any other caller need no changes).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_permission_gate.py`:

```python
async def test_hook_deny_overrides_allow_list():
    """A hook returning 'deny' wins even though the tool is in the allow list."""

    def always_deny(tool_name: str, arguments: dict, principal: str) -> str:
        return "deny"

    gate = PermissionGate(allow={"write_file"}, deny=set(), hooks=[always_deny])
    decision = await gate.check("write_file", {}, "local")
    assert decision == "deny"


async def test_hook_pass_falls_through_to_deny_list():
    """A hook returning 'pass' means 'no opinion' — the deny list still applies."""

    def no_opinion(tool_name: str, arguments: dict, principal: str) -> str:
        return "pass"

    gate = PermissionGate(allow=set(), deny={"shell"}, hooks=[no_opinion])
    decision = await gate.check("shell", {}, "local")
    assert decision == "deny"


async def test_hook_ask_short_circuits_even_with_allow_match():
    """A hook returning 'ask' wins over an allow-list match — hooks run first."""

    def force_ask(tool_name: str, arguments: dict, principal: str) -> str:
        return "ask"

    gate = PermissionGate(allow={"write_file"}, deny=set(), hooks=[force_ask])
    decision = await gate.check("write_file", {}, "local")
    assert decision == "ask"


async def test_no_hooks_behaves_like_task_2():
    """hooks=None (the default) skips hook evaluation entirely."""
    gate = PermissionGate(allow={"read_file"}, deny=set())
    decision = await gate.check("read_file", {}, "local")
    assert decision == "allow"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_permission_gate.py -k hook -v`
Expected: FAIL with `TypeError: PermissionGate.__init__() got an unexpected keyword argument 'hooks'`

- [ ] **Step 3: Write minimal implementation**

Replace the full contents of `backend/saddlery/permissions/gate.py`:

```python
"""The PermissionGate seam — hooks -> deny -> allow -> ask evaluation order.

Mirrors ToolRegistry: constructed once in build_agent(), called from Agent.run()
between emitting ToolCall and invoking tool.call().
"""

from __future__ import annotations

from typing import Callable, Literal

Decision = Literal["allow", "deny", "ask"]
HookResult = Literal["allow", "deny", "ask", "pass"]
Hook = Callable[[str, dict, str], HookResult]


class PermissionGate:
    def __init__(
        self,
        *,
        allow: set[str],
        deny: set[str],
        hooks: list[Hook] | None = None,
    ) -> None:
        self._allow = allow
        self._deny = deny
        self._hooks = hooks or []

    async def check(self, tool_name: str, arguments: dict, principal: str) -> Decision:
        for hook in self._hooks:
            result = hook(tool_name, arguments, principal)
            if result != "pass":
                return result

        if tool_name in self._deny:
            return "deny"
        if tool_name in self._allow:
            return "allow"
        return "ask"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_permission_gate.py -v`
Expected: PASS (8 tests total: 4 from Task 2 + 4 new)

- [ ] **Step 5: Lint, format, type-check**

Run: `cd backend && uv run ruff format . && uv run ruff check . && uv run ty check`

- [ ] **Step 6: Commit**

```bash
cd /Users/markmansour/Documents/Code/agent-saddlery
git add backend/saddlery/permissions/gate.py backend/tests/test_permission_gate.py
git commit -m "feat(permissions): add hooks seam to PermissionGate, running before deny/allow"
```

---

### Task 4: Per-session, per-tool decision memory

**Files:**
- Modify: `backend/saddlery/permissions/gate.py`
- Test: `backend/tests/test_permission_gate.py` (add to existing file)

**Interfaces:**
- Consumes: `PermissionGate` from Task 3.
- Produces: `PermissionGate.remember(self, tool_name: str, principal: str, decision:
  Literal["allow", "deny"]) -> None` — records a decision so future `check()` calls for the same
  `(principal, tool_name)` return it directly, skipping hooks/deny/allow/ask entirely. This method
  is what Task 6 (agent loop wiring) calls after an "ask" round-trip resolves.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_permission_gate.py`:

```python
async def test_remembered_decision_short_circuits_future_checks():
    """Once a decision is remembered for (principal, tool_name), check() returns it directly."""
    gate = PermissionGate(allow=set(), deny=set())  # unlisted -> would normally ask

    gate.remember("write_file", "local", "allow")
    decision = await gate.check("write_file", {}, "local")

    assert decision == "allow"


async def test_remembered_decision_is_scoped_per_principal():
    """A decision remembered for one principal does not apply to another."""
    gate = PermissionGate(allow=set(), deny=set())

    gate.remember("write_file", "local", "allow")
    decision = await gate.check("write_file", {}, "other-user")

    assert decision == "ask"  # not remembered for this principal


async def test_remembered_decision_is_scoped_per_tool():
    """A decision remembered for one tool does not apply to another tool."""
    gate = PermissionGate(allow=set(), deny=set())

    gate.remember("write_file", "local", "allow")
    decision = await gate.check("shell", {}, "local")

    assert decision == "ask"  # different tool, not remembered


async def test_remembered_deny_short_circuits_future_checks():
    gate = PermissionGate(allow={"write_file"}, deny=set())  # would normally allow

    gate.remember("write_file", "local", "deny")
    decision = await gate.check("write_file", {}, "local")

    assert decision == "deny"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_permission_gate.py -k remember -v`
Expected: FAIL with `AttributeError: 'PermissionGate' object has no attribute 'remember'`

- [ ] **Step 3: Write minimal implementation**

In `backend/saddlery/permissions/gate.py`, add the memory dict to `__init__` and a `remember`
method, and check the memory first in `check()`:

```python
class PermissionGate:
    def __init__(
        self,
        *,
        allow: set[str],
        deny: set[str],
        hooks: list[Hook] | None = None,
    ) -> None:
        self._allow = allow
        self._deny = deny
        self._hooks = hooks or []
        self._remembered: dict[tuple[str, str], Literal["allow", "deny"]] = {}

    def remember(self, tool_name: str, principal: str, decision: Literal["allow", "deny"]) -> None:
        self._remembered[(principal, tool_name)] = decision

    async def check(self, tool_name: str, arguments: dict, principal: str) -> Decision:
        remembered = self._remembered.get((principal, tool_name))
        if remembered is not None:
            return remembered

        for hook in self._hooks:
            result = hook(tool_name, arguments, principal)
            if result != "pass":
                return result

        if tool_name in self._deny:
            return "deny"
        if tool_name in self._allow:
            return "allow"
        return "ask"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_permission_gate.py -v`
Expected: PASS (12 tests total)

- [ ] **Step 5: Lint, format, type-check**

Run: `cd backend && uv run ruff format . && uv run ruff check . && uv run ty check`

- [ ] **Step 6: Commit**

```bash
cd /Users/markmansour/Documents/Code/agent-saddlery
git add backend/saddlery/permissions/gate.py backend/tests/test_permission_gate.py
git commit -m "feat(permissions): remember ask-decisions per (principal, tool_name)"
```

---

### Task 5: `FileWriteTool`

**Files:**
- Create: `backend/saddlery/tools/write_file.py`
- Test: `backend/tests/test_write_file.py`

**Interfaces:**
- Consumes: `Tool`, `ToolExecutionResult` from `backend/saddlery/tools/base.py` (unchanged).
- Produces: `FileWriteTool(root: Path | None = None)` with `.name == "write_file"`,
  `.input_schema` requiring `path` and `content` (both strings), and `async def call(self,
  arguments: dict) -> ToolExecutionResult`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_write_file.py`, mirroring `backend/tests/test_read_file.py`'s
structure exactly (same `tmp_path` fixture usage, same assertion style):

```python
"""Tests for FileWriteTool."""

from __future__ import annotations

import os
import sys

import pytest

from saddlery.tools.write_file import FileWriteTool


async def test_write_new_file(tmp_path):
    """FileWriteTool creates a new file with the given content."""
    tool = FileWriteTool(root=tmp_path)
    result = await tool.call({"path": "out.txt", "content": "hello"})

    assert not result.is_error
    assert (tmp_path / "out.txt").read_text() == "hello"


async def test_overwrite_existing_file(tmp_path):
    """FileWriteTool overwrites an existing file's content."""
    existing = tmp_path / "out.txt"
    existing.write_text("old content")

    tool = FileWriteTool(root=tmp_path)
    result = await tool.call({"path": "out.txt", "content": "new content"})

    assert not result.is_error
    assert existing.read_text() == "new content"


async def test_path_traversal_rejected(tmp_path):
    """Path traversal (../../etc/passwd) returns is_error=True and does not write."""
    tool = FileWriteTool(root=tmp_path)
    result = await tool.call({"path": "../../etc/passwd", "content": "pwned"})

    assert result.is_error
    assert "escape" in result.content.lower()


async def test_absolute_path_rejected(tmp_path):
    """Absolute path returns is_error=True and does not write."""
    tool = FileWriteTool(root=tmp_path)
    result = await tool.call({"path": "/etc/passwd", "content": "pwned"})

    assert result.is_error
    assert "escape" in result.content.lower()


async def test_missing_parent_directory_rejected(tmp_path):
    """Writing into a non-existent subdirectory returns is_error=True."""
    tool = FileWriteTool(root=tmp_path)
    result = await tool.call({"path": "no/such/dir/out.txt", "content": "hi"})

    assert result.is_error
    assert "not found" in result.content.lower() or "no such" in result.content.lower()


async def test_directory_path_rejected(tmp_path):
    """Writing to a path that is a directory returns is_error=True."""
    subdir = tmp_path / "subdir"
    subdir.mkdir()

    tool = FileWriteTool(root=tmp_path)
    result = await tool.call({"path": "subdir", "content": "hi"})

    assert result.is_error
    assert "directory" in result.content.lower()


async def test_missing_path_argument(tmp_path):
    tool = FileWriteTool(root=tmp_path)
    result = await tool.call({"content": "hi"})

    assert result.is_error
    assert "path" in result.content.lower()


async def test_missing_content_argument(tmp_path):
    tool = FileWriteTool(root=tmp_path)
    result = await tool.call({"path": "out.txt"})

    assert result.is_error
    assert "content" in result.content.lower()


async def test_non_string_content_argument(tmp_path):
    tool = FileWriteTool(root=tmp_path)
    result = await tool.call({"path": "out.txt", "content": 123})

    assert result.is_error
    assert "string" in result.content.lower()


async def test_invalid_arguments_type(tmp_path):
    tool = FileWriteTool(root=tmp_path)
    result = await tool.call("not a dict")  # type: ignore

    assert result.is_error
    assert "dictionary" in result.content.lower()


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="POSIX permission bits aren't enforced on Windows, and root bypasses them entirely",
)
async def test_os_permission_denied_rejected(tmp_path):
    """Writing into a directory without write permission returns is_error=True, not a crash.

    This is an OS-level filesystem PermissionError (e.g. a read-only directory) — a distinct
    failure mode from PermissionGate's allow/deny/ask decision (Task 2+), which governs whether
    the *call* happens at all. The gate can allow a write and the OS can still refuse it.
    """
    readonly_dir = tmp_path / "readonly"
    readonly_dir.mkdir()
    readonly_dir.chmod(0o555)
    try:
        tool = FileWriteTool(root=tmp_path)
        result = await tool.call({"path": "readonly/out.txt", "content": "x"})

        assert result.is_error
        assert "permission" in result.content.lower()
    finally:
        readonly_dir.chmod(0o755)  # restore so tmp_path cleanup can remove it


async def test_never_raises_exception(tmp_path):
    """FileWriteTool.call() never raises, only returns is_error=True."""
    tool = FileWriteTool(root=tmp_path)

    readonly_dir = tmp_path / "readonly2"
    readonly_dir.mkdir()
    readonly_dir.chmod(0o555)

    test_cases = [
        {},  # missing path and content
        {"path": "../../etc/passwd", "content": "x"},  # traversal
        {"path": "/etc/passwd", "content": "x"},  # absolute
        {"path": "no/such/dir/f.txt", "content": "x"},  # missing parent
        {"path": 123, "content": "x"},  # wrong type
        "not a dict",  # wrong type for arguments
    ]
    if sys.platform != "win32" and os.geteuid() != 0:
        # OS permission denied
        test_cases.append({"path": "readonly2/out.txt", "content": "x"})

    try:
        for args in test_cases:
            try:
                result = await tool.call(args)  # type: ignore
                assert isinstance(result.content, str)
                assert isinstance(result.is_error, bool)
            except Exception as e:
                raise AssertionError(
                    f"call() raised {type(e).__name__}: {e} for args {args}"
                ) from e
    finally:
        readonly_dir.chmod(0o755)


async def test_tool_attributes(tmp_path):
    tool = FileWriteTool(root=tmp_path)

    assert tool.name == "write_file"
    assert isinstance(tool.description, str)
    assert len(tool.description) > 0
    assert isinstance(tool.input_schema, dict)
    assert "properties" in tool.input_schema
    assert "path" in tool.input_schema["properties"]
    assert "content" in tool.input_schema["properties"]
    assert "required" in tool.input_schema
    assert "path" in tool.input_schema["required"]
    assert "content" in tool.input_schema["required"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_write_file.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'saddlery.tools.write_file'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/saddlery/tools/write_file.py`:

```python
"""Concrete tool implementation: write_file."""

from __future__ import annotations

from pathlib import Path

from saddlery.tools.base import Tool, ToolExecutionResult


class FileWriteTool(Tool):
    """Write text content to a file (UTF-8), creating or overwriting it."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path.cwd()
        self.name = "write_file"
        self.description = "Write text content to a file, creating or overwriting it."
        self.input_schema = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to write, relative to the root.",
                },
                "content": {
                    "type": "string",
                    "description": "The text content to write to the file.",
                },
            },
            "required": ["path", "content"],
        }

    async def call(self, arguments: dict) -> ToolExecutionResult:
        """Write content to a file, or return an error if it fails.

        Never raises; all failures become is_error=True results.
        """
        try:
            if not isinstance(arguments, dict):
                return ToolExecutionResult("Arguments must be a dictionary.", is_error=True)

            if "path" not in arguments:
                return ToolExecutionResult("Missing required argument: path", is_error=True)
            if "content" not in arguments:
                return ToolExecutionResult("Missing required argument: content", is_error=True)

            path_str = arguments["path"]
            if not isinstance(path_str, str):
                return ToolExecutionResult(
                    f"path must be a string, got {type(path_str).__name__}",
                    is_error=True,
                )

            content = arguments["content"]
            if not isinstance(content, str):
                return ToolExecutionResult(
                    f"content must be a string, got {type(content).__name__}",
                    is_error=True,
                )

            # Resolve path relative to root and check for traversal
            target_path = (self.root / path_str).resolve()
            try:
                target_path.relative_to(self.root.resolve())
            except ValueError:
                return ToolExecutionResult(
                    f"Path {path_str} escapes root directory.",
                    is_error=True,
                )

            if target_path.is_dir():
                return ToolExecutionResult(
                    f"Path {path_str} is a directory, not a file.",
                    is_error=True,
                )

            target_path.write_text(content, encoding="utf-8")
            return ToolExecutionResult(f"Wrote {len(content)} bytes to {path_str}")

        except FileNotFoundError:
            return ToolExecutionResult(
                f"Parent directory not found for: {arguments.get('path', 'unknown')}",
                is_error=True,
            )
        except IsADirectoryError:
            return ToolExecutionResult(
                f"Path is a directory: {arguments.get('path', 'unknown')}",
                is_error=True,
            )
        except PermissionError:
            return ToolExecutionResult(
                f"Permission denied: {arguments.get('path', 'unknown')}",
                is_error=True,
            )
        except Exception as e:
            return ToolExecutionResult(
                f"Error writing file: {type(e).__name__}: {e}",
                is_error=True,
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_write_file.py -v`
Expected: PASS (14 tests — `test_os_permission_denied_rejected` and the read-only-directory case
added to `test_never_raises_exception` are skipped on Windows or when running as root, per the
`skipif` guards)

- [ ] **Step 5: Lint, format, type-check**

Run: `cd backend && uv run ruff format . && uv run ruff check . && uv run ty check`

- [ ] **Step 6: Commit**

```bash
cd /Users/markmansour/Documents/Code/agent-saddlery
git add backend/saddlery/tools/write_file.py backend/tests/test_write_file.py
git commit -m "feat(tools): add FileWriteTool"
```

---

### Task 6: Wire `PermissionGate` into `Agent.run()` — allow/deny paths only

**Files:**
- Modify: `backend/saddlery/agent.py`
- Test: `backend/tests/test_agent.py`

**Interfaces:**
- Consumes: `PermissionGate.check(tool_name, arguments, principal) -> Decision` (Task 4),
  `PermissionRequest`/`PermissionDecision` events (Task 1, not yet used — the `ask` path is Task
  7).
- Produces: `Agent` gains a new field `permission_gate: PermissionGate | None = None` (defaulting
  to `None` so existing tests/callers that don't pass one keep working — Task 7 will make the
  `ask` path use it when present; this task only handles `allow`/`deny` resolution, and treats
  `ask` as if the gate were absent, i.e. runs the tool — Task 7 changes that).

This task deliberately does NOT implement the ask-suspend behavior yet — that is Task 7. This
task only proves that `allow` results in the tool running and `deny` results in a synthesized
error `ToolResult`, without calling `tool.call()`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_agent.py` (the file already has `_StubTool`, `_session_with_user`,
imports for `ToolRegistry`, `ToolCallDelta`, `FakeProvider`, `RecordingSink` — reuse those, add
one import: `from saddlery.permissions.gate import PermissionGate`):

```python
async def test_run_denied_tool_call_short_circuits_without_calling_tool():
    """A gate that denies a tool never calls tool.call(); ToolResult reflects the denial."""
    session = _session_with_user("call a tool")
    sink = RecordingSink()

    class _RaisingTool:
        """A tool that would fail the test if call() were ever invoked."""

        name = "get_info"
        description = "test"
        input_schema = {"type": "object", "properties": {}}

        async def call(self, arguments: dict) -> ToolExecutionResult:
            raise AssertionError("call() should not have been invoked for a denied tool")

    tools = ToolRegistry([_RaisingTool()])
    gate = PermissionGate(allow=set(), deny={"get_info"})

    fake = FakeProvider(
        chunks=["done"],
        tool_calls=[ToolCallDelta(id="call-1", name="get_info", input={"query": "x"})],
    )
    agent = Agent(provider=fake, tools=tools, permission_gate=gate)

    await agent.run(session, sink)

    tool_result_event = next(e for e in sink.events if e.type == "tool_result")
    assert tool_result_event.tool_call_id == "call-1"
    assert tool_result_event.is_error is True
    assert "denied" in tool_result_event.content.lower()


async def test_run_allowed_tool_call_executes_normally():
    """A gate that allows a tool proceeds to call tool.call() as before."""
    session = _session_with_user("call a tool")
    sink = RecordingSink()
    stub_tool = _StubTool(name="get_info", response="file contents")
    tools = ToolRegistry([stub_tool])
    gate = PermissionGate(allow={"get_info"}, deny=set())

    fake = FakeProvider(
        chunks=["Response text"],
        tool_calls=[ToolCallDelta(id="call-1", name="get_info", input={"query": "test"})],
    )
    agent = Agent(provider=fake, tools=tools, permission_gate=gate)

    await agent.run(session, sink)

    tool_result_event = next(e for e in sink.events if e.type == "tool_result")
    assert tool_result_event.content == "file contents"
    assert tool_result_event.is_error is False


async def test_run_without_permission_gate_behaves_as_before():
    """Agent without permission_gate (the default) is unaffected — existing behavior."""
    session = _session_with_user("call a tool")
    sink = RecordingSink()
    stub_tool = _StubTool(name="get_info", response="file contents")
    tools = ToolRegistry([stub_tool])

    fake = FakeProvider(
        chunks=["Response text"],
        tool_calls=[ToolCallDelta(id="call-1", name="get_info", input={"query": "test"})],
    )
    agent = Agent(provider=fake, tools=tools)  # no permission_gate

    await agent.run(session, sink)

    tool_result_event = next(e for e in sink.events if e.type == "tool_result")
    assert tool_result_event.content == "file contents"
    assert tool_result_event.is_error is False
```

Add `from saddlery.tools.base import ToolExecutionResult` to the top of `test_agent.py` if not
already imported (check the existing file — it's likely already imported since `_StubTool`
returns `ToolExecutionResult`).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_agent.py -k "denied or allowed_tool_call or without_permission" -v`
Expected: FAIL with `TypeError: Agent.__init__() got an unexpected keyword argument 'permission_gate'`

- [ ] **Step 3: Write minimal implementation**

In `backend/saddlery/agent.py`, add the import and the new field, then wire the check into the
tool-execution loop.

Add to the imports at the top:

```python
from saddlery.permissions.gate import PermissionGate
```

Add `permission_gate` to the `Agent` dataclass fields (after `max_tool_iterations`):

```python
@dataclass(frozen=True)
class Agent:
    provider: LLMProvider
    system_prompt: str = "You are a helpful assistant."
    model: str = DEFAULT_MODEL
    tools: ToolRegistry = field(default_factory=lambda: ToolRegistry([]))
    max_tool_iterations: int = 8
    permission_gate: PermissionGate | None = None
```

In the tool-execution loop inside `run()` (the `for call in tool_calls:` block), replace:

```python
                for call in tool_calls:
                    await emit(
                        ToolCall(
                            session_id=sid,
                            principal=principal,
                            tool_call_id=call.id,
                            tool_name=call.name,
                            arguments=call.input,
                        )
                    )
                    tool = self.tools.get(call.name)
                    if tool is None:
                        result_content, is_error = f"Error: unknown tool '{call.name}'", True
                    else:
                        outcome = await tool.call(call.input)
                        result_content, is_error = outcome.content, outcome.is_error
                    await emit(
                        ToolResult(
                            session_id=sid,
                            principal=principal,
                            tool_call_id=call.id,
                            content=result_content,
                            is_error=is_error,
                        )
                    )
```

with:

```python
                for call in tool_calls:
                    await emit(
                        ToolCall(
                            session_id=sid,
                            principal=principal,
                            tool_call_id=call.id,
                            tool_name=call.name,
                            arguments=call.input,
                        )
                    )
                    tool = self.tools.get(call.name)
                    if tool is None:
                        result_content, is_error = f"Error: unknown tool '{call.name}'", True
                    else:
                        decision = "allow"
                        if self.permission_gate is not None:
                            decision = await self.permission_gate.check(
                                call.name, call.input, principal
                            )
                        if decision == "deny":
                            result_content, is_error = "Permission denied", True
                        else:
                            # "ask" is handled fully in Task 7; for now treat it like "allow"
                            # so this task's scope stays limited to allow/deny.
                            outcome = await tool.call(call.input)
                            result_content, is_error = outcome.content, outcome.is_error
                    await emit(
                        ToolResult(
                            session_id=sid,
                            principal=principal,
                            tool_call_id=call.id,
                            content=result_content,
                            is_error=is_error,
                        )
                    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_agent.py -v`
Expected: PASS (all tests in the file — the 3 new plus every pre-existing one, confirming no
regression)

- [ ] **Step 5: Lint, format, type-check**

Run: `cd backend && uv run ruff format . && uv run ruff check . && uv run ty check`

- [ ] **Step 6: Commit**

```bash
cd /Users/markmansour/Documents/Code/agent-saddlery
git add backend/saddlery/agent.py backend/tests/test_agent.py
git commit -m "feat(agent): wire PermissionGate allow/deny into the tool-execution loop"
```

---

### Task 7: The "ask" round-trip — suspend and resume via `asyncio.Future`

**Files:**
- Modify: `backend/saddlery/agent.py`
- Test: `backend/tests/test_agent.py`

**Interfaces:**
- Consumes: `PermissionGate.check(...)` returning `"ask"` (Task 4); `PermissionRequest`,
  `PermissionDecision` events (Task 1); `PermissionGate.remember(...)` (Task 4).
- Produces: `Agent.run()` gains the ability to suspend mid-loop. A new dataclass field on `Agent`,
  `_pending_decisions: dict[str, asyncio.Future]`, and a new public method:
  `async def resolve_permission(self, tool_call_id: str, decision: Literal["allow", "deny"]) ->
  None`. This method is what Task 9 (CLI wiring) calls when a `permission_decision` JSON line
  arrives on stdin.

Design note on state placement: `Agent` is `@dataclass(frozen=True)` (immutable config), but a
single `Agent` instance's `run()` is called repeatedly across turns in the same process (see
`cli/main.py`'s input loop) — so pending-decision state must NOT be local to a single `run()` call,
because `resolve_permission` needs to reach it from outside that call, invoked by the CLI's
input-reading coroutine running concurrently.

`frozen=True` only blocks *rebinding* an attribute (`self.x = y` after `__init__`); it does not
block *mutating* a mutable object an attribute already points to (`self.x["key"] = y` is fine).
So the fix is a dataclass field holding a dict, created fresh per-instance via
`field(default_factory=dict, init=False, repr=False, compare=False)` — `init=False` keeps it out
of the generated `__init__` signature (callers never pass it), and `default_factory=dict` ensures
each `Agent` instance gets its own dict rather than sharing one across instances. This was
verified directly against this project's `ty` type checker before writing this plan: a bare
`# type: ignore` comment does **not** suppress `ty`'s `unresolved-attribute` diagnostic for an
attribute set via `object.__setattr__` in `__post_init__` (a `__post_init__`-based approach was
tried first and rejected for exactly this reason) — but a real dataclass field with
`default_factory` is understood natively by `ty` with zero ignore comments needed. Confirmed
working: `uv run ty check` passes clean on this pattern.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_agent.py`:

```python
async def test_run_ask_decision_suspends_until_resolved():
    """A gate that returns 'ask' suspends the run; resolve_permission() lets it continue."""
    session = _session_with_user("call a tool")
    sink = RecordingSink()
    stub_tool = _StubTool(name="write_file", response="wrote it")
    tools = ToolRegistry([stub_tool])
    gate = PermissionGate(allow=set(), deny=set())  # unlisted -> ask

    fake = FakeProvider(
        chunks=["Response text"],
        tool_calls=[ToolCallDelta(id="call-1", name="write_file", input={"path": "x"})],
    )
    agent = Agent(provider=fake, tools=tools, permission_gate=gate)

    run_task = asyncio.ensure_future(agent.run(session, sink))

    # Give the run loop a chance to reach the ask-suspend point.
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    request_event = next(e for e in sink.events if e.type == "permission_request")
    assert request_event.tool_call_id == "call-1"
    assert request_event.tool_name == "write_file"
    assert not run_task.done()  # still suspended, waiting for a decision

    await agent.resolve_permission("call-1", "allow")
    await run_task

    tool_result_event = next(e for e in sink.events if e.type == "tool_result")
    assert tool_result_event.content == "wrote it"
    assert tool_result_event.is_error is False

    decision_event = next(e for e in sink.events if e.type == "permission_decision")
    assert decision_event.tool_call_id == "call-1"
    assert decision_event.decision == "allow"


async def test_run_ask_deny_produces_error_result_without_calling_tool():
    """Denying via resolve_permission() short-circuits to an error ToolResult."""
    session = _session_with_user("call a tool")
    sink = RecordingSink()

    class _RaisingTool:
        name = "write_file"
        description = "test"
        input_schema = {"type": "object", "properties": {}}

        async def call(self, arguments: dict) -> ToolExecutionResult:
            raise AssertionError("call() should not have been invoked for a denied tool")

    tools = ToolRegistry([_RaisingTool()])
    gate = PermissionGate(allow=set(), deny=set())  # unlisted -> ask

    fake = FakeProvider(
        chunks=["done"],
        tool_calls=[ToolCallDelta(id="call-2", name="write_file", input={"path": "x"})],
    )
    agent = Agent(provider=fake, tools=tools, permission_gate=gate)

    run_task = asyncio.ensure_future(agent.run(session, sink))
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    await agent.resolve_permission("call-2", "deny")
    await run_task

    tool_result_event = next(e for e in sink.events if e.type == "tool_result")
    assert tool_result_event.is_error is True
    assert "denied" in tool_result_event.content.lower()


async def test_run_remembers_ask_decision_for_second_call_in_same_run():
    """After one 'allow' decision, a second call to the same tool in a later iteration
    does not ask again (PermissionGate.remember() was invoked)."""
    session = _session_with_user("call a tool twice")
    sink = RecordingSink()
    stub_tool = _StubTool(name="write_file", response="ok")
    tools = ToolRegistry([stub_tool])
    gate = PermissionGate(allow=set(), deny=set())

    class TwoRoundProvider:
        """Emits a tool call for two iterations, then text — matches FakeProvider's shape."""

        def __init__(self) -> None:
            self._call_count = 0

        async def stream(self, messages, *, model, tools=None):
            self._call_count += 1
            if self._call_count <= 2:
                yield ToolCallDelta(
                    id=f"call-{self._call_count}", name="write_file", input={"path": "x"}
                )
            else:
                yield TextDelta(text="done")

    agent = Agent(provider=TwoRoundProvider(), tools=tools, permission_gate=gate)

    run_task = asyncio.ensure_future(agent.run(session, sink))
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    await agent.resolve_permission("call-1", "allow")

    # Give the loop time to advance to the second tool call before asserting no second ask.
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    await run_task

    request_events = [e for e in sink.events if e.type == "permission_request"]
    assert len(request_events) == 1  # only asked once, second call was remembered
```

Add these imports to the top of `test_agent.py` if not already present: `import asyncio`, and
`from saddlery.llm.base import TextDelta` (check the file first — `ToolCallDelta` is already
imported from the same module).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_agent.py -k "ask or remembers" -v`
Expected: FAIL with `AttributeError: 'Agent' object has no attribute 'resolve_permission'`

- [ ] **Step 3: Write minimal implementation**

In `backend/saddlery/agent.py`, make these changes:

1. Add imports: `import asyncio` at the top (with the other stdlib imports); change
   `from dataclasses import dataclass, field` (already imported — `field` is already used for
   `tools`) to also use `field` for the new attribute below; add `Literal` to the existing
   `typing` import so it reads `from typing import TYPE_CHECKING, Literal`; add
   `PermissionRequest` and `PermissionDecision` to the existing
   `from saddlery.events import (...)` block; add
   `from saddlery.permissions.gate import PermissionGate` (this import was already added in
   Task 6 — do not duplicate it if present).

2. Add the mutable-state field to the `Agent` dataclass, after `permission_gate` (added in Task
   6):

```python
    permission_gate: PermissionGate | None = None
    _pending_decisions: dict[str, asyncio.Future] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )
```

`init=False` keeps this out of `Agent(...)`'s constructor signature — callers never pass it, and
it doesn't appear in `Agent.__init__`. `default_factory=dict` gives each `Agent` instance its own
dict. This is a real, statically-visible dataclass field (not a dynamically-added attribute), so
`ty check` understands it natively — no `# type: ignore` needed anywhere for this attribute
(verified directly against this project's `ty` before writing this plan: an `object.__setattr__`
+ `__post_init__` alternative was tried first and rejected because `ty`'s
`unresolved-attribute` diagnostic could not be suppressed even with an ignore comment; a real
field has no such problem).

3. Add the public `resolve_permission` method (place it as a method on `Agent`, e.g. directly
   after `run`):

```python
    async def resolve_permission(
        self, tool_call_id: str, decision: Literal["allow", "deny"]
    ) -> None:
        future = self._pending_decisions.get(tool_call_id)
        if future is not None and not future.done():
            future.set_result(decision)
```

4. Replace the tool-execution loop body (from Task 6) to handle `"ask"` properly instead of
   treating it like allow. Find the block Task 6 introduced:

```python
                    tool = self.tools.get(call.name)
                    if tool is None:
                        result_content, is_error = f"Error: unknown tool '{call.name}'", True
                    else:
                        decision = "allow"
                        if self.permission_gate is not None:
                            decision = await self.permission_gate.check(
                                call.name, call.input, principal
                            )
                        if decision == "deny":
                            result_content, is_error = "Permission denied", True
                        else:
                            # "ask" is handled fully in Task 7; for now treat it like "allow"
                            # so this task's scope stays limited to allow/deny.
                            outcome = await tool.call(call.input)
                            result_content, is_error = outcome.content, outcome.is_error
```

Replace it with:

```python
                    tool = self.tools.get(call.name)
                    if tool is None:
                        result_content, is_error = f"Error: unknown tool '{call.name}'", True
                    else:
                        decision: str = "allow"
                        if self.permission_gate is not None:
                            decision = await self.permission_gate.check(
                                call.name, call.input, principal
                            )
                            if decision == "ask":
                                await emit(
                                    PermissionRequest(
                                        session_id=sid,
                                        principal=principal,
                                        tool_call_id=call.id,
                                        tool_name=call.name,
                                        arguments=call.input,
                                    )
                                )
                                decision_future: asyncio.Future = (
                                    asyncio.get_running_loop().create_future()
                                )
                                self._pending_decisions[call.id] = decision_future
                                try:
                                    decision = await decision_future
                                finally:
                                    del self._pending_decisions[call.id]
                                await emit(
                                    PermissionDecision(
                                        session_id=sid,
                                        principal=principal,
                                        tool_call_id=call.id,
                                        decision=decision,
                                    )
                                )
                                self.permission_gate.remember(call.name, principal, decision)
                        if decision == "deny":
                            result_content, is_error = "Permission denied", True
                        else:
                            outcome = await tool.call(call.input)
                            result_content, is_error = outcome.content, outcome.is_error
```

Note the variable is named `decision_future` (not `future`) to avoid any ambiguity with the outer
scope, and `decision: str` is annotated broadly (not `Decision` from `permissions.gate`) because
after the `await decision_future` reassignment it holds a `Literal["allow", "deny"]` value, a
narrower type than the `Decision = Literal["allow", "deny", "ask"]` it started as — using `str` is
the simplest correct annotation without introducing a type-narrowing dance for a locally-scoped
variable used only for control flow (this passes `ty check`, see Step 5).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_agent.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Lint, format, type-check**

Run: `cd backend && uv run ruff format . && uv run ruff check . && uv run ty check`
Expected: all three pass clean, no ignore comments needed anywhere in this task's changes.

- [ ] **Step 6: Commit**

```bash
cd /Users/markmansour/Documents/Code/agent-saddlery
git add backend/saddlery/agent.py backend/tests/test_agent.py
git commit -m "feat(agent): suspend on ask-decisions via asyncio.Future, resolve_permission()"
```

---

### Task 8: Config loading — `.saddlery/permissions.json` + `build_agent()` wiring

**Files:**
- Create: `backend/saddlery/permissions/config.py`
- Modify: `backend/saddlery/cli/main.py`
- Modify: `backend/saddlery/cli/input.py`
- Test: `backend/tests/test_permission_config.py`
- Test: `backend/tests/test_cli_wiring.py` (add to existing file)

**Interfaces:**
- Produces: `load_permission_config(path: Path | None = None) -> tuple[set[str], set[str]]` —
  returns `(allow, deny)` sets. Defaults to `.saddlery/permissions.json` relative to CWD; if the
  file doesn't exist, returns `(set(), set())` (everything unlisted, so everything hits `ask` by
  default — a safe default with zero config).
- Modifies `build_agent()` (`backend/saddlery/cli/main.py`) to construct a `PermissionGate` from
  the loaded config and pass it to `Agent(...)`, and to register `FileWriteTool` alongside
  `FileReadTool`.
- Modifies `cli/input.py`'s `read_user_messages_json()` to also recognize
  `{"type": "permission_decision", ...}` lines — but per this task's scope, that recognition needs
  somewhere to route the decision to. Task 9 wires the actual `agent.resolve_permission(...)`
  call from `cli/main.py`'s main loop, since `input.py`'s reader function doesn't have a reference
  to the `Agent` instance today. This task only adds the config loader and tool/gate wiring in
  `build_agent()`; input.py's stdin-side change is Task 9's responsibility (kept separate so this
  task's test surface stays about config loading only).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_permission_config.py`:

```python
"""Tests for loading .saddlery/permissions.json."""

from __future__ import annotations

import json

from saddlery.permissions.config import load_permission_config


def test_loads_allow_and_deny_from_file(tmp_path):
    config_path = tmp_path / "permissions.json"
    config_path.write_text(json.dumps({"allow": ["read_file"], "deny": ["shell"]}))

    allow, deny = load_permission_config(config_path)

    assert allow == {"read_file"}
    assert deny == {"shell"}


def test_missing_file_returns_empty_sets(tmp_path):
    config_path = tmp_path / "does_not_exist.json"

    allow, deny = load_permission_config(config_path)

    assert allow == set()
    assert deny == set()


def test_missing_keys_default_to_empty_sets(tmp_path):
    config_path = tmp_path / "permissions.json"
    config_path.write_text(json.dumps({}))

    allow, deny = load_permission_config(config_path)

    assert allow == set()
    assert deny == set()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_permission_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'saddlery.permissions.config'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/saddlery/permissions/config.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_permission_config.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Write the failing test for `build_agent()` wiring**

Add to `backend/tests/test_cli_wiring.py`:

```python
def test_build_agent_registers_write_file_tool(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    agent = build_agent()
    assert agent.tools.get("write_file") is not None
    assert agent.tools.get("read_file") is not None


def test_build_agent_constructs_permission_gate(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    agent = build_agent()
    assert agent.permission_gate is not None
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_cli_wiring.py -v`
Expected: FAIL — `agent.tools.get("write_file")` is `None`, and/or `agent.permission_gate` is
`None` (whichever assertion pytest reaches first)

- [ ] **Step 7: Write minimal implementation**

In `backend/saddlery/cli/main.py`, add imports:

```python
from saddlery.permissions.config import load_permission_config
from saddlery.permissions.gate import PermissionGate
from saddlery.tools.write_file import FileWriteTool
```

Modify `build_agent()`'s final lines — replace:

```python
    provider = MockLMProvider() if use_mock else AnthropicProvider()
    return Agent(provider=provider, tools=ToolRegistry([FileReadTool()]))
```

with:

```python
    provider = MockLMProvider() if use_mock else AnthropicProvider()
    allow, deny = load_permission_config()
    gate = PermissionGate(allow=allow, deny=deny)
    return Agent(
        provider=provider,
        tools=ToolRegistry([FileReadTool(), FileWriteTool()]),
        permission_gate=gate,
    )
```

- [ ] **Step 8: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_cli_wiring.py tests/test_permission_config.py -v`
Expected: PASS (all tests)

- [ ] **Step 9: Run the full suite to confirm no regression**

Run: `cd backend && uv run pytest tests/ -q`
Expected: all tests pass (this is the first task where `build_agent()`'s output changes shape —
confirm nothing else asserted the old `ToolRegistry([FileReadTool()])`-only shape)

- [ ] **Step 10: Lint, format, type-check**

Run: `cd backend && uv run ruff format . && uv run ruff check . && uv run ty check`

- [ ] **Step 11: Commit**

```bash
cd /Users/markmansour/Documents/Code/agent-saddlery
git add backend/saddlery/permissions/config.py backend/saddlery/cli/main.py \
        backend/tests/test_permission_config.py backend/tests/test_cli_wiring.py
git commit -m "feat(cli): load permission config, wire PermissionGate and FileWriteTool into build_agent()"
```

---

### Task 9: Stdin wiring — `permission_decision` reaches `agent.resolve_permission()`

**Files:**
- Modify: `backend/saddlery/cli/main.py`
- Test: `backend/tests/test_cli_wiring.py` (add to existing file) — this task's core logic is best
  tested as an integration-style test of `_amain()`'s loop shape, but since `_amain()` is an
  entrypoint function that's hard to unit test in isolation (it owns stdin/stdout directly), this
  task instead restructures the JSON input reading so the routing logic is a separately testable
  function. See Step 1.

**Interfaces:**
- Consumes: `Agent.resolve_permission(tool_call_id: str, decision: Literal["allow", "deny"]) ->
  None` (Task 7).
- Produces: a new function `parse_input_line(line: str) -> tuple[str, dict] | None` in
  `cli/input.py`, replacing the inline `json.loads` + `obj.get("type")` dispatch currently
  duplicated across `read_user_messages_json`'s body — returns `(event_type, payload)` or `None`
  for a blank/unparseable line, so `_amain()`'s loop can route `"user_message"` vs
  `"permission_decision"` without `cli/input.py` needing to know about `Agent` at all.

Design note: `read_user_messages_json()` currently only yields `str` (user message content) and
silently drops anything that isn't `type: "user_message"`. Since it needs to now also let
`permission_decision` lines through to the caller, its generator's yield type must change from
`str` to something that carries both kinds of message. Rather than overload the string type
(fragile), this task changes `read_user_messages_json()` to yield the parsed `(event_type,
payload)` tuple instead of a bare string, and moves the "extract content for a user_message" logic
into `_amain()`'s loop. This is a signature change to an existing function — check for other
callers before starting (Step 0 below).

- [ ] **Step 0: Check for other callers of `read_user_messages_json`**

Run: `cd backend && grep -rn "read_user_messages_json" --include="*.py" .`
Expected: only `cli/input.py` (definition) and `cli/main.py` (the one call site already read in
this plan's context-gathering). If this search finds additional callers, stop and adapt this
task's steps to update them too — do not proceed with only `cli/main.py` in mind if there are
others.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_cli_wiring.py` (new import needed: `from saddlery.cli.input import
parse_input_line`):

```python
def test_parse_input_line_extracts_user_message():
    result = parse_input_line('{"type": "user_message", "content": "hello"}')
    assert result == ("user_message", {"content": "hello"})


def test_parse_input_line_extracts_permission_decision():
    result = parse_input_line(
        '{"type": "permission_decision", "tool_call_id": "call-1", "decision": "allow"}'
    )
    assert result == (
        "permission_decision",
        {"tool_call_id": "call-1", "decision": "allow"},
    )


def test_parse_input_line_returns_none_for_blank_line():
    assert parse_input_line("") is None
    assert parse_input_line("   ") is None


def test_parse_input_line_returns_none_for_malformed_json():
    assert parse_input_line("{not valid json") is None


def test_parse_input_line_returns_none_for_unknown_type():
    assert parse_input_line('{"type": "something_else"}') is None


def test_parse_input_line_returns_none_for_empty_user_message_content():
    result = parse_input_line('{"type": "user_message", "content": "   "}')
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_cli_wiring.py -k parse_input_line -v`
Expected: FAIL with `ImportError: cannot import name 'parse_input_line'`

- [ ] **Step 3: Write minimal implementation — `parse_input_line`**

In `backend/saddlery/cli/input.py`, add this function (place it above
`read_user_messages_json`):

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_cli_wiring.py -k parse_input_line -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Rewrite `read_user_messages_json` to use `parse_input_line` and yield tuples**

Replace `read_user_messages_json` in `backend/saddlery/cli/input.py` with:

```python
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
```

Delete the old `read_user_messages_json` function body — `read_input_lines` replaces it. Keep
`read_user_messages_interactive` unchanged (interactive terminal mode has no permission-decision
concept — a human types directly, and Task 10's TUI-only ask-prompt doesn't apply to the plain
interactive CLI mode in this slice).

- [ ] **Step 6: Update `cli/main.py`'s `_amain()` to consume the new shape**

In `backend/saddlery/cli/main.py`, update the import:

```python
from saddlery.cli.input import parse_input_line, read_input_lines, read_user_messages_interactive
```

(Remove `read_user_messages_json` from the import list — it no longer exists.)

Replace the `_use_json_input`-driven section of `_amain()`. Find:

```python
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
```

Replace with:

```python
    # Determine input mode: JSON (for TUI) or interactive (for CLI)
    use_json = _use_json_input()

    try:
        if use_json:
            async for event_type, payload in read_input_lines():
                if event_type == "user_message":
                    session.append(
                        UserMessage(
                            session_id=session.session_id,
                            principal=principal,
                            content=payload["content"],
                        )
                    )
                    await agent.run(session, sink)
                elif event_type == "permission_decision":
                    await agent.resolve_permission(
                        payload["tool_call_id"], payload["decision"]
                    )
        else:
            print("Agent Saddlery — 0.1 echo loop. Type a message; Ctrl-D to exit.")
            async for text in read_user_messages_interactive():
                session.append(
                    UserMessage(session_id=session.session_id, principal=principal, content=text)
                )
                await agent.run(session, sink)
    finally:
        log.info(
            "session_finished", session_id=session.session_id, event_count=len(session.events)
        )
```

Note the behavior change this introduces: previously, `await agent.run(session, sink)` blocked
the whole input loop until the run finished, meaning no second `user_message` could be processed
concurrently with a pending "ask." With this change, `agent.run(...)` is still awaited
sequentially inside the `user_message` branch — but `permission_decision` lines are now read from
the *same* loop, interleaved. Because `read_input_lines()` reads one line at a time and the loop
body awaits `agent.run(...)` to completion before reading the next line, a `permission_decision`
line sent by the TUI while a run is suspended on `await future` (Task 7) will not be read until
the *next* iteration of this same `async for` loop — but that iteration is blocked because we're
inside `await agent.run(...)` from the *previous* iteration, which is itself suspended waiting for
that very `permission_decision`. **This is a deadlock as written.** Fix it: `agent.run(...)` must
be scheduled as a background task (not awaited inline) so the input loop keeps reading lines
(including the `permission_decision` that unblocks the running task) while a run is in-flight.
This was verified directly before writing this plan: a background-task version was tested against
`loop.run_in_executor(None, sys.stdin.readline)` (the exact mechanism `read_input_lines()` uses)
with a real pending `asyncio.Future`, confirming `run_in_executor` genuinely yields control back
to the event loop between each line read — so the input loop can read and process a
`permission_decision` line while a scheduled run task is suspended on `await decision_future`,
with no deadlock. Change the `user_message` branch to:

```python
                if event_type == "user_message":
                    session.append(
                        UserMessage(
                            session_id=session.session_id,
                            principal=principal,
                            content=payload["content"],
                        )
                    )
                    asyncio.ensure_future(agent.run(session, sink))
```

This means `_amain()` no longer waits for a run to finish before reading the next stdin line,
which is required for the ask round-trip to work at all, but changes the shutdown behavior: on
EOF (`read_input_lines()` returning), a run may still be in-flight. Handle this by tracking the
task and awaiting it after the loop:

```python
    pending_run: asyncio.Task | None = None
    try:
        if use_json:
            async for event_type, payload in read_input_lines():
                if event_type == "user_message":
                    session.append(
                        UserMessage(
                            session_id=session.session_id,
                            principal=principal,
                            content=payload["content"],
                        )
                    )
                    pending_run = asyncio.ensure_future(agent.run(session, sink))
                elif event_type == "permission_decision":
                    await agent.resolve_permission(
                        payload["tool_call_id"], payload["decision"]
                    )
            if pending_run is not None:
                await pending_run
        else:
            print("Agent Saddlery — 0.1 echo loop. Type a message; Ctrl-D to exit.")
            async for text in read_user_messages_interactive():
                session.append(
                    UserMessage(session_id=session.session_id, principal=principal, content=text)
                )
                await agent.run(session, sink)
    finally:
        log.info(
            "session_finished", session_id=session.session_id, event_count=len(session.events)
        )
```

This keeps `read_user_messages_interactive`'s plain CLI mode fully synchronous (unchanged
behavior — no concurrent-run concept needed there, since it has no ask-prompt UI), while the JSON
mode (used by the TUI) now runs each turn as a background task so incoming
`permission_decision` lines can be read and routed while a run is suspended.

- [ ] **Step 7: Run the full backend test suite**

Run: `cd backend && uv run pytest tests/ -q`
Expected: all tests pass. Pay particular attention to any test that previously called
`read_user_messages_json` directly (Step 0's grep should have already ruled this out, but this is
the checkpoint to catch it if missed).

- [ ] **Step 8: Lint, format, type-check**

Run: `cd backend && uv run ruff format . && uv run ruff check . && uv run ty check`

- [ ] **Step 9: Manual smoke test**

Run: `cd backend && echo '{"type": "user_message", "content": "Write hello to demo.txt"}' | uv run python -m saddlery.cli.main --json-input --test-mode`

Expected: with `--test-mode` (mock provider), the mock never calls tools, so this should just
stream a canned response and `run_finished` — confirming the restructured loop still completes a
plain turn without hanging. This does not exercise the ask path (mock never emits tool calls) —
that end-to-end path is exercised in Task 10's manual test once the TUI can answer prompts.

- [ ] **Step 10: Commit**

```bash
cd /Users/markmansour/Documents/Code/agent-saddlery
git add backend/saddlery/cli/input.py backend/saddlery/cli/main.py backend/tests/test_cli_wiring.py
git commit -m "feat(cli): route permission_decision lines to agent.resolve_permission(), run turns as background tasks"
```

---

### Task 10: TUI — render `permission_request`, send `permission_decision`

**Files:**
- Modify: `frontend/tui/src/core/subprocess.ts`
- Modify: `frontend/tui/src/components/ChatApp.tsx`
- Modify: `frontend/tui/src/components/MessageHistory.tsx`
- Test: `frontend/tui/src/core/subprocess.test.ts` (check if this file exists already — if not,
  check whatever test file covers `CoreSubprocess`'s event handling today, e.g. search for
  `describe("CoreSubprocess"` or similar, and add to that file instead of creating a new one)

**Interfaces:**
- Consumes: `permission_request` / `permission_decision` wire events (backend Tasks 1, 7, 9).
- Produces: `CoreSubprocess` emits a new JS event `"permission_request"` with payload `{
  toolCallId: string; toolName: string; arguments: Record<string, unknown> }`; gains a new public
  method `sendPermissionDecision(toolCallId: string, decision: "allow" | "deny"): void`.

- [ ] **Step 1: Find the existing subprocess test file**

Run: `cd frontend/tui && grep -rl "CoreSubprocess" src/ --include="*.test.ts"`
Expected: one file (or none, if `CoreSubprocess` is only tested via a different pattern — check
`src/core/` and `src/components/` for any `.test.ts`/`.test.tsx` files and read whichever one
imports `CoreSubprocess` before writing Step 2's test, so the new tests match the existing
mocking/setup style exactly, e.g. how `this.process` / spawn is mocked).

- [ ] **Step 2: Write the failing test**

Add to the file found in Step 1 (adapt the exact mocking setup to match what's already there —
the following shows the test bodies, not the file's boilerplate/setup which must be copied from
existing tests in the same file):

```typescript
it("emits permission_request when a permission_request event arrives", () => {
  const core = new CoreSubprocess();
  const handler = vi.fn();
  core.on("permission_request", handler);

  // Reach into the private handleEvent the same way existing tests in this file do
  // (check the existing test file for the exact technique — likely calling a private
  // method via `(core as any).handleEvent(...)` or emitting a raw stdout line through
  // the mocked process, matching the established pattern in this file).
  (core as unknown as { handleEvent: (e: unknown) => void }).handleEvent({
    event_type: "permission_request",
    event_data: {
      tool_call_id: "call-1",
      tool_name: "write_file",
      arguments: { path: "out.txt" },
    },
  });

  expect(handler).toHaveBeenCalledWith({
    toolCallId: "call-1",
    toolName: "write_file",
    arguments: { path: "out.txt" },
  });
});

it("sendPermissionDecision writes a permission_decision JSON line to stdin", () => {
  const core = new CoreSubprocess();
  const writeSpy = vi.fn();
  (core as unknown as { process: { stdin: { write: typeof writeSpy } } }).process = {
    stdin: { write: writeSpy },
  };

  core.sendPermissionDecision("call-1", "allow");

  expect(writeSpy).toHaveBeenCalledWith(
    JSON.stringify({
      type: "permission_decision",
      tool_call_id: "call-1",
      decision: "allow",
    }) + "\n"
  );
});
```

Note: adapt the mock setup for `process.stdin` to match exactly how the existing test file mocks
`this.process` for `sendUserMessage` tests, if one exists — do not invent a different mocking
approach for consistency's sake.

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend/tui && npm run test:run`
Expected: FAIL — `permission_request` handler never called (no such case in `handleEvent`), and/or
`sendPermissionDecision is not a function`

- [ ] **Step 4: Write minimal implementation**

In `frontend/tui/src/core/subprocess.ts`, add a new `else if` branch inside `handleEvent` (place
it after the existing `tool_result` branch, before `run_finished`):

```typescript
    } else if (eventType === "permission_request") {
      const eventData = event.event_data as Record<string, unknown>;
      const toolCallId = eventData?.tool_call_id as string | undefined;
      const toolName = eventData?.tool_name as string | undefined;
      const args = eventData?.arguments as Record<string, unknown> | undefined;
      const ts = new Date().toISOString();
      appendFileSync(
        "tui.log",
        `${ts} [? ask] ${toolName}(${JSON.stringify(args)})\n`
      );
      if (toolCallId && toolName) {
        this.emit("permission_request", {
          toolCallId,
          toolName,
          arguments: args ?? {},
        });
      }
    } else if (eventType === "run_finished") {
```

(This inserts before the existing `} else if (eventType === "run_finished") {` line — do not
duplicate it, just add the new branch immediately above it.)

Add the new public method after `sendUserMessage` (matching its exact style):

```typescript
  sendPermissionDecision(toolCallId: string, decision: "allow" | "deny"): void {
    if (!this.process?.stdin) {
      throw new Error("Core process not running");
    }

    const msg = {
      type: "permission_decision",
      tool_call_id: toolCallId,
      decision,
    };

    const msgStr = JSON.stringify(msg);
    const ts = new Date().toISOString();
    appendFileSync("tui.log", `${ts} [→ decision] ${toolCallId}: ${decision}\n`);
    appendFileSync("tui.log", `${ts} [wire→] ${msgStr}\n`);
    this.process.stdin.write(msgStr + "\n");
  }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend/tui && npm run test:run`
Expected: PASS (all tests, including the 2 new ones)

- [ ] **Step 6: Wire the TUI's chat UI to show the prompt and answer it**

This step has no isolated unit test (it's UI wiring exercised by the manual smoke test in Step 8)
— follow TDD's spirit by keeping this step minimal and verifying by hand immediately after.

In `frontend/tui/src/components/ChatApp.tsx`, add a new piece of state for a pending permission
prompt, alongside the existing `useState` calls:

```typescript
  const [pendingPermission, setPendingPermission] = useState<{
    toolCallId: string;
    toolName: string;
    arguments: Record<string, unknown>;
  } | null>(null);
```

Add a new `core.on("permission_request", ...)` handler inside the `initCore` function, placed
after the existing `core.on("tool_result", ...)` handler:

```typescript
        core.on(
          "permission_request",
          (request: { toolCallId: string; toolName: string; arguments: Record<string, unknown> }) => {
            setPendingPermission(request);
          }
        );
```

Add a handler function near `handleUserMessage`:

```typescript
  const handlePermissionResponse = (allow: boolean) => {
    if (!pendingPermission || !coreRef.current) return;
    coreRef.current.sendPermissionDecision(
      pendingPermission.toolCallId,
      allow ? "allow" : "deny"
    );
    setPendingPermission(null);
  };
```

Modify `handleUserMessage`'s first line to also handle the case where a permission prompt is
pending — the input box, when a permission is pending, should interpret `y`/`n` as the answer
instead of sending a normal chat message:

```typescript
  const handleUserMessage = (content: string) => {
    if (pendingPermission) {
      const answer = content.trim().toLowerCase();
      if (answer === "y" || answer === "yes") {
        handlePermissionResponse(true);
      } else if (answer === "n" || answer === "no") {
        handlePermissionResponse(false);
      }
      return;
    }

    if (isRunning || !coreRef.current) return;
    // ... existing body unchanged below this point
```

Finally, render the prompt. In the `return (...)` JSX, add a conditional block above
`<InputBox ...>`:

```typescript
      {pendingPermission && (
        <Box marginBottom={1}>
          <Text color="yellow" bold>
            Allow {pendingPermission.toolName}(
            {JSON.stringify(pendingPermission.arguments)})? [y/n]
          </Text>
        </Box>
      )}
      <InputBox onSubmit={handleUserMessage} disabled={isRunning && !pendingPermission} />
```

Note the `disabled` prop change: `isRunning && !pendingPermission` — the input box must stay
enabled while a permission is pending even though `isRunning` is true (a run is suspended, not
finished), so the user can type `y`/`n`. Import `Text` at the top of the file if not already
imported (`ChatApp.tsx` currently imports `Box` from `"ink"` — check whether `Text` needs adding
to that import line).

- [ ] **Step 7: Type-check and lint the TUI**

Run: `cd frontend/tui && npm run type-check && npm run lint`
Expected: both pass with no errors

- [ ] **Step 8: Manual end-to-end smoke test**

This is the first point in the whole plan where the full round-trip can be verified against the
real Anthropic API (the mock provider never calls tools, so `--test-mode` cannot exercise this).

```bash
# Terminal 1 — from repo root, with a real ANTHROPIC_API_KEY in .env (see README Quick Start)
cd frontend/tui
npm run dev
```

In the TUI, type: `Write "hello from the permission gate" to demo.txt`

Expected: the model calls `write_file`, a yellow `Allow write_file(...)? [y/n]` prompt appears,
typing `y` and pressing Enter allows the write (confirm `demo.txt` was created in `backend/` with
the expected content), and the conversation continues normally afterward. Typing `n` for a
different request should show a "Permission denied" tool-result line instead, with no file
written.

- [ ] **Step 9: Run the full test suites one more time (backend + TUI)**

Run: `cd backend && uv run pytest tests/ -q && cd ../frontend/tui && npm run test:run`
Expected: all green, zero failures

- [ ] **Step 10: Commit**

```bash
cd /Users/markmansour/Documents/Code/agent-saddlery
git add frontend/tui/src/core/subprocess.ts frontend/tui/src/components/ChatApp.tsx \
        frontend/tui/src/components/MessageHistory.tsx
git add frontend/tui/src/core/*.test.ts 2>/dev/null || true
git commit -m "feat(tui): render permission_request prompts and send permission_decision"
```

---

### Task 11: Documentation — README, docs/tools/, DEVELOPMENT.md

**Files:**
- Modify: `README.md`
- Modify: `docs/tools/README.md`
- Modify: `DEVELOPMENT.md`
- Create: `docs/diagrams/permission-gate-sequence.md`

This task has no code/tests of its own — it documents what Tasks 1–10 built, following the same
pattern established for MM-8 (see `docs/tools/README.md`'s existing structure and
`docs/diagrams/tool-round-trip-sequence.md` as the template for the new sequence diagram).

- [ ] **Step 1: Add a hand-authored sequence diagram**

Create `docs/diagrams/permission-gate-sequence.md`, following the exact header/banner convention
of `docs/diagrams/tool-round-trip-sequence.md` (hand-authored diagrams get a one-line
provenance note, not the generated-file banner):

```markdown
# Permission gate (MM-9) — sequence

Hand-authored. Extends the MM-8 tool round-trip: `PermissionGate.check()` runs between emitting
`ToolCall` and invoking `tool.call()`. An "ask" result suspends `Agent.run()` on an
`asyncio.Future` until `resolve_permission()` is called — see `Agent.run()` and
`docs/specs/2026-07-25-permission-gate-design.md`.

\`\`\`mermaid
sequenceDiagram
    participant TUI
    participant Agent
    participant PermissionGate
    participant Tool
    participant EventSink

    Agent->>EventSink: emit(ToolCall)
    Agent->>PermissionGate: check(tool_name, arguments, principal)
    alt hook or list resolves to deny
        PermissionGate-->>Agent: "deny"
        Agent->>EventSink: emit(ToolResult(is_error=True, "Permission denied"))
    else hook or list resolves to allow
        PermissionGate-->>Agent: "allow"
        Agent->>Tool: call(arguments)
        Tool-->>Agent: ToolExecutionResult
        Agent->>EventSink: emit(ToolResult)
    else nothing resolves it
        PermissionGate-->>Agent: "ask"
        Agent->>EventSink: emit(PermissionRequest)
        Agent->>Agent: await future (suspended)
        TUI->>Agent: resolve_permission(tool_call_id, decision) [via stdin]
        Agent->>EventSink: emit(PermissionDecision)
        Agent->>PermissionGate: remember(tool_name, principal, decision)
        alt decision == allow
            Agent->>Tool: call(arguments)
            Tool-->>Agent: ToolExecutionResult
            Agent->>EventSink: emit(ToolResult)
        else decision == deny
            Agent->>EventSink: emit(ToolResult(is_error=True, "Permission denied"))
        end
    end
\`\`\`
```

(Remove the backslash-escapes before the triple-backtick fences above when actually writing the
file — they're shown here only to keep this plan's own markdown from breaking.)

- [ ] **Step 2: Update `docs/diagrams/README.md`'s table**

Add a row to the existing table (mirroring the `tool-round-trip-sequence.md` row added for MM-8):

```markdown
| [permission-gate-sequence.md](permission-gate-sequence.md) | Hand-authored — the MM-9 permission gate ask round-trip. |
```

- [ ] **Step 3: Add a "Permission gate" section to `docs/tools/README.md`**

Add a new top-level section (after the existing "Tools" content, before "Debugging tool calls" —
check the file's current structure and place it logically), covering: the `PermissionGate`
evaluation order (hooks → deny → allow → ask), where `.saddlery/permissions.json` lives and its
schema, `FileWriteTool`'s schema/safety constraints (mirroring how `read_file` is documented in
the same file), and a link to `docs/diagrams/permission-gate-sequence.md`.

- [ ] **Step 4: Add a "Quick start" note about `.saddlery/permissions.json`**

In `README.md`'s Quick Start section, add one sentence noting that tool calls without an
allow/deny entry will prompt for approval in the TUI, and link to `docs/tools/README.md` for
details.

- [ ] **Step 5: Add a manual-testing note to `DEVELOPMENT.md`**

Add a short subsection (mirroring the existing "Testing tool calls" section's style) showing how
to manually exercise the ask round-trip via the TUI (the same steps as Task 10 Step 8), plus how
to pre-populate `.saddlery/permissions.json` to skip prompts during repeated manual testing.

- [ ] **Step 6: Commit**

```bash
cd /Users/markmansour/Documents/Code/agent-saddlery
git add README.md docs/tools/README.md DEVELOPMENT.md docs/diagrams/
git commit -m "docs: document the MM-9 permission gate (README, docs/tools, DEVELOPMENT.md, sequence diagram)"
```

---

## Self-Review Notes

**Spec coverage:** §1 (evaluation pipeline) → Tasks 2–4. §2 (config) → Task 8. §3 (ask round-trip)
→ Tasks 1, 7, 9. §4 (TUI rendering) → Task 10. §5 (`FileWriteTool`) → Task 5. §6 (`principal`
scoping) → threaded through Tasks 2–4, 6–7 (every `check()`/`remember()` call already takes
`principal`). Testing section → covered by every task's own test steps; the specific "deny wins
even when allow also matches" case named in the issue is `test_deny_wins_even_when_also_allowed`
in Task 2, Step 1. Out-of-scope items are correctly not built anywhere in this plan.

**Deadlock fix (verified, not just asserted):** Task 9 surfaced and fixed a real correctness bug
during planning — awaiting `agent.run()` inline in the input loop would deadlock the ask
round-trip, since the same loop that reads the resolving `permission_decision` line would be
blocked awaiting the run it's supposed to unblock. Fixed by running turns as background tasks
(`asyncio.ensure_future`) instead of awaiting them inline, with a `pending_run` tracked and awaited
after the input loop ends (EOF) so the process doesn't exit mid-run. This fix was tested directly
(a standalone script using `loop.run_in_executor(None, sys.stdin.readline)`-equivalent line
reading plus a real `asyncio.Future`) before writing this plan, confirming `run_in_executor`
genuinely yields control between reads so the fix works and doesn't just move the race elsewhere.

**Frozen dataclass + mutable state:** `Agent` is `@dataclass(frozen=True)`; Task 7's suspend/resume
mechanism needs mutable per-instance state (`_pending_decisions`) reachable both from inside
`run()` and from an externally-called `resolve_permission()`. The plan originally specified
`__post_init__` + `object.__setattr__` (a common pattern for this in general Python code) but this
was tested directly against this project's actual type checker (`ty`) before finalizing the plan
and found to produce an `unresolved-attribute` diagnostic that a bare `# type: ignore` comment
does not suppress. Switched to a real dataclass field —
`field(default_factory=dict, init=False, repr=False, compare=False)` — which `ty check` accepts
natively with zero ignore comments (also verified directly). `frozen=True` blocks *rebinding* an
attribute but not *mutating* a mutable object it already points to, so `self._pending_decisions[k]
= v` works fine at runtime even though `self._pending_decisions = {}` would raise.

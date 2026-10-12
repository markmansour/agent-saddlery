# Permission Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the permission gate capability classes, per-resource rules, a fail-closed shell command classifier, taint, serialized runs and strict config, so MM-10 can put a shell tool behind it.

**Architecture:** Tools declare a `capability` and name the thing a call acts on (`resource`, a tuple of tokens). `Agent.run()` builds an immutable `PolicyRequest` per tool call (including a `tainted` flag folded from the event log) and hands it to `PermissionGate.check()`, which evaluates deny → hooks → remembered → allow (taint-aware) → class default → ask. Rules are `(tool, token-prefix)` pairs loaded from `<root>/.saddlery/permissions.json` with strict validation. The backend runs one turn at a time per session.

**Tech Stack:** Python 3.12, pydantic v2, pytest (`asyncio_mode=auto`), ruff, ty (all enforced by pre-commit); TypeScript, Ink, vitest for the TUI.

**Spec:** `docs/specs/2026-10-12-permission-policy-design.md` (read it first; this plan implements §1–§8). Related: `docs/specs/2026-07-25-permission-gate-design.md` (MM-9).

## Global Constraints

- Python `>=3.12`; backend code under `backend/saddlery/`, tests under `backend/tests/`. Run Python tools from `backend/` as `.venv/bin/pytest`, `.venv/bin/python`.
- Commits run pre-commit (ruff format, ruff check, ty). Fix what they report; never `--no-verify`.
- **No AI attribution in any commit**: no `Co-Authored-By` trailer, no "Generated with" line.
- Tools never raise from `call()`; failures are `ToolExecutionResult(..., is_error=True)`.
- Events are frozen pydantic models (`BaseEvent` has `ConfigDict(frozen=True)`).
- Evaluation order, exactly: `deny → hooks → remembered → allow (taint-aware) → class default → ask`. Deny always wins, including over a hook.
- Capability classes, exactly: `read`, `write`, `exec`, `network`. Defaults when nothing decides: `read` → allow; `write`, `exec`, `network` → ask. A tool with a missing or invalid `capability` raises at registration. There is no default class.
- A shell command is **simple** only if all hold: `shlex` (`posix=True`, `punctuation_chars=True`, `whitespace_split=True`) parses it; no operator token (`; & | && || < > ( )`); none of `` ` ``, `$`, `\n`, `\r`, `\`, `*`, `?`, `~`, `{` appears anywhere in the raw string; `argv[0]` is not `NAME=value`. Anything else is `rejected` and denied before hooks.
- Remembered approvals: `write` class only, keyed `(principal, tool, exact resource tuple)`. Never for `exec` or `network`.
- Taint: a call is tainted when a `ToolResult` exists since the last `UserMessage`. It downgrades an allow-list match for `write`/`exec`/`network` to ask. It does not affect deny, remembered decisions, hooks (they see the flag) or `read`.
- Config: missing file → defaults; malformed file, unknown tool, invalid rule, or an unflagged single-token executor allow rule → startup fails with `ConfigError`.
- Token matching is NFC-normalized and case-folded on both sides (plan simplification of spec §3: applied to every tool's tokens, not only paths; it only widens matching, which fails closed for deny).
- **Checkpoint rule.** Tasks 4, 5, 6 and 7 change APIs that `cli/main.py` and `test_cli_wiring.py` still use, so ty and part of the suite are intentionally red between them. Do **not** commit in Tasks 4, 5 or 6: run only the test files each task names, then commit all four tasks' files together at the end of Task 7, when the full suite and pre-commit are green. Tasks 1, 2 and 3 commit on their own.
- The shell tool itself (MM-10) is **out of scope**. This plan builds the classifier and gate support it will use.

## Review Focus

Failure modes the spec implies; each has a test in the named task.

1. A case or Unicode variant of a denied path (`Docs/A.md`, NFD `é`) slipping past `deny: [{"tool":"write_file","match":["docs"]}]` — Task 1 (resource folding), Task 4 (matching), Task 5 (gate).
2. A sibling name matching a prefix rule (`docs-private` vs `["docs"]`) — Task 4, Task 5.
3. A hook returning `allow` overriding a static deny — Task 5.
4. A user message sent mid-run resetting taint or interleaving the event log — Task 3.
5. The approved target changing between check and use (symlink swapped after approval) — Task 6.

## File Structure

| File | Responsibility |
|---|---|
| `backend/saddlery/tools/base.py` (modify) | `Capability`, `CAPABILITIES`, `ResourceError`; `Tool` gains `capability`, `resource()`, `detail()` |
| `backend/saddlery/tools/paths.py` (create) | `fold()` and `path_resource()`: canonical path resource tuples |
| `backend/saddlery/tools/registry.py` (modify) | Reject tools with a missing or invalid capability |
| `backend/saddlery/tools/read_file.py`, `write_file.py` (modify) | Declare capability; implement `resource()`; write via `O_NOFOLLOW` |
| `backend/saddlery/permissions/shell.py` (create) | `ShellCommand`, `classify()`, `deny_candidates()` |
| `backend/saddlery/permissions/rules.py` (create) | `Rule`, `as_rule()`, prefix matching with folding |
| `backend/saddlery/permissions/config.py` (rewrite) | Strict loader → `PermissionConfig`, `ConfigError` |
| `backend/saddlery/permissions/gate.py` (rewrite) | `PolicyRequest`, `PermissionGate.check(request)` |
| `backend/saddlery/session.py` (modify) | `Session.is_tainted()` |
| `backend/saddlery/events.py` (modify) | `PermissionRequest` gains `capability`, `resource`, `tainted` |
| `backend/saddlery/agent.py` (modify) | Build `PolicyRequest`; `_run_tool_call()`, `_ask()`; re-check resource before executing |
| `backend/saddlery/cli/runner.py` (create) | `SessionRunner`: one run at a time, queued messages |
| `backend/saddlery/cli/main.py` (modify) | Use `SessionRunner`; load config from the root; exit on `ConfigError` |
| `frontend/tui/src/components/permissionPrompt.ts` (create) | `formatPermissionPrompt()` |
| `frontend/tui/src/core/subprocess.ts`, `components/ChatApp.tsx` (modify) | Pass and render the new request fields |
| `docs/tools/README.md`, spec, devlog (modify/create) | Documentation |

---

### Task 1: Capability classes and resources on tools

**Files:**
- Modify: `backend/saddlery/tools/base.py`, `backend/saddlery/tools/registry.py`, `backend/saddlery/tools/read_file.py`, `backend/saddlery/tools/write_file.py`
- Create: `backend/saddlery/tools/paths.py`
- Test: `backend/tests/test_paths.py` (create), `backend/tests/test_tool_registry.py` (create), `backend/tests/test_read_file.py`, `backend/tests/test_write_file.py` (append)
- Modify (fixtures): `backend/tests/test_agent.py`

**Interfaces:**
- Produces:
  - `saddlery.tools.base.Capability = Literal["read","write","exec","network"]`, `CAPABILITIES: frozenset[str]`, `class ResourceError(ValueError)`.
  - `Tool.capability: Capability`; `Tool.resource(self, arguments: dict) -> tuple[str, ...]` (raises `ResourceError`); `Tool.detail(self, arguments: dict) -> object | None` (default returns `None`).
  - `saddlery.tools.paths.fold(token: str) -> str`; `path_resource(root: Path, arguments: object) -> tuple[str, ...]`.
  - `ToolRegistry(tools)` raises `ValueError` for a tool without a valid `capability`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_paths.py`:

```python
"""Tests for canonical path resources."""

from __future__ import annotations

import unicodedata

import pytest

from saddlery.tools.base import ResourceError
from saddlery.tools.paths import fold, path_resource


def test_path_resource_returns_normalized_parts(tmp_path):
    assert path_resource(tmp_path, {"path": "docs/a.md"}) == ("docs", "a.md")


def test_path_resource_folds_case(tmp_path):
    assert path_resource(tmp_path, {"path": "Docs/A.MD"}) == ("docs", "a.md")


def test_path_resource_normalizes_unicode(tmp_path):
    nfd = unicodedata.normalize("NFD", "café.txt")
    nfc = unicodedata.normalize("NFC", "café.txt")
    assert path_resource(tmp_path, {"path": nfd}) == path_resource(tmp_path, {"path": nfc})


def test_path_resource_collapses_dotdot_inside_root(tmp_path):
    assert path_resource(tmp_path, {"path": "docs/../src/x.py"}) == ("src", "x.py")


def test_path_resource_rejects_escape(tmp_path):
    with pytest.raises(ResourceError):
        path_resource(tmp_path, {"path": "../outside.txt"})


def test_path_resource_rejects_absolute_outside_root(tmp_path):
    with pytest.raises(ResourceError):
        path_resource(tmp_path, {"path": "/etc/passwd"})


def test_path_resource_rejects_symlink_out_of_root(tmp_path):
    outside = tmp_path.parent / "outside_dir"
    outside.mkdir(exist_ok=True)
    (tmp_path / "link").symlink_to(outside)
    with pytest.raises(ResourceError):
        path_resource(tmp_path, {"path": "link/x.txt"})


@pytest.mark.parametrize("arguments", [None, [], {}, {"path": ""}, {"path": 3}])
def test_path_resource_rejects_bad_arguments(tmp_path, arguments):
    with pytest.raises(ResourceError):
        path_resource(tmp_path, arguments)


def test_fold_is_idempotent():
    assert fold(fold("Straße")) == fold("Straße")
```

`backend/tests/test_tool_registry.py`:

```python
"""ToolRegistry rejects tools that do not declare a valid capability."""

from __future__ import annotations

import pytest

from saddlery.tools.registry import ToolRegistry


class _T:
    name = "t"
    description = "d"
    input_schema: dict = {"type": "object", "properties": {}}

    async def call(self, arguments):  # pragma: no cover - never called
        raise AssertionError


def test_registry_rejects_tool_without_capability():
    with pytest.raises(ValueError, match="capability"):
        ToolRegistry([_T()])


def test_registry_rejects_invalid_capability():
    tool = _T()
    tool.capability = "sideways"  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="sideways"):
        ToolRegistry([tool])


def test_registry_accepts_each_valid_capability():
    for cap in ("read", "write", "exec", "network"):
        tool = _T()
        tool.capability = cap  # type: ignore[attr-defined]
        assert ToolRegistry([tool]).get("t") is tool
```

Append to `backend/tests/test_read_file.py`:

```python
def test_read_file_declares_read_capability():
    assert FileReadTool().capability == "read"


def test_read_file_resource_is_normalized_path_parts(tmp_path):
    tool = FileReadTool(root=tmp_path)
    assert tool.resource({"path": "Docs/A.md"}) == ("docs", "a.md")


def test_read_file_resource_rejects_escape(tmp_path):
    from saddlery.tools.base import ResourceError

    tool = FileReadTool(root=tmp_path)
    with pytest.raises(ResourceError):
        tool.resource({"path": "../x"})
```

Append to `backend/tests/test_write_file.py`:

```python
def test_write_file_declares_write_capability():
    assert FileWriteTool().capability == "write"


def test_write_file_resource_is_normalized_path_parts(tmp_path):
    tool = FileWriteTool(root=tmp_path)
    assert tool.resource({"path": "Docs/A.md", "content": "x"}) == ("docs", "a.md")
```

(If `pytest`, `FileReadTool` or `FileWriteTool` are not already imported at the top of those files, add the imports.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_paths.py tests/test_tool_registry.py tests/test_read_file.py tests/test_write_file.py -q`
Expected: collection errors / FAIL (`saddlery.tools.paths` missing, `ResourceError` undefined).

- [ ] **Step 3: Implement**

`backend/saddlery/tools/base.py`: add after the imports and keep everything else:

```python
from typing import Literal, Protocol, runtime_checkable

Capability = Literal["read", "write", "exec", "network"]
CAPABILITIES: frozenset[str] = frozenset({"read", "write", "exec", "network"})


class ResourceError(ValueError):
    """The tool's arguments do not name a valid resource (bad type, escapes the root)."""
```

and replace the `Tool` protocol body:

```python
@runtime_checkable
class Tool(Protocol):
    """Mirrors MCP's tool shape: schema (name/description/input_schema) + call().

    input_schema is a JSON Schema object (MCP's inputSchema, snake_case on our side).
    capability classifies the tool's side effects for the permission policy.
    """

    name: str
    description: str
    input_schema: dict
    capability: Capability

    async def call(self, arguments: dict) -> ToolExecutionResult: ...

    def resource(self, arguments: dict) -> tuple[str, ...]:
        """Name what this call acts on, as normalized tokens. Raise ResourceError if invalid."""
        ...

    def detail(self, arguments: dict) -> object | None:
        """Optional structured classification passed to the permission policy."""
        return None
```

`backend/saddlery/tools/paths.py`:

```python
"""Canonical resource tuples for path-based tools."""

from __future__ import annotations

import unicodedata
from pathlib import Path

from saddlery.tools.base import ResourceError


def fold(token: str) -> str:
    """NFC-normalize and case-fold a token, for matching on every filesystem."""
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", token).casefold())


def path_resource(root: Path, arguments: object) -> tuple[str, ...]:
    """Resolve arguments['path'] against root; return its normalized parts relative to root."""
    if not isinstance(arguments, dict):
        raise ResourceError("Arguments must be a dictionary.")
    path_str = arguments.get("path")
    if not isinstance(path_str, str) or not path_str:
        raise ResourceError("path must be a non-empty string")
    target = (root / path_str).resolve()
    try:
        relative = target.relative_to(root.resolve())
    except ValueError:
        raise ResourceError(f"Path {path_str} escapes root directory.") from None
    return tuple(fold(part) for part in relative.parts)
```

`backend/saddlery/tools/registry.py`: import `CAPABILITIES` at runtime and validate:

```python
from saddlery.tools.base import CAPABILITIES

    def __init__(self, tools: list[Tool]) -> None:
        for tool in tools:
            capability = getattr(tool, "capability", None)
            if capability not in CAPABILITIES:
                raise ValueError(
                    f"Tool {tool.name!r} must declare a capability in "
                    f"{sorted(CAPABILITIES)}, got {capability!r}"
                )
        self._tools = {tool.name: tool for tool in tools}
```

`backend/saddlery/tools/read_file.py`: add imports `from saddlery.tools.base import Capability, Tool, ToolExecutionResult` and `from saddlery.tools.paths import path_resource`; add to the class:

```python
    capability: Capability = "read"

    def resource(self, arguments: dict) -> tuple[str, ...]:
        return path_resource(self.root, arguments)
```

`backend/saddlery/tools/write_file.py`: same imports; add `capability: Capability = "write"` and the same `resource()` method. Replace the final `target_path.write_text(content, encoding="utf-8")` with a no-follow write:

```python
            fd = os.open(
                target_path,
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                0o666,
            )
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
```

and add `import os` at the top.

`backend/tests/test_agent.py` fixtures: add near the top

```python
class _PolicyStub:
    """Capability/resource/detail members every stub tool needs."""

    capability = "write"

    def resource(self, arguments: dict) -> tuple[str, ...]:
        return ("stub",)

    def detail(self, arguments: dict) -> object | None:
        return None
```

and make every stub tool class in that file inherit it: `class _StubTool(_PolicyStub):` and each `class _RaisingTool(_PolicyStub):` (there is one inside each of two tests).

- [ ] **Step 4: Run the full suite**

Run: `cd backend && .venv/bin/pytest -q`
Expected: all pass (the new tests plus the existing ones).

- [ ] **Step 5: Commit**

```bash
git add backend/saddlery/tools backend/tests
git commit -m "feat(tools): capability classes and canonical path resources"
```

---

### Task 2: Shell command classifier

**Files:**
- Create: `backend/saddlery/permissions/shell.py`
- Test: `backend/tests/test_shell_classifier.py` (create)

**Interfaces:**
- Produces: `ShellCommand(raw: str, argv: tuple[str, ...] | None, kind: Literal["simple","rejected"])` (frozen dataclass); `classify(raw: str) -> ShellCommand`; `deny_candidates(cmd: ShellCommand) -> list[tuple[str, ...]]` (the argvs a deny rule should be matched against: the command's own argv plus, best-effort, the inner commands of `bash -c`/`sh -c`).

- [ ] **Step 1: Write the failing test**

```python
"""The shell classifier fails closed: only provably simple commands are simple."""

from __future__ import annotations

import pytest

from saddlery.permissions.shell import classify, deny_candidates

SIMPLE = [
    ("git status", ("git", "status")),
    ("ls -la", ("ls", "-la")),
    ('echo "a;b"', ("echo", "a;b")),
    ("pytest -x tests/", ("pytest", "-x", "tests/")),
    ("find . -delete", ("find", ".", "-delete")),
    ("sudo rm -rf /", ("sudo", "rm", "-rf", "/")),
    ("bash -c 'rm -rf /'", ("bash", "-c", "rm -rf /")),
    ("ls #notacomment", ("ls", "#notacomment")),
]

REJECTED = [
    "ls; rm -rf ~",
    "ls && pwd | wc",
    "a & b",
    "ls > out.txt",
    "cat <<EOF",
    "cat <(id)",
    "echo (a)",
    "echo `id`",
    'echo "$(id)"',
    "echo $HOME",
    "ls\nrm -rf x",
    "ls\\\n-la",
    "FOO=1 git status",
    "ls {a,b}",
    "ls *.py",
    "ls ?",
    "echo ~",
    'echo "unclosed',
    "",
    "   ",
]


@pytest.mark.parametrize(("raw", "argv"), SIMPLE)
def test_simple_commands(raw, argv):
    cmd = classify(raw)
    assert cmd.kind == "simple"
    assert cmd.argv == argv
    assert cmd.raw == raw


@pytest.mark.parametrize("raw", REJECTED)
def test_rejected_commands(raw):
    cmd = classify(raw)
    assert cmd.kind == "rejected"
    assert cmd.argv is None


def test_deny_candidates_of_plain_command_is_its_argv():
    assert deny_candidates(classify("git status")) == [("git", "status")]


def test_deny_candidates_look_inside_bash_dash_c():
    cands = deny_candidates(classify('bash -c "rm -rf /"'))
    assert ("bash", "-c", "rm -rf /") in cands
    assert ("rm", "-rf", "/") in cands


def test_deny_candidates_split_compound_inner_command():
    cands = deny_candidates(classify('sh -c "ls; rm -rf /"'))
    assert ("ls",) in cands
    assert ("rm", "-rf", "/") in cands


def test_deny_candidates_handle_combined_flags_and_nesting():
    cands = deny_candidates(classify("""bash -lc "sh -c 'rm -rf /'" """))
    assert ("rm", "-rf", "/") in cands


def test_deny_candidates_of_rejected_command_is_empty():
    assert deny_candidates(classify("ls; rm -rf /")) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_shell_classifier.py -q`
Expected: FAIL (`saddlery.permissions.shell` missing).

- [ ] **Step 3: Implement `backend/saddlery/permissions/shell.py`**

```python
"""Fail-closed shell command classifier for the permission policy.

A command is *simple* only if it is provably one program with literal arguments. Anything
else is *rejected*. The shell tool never invokes a shell, so only simple commands ever run
and the argv recorded here is exactly what executes.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import Literal

_FORBIDDEN_CHARS = frozenset("`$\n\r\\*?~{")
_OPERATOR_CHARS = frozenset(";&|<>()")
_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
_SHELLS = frozenset({"bash", "sh", "zsh", "dash"})
_DASH_C = re.compile(r"-[A-Za-z]*c[A-Za-z]*")
_INNER_SPLIT = re.compile(r"[;&|\n\r`()<>]+")
_MAX_NESTING = 3


@dataclass(frozen=True)
class ShellCommand:
    raw: str
    argv: tuple[str, ...] | None
    kind: Literal["simple", "rejected"]


def classify(raw: str) -> ShellCommand:
    rejected = ShellCommand(raw=raw, argv=None, kind="rejected")
    if not raw.strip() or any(char in _FORBIDDEN_CHARS for char in raw):
        return rejected
    lexer = shlex.shlex(raw, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        return rejected
    if not tokens or _ASSIGNMENT.match(tokens[0]):
        return rejected
    if any(set(token) <= _OPERATOR_CHARS for token in tokens):
        return rejected
    return ShellCommand(raw=raw, argv=tuple(tokens), kind="simple")


def deny_candidates(cmd: ShellCommand) -> list[tuple[str, ...]]:
    """Argvs a deny rule should be matched against, best-effort.

    Includes the command's own argv and, for ``bash -c "..."`` style wrappers, the commands
    inside the string. Deny rules are a tripwire, not a boundary.
    """
    if cmd.argv is None:
        return []
    return _candidates(cmd.argv, 0)


def _candidates(argv: tuple[str, ...], depth: int) -> list[tuple[str, ...]]:
    found = [argv]
    if (
        depth < _MAX_NESTING
        and len(argv) >= 3
        and argv[0] in _SHELLS
        and _DASH_C.fullmatch(argv[1])
    ):
        for part in _INNER_SPLIT.split(argv[2]):
            tokens = _lenient_split(part.strip())
            if tokens:
                found.extend(_candidates(tokens, depth + 1))
    return found


def _lenient_split(text: str) -> tuple[str, ...]:
    try:
        return tuple(shlex.split(text))
    except ValueError:
        return tuple(text.split())
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_shell_classifier.py -q`
Expected: PASS. If a case fails, fix the classifier (not the table) unless the table contradicts the Global Constraints.

- [ ] **Step 5: Commit**

```bash
git add backend/saddlery/permissions/shell.py backend/tests/test_shell_classifier.py
git commit -m "feat(permissions): fail-closed shell command classifier"
```

---

### Task 3: One run at a time

**Files:**
- Create: `backend/saddlery/cli/runner.py`
- Modify: `backend/saddlery/cli/main.py` (the JSON-input branch)
- Test: `backend/tests/test_session_runner.py` (create)

**Interfaces:**
- Consumes: `Agent.run(session, sink)`, `UserMessage`.
- Produces: `SessionRunner(agent, session, sink)` with `submit(text: str) -> None` (sync, queues) and `async wait() -> None` (returns when the queue is drained and the worker has finished).

- [ ] **Step 1: Write the failing test**

```python
"""SessionRunner serializes turns: a message sent mid-run is queued, not interleaved."""

from __future__ import annotations

from saddlery.agent import Agent
from saddlery.cli.runner import SessionRunner
from saddlery.llm.fake import FakeProvider
from saddlery.session import Session
from saddlery.transport.recording import RecordingSink


def _types(session):
    return [e.type for e in session.events]


async def test_second_message_is_appended_only_after_the_first_run_finishes():
    session = Session(session_id="s1", principal="local")
    sink = RecordingSink()
    runner = SessionRunner(Agent(provider=FakeProvider(["ok"])), session, sink)

    runner.submit("one")
    runner.submit("two")  # sent while "one" is still pending or running
    await runner.wait()

    types = _types(session)
    assert types.count("user_message") == 2
    first_finish = types.index("run_finished")
    second_user = [i for i, t in enumerate(types) if t == "user_message"][1]
    assert second_user > first_finish


async def test_messages_run_in_submission_order():
    session = Session(session_id="s1", principal="local")
    runner = SessionRunner(Agent(provider=FakeProvider(["ok"])), session, RecordingSink())

    runner.submit("first")
    runner.submit("second")
    runner.submit("third")
    await runner.wait()

    user_texts = [e.content for e in session.events if e.type == "user_message"]
    assert user_texts == ["first", "second", "third"]


async def test_runner_restarts_after_going_idle():
    session = Session(session_id="s1", principal="local")
    runner = SessionRunner(Agent(provider=FakeProvider(["ok"])), session, RecordingSink())

    runner.submit("one")
    await runner.wait()
    runner.submit("two")
    await runner.wait()

    assert [e.content for e in session.events if e.type == "user_message"] == ["one", "two"]


async def test_wait_with_nothing_submitted_returns():
    session = Session(session_id="s1", principal="local")
    runner = SessionRunner(Agent(provider=FakeProvider([])), session, RecordingSink())
    await runner.wait()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_session_runner.py -q`
Expected: FAIL (`saddlery.cli.runner` missing).

- [ ] **Step 3: Implement**

`backend/saddlery/cli/runner.py`:

```python
"""Serializes agent turns for one session.

The permission policy's taint fold ("a ToolResult since the last UserMessage") is only sound
if user messages and runs never overlap, so a message that arrives mid-run is queued and
appended to the event log only when its run starts.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from saddlery.events import UserMessage

if TYPE_CHECKING:
    from saddlery.agent import Agent
    from saddlery.session import Session
    from saddlery.transport.base import EventSink


class SessionRunner:
    def __init__(self, agent: Agent, session: Session, sink: EventSink) -> None:
        self._agent = agent
        self._session = session
        self._sink = sink
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker: asyncio.Task | None = None

    def submit(self, text: str) -> None:
        self._queue.put_nowait(text)
        if self._worker is None or self._worker.done():
            self._worker = asyncio.ensure_future(self._work())

    async def wait(self) -> None:
        if self._worker is not None:
            await self._worker

    async def _work(self) -> None:
        while not self._queue.empty():
            text = self._queue.get_nowait()
            self._session.append(
                UserMessage(
                    session_id=self._session.session_id,
                    principal=self._session.principal,
                    content=text,
                )
            )
            await self._agent.run(self._session, self._sink)
```

(Check the real module path of `EventSink` with `grep -rn "class EventSink" backend/saddlery` and use it in the `TYPE_CHECKING` import.)

`backend/saddlery/cli/main.py`, JSON branch of `_amain()`: build the runner after `sink`, then replace the `user_message` handling and the final wait:

```python
    runner = SessionRunner(agent, session, sink)
```

```python
            async for event_type, payload in read_input_lines():
                if event_type == "user_message":
                    runner.submit(payload["content"])
                elif event_type == "permission_decision":
                    await agent.resolve_permission(payload["tool_call_id"], payload["decision"])
            await runner.wait()
```

Delete the `pending_run` variable and its explanatory comment block (the runner replaces it), and add `from saddlery.cli.runner import SessionRunner` to the imports. Leave the interactive (non-JSON) branch as is; it is already sequential.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_session_runner.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/saddlery/cli backend/tests/test_session_runner.py
git commit -m "feat(cli): serialize runs per session so taint cannot be reset mid-run"
```

---

### Task 4: Rules and strict config

**Files:**
- Create: `backend/saddlery/permissions/rules.py`
- Rewrite: `backend/saddlery/permissions/config.py`
- Test: `backend/tests/test_permission_rules.py` (create), `backend/tests/test_permission_config.py` (rewrite)

**Interfaces:**
- Consumes: `saddlery.tools.paths.fold`.
- Produces:
  - `Rule(tool: str, match: tuple[str, ...] = ())` frozen dataclass; `Rule.matches(tool_name: str, resource: tuple[str, ...]) -> bool` (prefix match after folding; empty `match` matches every resource); `as_rule(item: str | Rule) -> Rule`.
  - `PermissionConfig(allow: tuple[Rule, ...], deny: tuple[Rule, ...])`; `ConfigError(Exception)`; `load_permission_config(path: Path, *, known_tools: Collection[str] | None = None) -> PermissionConfig`; constants `BROAD_EXECUTORS`, `PATH_TOOLS`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_permission_rules.py`:

```python
"""Rules match a tool plus a token prefix of the call's resource."""

from __future__ import annotations

from saddlery.permissions.rules import Rule, as_rule


def test_bare_rule_matches_every_resource_of_the_tool():
    rule = Rule("write_file")
    assert rule.matches("write_file", ("a.txt",))
    assert rule.matches("write_file", ())
    assert not rule.matches("read_file", ("a.txt",))


def test_prefix_rule_matches_under_the_prefix():
    rule = Rule("write_file", ("docs",))
    assert rule.matches("write_file", ("docs", "a.md"))
    assert rule.matches("write_file", ("docs",))
    assert not rule.matches("write_file", ("src", "a.md"))


def test_prefix_rule_matches_whole_tokens_only():
    rule = Rule("write_file", ("docs",))
    assert not rule.matches("write_file", ("docs-private", "a.md"))


def test_matching_folds_case_and_unicode():
    rule = Rule("write_file", ("docs",))
    assert rule.matches("write_file", ("Docs", "A.md"))
    assert Rule("write_file", ("café",)).matches("write_file", ("café", "x"))


def test_shell_argv_prefix():
    rule = Rule("shell", ("git", "status"))
    assert rule.matches("shell", ("git", "status", "-s"))
    assert not rule.matches("shell", ("git", "push"))
    assert not rule.matches("shell", ("git",))


def test_as_rule_wraps_a_bare_tool_name():
    assert as_rule("read_file") == Rule("read_file")
    rule = Rule("shell", ("ls",))
    assert as_rule(rule) is rule
```

`backend/tests/test_permission_config.py` (replace the whole file):

```python
"""Loading and validating .saddlery/permissions.json."""

from __future__ import annotations

import json

import pytest

from saddlery.permissions.config import ConfigError, load_permission_config
from saddlery.permissions.rules import Rule


def _write(tmp_path, data):
    path = tmp_path / "permissions.json"
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return path


def test_bare_tool_names_become_whole_tool_rules(tmp_path):
    cfg = load_permission_config(_write(tmp_path, {"allow": ["read_file"], "deny": ["shell"]}))
    assert cfg.allow == (Rule("read_file"),)
    assert cfg.deny == (Rule("shell"),)


def test_scoped_rules(tmp_path):
    data = {
        "allow": [{"tool": "shell", "match": ["git", "status"]}],
        "deny": [{"tool": "write_file", "match": ["docs"]}],
    }
    cfg = load_permission_config(_write(tmp_path, data))
    assert cfg.allow == (Rule("shell", ("git", "status")),)
    assert cfg.deny == (Rule("write_file", ("docs",)),)


def test_missing_file_gives_empty_config(tmp_path):
    cfg = load_permission_config(tmp_path / "nope.json")
    assert cfg.allow == () and cfg.deny == ()


def test_empty_object_gives_empty_config(tmp_path):
    cfg = load_permission_config(_write(tmp_path, {}))
    assert cfg.allow == () and cfg.deny == ()


@pytest.mark.parametrize(
    "data",
    [
        "{not json",
        "[]",
        {"allow": "read_file"},
        {"deny": [3]},
        {"allow": [{"match": ["ls"]}]},
        {"allow": [{"tool": "shell", "match": []}]},
        {"allow": [{"tool": "shell", "match": ["ls", ""]}]},
        {"allow": [{"tool": "shell", "match": "ls"}]},
        {"allow": [{"tool": "shell", "match": ["ls"], "surprise": True}]},
        {"allow": [{"tool": "write_file", "match": ["docs/a.md"]}]},
        {"allow": [{"tool": "write_file", "match": [".."]}]},
        {"allow": [{"tool": "write_file", "match": ["/etc"]}]},
        {"surprise": []},
    ],
)
def test_invalid_config_fails_startup(tmp_path, data):
    with pytest.raises(ConfigError):
        load_permission_config(_write(tmp_path, data))


def test_unknown_tool_fails_when_known_tools_given(tmp_path):
    path = _write(tmp_path, {"allow": ["wrte_file"]})
    with pytest.raises(ConfigError, match="wrte_file"):
        load_permission_config(path, known_tools={"read_file", "write_file"})


def test_known_tool_passes(tmp_path):
    path = _write(tmp_path, {"allow": ["write_file"]})
    cfg = load_permission_config(path, known_tools={"read_file", "write_file"})
    assert cfg.allow == (Rule("write_file"),)


@pytest.mark.parametrize("executor", ["bash", "python", "find", "sudo", "env", "xargs"])
def test_single_token_executor_allow_needs_opt_in(tmp_path, executor):
    path = _write(tmp_path, {"allow": [{"tool": "shell", "match": [executor]}]})
    with pytest.raises(ConfigError, match="unsafe_broad_allow"):
        load_permission_config(path)


def test_single_token_executor_allow_with_opt_in_loads(tmp_path):
    data = {"allow": [{"tool": "shell", "match": ["python"], "unsafe_broad_allow": True}]}
    cfg = load_permission_config(_write(tmp_path, data))
    assert cfg.allow == (Rule("shell", ("python",)),)


def test_two_token_executor_rule_is_fine(tmp_path):
    data = {"allow": [{"tool": "shell", "match": ["python", "-m", "pytest"]}]}
    assert load_permission_config(_write(tmp_path, data)).allow


def test_executor_deny_rule_is_fine(tmp_path):
    data = {"deny": [{"tool": "shell", "match": ["bash"]}]}
    assert load_permission_config(_write(tmp_path, data)).deny == (Rule("shell", ("bash",)),)
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_permission_rules.py tests/test_permission_config.py -q`
Expected: FAIL (`rules` module missing; `ConfigError` undefined).

- [ ] **Step 3: Implement**

`backend/saddlery/permissions/rules.py`:

```python
"""Permission rules: a tool plus an optional token prefix of the call's resource."""

from __future__ import annotations

from dataclasses import dataclass

from saddlery.tools.paths import fold


@dataclass(frozen=True)
class Rule:
    tool: str
    match: tuple[str, ...] = ()

    def matches(self, tool_name: str, resource: tuple[str, ...]) -> bool:
        if tool_name != self.tool:
            return False
        prefix = tuple(fold(token) for token in self.match)
        folded = tuple(fold(token) for token in resource)
        return folded[: len(prefix)] == prefix


def as_rule(item: str | Rule) -> Rule:
    return item if isinstance(item, Rule) else Rule(item)
```

`backend/saddlery/permissions/config.py` (replace entirely):

```python
"""Loads and validates the project-level permission rules (.saddlery/permissions.json)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

from saddlery.permissions.rules import Rule

if TYPE_CHECKING:
    from collections.abc import Collection
    from pathlib import Path

#: Single-token shell allow rules for these run arbitrary programs; they need an explicit opt-in.
BROAD_EXECUTORS = frozenset(
    {
        "bash", "sh", "zsh", "python", "python3", "node", "ruby", "perl",
        "env", "xargs", "find", "sudo", "awk", "make", "npm",
    }
)  # fmt: skip
#: Tools whose rule tokens are path components.
PATH_TOOLS = frozenset({"read_file", "write_file"})

_TOP_LEVEL_KEYS = {"allow", "deny"}
_RULE_KEYS = {"tool", "match", "unsafe_broad_allow"}


class ConfigError(Exception):
    """The permissions file is malformed. Startup must fail rather than drop rules."""


@dataclass(frozen=True)
class PermissionConfig:
    allow: tuple[Rule, ...] = ()
    deny: tuple[Rule, ...] = ()


def load_permission_config(
    path: Path, *, known_tools: Collection[str] | None = None
) -> PermissionConfig:
    """Load rules from path. A missing file is the empty config; anything malformed raises."""
    if not path.exists():
        return PermissionConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be an object")
    unknown = set(data) - _TOP_LEVEL_KEYS
    if unknown:
        raise ConfigError(f"{path}: unknown keys {sorted(unknown)}")
    return PermissionConfig(
        allow=_parse_rules(data.get("allow", []), "allow", path, known_tools),
        deny=_parse_rules(data.get("deny", []), "deny", path, known_tools),
    )


def _parse_rules(
    items: Any, kind: str, path: Path, known_tools: Collection[str] | None
) -> tuple[Rule, ...]:
    if not isinstance(items, list):
        raise ConfigError(f"{path}: '{kind}' must be a list")
    return tuple(_parse_rule(item, kind, path, known_tools) for item in items)


def _parse_rule(item: Any, kind: str, path: Path, known_tools: Collection[str] | None) -> Rule:
    where = f"{path}: {kind} rule {item!r}"
    if isinstance(item, str):
        tool, match, opted_in = item, (), False
    elif isinstance(item, dict):
        unknown = set(item) - _RULE_KEYS
        if unknown:
            raise ConfigError(f"{where}: unknown keys {sorted(unknown)}")
        tool = item.get("tool")
        raw_match = item.get("match", [])
        opted_in = item.get("unsafe_broad_allow", False)
        if not isinstance(raw_match, list):
            raise ConfigError(f"{where}: 'match' must be a list")
        if "match" in item and not raw_match:
            raise ConfigError(f"{where}: 'match' must not be empty")
        match = tuple(raw_match)
    else:
        raise ConfigError(f"{where}: a rule is a tool name or an object")
    if not isinstance(tool, str) or not tool:
        raise ConfigError(f"{where}: 'tool' must be a non-empty string")
    if known_tools is not None and tool not in known_tools:
        raise ConfigError(f"{where}: unknown tool {tool!r}")
    for token in match:
        if not isinstance(token, str) or not token:
            raise ConfigError(f"{where}: match tokens must be non-empty strings")
        if tool in PATH_TOOLS and ("/" in token or token in {".", ".."}):
            raise ConfigError(f"{where}: path tokens may not contain '/' or be '.' or '..'")
    if kind == "allow" and tool == "shell" and len(match) == 1 and match[0] in BROAD_EXECUTORS:
        if opted_in is not True:
            raise ConfigError(
                f"{where}: allowing every '{match[0]}' command runs arbitrary programs; "
                "set \"unsafe_broad_allow\": true to accept that"
            )
        structlog.get_logger().warning("unsafe_broad_allow", tool=tool, match=list(match))
    return Rule(tool, match)
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_permission_rules.py tests/test_permission_config.py -q`
Expected: PASS. (`cli/main.py` still calls the old `load_permission_config()`; the full suite is red until Task 7. Run only the files named in this task.)

- [ ] **Step 5: Checkpoint (no commit)**

Leave these changes uncommitted; they commit together at the end of Task 7 (see the Checkpoint rule in Global Constraints).

---

### Task 5: `PolicyRequest` and the gate

**Files:**
- Rewrite: `backend/saddlery/permissions/gate.py`
- Rewrite: `backend/tests/test_permission_gate.py`

**Interfaces:**
- Consumes: `Rule`, `as_rule` (Task 4); `ShellCommand`, `deny_candidates` (Task 2); `fold`, `Capability` (Task 1).
- Produces:
  - `PolicyRequest(tool_name, arguments, principal, capability, resource, tainted, detail=None)` (frozen, `eq=False` dataclass).
  - `Decision = Literal["allow","deny","ask"]`; `HookResult = Literal["allow","deny","ask","pass"]`; `Hook = Callable[[PolicyRequest], HookResult]`.
  - `PermissionGate(*, allow: Iterable[str | Rule] = (), deny: Iterable[str | Rule] = (), hooks: list[Hook] | None = None)`; `async check(request) -> Decision`; `remember(request, decision: Literal["allow","deny"]) -> None`.

- [ ] **Step 1: Replace `backend/tests/test_permission_gate.py`**

```python
"""PermissionGate: deny → hooks → remembered → allow (taint-aware) → class default → ask."""

from __future__ import annotations

from saddlery.permissions.gate import HookResult, PermissionGate, PolicyRequest
from saddlery.permissions.rules import Rule
from saddlery.permissions.shell import classify


def req(
    tool="write_file",
    *,
    capability="write",
    resource=("a.txt",),
    arguments=None,
    principal="local",
    tainted=False,
    detail=None,
) -> PolicyRequest:
    return PolicyRequest(
        tool_name=tool,
        arguments=arguments or {},
        principal=principal,
        capability=capability,
        resource=resource,
        tainted=tainted,
        detail=detail,
    )


def shell_req(raw: str, **kwargs) -> PolicyRequest:
    cmd = classify(raw)
    return req("shell", capability="exec", resource=cmd.argv or (), detail=cmd, **kwargs)


# --- static rules and class defaults -------------------------------------------------


async def test_deny_wins_even_when_also_allowed():
    gate = PermissionGate(allow={"write_file"}, deny={"write_file"})
    assert await gate.check(req()) == "deny"


async def test_allow_list_resolves_to_allow():
    gate = PermissionGate(allow={"read_file"})
    assert await gate.check(req("read_file", capability="read")) == "allow"


async def test_unlisted_write_asks():
    assert await PermissionGate().check(req()) == "ask"


async def test_unlisted_exec_asks():
    assert await PermissionGate().check(req("shell", capability="exec")) == "ask"


async def test_unlisted_read_is_allowed_by_class_default():
    assert await PermissionGate().check(req("read_file", capability="read")) == "allow"


async def test_deny_list_resolves_to_deny():
    assert await PermissionGate(deny={"shell"}).check(req("shell", capability="exec")) == "deny"


async def test_scoped_deny_blocks_under_prefix_only():
    gate = PermissionGate(allow={"write_file"}, deny=[Rule("write_file", ("docs",))])
    assert await gate.check(req(resource=("docs", "a.md"))) == "deny"
    assert await gate.check(req(resource=("docs-private", "a.md"))) == "allow"


async def test_scoped_deny_matches_case_variants():
    gate = PermissionGate(allow={"write_file"}, deny=[Rule("write_file", ("docs",))])
    assert await gate.check(req(resource=("Docs", "A.md"))) == "deny"


async def test_scoped_allow_does_not_allow_other_resources():
    gate = PermissionGate(allow=[Rule("shell", ("git", "status"))])
    assert await gate.check(shell_req("git status -s")) == "allow"
    assert await gate.check(shell_req("git push")) == "ask"


# --- hooks ----------------------------------------------------------------------------


async def test_hook_deny_overrides_allow_list():
    def always_deny(request: PolicyRequest) -> HookResult:
        return "deny"

    gate = PermissionGate(allow={"write_file"}, hooks=[always_deny])
    assert await gate.check(req()) == "deny"


async def test_hook_pass_falls_through_to_the_rest():
    def no_opinion(request: PolicyRequest) -> HookResult:
        return "pass"

    gate = PermissionGate(allow={"write_file"}, hooks=[no_opinion])
    assert await gate.check(req()) == "allow"


async def test_hook_ask_wins_over_allow_match():
    def force_ask(request: PolicyRequest) -> HookResult:
        return "ask"

    gate = PermissionGate(allow={"write_file"}, hooks=[force_ask])
    assert await gate.check(req()) == "ask"


async def test_hook_allow_cannot_override_static_deny():
    def always_allow(request: PolicyRequest) -> HookResult:
        return "allow"

    gate = PermissionGate(deny=[Rule("shell", ("rm", "-rf"))], hooks=[always_allow])
    assert await gate.check(shell_req("rm -rf /")) == "deny"


async def test_hook_sees_the_whole_request_including_taint():
    seen: list[PolicyRequest] = []

    def spy(request: PolicyRequest) -> HookResult:
        seen.append(request)
        return "pass"

    gate = PermissionGate(hooks=[spy])
    request = req(tainted=True)
    await gate.check(request)
    assert seen == [request]
    assert seen[0].tainted is True


# --- remembered decisions -------------------------------------------------------------


async def test_remembered_allow_short_circuits_ask():
    gate = PermissionGate()
    gate.remember(req(), "allow")
    assert await gate.check(req()) == "allow"


async def test_remembered_decision_is_scoped_per_principal():
    gate = PermissionGate()
    gate.remember(req(), "allow")
    assert await gate.check(req(principal="other")) == "ask"


async def test_remembered_decision_is_scoped_per_tool():
    gate = PermissionGate()
    gate.remember(req(), "allow")
    assert await gate.check(req("other_tool")) == "ask"


async def test_remembered_decision_is_scoped_per_exact_resource():
    gate = PermissionGate()
    gate.remember(req(resource=("a.txt",)), "allow")
    assert await gate.check(req(resource=("a.txt",))) == "allow"
    assert await gate.check(req(resource=("b.txt",))) == "ask"
    assert await gate.check(req(resource=("a.txt", "x"))) == "ask"


async def test_remembered_deny_beats_allow_list():
    gate = PermissionGate(allow={"write_file"})
    gate.remember(req(), "deny")
    assert await gate.check(req()) == "deny"


async def test_hook_deny_beats_remembered_allow():
    def protect_git(request: PolicyRequest) -> HookResult:
        if str(request.arguments.get("path", "")).startswith(".git/"):
            return "deny"
        return "pass"

    gate = PermissionGate(hooks=[protect_git])
    gate.remember(req(arguments={"path": "a.txt"}), "allow")
    assert await gate.check(req(arguments={"path": "a.txt"})) == "allow"
    gate.remember(req(arguments={"path": ".git/config"}, resource=("a.txt",)), "allow")
    assert await gate.check(req(arguments={"path": ".git/config"})) == "deny"


async def test_static_deny_beats_remembered_allow():
    gate = PermissionGate(deny={"write_file"})
    gate.remember(req(), "allow")
    assert await gate.check(req()) == "deny"


async def test_exec_decisions_are_never_remembered():
    gate = PermissionGate()
    request = shell_req("git push")
    gate.remember(request, "allow")
    assert await gate.check(request) == "ask"


async def test_network_decisions_are_never_remembered():
    gate = PermissionGate()
    request = req("fetch", capability="network", resource=("example.com",))
    gate.remember(request, "allow")
    assert await gate.check(request) == "ask"


# --- taint ----------------------------------------------------------------------------


async def test_tainted_write_allow_match_downgrades_to_ask():
    gate = PermissionGate(allow={"write_file"})
    assert await gate.check(req(tainted=False)) == "allow"
    assert await gate.check(req(tainted=True)) == "ask"


async def test_tainted_exec_allow_match_downgrades_to_ask():
    gate = PermissionGate(allow=[Rule("shell", ("pytest",))])
    assert await gate.check(shell_req("pytest -x")) == "allow"
    assert await gate.check(shell_req("pytest -x", tainted=True)) == "ask"


async def test_tainted_read_stays_allowed():
    gate = PermissionGate(allow={"read_file"})
    assert await gate.check(req("read_file", capability="read", tainted=True)) == "allow"
    assert await PermissionGate().check(req("read_file", capability="read", tainted=True)) == "allow"


async def test_tainted_does_not_weaken_deny():
    gate = PermissionGate(deny={"write_file"})
    assert await gate.check(req(tainted=True)) == "deny"


async def test_remembered_decision_applies_while_tainted():
    gate = PermissionGate()
    gate.remember(req(), "allow")
    assert await gate.check(req(tainted=True)) == "allow"


# --- shell specifics ------------------------------------------------------------------


async def test_rejected_shell_command_is_denied():
    gate = PermissionGate(allow={"shell"})
    assert await gate.check(shell_req("ls; rm -rf ~")) == "deny"


async def test_rejected_shell_command_cannot_be_rescued_by_a_hook():
    def always_allow(request: PolicyRequest) -> HookResult:
        return "allow"

    gate = PermissionGate(hooks=[always_allow])
    assert await gate.check(shell_req("echo `id`")) == "deny"


async def test_deny_rule_sees_inside_bash_dash_c():
    gate = PermissionGate(deny=[Rule("shell", ("rm", "-rf"))])
    assert await gate.check(shell_req('bash -c "rm -rf /"')) == "deny"
    assert await gate.check(shell_req('sh -c "ls; rm -rf /"')) == "deny"


async def test_deny_rule_does_not_block_unrelated_shell_commands():
    gate = PermissionGate(deny=[Rule("shell", ("rm", "-rf"))])
    assert await gate.check(shell_req("ls -la")) == "ask"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_permission_gate.py -q`
Expected: FAIL (`PolicyRequest` missing).

- [ ] **Step 3: Replace `backend/saddlery/permissions/gate.py`**

```python
"""The PermissionGate seam: deny → hooks → remembered → allow → class default → ask.

Mirrors ToolRegistry: constructed once in build_agent(), called from Agent.run() between
emitting ToolCall and invoking tool.call(). Policy lives here; the TUI only renders prompts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from saddlery.permissions.rules import Rule, as_rule
from saddlery.permissions.shell import ShellCommand, deny_candidates
from saddlery.tools.paths import fold

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from saddlery.tools.base import Capability

Decision = Literal["allow", "deny", "ask"]
HookResult = Literal["allow", "deny", "ask", "pass"]


@dataclass(frozen=True, eq=False)
class PolicyRequest:
    """Everything policy may use to decide one tool call. Built by Agent.run()."""

    tool_name: str
    arguments: dict
    principal: str
    capability: Capability
    resource: tuple[str, ...]
    tainted: bool
    detail: object | None = None


Hook = Callable[[PolicyRequest], HookResult]

_REMEMBERED_CLASSES = frozenset({"write"})


class PermissionGate:
    def __init__(
        self,
        *,
        allow: Iterable[str | Rule] = (),
        deny: Iterable[str | Rule] = (),
        hooks: list[Hook] | None = None,
    ) -> None:
        self._allow = [as_rule(item) for item in allow]
        self._deny = [as_rule(item) for item in deny]
        self._hooks = hooks or []
        self._remembered: dict[tuple[str, str, tuple[str, ...]], Literal["allow", "deny"]] = {}

    def remember(self, request: PolicyRequest, decision: Literal["allow", "deny"]) -> None:
        if request.capability not in _REMEMBERED_CLASSES:
            return
        self._remembered[self._key(request)] = decision

    async def check(self, request: PolicyRequest) -> Decision:
        if self._is_rejected(request) or self._is_denied(request):
            return "deny"

        for hook in self._hooks:
            result = hook(request)
            if result != "pass":
                return result

        remembered = self._remembered.get(self._key(request))
        if remembered is not None:
            return remembered

        if any(rule.matches(request.tool_name, request.resource) for rule in self._allow):
            if request.tainted and request.capability != "read":
                return "ask"
            return "allow"

        return "allow" if request.capability == "read" else "ask"

    @staticmethod
    def _key(request: PolicyRequest) -> tuple[str, str, tuple[str, ...]]:
        return (request.principal, request.tool_name, tuple(fold(t) for t in request.resource))

    @staticmethod
    def _is_rejected(request: PolicyRequest) -> bool:
        return isinstance(request.detail, ShellCommand) and request.detail.kind == "rejected"

    def _is_denied(self, request: PolicyRequest) -> bool:
        candidates = [request.resource]
        if isinstance(request.detail, ShellCommand):
            candidates.extend(deny_candidates(request.detail))
        return any(
            rule.matches(request.tool_name, candidate)
            for rule in self._deny
            for candidate in candidates
        )
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_permission_gate.py -q`
Expected: PASS. (Other modules still use the old gate API until Tasks 5 and 7.)

- [ ] **Step 5: Checkpoint (no commit)**

Leave these changes uncommitted; they commit together at the end of Task 7 (see the Checkpoint rule in Global Constraints).

---

### Task 6: Taint fold and agent wiring

**Files:**
- Modify: `backend/saddlery/session.py`, `backend/saddlery/events.py`, `backend/saddlery/agent.py`
- Test: `backend/tests/test_session.py`, `backend/tests/test_agent.py` (append)

**Interfaces:**
- Consumes: `PolicyRequest`, `PermissionGate.check/remember` (Task 5); `Tool.capability/resource/detail`, `ResourceError` (Task 1); `ShellCommand` (Task 2).
- Produces: `Session.is_tainted() -> bool`; `PermissionRequest.capability: Capability`, `.resource: list[str]`, `.tainted: bool`; `Agent._run_tool_call(call, tool, session, emit) -> tuple[str, bool]`, `Agent._ask(...)`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_session.py`:

```python
def test_is_tainted_false_with_no_tool_results():
    s = Session(session_id="s1", principal="local")
    s.append(UserMessage(session_id="s1", principal="local", content="hi"))
    assert s.is_tainted() is False


def test_is_tainted_true_after_a_tool_result_since_the_last_user_message():
    s = Session(session_id="s1", principal="local")
    s.append(UserMessage(session_id="s1", principal="local", content="read it"))
    s.append(ToolResult(session_id="s1", principal="local", tool_call_id="c1", content="x"))
    assert s.is_tainted() is True


def test_is_tainted_resets_on_a_new_user_message():
    s = Session(session_id="s1", principal="local")
    s.append(UserMessage(session_id="s1", principal="local", content="read it"))
    s.append(ToolResult(session_id="s1", principal="local", tool_call_id="c1", content="x"))
    s.append(UserMessage(session_id="s1", principal="local", content="thanks"))
    assert s.is_tainted() is False
```

(Add `ToolResult`, `UserMessage` to the file's event imports if absent.)

Append to `backend/tests/test_agent.py` (the `_StubTool` from Task 1 needs configurable class and resource; change its `__init__` to accept `capability: str = "write", resource: tuple[str, ...] = ("stub",)`, store them, and make `_PolicyStub.capability`/`resource` come from those attributes for `_StubTool` — i.e. in `_StubTool.__init__` set `self.capability = capability` and `self._resource = resource`, and override `def resource(self, arguments): return self._resource`):

```python
from saddlery.events import ToolResult
from saddlery.tools.base import ResourceError


async def test_permission_request_carries_capability_resource_and_taint():
    session = _session_with_user("write it")
    sink = RecordingSink()
    tool = _StubTool(name="write_file", response="ok", resource=("out.txt",))
    agent = Agent(
        provider=FakeProvider(
            chunks=["done"],
            tool_calls=[ToolCallDelta(id="c1", name="write_file", input={"path": "out.txt"})],
        ),
        tools=ToolRegistry([tool]),
        permission_gate=PermissionGate(),
    )

    run_task = asyncio.ensure_future(agent.run(session, sink))
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    request_event = next(e for e in sink.events if e.type == "permission_request")
    assert request_event.capability == "write"
    assert request_event.resource == ["out.txt"]
    assert request_event.tainted is False
    await agent.resolve_permission("c1", "allow")
    await run_task


async def test_allowlisted_write_asks_when_a_tool_result_precedes_it():
    session = _session_with_user("fix it")
    session.append(ToolResult(session_id="s1", principal="local", tool_call_id="old", content="x"))
    sink = RecordingSink()
    tool = _StubTool(name="write_file", response="ok")
    agent = Agent(
        provider=FakeProvider(
            chunks=["done"],
            tool_calls=[ToolCallDelta(id="c1", name="write_file", input={"path": "p"})],
        ),
        tools=ToolRegistry([tool]),
        permission_gate=PermissionGate(allow={"write_file"}),
    )

    run_task = asyncio.ensure_future(agent.run(session, sink))
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    request_event = next(e for e in sink.events if e.type == "permission_request")
    assert request_event.tainted is True
    await agent.resolve_permission("c1", "deny")
    await run_task


async def test_invalid_resource_becomes_an_error_result_without_calling_the_tool():
    class _BadResource(_PolicyStub):
        name = "write_file"
        description = "d"
        input_schema: ClassVar[dict] = {"type": "object", "properties": {}}

        def resource(self, arguments):
            raise ResourceError("escapes root")

        async def call(self, arguments):
            raise AssertionError("must not run")

    session = _session_with_user("go")
    sink = RecordingSink()
    agent = Agent(
        provider=FakeProvider(
            chunks=["done"],
            tool_calls=[ToolCallDelta(id="c1", name="write_file", input={"path": "../x"})],
        ),
        tools=ToolRegistry([_BadResource()]),
        permission_gate=PermissionGate(allow={"write_file"}),
    )

    await agent.run(session, sink)

    result = next(e for e in sink.events if e.type == "tool_result")
    assert result.is_error is True
    assert "Invalid arguments" in result.content


async def test_target_changing_after_approval_blocks_the_call():
    class _Shifty(_PolicyStub):
        name = "write_file"
        description = "d"
        input_schema: ClassVar[dict] = {"type": "object", "properties": {}}

        def __init__(self):
            self.resources = [("approved.txt",), ("elsewhere.txt",)]

        def resource(self, arguments):
            return self.resources.pop(0)

        async def call(self, arguments):
            raise AssertionError("must not run")

    session = _session_with_user("go")
    sink = RecordingSink()
    agent = Agent(
        provider=FakeProvider(
            chunks=["done"],
            tool_calls=[ToolCallDelta(id="c1", name="write_file", input={"path": "p"})],
        ),
        tools=ToolRegistry([_Shifty()]),
        permission_gate=PermissionGate(allow={"write_file"}),
    )

    await agent.run(session, sink)

    result = next(e for e in sink.events if e.type == "tool_result")
    assert result.is_error is True
    assert "changed after approval" in result.content


async def test_rejected_shell_command_reports_why():
    from saddlery.permissions.shell import classify

    class _Shell(_PolicyStub):
        name = "shell"
        capability = "exec"
        description = "d"
        input_schema: ClassVar[dict] = {"type": "object", "properties": {}}

        def resource(self, arguments):
            return classify(arguments["command"]).argv or ()

        def detail(self, arguments):
            return classify(arguments["command"])

        async def call(self, arguments):
            raise AssertionError("must not run")

    session = _session_with_user("go")
    sink = RecordingSink()
    agent = Agent(
        provider=FakeProvider(
            chunks=["done"],
            tool_calls=[ToolCallDelta(id="c1", name="shell", input={"command": "ls; id"})],
        ),
        tools=ToolRegistry([_Shell()]),
        permission_gate=PermissionGate(allow={"shell"}),
    )

    await agent.run(session, sink)

    result = next(e for e in sink.events if e.type == "tool_result")
    assert result.is_error is True
    assert "Run each command separately" in result.content
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_session.py tests/test_agent.py -q`
Expected: FAIL (`is_tainted` missing; `PermissionRequest` lacks the new fields; agent still calls the old gate API).

- [ ] **Step 3: Implement**

`backend/saddlery/session.py`: add a method to `Session`:

```python
    def is_tainted(self) -> bool:
        """True when a ToolResult (untrusted content) exists since the last UserMessage."""
        for event in reversed(self._events):
            if isinstance(event, UserMessage):
                return False
            if isinstance(event, ToolResult):
                return True
        return False
```

`backend/saddlery/events.py`: add `from saddlery.tools.base import Capability` is a layering inversion; instead declare the literal inline. Replace `PermissionRequest`:

```python
class PermissionRequest(BaseEvent):
    type: Literal["permission_request"] = "permission_request"
    tool_call_id: str
    tool_name: str
    arguments: dict
    capability: Literal["read", "write", "exec", "network"]
    resource: list[str]
    tainted: bool
```

`backend/saddlery/agent.py`:

1. Imports: add `from saddlery.permissions.gate import PolicyRequest`, `from saddlery.permissions.shell import ShellCommand`, `from saddlery.tools.base import ResourceError` (runtime; the file already imports `PermissionGate` for typing — follow ruff's TYPE_CHECKING advice for type-only names such as `Tool` and `ToolCallDelta`).
2. In `run()`, delete everything inside the `else:` branch of `if tool is None:` (from `decision: str = "allow"` through `result_content, is_error = outcome.content, outcome.is_error`) and replace it with:

```python
                    else:
                        result_content, is_error = await self._run_tool_call(
                            call, tool, session, emit
                        )
```

3. Add these methods to `Agent` (before `resolve_permission`):

```python
    async def _run_tool_call(self, call, tool, session, emit) -> tuple[str, bool]:
        """Gate (when configured) and execute one tool call. Returns (content, is_error)."""
        gate = self.permission_gate
        if gate is not None:
            try:
                request = PolicyRequest(
                    tool_name=call.name,
                    arguments=call.input,
                    principal=session.principal,
                    capability=tool.capability,
                    resource=tool.resource(call.input),
                    tainted=session.is_tainted(),
                    detail=tool.detail(call.input),
                )
            except ResourceError as exc:
                return f"Invalid arguments: {exc}", True
            decision = await gate.check(request)
            if decision == "ask":
                decision = await self._ask(call, request, session, emit)
                gate.remember(request, decision)
            if decision == "deny":
                return self._denial_message(request), True
            try:
                changed = tool.resource(call.input) != request.resource
            except ResourceError:
                changed = True
            if changed:
                return "Permission denied: the target changed after approval.", True
        outcome = await tool.call(call.input)
        return outcome.content, outcome.is_error

    async def _ask(self, call, request, session, emit) -> Literal["allow", "deny"]:
        """Emit a PermissionRequest, suspend until resolve_permission(), emit the decision."""
        sid, principal = session.session_id, session.principal
        await emit(
            PermissionRequest(
                session_id=sid,
                principal=principal,
                tool_call_id=call.id,
                tool_name=call.name,
                arguments=call.input,
                capability=request.capability,
                resource=list(request.resource),
                tainted=request.tainted,
            )
        )
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending_decisions[call.id] = future
        try:
            decision = await future
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
        return decision

    @staticmethod
    def _denial_message(request: PolicyRequest) -> str:
        if isinstance(request.detail, ShellCommand) and request.detail.kind == "rejected":
            return "Compound commands are not supported. Run each command separately."
        return "Permission denied"
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_session.py tests/test_agent.py tests/test_permission_gate.py -q`
Expected: PASS. Existing agent tests (denied, allowed, ask-suspends, ask-deny) must still pass unchanged apart from the stub fixtures from Task 1.

- [ ] **Step 5: Checkpoint (no commit)**

Leave these changes uncommitted; they commit together at the end of Task 7 (see the Checkpoint rule in Global Constraints).

---

### Task 7: Wire config into `build_agent()`

**Files:**
- Modify: `backend/saddlery/cli/main.py`
- Test: `backend/tests/test_cli_wiring.py` (append)

**Interfaces:**
- Consumes: `load_permission_config`, `ConfigError` (Task 4); `PermissionGate` (Task 5).
- Produces: `build_agent()` loads `<root>/.saddlery/permissions.json` (root from `SADDLERY_ROOT`, else cwd) with `known_tools` = registered tool names; `_amain()` exits `2` and prints the error to stderr on `ConfigError`.

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_cli_wiring.py`)

```python
import json

import pytest

from saddlery.permissions.config import ConfigError
from saddlery.permissions.gate import PolicyRequest


def _write_perms(root, data):
    config_dir = root / ".saddlery"
    config_dir.mkdir()
    (config_dir / "permissions.json").write_text(
        data if isinstance(data, str) else json.dumps(data), encoding="utf-8"
    )


def _write_request(resource):
    return PolicyRequest(
        tool_name="write_file",
        arguments={},
        principal="local",
        capability="write",
        resource=resource,
        tainted=False,
    )


async def test_build_agent_loads_rules_from_the_root(monkeypatch, tmp_path):
    _write_perms(tmp_path, {"allow": ["write_file"], "deny": [{"tool": "write_file", "match": ["docs"]}]})
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("SADDLERY_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path.parent)  # config must come from the root, not the cwd

    gate = build_agent().permission_gate

    assert gate is not None
    assert await gate.check(_write_request(("src", "a.py"))) == "allow"
    assert await gate.check(_write_request(("docs", "a.md"))) == "deny"


def test_build_agent_fails_on_malformed_permissions(monkeypatch, tmp_path):
    _write_perms(tmp_path, "{not json")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("SADDLERY_ROOT", str(tmp_path))
    with pytest.raises(ConfigError):
        build_agent()


def test_build_agent_fails_on_rule_for_unknown_tool(monkeypatch, tmp_path):
    _write_perms(tmp_path, {"allow": ["wrte_file"]})
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("SADDLERY_ROOT", str(tmp_path))
    with pytest.raises(ConfigError, match="wrte_file"):
        build_agent()
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_cli_wiring.py -q`
Expected: FAIL (`build_agent()` still calls `load_permission_config()` with no path).

- [ ] **Step 3: Implement** in `backend/saddlery/cli/main.py`

Replace the permission/tool section of `build_agent()`:

```python
    provider = MockLMProvider() if use_mock else AnthropicProvider()
    # The TUI runs this process from backend/ (so uv finds pyproject.toml), so the cwd is not
    # the project. SADDLERY_ROOT names the directory the file tools may touch and where the
    # permission rules live.
    root = Path(os.environ["SADDLERY_ROOT"]) if os.environ.get("SADDLERY_ROOT") else Path.cwd()
    tools = ToolRegistry([FileReadTool(root), FileWriteTool(root)])
    config = load_permission_config(
        root / ".saddlery" / "permissions.json", known_tools=tools.names()
    )
    gate = PermissionGate(allow=config.allow, deny=config.deny)
    return Agent(provider=provider, tools=tools, permission_gate=gate)
```

Add to `ToolRegistry` (`backend/saddlery/tools/registry.py`):

```python
    def names(self) -> list[str]:
        """Registered tool names."""
        return list(self._tools)
```

Handle `ConfigError` at startup in `_amain()`: replace `agent = build_agent()` with

```python
    try:
        agent = build_agent()
    except ConfigError as exc:
        print(f"permissions config error: {exc}", file=sys.stderr)
        return 2
```

and import `from saddlery.permissions.config import ConfigError, load_permission_config`.

- [ ] **Step 4: Run the whole backend suite**

Run: `cd backend && .venv/bin/pytest -q`
Expected: everything passes (the first point since Task 4 where the full suite is green again). Also run `.venv/bin/ruff check . && .venv/bin/ruff format --check .`.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat(permissions): capability-aware policy — scoped rules, taint, strict config, deny-first gate"
```

---

### Task 8: TUI prompt

**Files:**
- Create: `frontend/tui/src/components/permissionPrompt.ts`
- Modify: `frontend/tui/src/core/subprocess.ts`, `frontend/tui/src/components/ChatApp.tsx`
- Test: `frontend/tui/src/__tests__/permissionPrompt.test.ts` (create), `frontend/tui/src/__tests__/subprocess.test.ts` (update)

**Interfaces:**
- Consumes: wire fields `capability`, `resource` (string[]), `tainted` on `permission_request` events (Task 6).
- Produces: `PermissionRequestInfo = { toolCallId; toolName; arguments; capability; resource: string[]; tainted: boolean }`; `formatPermissionPrompt(info): string`.

- [ ] **Step 1: Write the failing tests**

`frontend/tui/src/__tests__/permissionPrompt.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { formatPermissionPrompt } from "../components/permissionPrompt";

const base = {
  toolCallId: "c1",
  toolName: "write_file",
  arguments: {},
  capability: "write",
  resource: ["docs", "a.md"],
  tainted: false,
};

describe("formatPermissionPrompt", () => {
  it("joins path resources with slashes", () => {
    expect(formatPermissionPrompt(base)).toBe("Allow write_file: docs/a.md? [y/n]");
  });

  it("joins exec resources with spaces", () => {
    expect(
      formatPermissionPrompt({
        ...base,
        toolName: "shell",
        capability: "exec",
        resource: ["git", "push", "origin", "main"],
      })
    ).toBe("Allow shell: git push origin main? [y/n]");
  });

  it("flags requests that follow untrusted content", () => {
    expect(formatPermissionPrompt({ ...base, tainted: true })).toBe(
      "Allow write_file: docs/a.md? (follows untrusted content) [y/n]"
    );
  });

  it("falls back to the tool name when the resource is empty", () => {
    expect(formatPermissionPrompt({ ...base, resource: [] })).toBe("Allow write_file? [y/n]");
  });
});
```

In `frontend/tui/src/__tests__/subprocess.test.ts`, extend the existing `permission_request` test: add `capability: "write", resource: ["out.txt"], tainted: true` to `event_data`, and expect the handler to be called with `{ toolCallId: "call-1", toolName: "write_file", arguments: { path: "out.txt" }, capability: "write", resource: ["out.txt"], tainted: true }`.

- [ ] **Step 2: Run to verify they fail**

Run: `cd frontend/tui && npx vitest run`
Expected: FAIL (`permissionPrompt` missing; handler payload lacks the new fields).

- [ ] **Step 3: Implement**

`frontend/tui/src/components/permissionPrompt.ts`:

```typescript
export interface PermissionRequestInfo {
  toolCallId: string;
  toolName: string;
  arguments: Record<string, unknown>;
  capability: string;
  resource: string[];
  tainted: boolean;
}

/** The prompt shows the backend's `resource`, never one rebuilt from raw arguments. */
export function formatPermissionPrompt(info: PermissionRequestInfo): string {
  const separator = info.capability === "exec" ? " " : "/";
  const target = info.resource.join(separator);
  const subject = target ? `${info.toolName}: ${target}` : info.toolName;
  const taint = info.tainted ? " (follows untrusted content)" : "";
  return `Allow ${subject}?${taint} [y/n]`;
}
```

`frontend/tui/src/core/subprocess.ts`, the `permission_request` branch: read the new fields and include them in the emit:

```typescript
      const capability = eventData?.capability as string | undefined;
      const resource = eventData?.resource as string[] | undefined;
      const tainted = eventData?.tainted as boolean | undefined;
      ...
        this.emit("permission_request", {
          toolCallId,
          toolName,
          arguments: args ?? {},
          capability: capability ?? "write",
          resource: resource ?? [],
          tainted: tainted ?? false,
        });
```

`frontend/tui/src/components/ChatApp.tsx`: type `pendingPermission` as `PermissionRequestInfo | null` (import it), and replace the prompt text:

```tsx
          <Text color="yellow" bold>
            {formatPermissionPrompt(pendingPermission)}
          </Text>
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd frontend/tui && npm run type-check && npm run lint && npx vitest run`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/tui/src
git commit -m "feat(tui): show capability-aware permission prompts with a taint note"
```

---

### Task 9: Documentation and devlog

**Files:**
- Modify: `docs/tools/README.md`, `docs/specs/2026-10-12-permission-policy-design.md`
- Create: `research/devlog/2026-10-12-permission-policy.md`

- [ ] **Step 1: Update `docs/tools/README.md`**

Rewrite the permission section so it matches the code: evaluation order `deny → hooks → remembered → allow → class default → ask`; the four capability classes and their defaults; rule syntax (bare tool names and `{"tool","match","unsafe_broad_allow"}`); the config location `<root>/.saddlery/permissions.json` and the strict startup behavior; the `rejected` shell rule; taint; per-class memory; and `SADDLERY_ROOT`. Delete the now-wrong "five-stage pipeline" text.

- [ ] **Step 2: Reconcile the spec with the build**

In spec §3 add one sentence: "Matching folds every tool's tokens (not only path tokens); this only widens matching and fails closed for deny." Check `docs/diagrams/permission-gate-sequence.md`: if `docs/diagrams/README.md` says it is generated, regenerate it per that README; otherwise edit `remember(tool_name, principal, decision)` to `remember(request, decision)` and add the `PolicyRequest` hand-off.

- [ ] **Step 3: Write the devlog entry** `research/devlog/2026-10-12-permission-policy.md`, following `research/devlog/README.md` (what we set out to do; decisions and rationale; dead ends; what we learned; open threads). It must record, as facts rather than placeholders: the Codex review and what it changed in the spec (deny before hooks, serialized runs, substitution then outright compound rejection, path folding, `shell=False`, broad-allow opt-in); the MM-9 ordering bug found by the red test in `b4bc59b`; the cwd/root bug found by running the TUI (`SADDLERY_ROOT`); the demo result (see Step 4); the taint limitation and MM-210; and the shell tool as the next slice (MM-10).

- [ ] **Step 4: Verify the demo end to end**

Run the TUI from a separate terminal (`cd frontend/tui && npm run dev`) and confirm: reading a file works without a prompt; a write prompts; approving `a.txt` then asking for `b.txt` prompts again; a prompt after a file read carries "(follows untrusted content)" when the path is allowlisted in `.saddlery/permissions.json`. Record what you saw in the devlog.

- [ ] **Step 5: Run everything and commit**

Run: `cd backend && .venv/bin/pytest -q && cd ../frontend/tui && npm run type-check && npm run lint && npx vitest run`
Expected: all pass.

```bash
git add docs research
git commit -m "docs: permission policy — tools README, spec reconciliation, devlog"
```

# MM-9: Permission gate — allow/deny/ask + hooks seam

Design for [MM-9](https://linear.app/mark-mansour/issue/MM-9/05-permission-gate-allowdenyask-hooks-seam),
Phase 0 slice 0.5. Copies the Claude Code permission model documented in
[`research/security/permissions-secrets.md`](../../research/security/permissions-secrets.md) and
[`research/reference-designs/claude-code.md`](../../research/reference-designs/claude-code.md).

## Goal

A permission check sits in the tool-execution path between `ToolCall` and `tool.call()`.
Evaluation order: **hooks → deny → allow → ask**, deny always wins. First gated tool is a new
`FileWriteTool`. An "ask" decision is rendered in the TUI and answered by the user.

## 1. Evaluation pipeline & `PermissionGate`

A new module, `backend/saddlery/permissions/gate.py`, structured as a seam — the same shape as
`ToolRegistry`:

```python
Decision = Literal["allow", "deny", "ask"]
HookResult = Literal["allow", "deny", "ask", "pass"]
Hook = Callable[[str, dict, str], HookResult]  # (tool_name, arguments, principal) -> HookResult

class PermissionGate:
    def __init__(self, hooks: list[Hook], allow: set[str], deny: set[str]) -> None: ...

    async def check(self, tool_name: str, arguments: dict, principal: str) -> Decision: ...
```

`Agent.run()` calls `gate.check(...)` immediately after emitting `ToolCall`, before calling
`tool.call(...)`.

Inside `check()`:

1. **Hooks** run in order. Each returns `allow` / `deny` / `ask` / `pass` (`pass` = no opinion,
   continue). The first non-`pass` result short-circuits the whole pipeline.
2. **Deny list** — if `tool_name` is in the deny set, deny. This wins even if `tool_name` is also
   in the allow set (the explicit test case named in the issue).
3. **Allow list** — if `tool_name` is in the allow set, allow.
4. **Ask** — nothing above resolved it; fall through to the ask flow (§3).

No input mutation or context injection in this slice, even though the reference design supports
it — nothing in MM-9's scope (gating file write) needs it. Deferred until a real use case
(prompt-injection defense, Phase 1) needs it.

## 2. Config: allow/deny list storage

A single project-level settings file, `.saddlery/permissions.json`:

```json
{ "allow": ["read_file"], "deny": [] }
```

Loaded once in `build_agent()`, passed into `PermissionGate`. Rules match on `tool_name` only —
no per-command granularity yet (file write has no natural "command" to key on the way shell
commands do). Per-command matching is deferred to MM-10, which needs it for the shell tool.

No user-level layering (Enterprise/User/Project precedence from the reference design) in this
slice — there's no concrete multi-layer use case yet at single-tool granularity. Single
project-level file is enough to demo and test.

## 3. The "ask" round-trip

Today's wire protocol only supports the backend streaming events out and the TUI sending new user
messages in — there's no "backend asks a question, waits for an answer" round-trip. This slice
adds one, using two new event types (following the existing `ToolCall`/`ToolResult` pattern in
`events.py`):

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

When the gate resolves to `ask`, `Agent.run()`:

1. Emits `PermissionRequest` (session log + sink — an event like any other).
2. **Suspends** — awaits an `asyncio.Future` registered against `tool_call_id`, instead of
   proceeding to `tool.call()`.
3. `cli/input.py`'s JSON input reader is extended to also recognize an incoming
   `{"type": "permission_decision", "tool_call_id": ..., "decision": "allow"|"deny"}` line on
   stdin, resolving the matching pending `Future`.
4. Once resolved, `PermissionGate` records the decision **per-session, per-tool-name** — an
   in-memory dict on the `PermissionGate` instance, keyed by `(principal, tool_name)`. This works
   because one `PermissionGate` is constructed per agent process today, and one process handles
   exactly one session — so "remembered for the process" and "remembered for the session" are the
   same thing right now. See §7 for what breaks when this assumption stops holding.
5. `Agent.run()` proceeds to `tool.call()` if allowed, or synthesizes
   `ToolResult(is_error=True, content="Permission denied")` if denied — no change to the existing
   `ToolResult` emission point.

`PermissionDecision` carries no notion of *who* or *what* answered — it's just
`{tool_call_id, decision}` on the same stdin channel user messages already arrive on. The gate
doesn't distinguish a human clicking "allow" in the TUI from a script, another process, or a
future policy-automation layer writing the same JSON line. This is deliberate for this slice: the
mechanism is open by construction, so no code changes are needed later to support a non-human
answerer — only a client that speaks the existing protocol. A dedicated automated-answerer
feature (e.g. a policy engine or trusted-reviewer agent that consumes `PermissionRequest` events
and emits `PermissionDecision`s on its own) is tracked as separate future work — see
[MM-108](https://linear.app/mark-mansour/issue/MM-108).

This reuses the existing JSON-lines stdin/stdout channel between backend and TUI — no new
transport or subprocess plumbing beyond parsing two new event types on each side.

## 4. TUI rendering

Extends `CoreSubprocess` (`frontend/tui/src/core/subprocess.ts`) exactly like the existing
`tool_call`/`tool_result` handling: a new case for `permission_request` emits a JS event
`{ toolCallId, toolName, arguments }`. `ChatApp.tsx` renders a prompt (e.g. `"Allow
write_file(path=...)? [y/n]"`) and, on keypress, writes a `permission_decision` JSON line to the
subprocess's stdin — mirroring how user messages are already written to stdin today.

## 5. `FileWriteTool` — the first gated tool

New `backend/saddlery/tools/write_file.py`, mirroring `FileReadTool`'s safety pattern
(`backend/saddlery/tools/read_file.py`) exactly:

- Root-scoped (`Path.cwd()` default), path resolved and checked via `relative_to()` for
  traversal.
- Writes UTF-8 text.
- Never raises — all failure modes (traversal, permission error, parent dir missing, etc.) become
  `ToolExecutionResult(is_error=True)`.

Registered in `build_agent()` alongside `FileReadTool`. Not in the default allow or deny list, so
every call hits `ask` by default.

## 6. `principal` scoping

`principal` is threaded through every decision point (`PermissionGate.check(principal=...)`, the
per-session-per-tool memory keyed by `(principal, tool_name)`) even though today there is only
ever one `principal` (`"local"`) per process. This costs nothing now and means the plumbing is
already shaped for Phase 3 multi-user support — a different `principal` value flows through the
same parameters later, no redesign needed.

## 7. Known limitation: this is not stateless-server-safe

Surfaced 2026-07-26, while reviewing the plan: both stateful mechanisms in this design —
`PermissionGate`'s remembered-decision dict (§3, step 4) and `Agent`'s suspended
`asyncio.Future` for a pending ask (§3, step 2) — live in one Python process's memory, tied to
one running event loop. This is correct and sufficient for **today's actual deployment shape**:
the TUI spawns the backend as a long-lived subprocess for the duration of one session (see
`frontend/tui/src/core/subprocess.ts`), so "in-memory for the process" and "in-memory for the
session" are the same guarantee. It will not survive Phase 2's stateless multi-frontend server,
where a request can be served by a different process — or no live process at all — between the
`PermissionRequest` being emitted and the `PermissionDecision` arriving. Two distinct problems,
with very different fixes:

- **Remembered decisions** — the easy case. [MM-12](https://linear.app/mark-mansour/issue/MM-12)
  ("execution seam + persistence") already commits to persisting the event log to SQLite and
  replaying a session deterministically from it. Once that exists, remembered decisions should
  move from `PermissionGate`'s in-memory dict onto the event log itself (each remembered decision
  is just another fact recoverable by folding `PermissionDecision` events), rather than
  maintaining a second, competing source of truth. This falls out of MM-12's existing scope with
  no new mechanism — it is not free, but it is not a new design problem either.
- **Suspended asks** — the hard case, and **not** solved by MM-12 alone. A stateless
  request/response backend cannot pause a live coroutine in memory and resume it from a different
  process later — there's no `asyncio.Future` to resume; it never existed in that process. Fixing
  this needs the ask-suspend point to change shape entirely: instead of `Agent.run()` blocking on
  `await future`, the run would need to durably persist "waiting on tool_call_id X" and actually
  return/exit at that point, with a later, independent invocation re-entering from the persisted
  event log (the same fold `Session.to_messages()` already performs) when the matching
  `PermissionDecision` shows up. This is a real redesign of the suspend/resume mechanism, not a
  storage swap — explicitly **not** attempted in this slice. Tracked as follow-up work in
  [MM-109](https://linear.app/mark-mansour/issue/MM-109), to revisit once Phase 2's server
  architecture (and MM-12's persistence layer) actually exist to design against, rather than
  speculating on their shape now.

## Testing

- `PermissionGate` unit tests: deny wins even when allow also matches (explicit issue
  requirement); hooks can override each stage; `ask` is reached only when nothing else resolves.
- `Agent.run()` integration test: a gated tool call suspends the run; a `PermissionDecision`
  resolves it; `ToolResult` reflects the outcome. A denied decision short-circuits to an error
  `ToolResult` without calling `tool.call()`.
- `FileWriteTool` unit tests: mirrors `backend/tests/test_read_file.py`'s structure — happy path,
  traversal rejection, permission error, missing parent directory, etc.

## Out of scope for this slice

- Per-command granularity (deferred to MM-10, shell tool).
- User-level layered settings (Enterprise/User/Project precedence).
- Hook input mutation / context injection (deferred to Phase 1 prompt-injection defense).
- Persisting ask-decisions across sessions (session-scoped memory only).

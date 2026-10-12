# Permission policy: capability classes, resources, and taint

Design for the policy layer of the permission gate, written before
[MM-10](https://linear.app/mark-mansour/issue/MM-10) (shell tool behind the gate). It extends the
mechanism from [`2026-07-25-permission-gate-design.md`](2026-07-25-permission-gate-design.md)
(MM-9) and the model in
[`research/security/permissions-secrets.md`](../../research/security/permissions-secrets.md).

## Why this exists

MM-9 shipped the mechanism: hooks → deny → allow → ask, with deny winning. Its rules match on
`tool_name` alone, which is too coarse:

- Approving `write_file` once approved every path under `root`.
- There is no way to say "reads are low-risk, writes are not" without listing tool names by hand.
- MM-10 needs "allowlisted command runs, denylisted command is blocked, ambiguous command
  prompts". Name-only rules cannot express that.
- Shell runs without a sandbox (Phase 4). The policy is the only guard, so an injected command
  must not auto-run.

This spec defines what a rule is, how it matches, what an approval covers, and how untrusted
content affects the decision. It supersedes MM-9 §2 ("rules match on `tool_name` only") and the
memory rule in MM-9 §3 step 4.

## Decisions

| # | Decision |
|---|---|
| 1 | A shell command that matches no rule asks, every time. |
| 2 | Rules match a parsed argv token prefix. Compound commands never match an allow rule. Deny rules scan every segment. |
| 3 | A `write_file` approval covers that exact resolved path. |
| 4 | Capability classes (`read`, `write`, `exec`, `network`) live on the `Tool`. A tool without a valid class fails at registration. |
| 5 | Taint is in scope. A call is tainted when a `ToolResult` exists since the last `UserMessage`. |
| 6 | Policy lives in the backend. The TUI renders and relays. |
| 7 | Command parsing fails closed. |
| 8 | Static deny is evaluated before hooks. A hook cannot override a deny rule. |
| 9 | One run at a time per session. A second user message queues until the in-flight run finishes. |
| 10 | Command substitution (`` ` ``, `$( )`, `<( )`) asks and may be approved once. Deny rules do not see inside it. This is a stated limit. |

## 1. Evaluation order

```
deny → hooks → remembered → allow (taint-aware) → class default → ask
```

Static deny runs first, so **deny always wins**, including over a hook. Hooks can still deny or
ask on top of the static rules, and can allow anything that is not denied. A remembered decision
ranks below deny and hooks, so an earlier approval can never override policy. A remembered deny
still beats the allow list.

**Change from the code.** `b4bc59b` fixed remembered-versus-hook ordering but left hooks ahead of
deny, so a hook returning `allow` still overrides a static deny. `PermissionGate.check()` must
move the deny check ahead of the hooks. This reverses the "hooks first" order in the MM-9 spec.
A test must cover a hook `allow` against a static deny.

## 2. Capability classes

`Tool` gains `capability: Literal["read", "write", "exec", "network"]`.

| Tool | Class |
|---|---|
| `read_file` | `read` |
| `write_file` | `write` |
| shell (MM-10) | `exec` |
| web fetch (later) | `network` |

`network` has no tool yet. It is reserved because exfiltration, an injected instruction that reads
a secret and sends it out, is the case where an autonomous `read` becomes dangerous.

**Undeclared class fails.** `ToolRegistry` raises at registration if a tool lacks a valid
`capability`. `build_agent()` therefore fails at startup. There is no default class. A forgotten
declaration must not run under a guessed class.

**Defaults by class**, when no hook or rule decides:

| Class | Default |
|---|---|
| `read` | allow |
| `write`, `exec`, `network` | ask |

## 3. Resources and rules

A tool names the thing a call acts on: `Tool.resource(arguments) -> tuple[str, ...]`.

| Tool | Resource | Example |
|---|---|---|
| shell | normalized argv | `("git", "status")` |
| `write_file` | path parts, resolved against `root` | `("docs", "a.md")` |
| `read_file` | path parts, resolved against `root` | `("docs", "a.md")` |

A **rule** is a tool plus an optional token prefix. It matches when the resource starts with those
tokens. A bare tool name means the whole tool, so existing config keeps working.

```json
{
  "allow": ["read_file", {"tool": "shell", "match": ["git", "status"]}],
  "deny":  [{"tool": "shell", "match": ["rm", "-rf"]}]
}
```

`["docs"]` on `write_file` matches every path under `docs/`. `["git", "status"]` on shell matches
`git status` and `git status -s`. Remembered approvals use exact tuple equality, not prefix.

## 4. Shell command parsing

The shell tool's `resource()` runs a strict classifier. A command is **simple** only if every
check passes. Anything else is **compound** and fails closed.

Simple requires all of:

1. `shlex` (`posix=True`, `punctuation_chars=True`, `whitespace_split=True`) parses it without
   error.
2. No operator token (`; & | && || < > ( )`) appears.
3. None of `` ` ``, `$`, `\n`, `\r`, `\`, `*`, `?`, `~`, `{` appears anywhere in the raw string,
   quoted or not. Quoted `$` and globs can still expand.
4. `argv[0]` is not an assignment (`NAME=value`).

`shlex` alone is not enough. It leaves backticks, `"$(id)"` and newlines uninterpreted, and an
`FOO=1` prefix shifts argv. Checks 3 and 4 close those gaps. The classifier will reject some
harmless commands, such as `echo "$5"`. A false ask costs a prompt. A false allow costs a command.

**Effects of a compound result:**

- It never matches an allow rule, so it asks.
- The user may approve the exact string once. Shell approvals are never remembered (§6).
- **Deny rules scan every segment.** The string is split on the operators above and each segment's
  argv is checked against deny rules. `ls; rm -rf ~` is blocked.
- A parse error asks. The deny scan falls back to whitespace splitting.

**Stated limit: command substitution.** The segment scan splits on operators. It does not see
inside `` `...` ``, `$( )` or `<( )`. `` echo `rm -rf /tmp/x` `` tokenizes as
`` ['echo', '`rm', '-rf', '/tmp/x`'] ``, so a deny rule on `["rm", "-rf"]` does not match. Such a
command is compound and asks, and the user may approve it once. That approval can run a command a
deny rule names. The spec does not claim otherwise. Deny rules guarantee nothing about syntax the
classifier does not parse. The prompt must show the raw command in full so the user can see the
substitution.

**Wrappers.** There is no wrapper blocklist. Programs that run their arguments are open-ended
(`find -exec`, `git -c`, `python -c`, `awk`, `npm run`, `make`). Allow rules need none, because
they are explicit prefixes: `sudo git status` has `argv[0] == "sudo"` and cannot match
`["git", "status"]`. Two measures remain:

- Config load **warns** on a single-token allow rule for a known interpreter or executor (`bash`,
  `sh`, `python`, `node`, `env`, `xargs`, `find`, `sudo`).
- The deny scan re-parses the string argument of `bash -c` and `sh -c`. This is best-effort.

**The deny list is a tripwire, not a boundary** (see the stated limit above). String matching cannot be airtight against shell
syntax (variable expansion, aliases, encoded payloads). The guard is that `exec` asks by default.

## 5. Taint

A call is **tainted** when at least one `ToolResult` has been appended to the session since the
last `UserMessage`. `Session` exposes this as a pure fold over the event log, like
`to_messages()`. Nothing is stored, so replay reproduces it. `Agent.run()` computes it per call.

Taint acts at one point, the static allow list:

| Step | Clean | Tainted |
|---|---|---|
| Deny | blocks | blocks |
| Hooks | see `tainted` and decide | same |
| Remembered | applies | applies (the user saw that exact resource) |
| Allow match, class `write`/`exec`/`network` | allow | **ask** |
| Allow match, class `read` | allow | allow |
| No match | class default | class default |

Example, with `pytest` allowlisted: "run the tests" runs without a prompt. "Fix the failures" does
`read_file` first, so the later `pytest` asks.

**One run at a time.** The taint fold is sound only if user messages and runs do not overlap.
`cli/main.py` currently schedules each turn as a background task, so a second `UserMessage` can
arrive while the first run is still using an untrusted `ToolResult`, which would reset taint. The
backend therefore serializes runs per session. A message that arrives during a run is queued and
appended to the event log only when its run starts. This changes the CLI's current behavior and is
part of the implementation plan.

**Known limitation.** Taint resets on each user message. This is a heuristic, not provenance. An
injection read in turn 1 can still sway the model in turn 3, which looks clean. See Future work.

## 6. Memory

Memory varies by class.

| Class | Remembered after approval |
|---|---|
| `write` | yes, keyed `(principal, tool, exact resource tuple)` |
| `exec` | never. Every unmatched command asks, even a repeat. |
| `network` | never |

## 7. Gate API, events and wire

- `PolicyRequest(tool_name, arguments, principal, capability, resource, tainted)`: immutable,
  built by `Agent.run()`.
- `PermissionGate.check(request) -> Decision`.
- `Hook = Callable[[PolicyRequest], HookResult]`. This changes the MM-9 signature. Only tests use
  hooks today.
- `PermissionGate.remember(request, decision)` is a no-op for `exec` and `network`.
- `PermissionRequest` gains `capability`, `resource` (a list of tokens on the wire) and
  `tainted`. `PermissionDecision` is unchanged.

**Backend/TUI boundary.** The gate runs in the backend (`Agent.run()`). The TUI renders the
prompt and writes a `permission_decision` line. It holds no rules.

- Taint, capability and resource are computed in the backend. The TUI displays them.
- The prompt renders `resource` from the event, not a value rebuilt from raw arguments. What the
  user sees is what the approval covers.
- Prompt text: `Allow shell: git push origin main? (follows untrusted content)`.
- The decision channel is trusted. Anything that can write the backend's stdin can answer a
  prompt. That is acceptable for a local subprocess. It becomes a real boundary in Phase 2
  (MM-109).

## 8. Config loading

`.saddlery/permissions.json`:

- **Missing file:** defaults only, as today.
- **Malformed file, unknown tool in a rule, or invalid rule:** startup fails with a clear message.
  MM-9 treated a malformed file as empty. With deny rules that now matter, that silently drops
  them, which is fail-open.
- **Over-broad rule** (§4): a warning at load.

## Testing

- Hook deny and static deny beat a remembered allow (written in `b4bc59b`).
- A hook `allow` does not override a static deny.
- A user message sent during a run is queued, and taint is not reset by it.
- Command classifier: a table-driven test. Cases: `ls; rm -rf ~`, `` echo `id` ``, `echo "$(id)"`,
  `ls\nrm -rf x`, `FOO=1 git status`, `sudo rm -rf /`, `bash -c "rm -rf /"`, `find . -exec rm {} +`,
  an unclosed quote, and `echo "a;b"`. Each asserts simple or compound, and found deny segments.
- Matching: prefix semantics, exact-tuple memory, compound never matches allow.
- Taint: a fold test (true after a result, false after a new `UserMessage`), and the downgrade
  table in §5.
- Registry: a missing or invalid capability raises at registration.
- Config: each startup failure, and the over-broad warning.
- End to end: with `pytest` allowlisted, "run the tests" runs unprompted. A turn that reads a file
  first prompts, and the `PermissionRequest` has `tainted=true`.

## Out of scope

- Layered settings (user plus project) and permission modes (plan, normal, auto).
- Hook input mutation and context injection (Phase 1 prompt-injection defense).
- Persisting approvals across sessions (MM-12 and MM-109).
- An automated answerer for `PermissionRequest` ([MM-108](https://linear.app/mark-mansour/issue/MM-108)).
- Sandboxing (Phase 4).

## Future work

- **Better taint.** The per-turn reset is a heuristic. A classifier that decides whether untrusted
  text contains an injection could replace or refine it, and could carry across turns.
- **The `network` class.** Design it when web fetch lands, including exfiltration after a `read`.
- **Session-wide taint** as an opt-in stricter mode.

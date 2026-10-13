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
| 2 | Rules match a parsed argv token prefix. Compound commands are rejected outright. |
| 3 | A `write_file` approval covers that exact resolved path. |
| 4 | Capability classes (`read`, `write`, `exec`, `network`) live on the `Tool`. A tool without a valid class fails at registration. |
| 5 | Taint is in scope. A call is tainted when a `ToolResult` exists since the last `UserMessage`. |
| 6 | Policy lives in the backend. The TUI renders and relays. |
| 7 | Command parsing fails closed. |
| 8 | Static deny is evaluated before hooks. A hook cannot override a deny rule. |
| 9 | One run at a time per session. A second user message queues until the in-flight run finishes. |
| 10 | Compound commands (operators, command substitution, and anything else that is not a simple command) are denied, never approved. The shell tool never invokes a shell. |
| 11 | Path resources are NFC-normalized and case-folded for all matching. The tool re-verifies the resolved resource at write time, with no-follow. |
| 12 | The shell tool uses `shell=False`, the classifier's argv and a sanitized environment. The classifier returns one immutable `ShellCommand` carried in `PolicyRequest`. |
| 13 | A single-token executor allow rule (`bash`, `python`, `find`, ...) fails startup without `unsafe_broad_allow`. |

## 1. Evaluation order

```
deny → hooks → remembered → allow (taint-aware) → class default → ask
```

Static deny runs first, so **deny always wins**, including over a hook. Hooks can still deny or
ask on top of the static rules, and can allow anything that is not denied. A remembered decision
ranks below deny and hooks, so an earlier approval can never override policy. A remembered deny
still beats the allow list.

A shell command the classifier marks `rejected` (§4) is denied at the deny step, so no hook, remembered
decision or allow rule can reach it.

**Change from the code (done).** `b4bc59b` fixed remembered-versus-hook ordering but left hooks ahead of
deny, so a hook returning `allow` still overrides a static deny. `PermissionGate.check()` now
runs the deny check ahead of the hooks. This reverses the "hooks first" order in the MM-9 spec.
A test covers a hook `allow` against a static deny.

**As built.** Three behaviors go beyond the text above:

- A hook result outside `allow`, `deny`, `ask`, `pass` is treated as `deny`, and `Agent` runs a
  tool only on an explicit `allow`.
- Path errors (NUL bytes, symlink loops) become `Invalid arguments` tool results, not exceptions.
- `Agent` recomputes the resource after approval and refuses the call if it changed. `write_file`
  opens with `O_NOFOLLOW`. The tool itself does not re-verify the approved resource.

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

**Path canonicalization.** A path resource is built as follows:

1. Resolve against `root` (symlinks followed). A result outside `root` is an error, not a resource.
2. Take the path parts relative to `root`. `..`, `.` and empty parts cannot remain.
3. Normalize each part to NFC and case-fold it. Matching and remembered equality both use the
   normalized form, always, on every filesystem. Rules are normalized the same way at load. This is
   deliberate: on macOS's default case-insensitive filesystem `Docs/a.md` reaches `docs/`, and a
   deny rule on `["docs"]` must still match. Case-folding on a case-sensitive filesystem only makes
   deny rules broader, which fails closed.

Matching is on whole tokens, so `["docs"]` does not match `docs-private`. Matching folds every
tool's tokens (not only path tokens); this only widens matching and fails closed for deny.

**Race between check and use.** The resource is computed before the tool runs, so a parent
directory could become a symlink in between. The tool therefore re-resolves immediately before
writing, verifies the normalized resource equals the approved one, and opens the target with
no-follow semantics. A mismatch returns an error `ToolResult`, with no write.

**Rule validation.** A rule's `match` must be a non-empty list of non-empty strings. For path
tools, tokens may not contain a separator, `..` or `.`, and may not be absolute. A deny rule that
matches takes precedence over every allow rule, including a bare-tool allow. Duplicate rules are
harmless. A rule that fails validation fails startup (§8).

## 4. Shell command parsing

The shell tool's `resource()` runs a strict classifier. A command is **simple** only if every
check passes. Anything else is **rejected**: the gate denies it before hooks run, and the
`ToolResult` says "Compound commands are not supported. Run each command separately." There is no
approve-once path for a rejected command.

The classifier runs once and returns an immutable `ShellCommand(raw, argv, kind)`. `kind` is
`simple` or `rejected`. `argv` is set only for `simple`. `PolicyRequest` carries this object
(`detail`), so the gate, hooks and prompt use one parse, with no re-parsing and no divergence.

**Executor.** The shell tool runs `subprocess` with `shell=False` and exactly the classifier's
`argv`, a fixed sanitized environment (no inherited `BASH_ENV`, `ENV`, `LD_*`, `DYLD_*` or
`PYTHON*`) and a fixed cwd. The tool never invokes a shell, so only a `simple` command ever runs
and the classifier's guarantee is total. Shell builtins (`cd`, `export`) do not exist without a
shell and return an error `ToolResult`.

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

**Why reject instead of ask.** A compound command cannot run without a shell, and a deny scan over
shell syntax is not airtight. `` echo `rm -rf /tmp/x` `` tokenizes as
`` ['echo', '`rm', '-rf', '/tmp/x`'] ``, so a deny rule on `["rm", "-rf"]` would not match, and a
user's one-time approval could then run it. Rejecting such commands removes that gap. The cost is
that pipes, `&&` and redirects cannot run. The model must issue separate calls, and each one is
checked on its own. A false reject costs a retry. A false allow costs a command.

Allow and deny rules therefore apply to `simple` commands only, which is what makes argv-prefix
matching sound.

**Wrappers.** There is no wrapper blocklist. Programs that run their arguments are open-ended
(`find -exec`, `git -c`, `python -c`, `awk`, `npm run`, `make`). Allow rules need none, because
they are explicit prefixes: `sudo git status` has `argv[0] == "sudo"` and cannot match
`["git", "status"]`. Two measures remain:

- A single-token allow rule for a known interpreter or executor (`bash`, `sh`, `zsh`, `python`,
  `python3`, `node`, `ruby`, `perl`, `env`, `xargs`, `find`, `sudo`, `awk`, `make`, `npm`)
  **fails startup** unless the rule sets `"unsafe_broad_allow": true`. With the flag it loads and
  logs a warning. `find` is on the list because `find . -delete` classifies as simple. The list is
  incomplete by nature, so it is a guard against common mistakes, not a proof.
- A deny rule also matches the string argument of `bash -c` and `sh -c` after re-parsing it, as
  a best-effort check.

**The deny list is a tripwire, not a boundary** (see the stated limit above). Even on simple commands, string matching cannot catch every
route to a dangerous action (a script written earlier, an interpreter given inline code). The guard
is that `exec` asks by default.

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

- `PolicyRequest(tool_name, arguments, principal, capability, resource, tainted, detail)`: immutable,
  built by `Agent.run()`. `detail` is the tool's structured classification (a `ShellCommand` for
  shell, otherwise `None`).
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
- **Malformed file, duplicate JSON key, unknown tool in a rule, or invalid rule:** startup fails with a clear message.
  MM-9 treated a malformed file as empty. With deny rules that now matter, that silently drops
  them, which is fail-open.
- **Over-broad rule** (§4): a single-token executor allow rule fails startup unless it sets
  `unsafe_broad_allow`; with the flag it loads and logs a warning.

## Testing

- Hook deny and static deny beat a remembered allow (written in `b4bc59b`).
- A hook `allow` does not override a static deny.
- A user message sent during a run is queued, and taint is not reset by it.
- Command classifier: a table-driven test. Cases: `ls; rm -rf ~`, `` echo `id` ``, `echo "$(id)"`,
  `ls\nrm -rf x`, `FOO=1 git status`, `sudo rm -rf /`, `bash -c "rm -rf /"`, `find . -exec rm {} +`,
  an unclosed quote, and `echo "a;b"`. Each asserts `simple` or `rejected`. A rejected command is
  denied before hooks and the allow list, and is never executed.
- Matching: prefix semantics, exact-tuple memory, a rejected command never reaches the allow list.
- Taint: a fold test (true after a result, false after a new `UserMessage`), and the downgrade
  table in §5.
- Registry: a missing or invalid capability raises at registration.
- Config: each startup failure, the over-broad rule with and without `unsafe_broad_allow`, and each
  rule-validation failure (empty `match`, separator or `..` in a path token, absolute path).
- Paths: `docs-private` does not match `["docs"]`; `docs/../private` and a symlink out of `root`
  are rejected; `Docs/a.md` and an NFD-encoded name match a deny rule on `["docs"]`; a symlink
  swapped in after approval makes the write fail with no write.
- Executor: a `simple` command runs with `shell=False` and the sanitized environment (an inherited
  `BASH_ENV` has no effect); a builtin such as `cd` returns an error result.
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

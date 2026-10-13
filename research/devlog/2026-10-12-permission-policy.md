# 2026-10-12 — Permission policy: capability classes, scoped rules, taint (MM-212)

## What we set out to do
MM-9 shipped the gate mechanism. Its rules matched on tool name alone, so approving `write_file`
once approved every path under the root, and nothing could say "reads are low-risk, writes are
not." MM-10 (the shell tool) needs "allowlisted command runs, denylisted command is blocked,
ambiguous command prompts," which name-only rules cannot express. Shell will run without a
sandbox until Phase 4, so the policy is the only guard.

MM-212 builds that policy before the shell tool exists: four capability classes on every tool,
scoped rules over a resource, per-class memory, taint, and a strict config. The spec is
[`2026-10-12-permission-policy-design.md`](../../docs/specs/2026-10-12-permission-policy-design.md).

## Decisions & rationale
- **Deny, then hooks, then everything else.** MM-9 ran hooks first, so a hook returning `allow`
  overrode a static deny. The order is now `deny → hooks → remembered → allow → class default → ask`.
- **Capability classes live on the `Tool`.** `read`, `write`, `exec`, `network`. A tool without a
  valid class fails at registration, so a forgotten declaration cannot run under a guessed class.
  `network` has no tool yet. It is reserved for exfiltration, the case where an autonomous `read`
  turns dangerous.
- **A write approval covers one resolved path.** Approving `a.txt` does not approve `b.txt`.
  Exec and network approvals are never remembered.
- **Path resources are NFC-normalized and case-folded everywhere**, on every filesystem. On a
  case-insensitive macOS volume `Docs/a.md` reaches `docs/`, and a deny rule on `["docs"]` must
  still match. Folding on a case-sensitive volume only broadens deny, which fails closed. The
  build folds every tool's tokens, not only path tokens, which also only widens matching.
- **Compound shell commands are rejected outright.** The classifier returns an immutable
  `ShellCommand(raw, argv, kind)`. Anything that is not one program with literal arguments is
  `rejected`, denied before hooks, with no approve-once path. The shell tool will use
  `shell=False` and the classifier's argv.
- **Taint is a fold over the event log.** A call is tainted when a `ToolResult` exists since the
  last `UserMessage`. It downgrades an allow rule on a non-`read` call to ask. Nothing is stored,
  so replay reproduces it.
- **Runs are serialized per session** (`SessionRunner`). Without that, a second user message
  could reset taint while a run still held an untrusted result.
- **Config is strict.** A malformed file, duplicate JSON key, unknown tool or invalid rule stops
  startup with exit code 2. MM-9 treated a malformed file as empty, which silently drops deny
  rules.
- **Broad executor allow rules need an opt-in.** A single-token `shell` allow rule for `bash`,
  `python`, `find` and similar fails startup unless it sets `"unsafe_broad_allow": true`.

### The Codex adversarial review
I had Codex attack the spec before any code. It changed the design in six places:
1. **Deny before hooks.** The first draft kept hooks ahead of deny.
2. **Serialized runs.** Taint was unsound while turns could overlap in `cli/main.py`.
3. **Command substitution, then outright compound rejection.** The spec first added a
   substitution limit. The follow-up round showed that a deny scan over shell syntax is not
   airtight: `` echo `rm -rf /tmp/x` `` tokenizes so a deny on `["rm", "-rf"]` misses it. The spec
   then rejected compound commands outright and dropped the `sh -c` path and deny-segment scan.
4. **Path folding.** Canonicalization with NFC and case-folding for rules and resources alike.
5. **`shell=False`.** The executor never invokes a shell, so the classifier's guarantee is total.
6. **Broad-allow opt-in.** The `unsafe_broad_allow` flag and the executor list.

The review ran in three commits: `240383f`, `7403f62`, `a93ab72`.

## Dead-ends / things that bit
- **The MM-9 ordering bug.** While writing the red test for the spec's ordering, a remembered
  decision overrode both hooks and the deny list. Fixed in `b4bc59b` before the policy work began.
  The spec's own ordering (hooks ahead of deny) was still wrong. Codex caught that.
- **The cwd/root bug.** Running the TUI showed the core started from `backend/`, so the file tools
  and `.saddlery/permissions.json` pointed at the wrong directory. The core now reads
  `SADDLERY_ROOT`; the TUI sets it to its launch directory. An explicit value wins (`1d2e4a8`).
- **The checkpoint-commit problem.** The plan said Tasks 4-7 land together because they change
  the gate, agent, config and wiring in step. The pre-commit `ty` hook checks the whole backend
  (`pass_filenames: false`), so a commit of Task 4 alone fails while `cli/main.py` still uses the
  old APIs. I ruled that Tasks 4-7 run as one dispatch block, one implementer, one review package
  and one commit (`91df442`), and used the strongest model for both implementing and reviewing.
  The cost was a large diff to review. Separately, the implementer's own commit was blocked by the
  permission check, so the controller committed after I approved it and allowed `git add` and `git commit`.
- **Plan defect.** The plan imported `Callable` under `TYPE_CHECKING`, but `Hook = Callable[...]`
  is a runtime expression. That would raise `NameError`. I had it imported at runtime.

## What we learned
Tasks were built by subagents, each with a separate review. The review findings:

- **Task 1 (capability classes, paths):** clean. Deferred: `O_NOFOLLOW` narrows only the
  final-component race; parents can still be swapped.
- **Task 2 (shell classifier):** clean. Deferred: empty quoted args are rejected (safe side);
  NUL and control characters classify as simple; no tests for nesting depth or tab separators.
  Plan-level, for MM-10: the forbidden-character list omits `[ ] ! ^ %`, which is harmless only
  because the shell tool never invokes a shell. And `bash -c "<compound>"` is itself `simple`, so
  interpreters with `-c` are full-capability escapes that the policy must not rely on the
  classifier to stop.
- **Task 3 (serialized runs):** clean. Deferred: a worker that dies strands queued messages; a run
  suspended on an ask at stdin EOF hangs.
- **Tasks 4-7 (gate, agent, config, wiring):** review 1 found **three Important issues, all
  reproduced**:
  1. An out-of-contract hook result failed open. A hook returning `None` or a typo allowed the call.
  2. A NUL byte or symlink loop in a path raised something other than `ResourceError`, aborting
     the run and leaving an orphan `ToolCall`.
  3. Duplicate JSON keys dropped deny rules, because `json.loads` keeps the last one.

  One fix round (`ae3381a`) closed all three. A hook result outside `{allow, deny, ask, pass}` is
  now `deny`, and `Agent` runs a tool only on an explicit `allow`. Path errors become
  `Invalid arguments` results. Duplicate keys are a `ConfigError`. The block was clean after that.
- **Task 8 (TUI prompt):** approved with one Important finding: `tainted ?? false` failed open on
  a safety signal. A missing flag now renders as tainted (`40705ed`).
- **Fail-closed review is where the value was.** Every Important finding was a default that
  failed open: hook results, path errors, duplicate keys, a missing taint flag. Unit tests
  written from the plan did not catch any of them. A reviewer who asked "what if this is
  malformed?" did.
- **Known, deferred for the final review:** a bare `"shell"` allow rule skips the broad-allow
  guard; the guard misses `/usr/bin/python3`, `python3.12` and `["python", "-c"]`; shell tokens
  containing whitespace load as dead rules; `deny_candidates` misses `rm -r -f` and wrapper
  forms like `sudo` and `env`; shell rules fail startup until MM-10 registers the tool; the new
  `PermissionRequest` fields are required, so old logs will not validate; an unhashable hook
  result (a list) raises `TypeError` instead of denying.
- **Taint limitation.** Taint resets on each user message. It is a heuristic, not provenance.
  An injection read in turn 1 can still sway the model in turn 3, which looks clean. Better taint
  is [MM-210](https://linear.app/mark-mansour/issue/MM-210).

## Demo & test verification
- **Test:** 246 backend tests pass (2 skipped) on the branch tip.
- **Demo: pending, to be run by Mark.** The live TUI needs a TTY and an API key, so I did not run
  it. Nothing below has been observed. The MM-212 done-check is:
  1. Reading a file runs without a prompt.
  2. Approving a write to `a.txt` does not approve `b.txt`.
  3. A write allowlisted in `.saddlery/permissions.json` still prompts after a file read, with
     "(follows untrusted content)".
  4. A malformed permissions file stops startup with a clear message.

## Open threads
- [MM-10](https://linear.app/mark-mansour/issue/MM-10): the shell tool. It must run with
  `shell=False`, a sanitized environment, and never invoke an interpreter on classifier output.
  Until it registers, any `shell` rule fails startup.
- [MM-210](https://linear.app/mark-mansour/issue/MM-210): better taint than the per-turn reset.
- [MM-211](https://linear.app/mark-mansour/issue/MM-211): Bun.
- The deferred minor findings above, for the final whole-branch review.
- [MM-108](https://linear.app/mark-mansour/issue/MM-108) and
  [MM-109](https://linear.app/mark-mansour/issue/MM-109) remain open as in MM-9.

## For the blog (Mark to fill in)
- _Your take: Codex found six holes in a spec you thought was done. Did that change how much you
  trust a design before it meets an adversary?_
- _Your take: every Important review finding was a fail-open default. Was that a surprise, or the
  pattern you expected?_
- _Your take: you ran the TUI and found the wrong-directory bug that no test had. What does that
  say about where to spend your own time versus the subagents'?_

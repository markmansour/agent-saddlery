# 2026-07-25 — Landing MM-9: the permission gate

## What we set out to do
Ship [MM-9](https://linear.app/mark-mansour/issue/MM-9/05-permission-gate-allowdenyask-hooks-seam):
a permission check in the tool path, evaluated hooks → deny → allow → ask (deny wins), a hooks
seam for policy injection, file write as the first gated tool, and the decision rendered in the
TUI.

The feature itself had already been built on a worktree branch
(`worktree-mark+mm-9-permission-gate`). What actually happened in this session was landing it on
`main` — which turned into an unplanned lesson in how careless reverts interact with merges.

## Decisions & rationale
- **Merge the worktree branch, don't replay it.** The branch was fully built — `PermissionGate`
  (`backend/saddlery/permissions/gate.py`), project-level config loading
  (`permissions/config.py`), `FileWriteTool`, and CLI/TUI wiring for the ask round-trip. `git merge`
  was the correct tool; no reason to cherry-pick commit-by-commit.
- **Evaluation order lives in one place.** `PermissionGate.check()` short-circuits in a fixed
  order — remembered decision → hooks → deny → allow → ask — so "deny wins" isn't a convention
  callers have to honor, it's structurally true from the function's control flow.
- **Config failure defaults to `ask`, not a crash.** `load_permission_config()` treats a missing
  file, missing keys, or malformed JSON as empty allow/deny sets. An unlisted tool then falls
  through to `ask`, which is the safe default — a hand-edited config typo shouldn't take down the
  CLI at startup.

## Dead-ends / things that bit
- **A revert doesn't know which lines it "owns."** `main` had picked up a stray duplicate of the
  permission-gate commit (`e33bd7a`) — the same work, landed twice under different hashes because
  history-stripping the `Co-Authored-By` trailer changed the commit hash. The fix was to revert
  `e33bd7a`. But that commit's diff *also* happened to touch `events.py`'s `PermissionRequest` /
  `PermissionDecision` classes (because it re-added the whole feature, event types included), and a
  straight revert of the whole commit deleted them along with the duplicate. Reverting a commit
  reverts its diff, not its "intent" — if two unrelated concerns share a commit, a revert can't
  peel them apart.
- **A clean 3-way merge doesn't fix that.** Once `main` had deleted those two classes and the
  worktree branch — which never touched `events.py` again after adding them — was merged in, git's
  merge-base logic saw: base has the classes, worktree side unchanged, main side deleted them. One
  side changed, one didn't → deletion wins, no conflict reported. A "clean merge" is not proof
  nothing was lost; it just means git found exactly one intentional-looking change per hunk. Had
  to manually re-diff against the merge-base commit to catch it.
- **Test collection errors compound before you get to the real one.** The first `pytest` run after
  the merge still failed on the same `ImportError` — because I'd checked the merge diff instead of
  the file contents post-merge. Once that was actually fixed, six failing test files collapsed to
  one remaining cause (`structlog` not installed locally — an unrelated stale-venv issue, fixed
  with `uv sync`). Multiple red test files rarely mean multiple bugs; check for a shared import
  first.

## What we learned
- Systematic debugging earned its keep here: the naive fix ("just re-add the import") would have
  worked but wouldn't have explained *why* main's `events.py` was missing code that a commit
  message claimed to have added two commits earlier. Tracing it back to the revert's overlapping
  diff is the difference between patching a symptom and understanding the branch's actual history.
- `git diff HEAD -- <file>` after a merge is the trust-but-verify step. The merge commit's summary
  said "20 files changed, 1152 insertions" and looked complete; only comparing the specific file
  against the merge-base caught the gap.

## Where this is still too simplistic
Worth being honest about, not just filed under "future work": the permission model MM-9 ships is
coarser than it looks.

- **`PermissionGate.check()` keys everything on `tool_name` alone** — `gate.py`'s allow/deny/
  remembered lookups are all `dict`/`set` operations on the tool's name string, with `arguments`
  passed into hooks but never consulted by the core deny/allow/ask logic itself. There is no
  concept of "this file" vs. "any file."
- **Concretely: allowing `write_file` allows writing to any path under `root`, not the one file
  the user actually approved.** `FileWriteTool` takes a `path` argument and checks it doesn't
  escape `root` (`write_file.py:60-68`), but the gate approves or denies *the tool*, before it ever
  looks at which path was requested. Approve one write and you've approved all of them — the
  approval is directory-wide (really root-wide) in effect, not file-scoped, even though the TUI
  prompt reads like it's asking about a single file.
- **No way to split policy by read vs. write as a class.** There's no built-in notion of "reads are
  low-risk, writes are high-risk" — that distinction would have to be hand-encoded today by listing
  every read-like tool name in `allow` and every write-like tool name in neither `allow` nor `deny`
  (so it falls through to `ask`), one tool name at a time, and re-done by hand every time a new tool
  is added. The gate has no primitive for "all tools tagged `write`," only "this exact tool name."

None of this was invisible during design — MM-9's own "assumption to re-examine" flagged
granularity as open — but it's more concrete and more limiting in practice than the original
one-line caveat suggested. A future granularity pass likely needs the gate to key on
`(tool_name, resource)` rather than `tool_name` alone, plus some notion of tool *capability class*
(read vs. write vs. execute) that policy can target instead of enumerating tool names by hand.

## Demo & test verification
- **Test:** `test_permission_gate.py` covers deny-wins-over-allow and the ask/remembered-decision
  round-trip; 115 backend tests pass (2 skipped), 24 frontend tests pass.
- **Demo:** Mark ran the live TUI against all three demo scenarios in MM-9's description — a file
  write prompting for approval, a denied write actually being blocked, and an allowlisted tool
  running without a prompt — plus the permission-denied render path. All rendered correctly.

## Open threads
- Per-resource and per-capability-class granularity (see above) and layered settings
  (project-level only, no user-level layer) are deliberately still open, tracked via
  [MM-108](https://linear.app/mark-mansour/issue/MM-108) (automated `PermissionDecision` answerer)
  and [MM-109](https://linear.app/mark-mansour/issue/MM-109) (stateless-backend redesign), not
  dropped silently.
- MM-9's Linear issue predates the Definition-of-Done checklist convention ([MM-32](https://linear.app/mark-mansour/issue/MM-32))
  and has no DoD block in its description — worth adding retroactively so the issue's tracked state
  matches what's actually true.
- [MM-10](https://linear.app/mark-mansour/issue/MM-10) (shell tool execution behind the gate) was
  blocked on this and can now start.

## For the blog (Mark to fill in)
- _Your take: the revert-that-deletes-more-than-intended is a sharp edge worth its own war story —
  did the "clean merge, no conflicts" result mislead you at all, or did you expect to have to
  double-check it?_

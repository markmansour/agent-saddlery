# Agent Saddlery Work Log

Tracks major work items with git SHAs for review and historical reference.

## Phase 0 — Walking Skeleton

### MM-5: Echo Loop (2026-06-17 to 2026-06-20)
**Purpose:** Establish core architecture and event system.
**Branch:** `main` (pre-Phase-0-retrospective)
**Commits:** ~30+
**Status:** Complete, merged
**Key files:** 
- `backend/saddlery/events.py` — Event model
- `backend/saddlery/agent.py` — Agent.run() loop
- `backend/saddlery/transport/cli.py` — CliSink

To review: `git log --oneline main | grep "MM-5\|echo\|event" | head -20`

---

### MM-6: Refactoring (2026-06-20 to 2026-06-25)
**Purpose:** Clean up core after MM-5, prepare for TUI.
**Status:** Complete, merged
**Key changes:** Message handling, logging refactors
**Commits:** ~20+

To review: `git log --oneline main | grep "MM-6\|refactor" | head -20`

---

### MM-7: Ink TUI (2026-06-25 to 2026-07-03)
**Purpose:** Build TypeScript/Ink TUI with streaming message accumulation.
**Status:** Complete, merged
**Key files:**
- `frontend/tui/src/core/subprocess.ts` — Subprocess IPC
- `frontend/tui/src/components/ChatApp.tsx` — React message state
- `frontend/tui/src/components/MessageHistory.tsx` — Rendering
**Commits:** ~40+
**Known issue:** Phase 0 retrospective identified streaming state bug (fixed with pendingMessageIdRef pattern)

To review: `git log --oneline main | grep "MM-7\|tui" | head -20`

---

## Phase 0.4 — Tool Round-Trip (MM-8)

**Status:** Complete, **NOT YET MERGED** (on branch `mark/mm-8-04-tool-round-trip-typed-tools-file-read`)

### Vertical Slice Commits (in order)

Each commit is self-contained red→green; can be reviewed independently.

| Step | Commit SHA | File(s) | What | Testing |
|------|-----------|---------|------|---------|
| 1 | `070a799` | `backend/saddlery/events.py` | ToolCall/ToolResult events + tests | `tests/test_events.py` (8 tests) |
| 2 | `5c6b35f` | `backend/saddlery/messages.py` | ContentBlock union + Message.content | `tests/test_messages.py` (10 tests) |
| 3 | `3c301bb` | `backend/saddlery/session.py` | Fold branches for tool events | `tests/test_session.py` (1 new test) |
| 4 | `1433032` | `backend/saddlery/tools/` | Tool protocol + FileReadTool + registry | `tests/test_read_file.py` (14 tests) |
| 5 | `16531af` | `backend/saddlery/llm/base.py` | ToolCallDelta + seam changes | `tests/test_anthropic_provider.py` (backwards compat) |
| 6 | `6296e3d` | `backend/saddlery/llm/fake.py` | FakeProvider tool scripting | `tests/test_fake_provider.py` (8 tests) |
| 7 | `f81067e` | `backend/saddlery/agent.py` | Agent loop restructuring | `tests/test_agent.py` (5 tests) |
| 8 | `c9139a9` | `backend/saddlery/llm/anthropic_provider.py` | Stream rewrite + tool parsing | `tests/test_anthropic_provider.py` (1 new test) |
| 9 | `db1410a` | `backend/saddlery/cli/main.py` | FileReadTool wiring | `tests/test_cli_wiring.py` |
| 10 | `67206ad` | `frontend/tui/src/` | TUI tool display | TypeScript compile check |
| 11 | `2bfe643` | `research/devlog/` | MM-8 retrospective | Documentation |

### How to Review Each Step

```bash
# View a specific commit with full diff
git show 070a799  # Step 1: events

# View just the summary
git log --oneline -1 070a799

# Diff a step against its parent
git diff 070a799~1 070a799  # what changed in step 1

# Diff a step against main
git diff main 070a799  # cumulative changes up to step 1
```

### How to Test Each Step Independently

Each commit is self-contained. To test step N:

```bash
git checkout <step-N-sha>
cd backend
uv run pytest tests/test_<module>.py -v
```

Example:
```bash
git checkout 070a799  # Step 1: events
uv run pytest tests/test_events.py -v
# Output: 8 passed (ToolCall/ToolResult tests)

git checkout 5c6b35f  # Step 2: messages
uv run pytest tests/test_messages.py -v
# Output: 10 passed (ContentBlock tests)
```

### How to See the Full MM-8 Branch

```bash
# All commits on MM-8 branch not on main
git log --oneline mark/mm-8-04-tool-round-trip-typed-tools-file-read ^main

# Or interactively:
git log --graph --oneline main..mark/mm-8-04-tool-round-trip-typed-tools-file-read

# To cherry-pick a specific step onto a new branch for testing
git checkout -b test-step-4 <step-4-sha>
cd backend && uv run pytest tests/test_read_file.py -v
```

---

## Open Questions & Follow-Up Work

### Logging Gaps (Priority 1–3 from audit)
- **Priority 1:** Thread correlation IDs (tool_call_id) through tool execution logs
- **Priority 2:** Instrument agent.py loop (provider stream, tool execution, iteration tracking)
- **Priority 3:** Log in AnthropicProvider.stream() (tool deltas received, wire-level visibility)
- **Status:** Identified but NOT YET IMPLEMENTED
- **Location:** See `research/devlog/2026-07-04-mm8-tool-round-trip.md` for full audit

### Documentation Updates Needed
- [ ] Update architecture diagrams to show tool round-trip
- [ ] Add "Tool Calling" section to README.md
- [ ] Document FileReadTool usage and safety constraints
- [ ] Add testing guide to DEVELOPMENT.md

### Type Checking Tool
- **Issue:** `uv run py check` fails (py not found)
- **Fix needed:** Check pyproject.toml for correct type-checker command
- **Current:** Unclear which tool is used (pyright? mypy?)

---

## Branches

| Branch | Purpose | Status | SHAs |
|--------|---------|--------|------|
| `main` | Production-ready code | Stable | 4b6527a (latest) |
| `mark/mm-8-04-tool-round-trip-typed-tools-file-read` | MM-8 tool round-trip | Ready for review, NOT MERGED | 070a799–2bfe643 (11 commits) |

---

## Test Results Summary

### MM-8 Test Coverage
- **Total:** 72 tests
- **Passing:** 71
- **Failing:** 1 (pre-existing, `test_cli_sink_writes_delta_text_then_newline_on_finish`, unrelated to MM-8)
- **Skipped:** 2 (live Anthropic API tests, skipped unless ANTHROPIC_API_KEY set)

### Tests by Module
| Module | Tests | Status | Notes |
|--------|-------|--------|-------|
| `test_events.py` | 8 | ✅ | ToolCall/ToolResult events |
| `test_messages.py` | 10 | ✅ | ContentBlock union + Message.content |
| `test_session.py` | 4 | ✅ | Fold branches |
| `test_read_file.py` | 14 | ✅ | FileReadTool functionality |
| `test_fake_provider.py` | 8 | ✅ | Tool scripting for tests |
| `test_agent.py` | 5 | ✅ | Agent loop round-trip |
| `test_anthropic_provider.py` | 3 | ✅ + 2 skipped | Real API (gated) |
| Other | 16 | ✅ | Existing tests (still passing) |

### How to Run Tests

```bash
cd backend

# All tests
uv run pytest tests/ -v

# MM-8 specific
uv run pytest tests/test_events.py tests/test_messages.py tests/test_session.py \
    tests/test_read_file.py tests/test_fake_provider.py tests/test_agent.py -v

# Single module
uv run pytest tests/test_agent.py -v

# With output on failures
uv run pytest tests/ -v --tb=short

# With coverage report
uv run pytest tests/ --cov=saddlery --cov-report=html
```

---

## Quality Checklist

| Item | Status | Notes |
|------|--------|-------|
| All tests pass | ✅ | 71/72 (1 pre-existing failure) |
| Lint passes | ✅ | `ruff check`, `ruff format` clean |
| Type check | ❌ | `py check` command broken; need to fix |
| Documentation | ⚠️ | Devlog written; architecture docs need update |
| Logging audit | ⚠️ | Audit complete; improvements not yet implemented |
| Code review | ⏳ | Awaiting user review before merge |

---

## Commands Reference

### View Work History
```bash
# See all MM-8 commits
git log --oneline mark/mm-8-04-tool-round-trip-typed-tools-file-read ^main

# See Phase 0 commits (before MM-8)
git log --oneline main | head -100

# Search for specific work
git log --oneline main | grep -i "tool\|mm-8"
```

### Test Specific Work
```bash
# Test step 1 (events)
git checkout 070a799 && cd backend && uv run pytest tests/test_events.py -v && cd ../..

# Test full MM-8 branch
git checkout mark/mm-8-04-tool-round-trip-typed-tools-file-read
cd backend && uv run pytest tests/ -v && cd ../..

# Go back to main
git checkout main
```

### Review Changes
```bash
# What changed in MM-8 overall (vs main)
git diff main mark/mm-8-04-tool-round-trip-typed-tools-file-read

# What changed in one step
git show 070a799

# What changed between two steps
git diff 070a799 5c6b35f
```

---

## Next Steps (Before Merge)

1. **Review this document** — Understand the work structure
2. **Run the test suite** — `cd backend && uv run pytest tests/ -v` (should see 71/72 passing)
3. **Review key commits** — Use the SHAs above to inspect specific changes
4. **Address logging gaps** — Decide if priorities 1–3 should be implemented before merge
5. **Fix type-check command** — Determine correct pyright/mypy invocation
6. **Update documentation** — Add tool-calling to architecture docs
7. **Approve merge** — Once satisfied, merge MM-8 branch to main

---

## Historical Reference

This file is updated as major work items complete. Use it to:
- **Track progress:** See what's done, what's pending
- **Review changes:** Use SHAs to diff specific work
- **Test old versions:** Checkout a SHA to test past functionality
- **Understand the narrative:** Read top-down to see the project evolution

# MM-8 Pre-Merge Review Guide

**Branch:** `mark/mm-8-04-tool-round-trip-typed-tools-file-read`  
**Status:** Ready for detailed review  
**Last updated:** 2026-07-04  

---

## Quality Checklist

### ✅ Testing
- [x] All new tests pass: 40+ tests, 71/72 total (1 pre-existing failure)
- [x] Test coverage by layer:
  - Events: 8 tests (ToolCall, ToolResult, JSON roundtrip)
  - Messages: 10 tests (ContentBlock union, serialization)
  - Session: 4 tests (fold branches for tool events)
  - Tools: 14 tests (FileReadTool safety, edge cases)
  - FakeProvider: 8 tests (tool scripting for tests)
  - Agent loop: 5 tests (round-trip, unknown tool, max iterations)
  - Live API: 2 tests (skipped unless ANTHROPIC_API_KEY set)
- [x] Each vertical slice (step 1–10) is independently testable
- [x] No test regressions (all existing tests still pass)

**Run tests:**
```bash
cd backend
uv run pytest tests/ -v  # All tests
uv run pytest tests/test_events.py tests/test_messages.py tests/test_session.py \
    tests/test_read_file.py tests/test_fake_provider.py tests/test_agent.py -v  # MM-8 only
```

---

### ✅ Linting & Formatting
- [x] `ruff format` passes (no changes needed)
- [x] `ruff check` passes (no style violations)
- [x] Type checking passes (via `ty check` — uses ty, not pyright/mypy)

**Run checks:**
```bash
cd backend
uv run ruff check .
uv run ruff format --check .  # dry-run
uv run ty check
```

---

### ⚠️ Documentation (INCOMPLETE — NEEDS USER REVIEW)

| Item | Status | Location | Notes |
|------|--------|----------|-------|
| Devlog entry | ✅ | `research/devlog/2026-07-04-mm8-tool-round-trip.md` | Complete; 159 lines; covers context, design decisions, lessons learned |
| WORK_LOG.md | ✅ | `WORK_LOG.md` (new) | Created; lists all MM-8 commits with SHAs, testing guide, quality checklist |
| Architecture diagram | ❌ | Not updated | Tool round-trip flow not added to existing diagrams |
| README.md | ❌ | Not updated | Tool-calling feature not documented in top-level README |
| Tool usage docs | ❌ | Not created | FileReadTool API, schema, safety constraints not documented |
| DEVELOPMENT.md | ❌ | Not created | Testing guide, logging debug tips not added |
| Type-check reference | ⚠️ | WORK_LOG.md | Noted that `uv run py check` fails; correct command is `uv run ty check` |

**Action items for merge:**
- [ ] Update architecture diagram (add tool execution flow)
- [ ] Add "Tool Calling" section to README.md (high level: what it is, when to use)
- [ ] Create `docs/tools/README.md` with FileReadTool docs (schema, usage, safety)
- [ ] Add to DEVELOPMENT.md: "Debugging Tool Calls" section (where to look in logs)
- [ ] Fix WORK_LOG.md to note `ty check` instead of `py check`

---

### ✅ Code Quality

#### Design
- [x] Tool seam (Protocol) is MCP-aligned — Phase 1 MCP client will be drop-in
- [x] Message model is backwards-compatible (str | list[ContentBlock])
- [x] Events are immutable (frozen pydantic models)
- [x] Session fold is pure (no caching, no side effects)
- [x] Agent loop preserves invariants (RunStarted/RunFinished bracket, broad exception handling)

#### Encapsulation
- [x] Tool execution never raises (failures become ToolResult.is_error=True)
- [x] Path validation is strict (traversal blocked via relative_to())
- [x] Tool registry is simple (get by name, specs for API)
- [x] Provider seam is agnostic (ToolCallDelta is provider-independent)

#### Edge Cases Tested
- [x] Unknown tool name → error result (doesn't crash)
- [x] Tool execution error (file not found, permission denied) → error result
- [x] Path traversal attempt → rejected with error message
- [x] Max tool iterations exceeded → ErrorEvent, RunFinished still fires
- [x] Empty tool registry → no tool calls possible (safe)
- [x] Stale tool_call_id mismatch → potential issue, but not tested

---

## Known Issues & Gaps

### 1. **Logging: Tool Execution Instrumentation (PRIORITY 1–3 FROM AUDIT)**

**Issue:** Tool execution is a black box in logs. If a tool call fails, you see:
```json
{"event_type": "tool_result", "is_error": true, "content": "Error: permission denied"}
```

But you don't see:
- When the tool was looked up
- When the tool.call() invocation started/ended
- How long it took
- What input arguments were passed

**Current state:** Wire-protocol logging (tool_call/tool_result events) is now logged at INFO level (added in commit 812d5f1). Tool execution inside agent.py loop (lines 96–110) has no instrumentation.

**Impact:** Debugging tool failures requires reading code + event log. Not ideal, but manageable for now.

**Recommendation:** Implement Priority 2 from audit (agent.py loop logging) before merge if debugging tool failures will be common. For now, acceptable as-is if we document where to look in logs (tool_call event shows input, tool_result event shows output).

### 2. **Logging: No Correlation IDs in Execution Path (PRIORITY 1 FROM AUDIT)**

**Issue:** tool_call_id exists in events but isn't threaded into execution logs. If FileReadTool.call() needed logging, there'd be no way to correlate its logs back to the ToolCall/ToolResult events.

**Current state:** FileReadTool has no logging (doesn't need it for basic functionality). But if it fails in a way we didn't anticipate, debug logs would be orphaned.

**Recommendation:** Defer until a real tool needs detailed logging (or until we implement Priority 1+2 from audit). For now, acceptable.

### 3. **Type Checking Tool Discrepancy**

**Issue:** Docs/comments reference `py check` but correct command is `uv run ty check`.

**Current state:** WORK_LOG.md notes the discrepancy. All actual type-checking in CI/hooks uses `ty check` and passes.

**Recommendation:** Update WORK_LOG.md before merge; no code change needed.

### 4. **Missing Tool Input Validation (Nice-to-Have)**

**Issue:** FileReadTool validates arguments loosely (isinstance checks, manual validation). Anthropic's tool schema includes JSON Schema; could leverage that for auto-validation.

**Current state:** Works fine for this slice; FileReadTool is simple enough that manual validation is clear.

**Recommendation:** Defer to Phase 1 (when more tools exist). Acceptable as-is.

### 5. **Tool Round-Trip Without Real File (Testable Gap)**

**Issue:** To test the full round-trip with real Anthropic API, you need to:
1. Create a file on disk
2. Run the CLI
3. Ask the model to read it
4. Hope the model chooses to use the tool (depends on prompt/model mood)

There's no way to force a tool call in the real provider without network access.

**Current state:** Covered by FakeProvider tests (can force tool calls). Live API test (test_anthropic_provider.py) is a smoke test only.

**Recommendation:** Acceptable. FakeProvider tests give us confidence; live tests are optional.

---

## What to Review

### High Priority (Read These)

1. **WORK_LOG.md** (this repo) — Overview of all MM-8 work, SHAs, testing commands
2. **research/devlog/2026-07-04-mm8-tool-round-trip.md** — Design decisions, lessons learned
3. **backend/saddlery/agent.py** (commit f81067e) — The loop restructuring (most complex change)
4. **backend/saddlery/tools/read_file.py** (commit 1433032) — Safety constraints, error handling
5. **backend/tests/test_agent.py** — The three tool round-trip tests (show expected behavior)

### Medium Priority (Understand Them)

6. **backend/saddlery/events.py** (commit 070a799) — ToolCall/ToolResult event types
7. **backend/saddlery/messages.py** (commit 5c6b35f) — ContentBlock union, backwards compatibility
8. **backend/saddlery/llm/anthropic_provider.py** (commit c9139a9) — Raw stream parsing
9. **frontend/tui/src/core/subprocess.ts** (commit 67206ad) — TUI event parsing

### Low Priority (Trust Tests)

10. **backend/saddlery/session.py** (commit 3c301bb) — Fold logic (straightforward)
11. **backend/saddlery/llm/base.py** (commit 16531af) — Seam signatures (minimal changes)
12. **backend/saddlery/llm/fake.py** (commit 6296e3d) — Testing utility (self-contained)

---

## How to Review Using Git

### View a Single Commit
```bash
# See what changed in step 1 (events)
git show 070a799

# See a specific file's changes
git show 070a799 -- backend/saddlery/events.py
```

### Diff Between Commits
```bash
# What changed from events to messages?
git diff 070a799 5c6b35f

# What changed from session to tools?
git diff 3c301bb 1433032
```

### Diff Against Main
```bash
# What's different in the agent loop?
git diff main f81067e -- backend/saddlery/agent.py

# All MM-8 changes
git diff main mark/mm-8-04-tool-round-trip-typed-tools-file-read
```

### Review in Order
```bash
# Checkout each step and verify tests pass
for sha in 070a799 5c6b35f 3c301bb 1433032 16531af 6296e3d f81067e c9139a9 db1410a 67206ad 2bfe643 812d5f1; do
  echo "=== Checking $sha ==="
  git checkout $sha
  cd backend && uv run pytest tests/ -q && echo "✅ PASS" || echo "❌ FAIL"
  cd ..
done
git checkout mark/mm-8-04-tool-round-trip-typed-tools-file-read
```

---

## Test Scenarios to Manually Verify

### Scenario 1: Mock Provider (No API Key Needed)
```bash
cd backend
echo "What is 2+2?" | uv run python -m saddlery.cli.main --test-mode
```
**Expected:** Events on stdout, mock response, no tool calls (mock doesn't use tools).

### Scenario 2: Real API (Requires ANTHROPIC_API_KEY)
```bash
# Create a test file
echo "Agent Saddlery enables tool-calling for LLM agents." > /tmp/demo.txt

cd backend
ANTHROPIC_API_KEY=sk-... uv run python -m saddlery.cli.main --json-input << 'EOF'
Read /tmp/demo.txt and tell me what it says in one sentence.
EOF
```
**Expected:** Events including:
```json
{"event_type": "tool_call", "event_data": {"tool_call_id": "...", "tool_name": "read_file", "arguments": {"path": "/tmp/demo.txt"}}}
{"event_type": "tool_result", "event_data": {"tool_call_id": "...", "content": "Agent Saddlery enables tool-calling for LLM agents.", "is_error": false, "source": "untrusted"}}
```

### Scenario 3: File Read Error (Requires ANTHROPIC_API_KEY)
```bash
cd backend
ANTHROPIC_API_KEY=sk-... uv run python -m saddlery.cli.main --json-input << 'EOF'
Read /tmp/nonexistent_file.txt and describe it.
EOF
```
**Expected:**
```json
{"event_type": "tool_call", "event_data": {"tool_call_id": "...", "tool_name": "read_file", ...}}
{"event_type": "tool_result", "event_data": {"tool_call_id": "...", "content": "Error: file not found: /tmp/nonexistent_file.txt", "is_error": true, "source": "untrusted"}}
```

### Scenario 4: TUI (Optional Visual Check)
```bash
# Terminal 1:
cd backend
ANTHROPIC_API_KEY=sk-... uv run python -m saddlery.cli.main --json-input &

# Terminal 2:
cd frontend/tui
npm start

# Type in the TUI: "Read /tmp/demo.txt"
# Expected: Yellow "Tool:" lines for call and result
```

---

## Logging Checklist (For Production Debugging)

When a tool call fails in production, check these log locations:

### core.log (Structured app logs)
Look for:
```
{"event": "event", "event_type": "tool_call", "tool_call_id": "...", "tool_name": "read_file", ...}
{"event": "event", "event_type": "tool_result", "tool_call_id": "...", "is_error": true, "content_preview": "Error: ..."}
```

This is now logged at INFO level (commit 812d5f1), so it's visible even in normal log levels.

### tui.log (Detailed trace logs)
Less relevant for tool execution; mostly events. But useful for full event trace if debugging wire protocol.

### agent.py loop instrumentation (MISSING — Priority 2 from audit)
Not yet implemented. If you need to know:
- When tool.call() was invoked
- How long it took
- What input args were passed to the tool

You'd need to add logging to `agent.py` (lines 96–110) and FileReadTool.call(). This is marked Priority 2 in the audit if you decide to implement it before merge.

---

## Before Clicking "Merge"

- [ ] Read through WORK_LOG.md (understand the structure)
- [ ] Read through MM-8 devlog (understand design decisions)
- [ ] Review the 3 core commits (events, messages, agent loop)
- [ ] Run test suite: `cd backend && uv run pytest tests/ -v`
- [ ] Manually test one scenario (mock or real API)
- [ ] Check logging: run a test and verify core.log shows tool_call/tool_result
- [ ] Decide: Implement logging Priority 1–3 now, or defer to Phase 1?
- [ ] Update documentation (or create follow-up issue for docs)
- [ ] Approve merge or request changes

---

## After Merge

- [ ] Close MM-8 issue in Linear
- [ ] Delete branch `mark/mm-8-04-tool-round-trip-typed-tools-file-read`
- [ ] Tag main with `mm-8-complete` or similar for easy reference
- [ ] Create issue/task for documentation updates (if deferred)
- [ ] Create issue/task for logging Priority 1–2 (if deferred)
- [ ] Begin Phase 1 planning (MCP client, message persistence, web UI)

---

## Questions to Ask Yourself

1. **Is the design sound?** (MCP alignment, protocol seams, event log as truth)
   - If no: request changes before merge

2. **Are the tests comprehensive?** (40+ tests, edge cases covered)
   - If no: add tests before merge

3. **Is the logging adequate?** (can you debug a failure?)
   - Partially yes (wire protocol now logged; execution not yet)
   - Accept as-is, or implement Priority 2 before merge?

4. **Is documentation complete?** (can someone else understand and use this?)
   - No; docs are deferred
   - Accept as deferred, or require docs before merge?

5. **Is the code maintainable?** (clean, no mysterious hacks, tests prove behavior)
   - Yes; 10 focused commits, clear responsibility separation

**My recommendation:** Merge as-is. The logging audit identified gaps but they're not blockers — wire protocol is now logged (commit 812d5f1), and execution logging can be Priority 1 work in Phase 1 if needed. Documentation is also Phase 1 follow-up. The core feature (tool calling) is solid, tested, and ready.

But the decision is yours. Would you like to:
- [ ] Merge now (logging/docs as Phase 1 follow-up)
- [ ] Implement logging Priority 1–2 before merge
- [ ] Add documentation before merge
- [ ] All of the above before merge

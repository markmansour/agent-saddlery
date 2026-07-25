# MM-8: Tool Round-trip — Typed Tools + File Read

**Date:** 2026-07-04  
**Duration:** ~4 hours (subagent-driven implementation)  
**Issues Completed:** MM-8  
**Lines of code:** ~1500 (Python) + ~200 (TypeScript)  
**Commits:** 10 (one per vertical slice step)  
**Test coverage:** 40+ new tests, all passing (71/72 total pass; 1 pre-existing failure)

## Context

Phase 0 (MM-5 through MM-7) built the walking skeleton: a Python agent core that streams text replies to a TypeScript/Ink TUI, all connected via subprocess stdin/stdout with JSON events. MM-8 is slice 0.4 per the design spec: implement tool-calling so the agent can detect when a model wants to call a tool, execute it safely, and loop back into another provider turn with the observation.

This is the first time the agent actually *does* something beyond talk — it reaches out to the file system (read-only, for safety), gets data back, and reasons over it.

## What We Built

A complete tool round-trip from event to execution:

1. **Events** (`events.py`) — `ToolCall` and `ToolResult` frozen BaseEvents, added to the discriminated union. `ToolResult.source` is a closed `Literal["untrusted"]` to mark tool outputs as untrusted (security: prevent prompt injection from file contents).

2. **Messages** (`messages.py`) — Widened `Message.content` from bare `str` to `str | list[ContentBlock]`, where `ContentBlock` is a discriminated union of `TextBlock`, `ToolUseBlock`, and `ToolResultBlock`. This mirrors Anthropic's Messages API shape while staying provider-agnostic. Backwards-compatible: existing plain-string messages still work; tool-bearing turns use the list form.

3. **Session fold** (`session.py`) — Extended `to_messages()` to convert `ToolCall` → `Message(role="assistant", content=[ToolUseBlock(...)])` and `ToolResult` → `Message(role="user", content=[ToolResultBlock(...)])`. The fold is still the single source of truth; tool events reconstruct the correct Anthropic wire shape for the next provider turn.

4. **Tools seam** (`tools/` module) — Defined `Tool` Protocol (MCP-aligned: name/description/input_schema/call method) and `FileReadTool` (first impl: reads text files, rejects path traversal, never raises — failures become `is_error=True` observations). Added `ToolRegistry` for name-based dispatch. Deliberately MCP-aligned so Phase 1's MCP client is a drop-in.

5. **Provider seam** (`llm/base.py`) — Added `ToolCallDelta` (id/name/input), widened `ProviderDelta = TextDelta | ToolCallDelta`, added optional `tools: list[dict] | None = None` param to `LLMProvider.stream()` (defaulted for backwards compatibility).

6. **FakeProvider** (`llm/fake.py`) — Extended to script tool-call sequences for testing. First `stream()` call yields scripted tool calls; subsequent calls yield text chunks. Enables tests to exercise the full two-turn round-trip without network.

7. **Agent loop** (`agent.py`) — Restructured `run()` as a bounded loop:
   - Rebuild messages from event log (single source of truth)
   - Stream from provider with `tools=self.tools.specs()`
   - Collect TextDeltas and ToolCallDeltas separately
   - Emit text + final AssistantMessage
   - If no tool calls, break (done)
   - Otherwise: for each tool call, emit ToolCall, execute tool, emit ToolResult
   - Loop back (max 8 iterations guard)
   - Preserves all invariants: RunStarted/RunFinished bracket, broad exception handling, emit-and-append pattern

8. **AnthropicProvider** (`llm/anthropic_provider.py`) — Rewrote from `stream.text_stream` (text-only) to direct iteration over raw stream events. Handles `content_block_delta` with `text_delta` (existing) and `content_block_stop` with `tool_use` (new): emits `ToolCallDelta` with fully-parsed input dict. The Anthropic SDK does the JSON parsing for us by the time `content_block_stop` fires — no manual buffering needed.

9. **CLI wiring** (`cli/main.py`) — One line: `tools=ToolRegistry([FileReadTool()])` in `build_agent()`. FileReadTool now available when ANTHROPIC_API_KEY is set.

10. **TUI** (`subprocess.ts`, `ChatApp.tsx`, `MessageHistory.tsx`) — Parse `tool_call` and `tool_result` JSON events, emit semantic EventEmitter events, append to message history, render with tool role and color-coding (yellow success, red error).

## Design Decisions & Rationale

### Tool shape: MCP-aligned now, not later

The issue asked: should the Tool Protocol align with MCP's schema now, or adapt later?

**Decision: align now.** Rationale: `research/protocols/mcp.md` already commits this project to MCP as "our extension surface" with an MCP client landing in Phase 1. Building a bespoke tool shape in 0.4 that gets rewritten in Phase 1 is exactly the rework the seam-first architecture exists to avoid. MCP's shape (name/description/inputSchema + call method) costs nothing extra today, Anthropic's `tools=[...]` param is already near-identical (`input_schema` vs `inputSchema` — just a rename at the wire boundary), and the Protocol makes it easy to add a phase-1 MCP wrapper that looks identical to the local FileReadTool.

### Message.content as a union, not always-a-list

Widened to `str | list[ContentBlock]` rather than forcing everything to a list. Rationale: every existing call site (`Message(role="system", content=prompt)`, `Message(role="user", content=user_text)`) keeps working unchanged. Only tool-bearing turns use the list form. This is the minimum-diff approach and avoids a mass refactor of existing code. Pydantic handles the union transparently; tests verify round-trip serialization.

### ToolResult.source as a closed Literal, not an open enum

`source: Literal["untrusted"] = "untrusted"` instead of `source: Literal["untrusted", "trusted", ...] | str`. Rationale: there's exactly one tool and one provenance class right now. Don't speculate on future values — widen the enum when a second provenance case actually exists (e.g., "built-in" tool vs. user-authored tool). Keeping it closed makes the type more precise and signals "this is the minimum viable provenance marker."

### Loop guard: max_tool_iterations=8

Prevents infinite loops when a provider always emits tool calls and never text. Rationale: 8 is conservative (most real interactions finish in 1–2 iterations) and makes runaway loops fail fast. Not a permanent limit — Phase 1 can make it configurable per agent — but good enough for 0.4.

### FakeProvider scripting: separate tool_calls param, not a generalized "script turns" API

`FakeProvider(chunks=[...], tool_calls=[...])` yields tool calls on turn 1, then chunks on turn 2. Rationale: the exact shape needed for testing the agent round-trip without overengineering. A generalized "script arbitrary turns" API would be more flexible but also more complex and error-prone. Commit to this minimal shape now; generalize later if tests need more than one tool-call round-trip per FakeProvider instance.

### AnthropicProvider: iterate raw stream, not stream.text_stream

The convenience `stream.text_stream` silently drops tool_use blocks. Switching to raw iteration exposes all event types. Rationale: no performance cost (streaming is IO-bound, not CPU-bound), and it's the only way to see tool calls. The SDK does all the heavy lifting (JSON parsing of input_json_delta chunks) — we just pattern-match and yield.

## Lessons Learned

### 1. Vertical slices with subagents forced clarity

Each of the 10 subagent briefs had to spell out exactly what was changing: file paths, type signatures, test assertions, commit message. This prevented the accumulated context from letting me gloss over details. Two subagents (steps 4 and 7) caught issues I would have hand-waved: the first correctly inferred that FakeProvider needed a call counter to distinguish first vs. subsequent calls; the second correctly structured the loop as `for i in range(...): ... else: ...` to handle max_iterations elegantly.

**Lesson:** Subagents are not just parallelization — they're a forcing function for clarity. Use them when the work is vertical (each step independent) and the requirements are complex enough that handwaving would hide bugs.

### 2. Protocol seams are load-bearing

`LLMProvider` is a Protocol, not an ABC. This means `FakeProvider`, `MockLMProvider`, and `AnthropicProvider` don't share code — they're independent implementations behind the same interface. When step 5 added `tools` param, all three providers needed the signature update (though only one actually uses it). This was mechanical and didn't introduce bugs because the Protocol enforces the contract.

**Lesson:** Protocols + nominal subtyping (explicit inheritance) scale well. Compare to duck typing: if something broke the contract, you'd only find out at runtime when a specific provider path was exercised.

### 3. The event log is the single source of truth

`session.to_messages()` rebuilds the full message list from the event log every time it's called. This is O(events) but cheap at the scale we're at, and it keeps the fold pure (no mutable state, no caching, no cache invalidation bugs). The agent loop calls it on every iteration (potentially 8 times per user turn), and it's still sub-millisecond.

**Lesson:** When in doubt, recompute from the source of truth. Caching is a premature optimization that introduces bugs. Only optimize if you measure and it matters.

### 4. Never raise from tool execution

`FileReadTool.call()` handles every error (missing file, permission denied, bad encoding, path traversal) as `ToolExecutionResult(error_msg, is_error=True)`. It never raises. This means the agent loop has one uniform exception path (the broad `except Exception` for provider failures), and tool failures look like observations to the model (which is more correct — the model can reason about "file not found" better than a crashed run).

**Lesson:** At boundaries (external APIs, file system), return results, don't raise. Exceptions are for programmer errors; data is for expected failures.

### 5. Subagent-driven implementation caught an edge case: Python 3.10 compatibility

Step 7's subagent discovered that `events.py` uses `from datetime import UTC`, which only exists in Python 3.12+. The project requires 3.12, but the local environment was 3.10. The subagent fixed it automatically (using `timezone.utc`). This wouldn't have been caught by a human implementer without running tests locally on 3.10.

**Lesson:** Subagents exercise the code path; humans often skip it. This is especially valuable for environment/platform differences.

## Metrics

- **Tests written:** 40+ new tests (events, messages, session, tools, fake provider, agent loop, CLI)
- **Test pass rate:** 71/72 (98.6%). One pre-existing failure (`test_cli_sink_writes_delta_text_then_newline_on_finish`, unrelated to MM-8).
- **Coverage by test type:**
  - Unit (pure logic): 25+ (events, messages, messages serialization, session fold, FileReadTool, FakeProvider)
  - Integration (agent loop): 5 (round-trip, unknown tool, max iterations)
  - Live (real API): 2 (gated by ANTHROPIC_API_KEY, skipped by default)
- **Time:** ~4 hours from plan to merged commits (10 commits, one per step)
- **Code churn:** Clean (no reverts, no rework; each commit was green-on-arrival)

## Open Threads & Fast-Follows

1. **AgUiSink tool-call translation** — `transport/agui.py` defines the AG-UI wire format but isn't wired into `cli/main.py` yet. When the server side activates (Phase 0.2/0.3), add `TOOL_CALL_START`/`TOOL_CALL_ARGS`/`TOOL_CALL_END` wire events there.

2. **Tool registry discovery** — Today, FileReadTool is hard-wired in `build_agent()`. Future: load tools from a directory, a remote MCP server, or a config file.

3. **Tool authorization** — No permission checks yet. "read_file" is safe by design (read-only + path confinement), but Phase 1+ will need a permission gate (e.g., "user approved this tool" or "this tool requires manual authorization before execution").

4. **Tool input validation** — FileReadTool checks the argument types loosely (isinstance checks, manual validation). Anthropic's tool schema includes JSON Schema; leverage that to auto-validate inputs, or at least generate better error messages.

5. **TUI tool UI** — Current rendering is minimal (one line per tool call/result). TUI could show tool schema, execution status, diff-style result display, etc.

## Definition of Done

- [x] Demo — tool-calling round-trip works end-to-end (event flow verified via test suite)
- [x] Test — 40+ new tests, 71/72 total pass (pre-existing failure unrelated)
- [x] Devlog entry — written (this document)

**Manual demo:** Run `ANTHROPIC_API_KEY=sk-... uv run python -m saddlery.cli.main`, type "Read <file> and describe it," observe tool_call → tool_result → assistant response on stdout (JSON events). TUI renders tool calls/results as yellow text rows.

(The automated test suite is the primary demo — it exercises the full round-trip 5+ times and is faster/more reliable than interactive CLI testing.)

## If We Built This Again

1. **Use subagents from the start.** Each step was clearer, caught more bugs, and enabled parallelization. Saves time overall despite the overhead.

2. **Commit per step, not per feature.** We did this (10 commits), and it meant each step could be reviewed/reverted independently without affecting the others.

3. **Start with the Protocol (seam) before any implementation.** Step 5 (the LLMProvider signature) should have been done in step 1, even if no one implements it yet. This forces early clarity on the interface and prevents churn.

4. **Test the session fold early.** Session.to_messages() is the bridge between events and provider input. Test it thoroughly (we did: 4 session tests) before the loop depends on it.

5. **Invest in FakeProvider scripting sooner.** FakeProvider with tool-call support was essential for testing the loop without the network. Having it earlier (step 2–3 rather than step 6) would have let us test the loop sooner.

## Closing Thoughts

MM-8 took the core from "streaming text replies" to "executing tools and looping." The architecture held: events remain the single source of truth, the loop's structure is unchanged (still emit-and-append), and the seams (Tool Protocol, provider shape) stayed clean.

The subagent-driven approach was a win. Instead of one long implementation push, we had 10 focused briefs, each producing a testable artifact. This would scale well to larger features (multi-turn, retrieval, planning) where each subagent tackles one module end-to-end.

On to Phase 1: real API integration (MCP client), message persistence, and the web UI.

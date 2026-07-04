# Phase 0 Retrospective — Walking Skeleton Complete

**Date:** 2026-07-04  
**Duration:** 17 days (2026-06-17 to 2026-07-04)  
**Issues Completed:** MM-5 through MM-7 (Echo loop, Refactoring, Ink TUI)  
**Lines of code:** ~2000 (Python core) + ~1500 (TUI TypeScript)  
**Commits:** 80+ across both backend and frontend

## What We Set Out To Do

Build the thinnest viable end-to-end path that proves the protocol boundary works:
1. **Core** — Python event loop that reads user input, calls an LLM, emits structured events
2. **Protocol** — Typed JSON events (AG-UI format) flowing over stdin/stdout
3. **TUI** — Terminal UI that sends messages and renders streamed responses

Phase 0 was explicitly **not** about building a production system. It was about proving that messages can flow from user → core → LLM → TUI without architectural dead-ends.

## What Actually Happened

We shipped exactly that, but the path was bumpier than expected. The core was straightforward, but the TUI exposed three categories of problems:

### 1. State Management in Streaming (Hardest)

The TUI needed to accumulate streaming tokens (deltas) into a growing message without losing data or overwriting previous messages. The bug was subtle:

```typescript
// WRONG: stale closure
const assistantBuffer = "";  // captured once
core.on("assistant_delta", (text) => {
  assistantBuffer += text;  // always adds to the same variable
  setMessages([...messages, assistantBuffer]);  // overwrites, doesn't accumulate
});
```

The fix required rethinking state:

```typescript
// RIGHT: per-message IDs
const pendingMessageIdRef = useRef<string | null>(null);
core.on("assistant_delta", (text) => {
  setMessages(prev => prev.map(msg => 
    msg.id === pendingMessageIdRef.current 
      ? { ...msg, content: msg.content + text }  // append to THE RIGHT MESSAGE
      : msg
  ));
});
```

This was a 6-hour debugging session that exposed the gap between what I *thought* the code did (accumulating a buffer) and what it *actually* did (overwriting a single variable). The fix was one variable (`pendingMessageIdRef`) and proper closure discipline.

**Lesson:** Streaming state in React is tricky. The abstraction (render based on props) breaks down when you're holding local state across multiple events. The fix was to externalize the "which message are we updating?" as a ref, not bake it into handler closures.

### 2. Subprocess IPC Edge Cases (Moderate)

Getting stdin/stdout communication between Node and Python to work required handling:
- **Buffering:** Python stdout was buffered, so events arrived in batches. Fixed with `PYTHONUNBUFFERED=1`.
- **Working directory:** `uv run` needs to start from `backend/`, not from wherever the TUI spawns. Fixed with `sh -c "cd /path && uv run ..."`.
- **Pipes vs TTY:** Ink's raw mode doesn't work with piped stdin. Not a problem (TTY is available in normal use), but complicated testing.
- **JSON parsing:** Had to be strict about what goes to stdout (events only) vs stderr (logs only).

The lesson here was that subprocess communication isn't a free abstraction—you pay for it with environmental setup. This is exactly where it's worth paying; the isolation is valuable. But it means deployment will need this care too.

### 3. Logging Design (Most Time-Consuming)

This was the biggest time sink and the most instructive failure. We went through five iterations:

1. **Start:** Detailed JSON logs mixed with events on stdout → unparseable (logs and data indistinguishable)
2. **Iteration 2:** Separated stderr (logs) from stdout (events) → lost visibility into message content
3. **Iteration 3:** Simplified log format to state transitions → `[✓] message complete` without telling you what the message was
4. **Iteration 4:** Added message content back → still truncating (lost important detail)
5. **Final:** Full content, timestamps, wire protocol logging → actually useful

The root problem: I designed logging reactively (adding detail when I hit a blocker) instead of upfront. By session end, we had a three-tier architecture (trace/wire/app), but it took 20+ commits and a code-review agent to get there.

**Lesson:** Logging architecture is *not* a detail. It should be designed alongside the system, not bolted on. If you're going to iterate on logging, iterate upfront in a design document, not in code commits. The agent's review identified 10 issues; we fixed 3. For Phase 1, I should design the logging architecture first, then implement.

## Decisions & Rationale

### subprocess IPC, not HTTP
Chose to run the core as a subprocess (stdin/stdout JSON pipes) rather than HTTP server. Rationale:
- **Lower latency** — no TCP/socket overhead for a local process
- **Simpler to develop** — no server boilerplate, no port conflicts, no registration
- **Shared Python environment** — the TUI is just JavaScript; it's clean to let the core be pure Python
- **Isolation ready** — stdin/stdout is how sandboxes (like nsjail) communicate with the outside

Downside: harder to test, requires more environmental setup (cwd, PYTHONUNBUFFERED, piping). But this is worth it.

### AG-UI protocol as the boundary
The core emits **events** (not responses). Each event has a `type` and `data`. This is higher-level than "raw JSON" but lower-level than "RPC calls". It's the right granularity for streaming (each delta is an event) and for decoupling (the TUI doesn't need to know about LLM internals).

The payoff: When we switched from mock LLM to understanding the real protocol, we didn't change the TUI at all. The contract held.

### Mock provider for Phase 0
Using `MockLMProvider` instead of the real Anthropic API was the right call. It:
- Removed a dependency (API key, network, rate limits)
- Made testing instant (no network latency)
- Let us focus on the TUI/core integration, not API integration
- Proved the protocol worked end-to-end without external dependencies

The cost: One bug (wrong method name) masked itself as protocol compliance ("it parsed as JSON, so it worked") for a while. We should have had a type-level check that MockLMProvider implements the right interface. We do now (Protocol[LLMProvider]).

## Dead Ends & What We Learned

### Attempt 1: Raw Ink without state management framework
Tried to manage message state directly in React without explicit ID tracking. Result: lost track of which delta belonged to which message. Learned: **Explicit IDs are load-bearing.**

### Attempt 2: Logging everything to one file
Tried tee'ing stdout+stderr to core.log. Result: unparseable mix of events and logs. Learned: **Stdout and stderr have different audiences; keep them separate.**

### Attempt 3: Truncating logged content
Logged message previews (first 50 chars) to keep logs readable. Result: when debugging, the crucial detail was in the truncated part. Learned: **The computer should abbreviate, not the logger. Log the full thing; let grep/jq filter.**

## What We Learned

### 1. Streaming State is Non-Obvious
The classic React pattern (props-driven rendering) breaks down when you're accumulating data across multiple async events. The fix isn't to fight React; it's to be explicit about *which* piece of state you're updating (via ID refs, not closure captures).

### 2. Subprocess Communication is Workable but Demanding
Running a subprocess with piped I/O is feasible for a local dev tool, but it has environmental requirements (cwd, buffering flags, shell setup). The isolation is worth it, but deployment needs care.

### 3. Protocol Boundaries Need Type Safety
The fact that MockLMProvider had the wrong method name (stream_completion vs stream) and we *still* got valid JSON was a red flag. The fix: Protocol[LLMProvider] at the type level. Now this is enforced.

### 4. Logging Can't Be Bolted On
It's tempting to add logging as you hit friction points. But this leads to chaotic iteration. Better: design upfront (even a rough 1-page design beats no design), then implement. The agent's code review identified 10 issues; a design-first approach would have caught most of them.

### 5. E2E Testing Is Hard For TUIs
Unit tests didn't catch the streaming bug. The bug only manifested in real usage (multiple messages, streaming tokens). For TUIs, manual E2E testing (hold a real conversation) beats any automated test. We should invest in a test harness that can replay recorded streams, but that's future work.

## Open Threads

1. **Real Claude API** — We're still using the mock provider. Phase 1 is integrating the Anthropic SDK.
2. **Message persistence** — No save/load yet. Phase 1 should add this.
3. **Logging architecture** — We have trace/wire/app logs; still missing handler-level instrumentation and message IDs for correlation.
4. **Web UI** — TUI is working; web UI is separate phase.
5. **Tool use** — Core doesn't call tools yet. That's Phase 2.

## Metrics

- **Time spent:** ~20 hours over 17 days
  - Architecture/setup: 4 hours
  - Streaming fixes: 6 hours
  - Logging iteration: 8 hours
  - Integration/polish: 2 hours
- **Code churn:** High in logging (20+ commits), low elsewhere
- **Bugs found:** 5 major (streaming state, protocol compliance, JSON serialization, subprocess blocking, wire protocol logging), ~10 minor (linting, type issues)
- **Tests:** 6 unit tests (not sufficient), E2E manual (gold standard)

## If I Built This Again

1. **Design logging upfront.** One design doc beats 20 debugging sessions.
2. **Use message IDs from day 1.** Makes correlation trivial.
3. **Separate wire protocol logging from start.** Don't bolt it on when you hit bugs.
4. **Invest in E2E test harness earlier.** Manual testing works but doesn't scale.
5. **Type-check protocol implementations.** Protocol[LLMProvider] prevented a class of bugs.

## Closing Thoughts

Phase 0 achieved its goal: proving the protocol boundary works end-to-end. The path was messy (especially logging), but the destination is solid. The core design (events, subprocess IPC, AG-UI protocol) held up under real usage.

The biggest surprise was how much time logging took. I went into it thinking "logging is a detail," and came out understanding it's a first-class design concern. The agent's code review helped a lot here—external perspective catches what you're blind to.

On to Phase 1: real API integration and message persistence.

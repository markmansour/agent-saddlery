# OpenHands (+ new Software Agent SDK)

**The blueprint.** Closest match to Agent Saddlery's goals: general-purpose agent, event-sourced
core, typed tools + MCP, multiple interaction surfaces.

## Original architecture (arXiv 2407.16741)
Three core pieces:
1. **Agent abstraction** — a `step(state) -> action` function. Agents live in an "agenthub" so the
   community contributes implementations. You define behavior; the framework handles execution.
2. **Event stream** — the backbone. A typed, chronological series of **actions** (by the agent) and
   **observations** (results). This record *is* the state agents reason over:
   `User Message → Agent → LLM → Action → Runtime → Observation → Agent`.
3. **Runtime / sandbox** — a Docker-isolated OS with bash shell, a web browser, and an IPython server.
   Arbitrary code runs without risking the host.

## New Software Agent SDK (arXiv 2511.03690, Nov 2025) — full redesign
A complete rewrite of the agent components (OpenHands has 64k+ stars). Key technical components:
- **Event-sourced state model with deterministic replay** — rebuild any session from its event log.
- **Immutable agent configuration.**
- **Typed tool system with MCP integration.**
- **Local↔remote execution portability** — same agent runs locally or on a remote runtime.
- **Integrated REST/WebSocket services.**
- **Multiple interfaces** — visual workspaces (VS Code, VNC, browser), CLI, and API.
- Self-described edge over OpenAI/Claude/Google SDKs: native sandboxed execution + lifecycle control +
  model-agnostic multi-LLM routing + built-in security analysis.

## What Agent Saddlery takes
- The **event stream as single source of truth**, upgraded to **event sourcing with replay** (gives us
  free session replay and audit logging).
- The **`step(state) → action`** agent abstraction.
- **Typed tools + MCP** as the extension surface.
- **Local↔remote runtime portability** — designed in via a runtime abstraction (deferred to Phase 4).

## Links
- SDK paper: https://arxiv.org/abs/2511.03690 (PDF in `../papers/openhands-sdk-2511.03690.pdf`)
- Original paper: https://arxiv.org/abs/2407.16741 (PDF in `../papers/openhands-2407.16741.pdf`)
- Runtime docs: https://docs.openhands.dev/openhands/usage/architecture/runtime
- Runtime README: https://github.com/OpenHands/OpenHands/blob/main/openhands/runtime/README.md
- Build-your-own walkthrough: https://dev.to/truongpx396/openhands-deep-dive-build-your-own-guide-1al0

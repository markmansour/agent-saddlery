# Agent Saddlery

A general-purpose agent harness — not coding-specific, but code-execution capable — built to be
run and extended, with multiple frontends (TUI, Web, desktop, IDE) over a shared
[AG-UI](https://docs.ag-ui.com/introduction) protocol, [MCP](https://modelcontextprotocol.io)
extensions, and pluggable LLM providers.

> Status: **Phase 0 in progress — 0.1 echo loop implemented.** Run the streaming chat CLI from
> `backend/`: `uv run saddlery` — needs `ANTHROPIC_API_KEY` (or keep it in `backend/.env` and run
> `export $(cat .env) && uv run saddlery`). Design in the
> [Phase 0 spec](docs/specs/2026-06-16-phase0-core-design.md); tasks in
> [Linear](https://linear.app/mark-mansour/project/agent-saddlery-594c6b585b2b/overview).

## Architecture (locked decisions)

- **Language:** Python core + TypeScript frontends (mirrors [OpenHands](https://docs.openhands.dev)).
- **Wire protocol:** AG-UI (frontend ↔ core). MCP = agent ↔ tools;
  [ACP](https://agentclientprotocol.com) = editor ↔ agent (stretch).
- **Multi-user server is the destination** — built tenancy-ready from Phase 0 (`owner`/`principal` on
  every session, event, secret, permission decision); full multi-user at Phase 3.
- **Sandboxing** is coupled to multi-user (per-user isolation *is* a tenant boundary); the runtime seam
  is designed in at Phase 0.
- **Plugins** are a packaging layer over primitives (skills / hooks / MCP / agents / commands), Phase 4.

## Roadmap

P0 walking skeleton → P1 MCP + permissions → P2 multi-frontend server → P3 multi-user + execution
isolation → P4 plugin packaging → P5 stretch (ACP, workflows, multi-agent, desktop, marketplace).

## Repository layout

- **[`backend/`](backend/)** — the headless Python package (`saddlery`): typed event stream, session, the
  `LLMProvider` / `EventSink` / `SessionStore` seams, transport (CLI now, AG-UI later), and the CLI
  entrypoint. Coding standards in [`docs/conventions/python.md`](docs/conventions/python.md).
- **[`frontend/`](frontend/)** — TypeScript frontends (TUI, Web, desktop, IDE), arriving from Phase 0.3.
- **[`docs/`](docs/)** — design docs for the build:
  - **Specs** ([`docs/specs/`](docs/specs/)) — [Phase 0 core](docs/specs/2026-06-16-phase0-core-design.md),
    [Python standards & enforcement](docs/specs/2026-06-24-python-standards-design.md),
    [Mermaid diagrams](docs/specs/2026-07-02-diagrams-design.md),
    [class-diagram readability & nominal conformance](docs/specs/2026-07-02-class-diagram-readability-design.md).
  - **Plans** ([`docs/plans/`](docs/plans/)) — the step-by-step implementation plan behind each spec.
  - **ADRs** ([`docs/adr/`](docs/adr/)) — architecture decision records for cross-cutting choices
    (start at [`docs/adr/README.md`](docs/adr/README.md); first up:
    [repository layout](docs/adr/0001-repository-layout.md)).
  - **Diagrams** ([`docs/diagrams/`](docs/diagrams/)) — Mermaid class, data-model (ER), and
    echo-loop sequence diagrams (rendered inline).
- **[`research/`](research/)** — the design library: reference-design teardowns (OpenHands, CrewAI,
  Goose, Claude Code), protocol notes (MCP, AG-UI, ACP, plugins), security (sandboxing, prompt
  injection, permissions & secrets), multi-user tenancy, LLM providers, a devlog, and source papers.
  Start at [`research/README.md`](research/README.md).

## Project management

Tasks live in **[Linear](https://linear.app/mark-mansour/project/agent-saddlery-594c6b585b2b/overview)**
(the source of truth); `research/build-roadmap.md` is the high-level map.
Phases are modeled as milestones, decomposed into demonstrable vertical-slice issues.

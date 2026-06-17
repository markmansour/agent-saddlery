# Agent Saddlery

A general-purpose agent harness — not coding-specific, but code-execution capable — built to be
run and extended, with multiple frontends (TUI, Web, desktop, IDE) over a shared **AG-UI** protocol,
**MCP** extensions, and pluggable LLM providers.

> Status: **research & planning complete; Phase 0 (walking skeleton) not yet started.** No application
> code yet — this repo currently holds the design research.

## Architecture (locked decisions)

- **Language:** Python core + TypeScript frontends (mirrors OpenHands).
- **Wire protocol:** AG-UI (frontend ↔ core). MCP = agent ↔ tools; ACP = editor ↔ agent (stretch).
- **Multi-user server is the destination** — built tenancy-ready from Phase 0 (`owner`/`principal` on
  every session, event, secret, permission decision); full multi-user at Phase 3.
- **Sandboxing** is coupled to multi-user (per-user isolation *is* a tenant boundary); the runtime seam
  is designed in at Phase 0.
- **Plugins** are a packaging layer over primitives (skills / hooks / MCP / agents / commands), Phase 4.

## Roadmap

P0 walking skeleton → P1 MCP + permissions → P2 multi-frontend server → P3 multi-user + execution
isolation → P4 plugin packaging → P5 stretch (ACP, workflows, multi-agent, desktop, marketplace).

## Repository layout

- **[`research/`](research/)** — the design library: reference-design teardowns (OpenHands, CrewAI,
  Goose, Claude Code), protocol notes (MCP, AG-UI, ACP, plugins), security (sandboxing, prompt
  injection, permissions & secrets), multi-user tenancy, LLM providers, a devlog, and source papers.
  Start at [`research/README.md`](research/README.md).

## Project management

Tasks live in **Linear** (the source of truth); `research/build-roadmap.md` is the high-level map.
Phases are modeled as milestones, decomposed into demonstrable vertical-slice issues.

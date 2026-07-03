# Changelog

All notable changes to Agent Saddlery are recorded here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com). The project is pre-release and planning-driven, so
entries are dated rather than versioned. This file is the **terse factual record**; the narrative
"why / how / what we learned" lives in [`research/devlog/`](research/devlog/), and tasks live in Linear.

Maintained as work lands — update it in the same commit as the change it describes.

## [Unreleased]

### 2026-07-02

#### Added
- **Generated package diagram** [`docs/diagrams/packages-core.md`](docs/diagrams/packages-core.md):
  `gen_diagrams.py` now writes the [pyreverse](https://pylint.readthedocs.io/en/stable/pyreverse.html)
  package (module-dependency) view alongside the class diagram from a single pyreverse run.
  ([MM-35](https://linear.app/mark-mansour/issue/MM-35))

#### Changed
- **CI actions bumped off deprecated Node 20**: [`actions/checkout`](https://github.com/actions/checkout)
  `v4`→`v7` (all workflows) and [`astral-sh/setup-uv`](https://github.com/astral-sh/setup-uv) `v5`→`v7`
  (`python-core.yml`) — both new majors run on Node 24, clearing the GitHub Actions deprecation
  warnings. ([MM-34](https://linear.app/mark-mansour/issue/MM-34))

### 2026-06-16

#### Added
- **Design research library** under [`research/`](research/): reference-design teardowns (OpenHands,
  CrewAI, Goose, Claude Code), protocol notes (MCP, AG-UI, ACP, plugins), security (sandboxing, prompt
  injection, permissions/secrets), multi-user tenancy, LLM providers, a devlog, and source papers.
- **Repository scaffolding**: root `README.md`, `.gitignore` (Python + TypeScript), private GitHub
  repo `markmansour/agent-saddlery`.
- **Phase 0 core design spec**: [`docs/specs/2026-06-16-phase0-core-design.md`](docs/specs/2026-06-16-phase0-core-design.md)
  — hand-rolled asyncio core, event-log-as-source-of-truth (Pydantic), an `LLMProvider` seam, an
  `EventSink` transport seam, `principal` threaded through for tenancy. Slice 0.1 (echo loop) is the
  first artifact.
- **Implementation plan for 0.1**: [`docs/plans/2026-06-16-mar5-echo-loop.md`](docs/plans/2026-06-16-mar5-echo-loop.md)
  — TDD, bite-sized tasks for the echo loop.
- **0.1 echo loop implemented** (`core/saddlery/`): immutable event models, `Session` + `to_messages()`
  fold + in-memory `SessionStore`, `LLMProvider` seam + native `AnthropicProvider` (default
  `claude-haiku-4-5`) + `FakeProvider`, `EventSink`/`CliSink`/`RecordingSink`, `Agent.run()` loop with
  the always-`RunFinished` error invariant, and the `saddlery` CLI. 16 tests + 1 gated live smoke test.
  Run `cd core && uv run saddlery` (needs `ANTHROPIC_API_KEY`). ([MAR-5](https://linear.app/mark-mansour/issue/MAR-5))
- **Project management in [Linear](https://linear.app/mark-mansour/project/agent-saddlery-594c6b585b2b/overview)**:
  project "Agent Saddlery", milestone "Phase 0 — Walking skeleton", and vertical-slice issues
  [MAR-5](https://linear.app/mark-mansour/issue/MAR-5)…[MAR-13](https://linear.app/mark-mansour/issue/MAR-13)
  (0.1 echo loop → 0.8 execution seam + persistence → 0.R retrospective), dependency-chained.

#### Decisions
- **Language**: Python core + TypeScript frontends (mirrors OpenHands).
- **Wire protocol**: [AG-UI](https://docs.ag-ui.com/introduction) (frontend↔core);
  [MCP](https://modelcontextprotocol.io) (agent↔tools); [ACP](https://agentclientprotocol.com)
  (editor↔agent, stretch).
- **First use cases**: resume writing, vacation research, running small programs.
- **Multi-user server is the destination** — build tenancy-ready from Phase 0 (`owner`/`principal` on
  every session, event, secret, permission decision); full multi-user is the Phase 3 bundle.
- **Sandboxing** is coupled to multi-user (per-user isolation *is* a tenant boundary), Phase 3; the
  runtime-abstraction seam is designed in at Phase 0.
- **Plugins** = a packaging layer over primitives (skills/hooks/MCP/agents/commands), Phase 4.
- **LLM providers**: pluggability lives in our own `LLMProvider` seam; native `AnthropicProvider`
  first. Default model `claude-haiku-4-5` (cheap, for testing — switch to Opus/Sonnet for quality);
  prompt caching and adaptive thinking on thinking-capable models. `OpenAICompatibleProvider`
  (≈ all OSS) and a gateway adapter ([LiteLLM](https://github.com/BerriAI/litellm) /
  [OpenRouter](https://openrouter.ai)) are later drop-ins. *Supersedes the survey's "LiteLLM in the core."*
- **Build approach**: vertical slices, each demonstrable end-to-end with a demo + test + devlog note;
  "define seams, fill one."

#### Changed
- `research/llm-providers.md` and `research/build-roadmap.md`: revised from "LiteLLM in core" to the
  `LLMProvider`-seam / Anthropic-native decision.
- Default model for development set to `claude-haiku-4-5` (cost saving while testing); docs now link
  Linear artifacts and referenced third-party software.

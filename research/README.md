# Agent Saddlery — Research Library

Survey of agent-harness designs and the architecture decisions for **Agent Saddlery**: a
general-purpose agent harness with a headless **Python** core and **TypeScript** frontends,
multiple surfaces (TUI, Web, desktop, IDE) over a shared **AG-UI** protocol, MCP extensions,
and pluggable LLM providers.

Survey date: **2026-06-16**.

## How to read this

- **[feature-catalog.md](feature-catalog.md)** — the full feature list, grouped by layer, with
  suggested phasing. Start here to rank/cut.
- **[build-roadmap.md](build-roadmap.md)** — the phased build order.
- **[multi-user-tenancy.md](multi-user-tenancy.md)** — how the confirmed multi-user-server goal reshapes
  the design (tenancy, per-user secrets, why it promotes sandboxing).
- **reference-designs/** — what each existing harness teaches us.
- **protocols/** — MCP, ACP, AG-UI, and **plugins** (packaging vs. MCP).
- **security/** — sandboxing, prompt injection, permissions & secrets.
- **[llm-providers.md](llm-providers.md)** — provider abstraction (LiteLLM / Vercel AI SDK).
- **devlog/** — the journey log; raw material for the blog series.
- **papers/** — downloaded PDFs.

## The architecture in one paragraph

Every serious harness converges on the same layers: a **core engine** (an agent loop —
`step(state) → action` — over a typed **event stream** that is the single source of truth),
a **provider layer** (pluggable LLMs), a **tools/extensions layer** (typed tools + MCP), an
**execution layer** (sandboxing, deferred for us), and a **frontend layer** (UIs over a wire
protocol). Cross-cutting: **security/governance** (permissions, prompt-injection defense,
secrets, supply-chain) and **observability**. Agent Saddlery copies OpenHands' event-sourced
core, Goose's MCP-as-extension model, Claude Code's permission model, and adopts AG-UI as the
frontend contract.

## Reference designs at a glance

| Harness | Language | What we take from it |
|---|---|---|
| **OpenHands** + new SDK | Python | Event-sourced core, `step()` agent abstraction, typed tools + MCP, local↔remote portability. The blueprint. |
| **CrewAI** | Python | Crews + Flows (workflow layer); AMP governance checklist (PII, RBAC, audit, SSO). |
| **Block Goose** | Rust | Extensions *are* MCP servers; core decoupled from extension layer. |
| **Claude Code** | — | Permission model (hooks → deny → allow → ask) and hooks as policy seam. |

## Key references

- OpenHands SDK paper — https://arxiv.org/abs/2511.03690 · original — https://arxiv.org/abs/2407.16741 · runtime docs — https://docs.openhands.dev/openhands/usage/architecture/runtime
- CrewAI — https://docs.crewai.com/en/introduction · repo — https://github.com/crewAIInc/crewAI
- Goose extensions — https://deepwiki.com/block/goose/5.3-extension-types-and-configuration
- MCP — https://modelcontextprotocol.io · auth — https://auth0.com/blog/mcp-specs-update-all-about-auth/
- AG-UI — https://docs.ag-ui.com/introduction · 17 events — https://www.copilotkit.ai/blog/master-the-17-ag-ui-event-types-for-building-agents-the-right-way · repo — https://github.com/ag-ui-protocol/ag-ui
- ACP — https://agentclientprotocol.com/get-started/introduction · https://zed.dev/acp · repo — https://github.com/agentclientprotocol/agent-client-protocol
- LiteLLM — https://github.com/BerriAI/litellm
- Sandboxing — https://github.com/restyler/awesome-sandbox · Daytona vs E2B — https://northflank.com/blog/daytona-vs-e2b-ai-code-execution-sandboxes
- Prompt injection — https://simonwillison.net/2025/Jun/13/prompt-injection-design-patterns/ · CaMeL — https://arxiv.org/abs/2601.09923
- Claude Code permissions — https://code.claude.com/docs/en/agent-sdk/permissions

# Feature Catalog

Every feature surfaced by the survey, grouped by layer. Tags are the suggested phasing:
`[MVP]` Phase 0, `[v1]` Phases 1–2, `[multi-user]` Phase 3, `[deferred]`/`[stretch]` later.
Rank/cut against the first use cases: **resume writing**, **vacation research**, **running small
programs** — and the confirmed destination of a **multi-user server**.

## A. Core engine
- `[MVP]` Agent loop as `step(state) → action` abstraction (OpenHands)
- `[MVP]` Typed **event stream** (actions + observations) as the single source of truth
- `[MVP]` **`owner`/`principal` on every session, event, secret, permission decision** (tenancy-ready)
- `[v1]` **Event-sourced state + deterministic replay** (OpenHands SDK) — also gives free replay + audit
- `[MVP]` Session/conversation manager (lifecycle, turns, multi-session)
- `[v1]` Memory/context management (condensation, summarization, injected-context "microagents")
- `[v1]` Immutable agent config

## B. LLM provider layer
- `[MVP]` Pluggable providers via **LiteLLM** + streaming tokens
- `[v1]` Fallback / retry / routing + cost & token tracking
- `[multi-user]` Per-user cost attribution + quotas (LiteLLM supports per-key tracking)
- `[v1]` Normalized tool-calling & structured output across providers

## C. Tools & extensions
- `[MVP]` Typed tool system
- `[MVP]` **MCP client** (tools/resources/prompts; stdio first, streamable-HTTP + OAuth later) — the
  *runtime* extension surface
- `[MVP]` Built-in tools: file read/write, web search, web fetch, **shell (behind permission gate)**
- `[deferred]` browser, Python/IPython (need sandbox)
- **Plugin primitives** (the things a plugin bundles):
  - `[v1]` Skills (instruction/workflow injection), slash commands, agent definitions
  - `[MVP]`/`[v1]` Hooks and MCP servers (already above — also plugin-bundleable)
- `[v1]` **Plugin packaging**: manifest bundling {skills, hooks, MCP servers, agents, commands} +
  install/enable/disable lifecycle + versioning (Claude Code & OpenHands SDK use the *same* model).
  Sits **on top of** the primitives — Phase 4.
- `[stretch]` Plugin **marketplace/distribution** (+ multi-tenant install-trust model)
- `[stretch]` Recipes / reusable workflows

## D. Execution & sandboxing  *(promoted by the multi-user goal — per-user isolation is a tenant boundary)*
- `[MVP]` Runtime-abstraction **seam** (tools call an execution interface) — design in P0, local impl
- `[multi-user]` Per-user/per-session **container isolation** (Docker baseline) — required once >1 user
  shares the server; a host allowlist is *not* a boundary between users
- `[multi-user]` Filesystem + network egress policy per tenant
- `[stretch]` Stronger isolation: gVisor / Firecracker-Kata microVM / managed (E2B, Daytona)

## E. Frontends & protocols
- `[MVP]` Headless core + UI-agnostic callback contract
- `[MVP]` **AG-UI** event protocol as the core wire format
- `[MVP]` **TUI** (Ink) on AG-UI
- `[v1]` **Web UI** (React/CopilotKit on AG-UI) + REST/WebSocket API server
- `[stretch]` Desktop GUI (Tauri); **ACP** IDE integration

## F. Security & governance  *(cross-cutting)*
- `[MVP]` **Permission model**: allow/deny/ask, layered settings, deny-always-wins (Claude Code)
- `[MVP]` **Hooks** (pre/post tool) as the policy-injection seam — also the shell guard
- `[v1]` **Prompt-injection defense**: trusted/quarantined LLM split; untrusted-by-default tool outputs
- `[v1]` **Secrets management** + least privilege (scoped tokens; env/keychain for single-user)
- `[v1]` **MCP supply-chain controls**: server pinning/allowlist, tool-poisoning checks, OAuth 2.1
- `[v1]` **Audit log** / provenance (cheap given event sourcing)

### F-multi. Multi-user server  *(Phase 3 — interdependent bundle, see `multi-user-tenancy.md`)*
- `[multi-user]` **AuthN/AuthZ**: accounts, login (OIDC/OAuth), sessions bound to principal
- `[multi-user]` **Tenancy isolation** in the event store (user sees only their own sessions)
- `[multi-user]` **Per-user secret store** (encrypted at rest, scoped) — replaces env/keychain
- `[multi-user]` **Per-user execution isolation** (see §D) + resource quotas
- `[multi-user]` **RBAC**: admin vs user; model/tool access; who can install plugins
- `[multi-user]` Per-user audit trail; `[stretch]` PII detection/masking (CrewAI AMP), SSO

## G. Orchestration / automation  *(stretch)*
- `[stretch]` Multi-agent crews (role-based delegation)
- `[stretch]` **Flows**: event-driven workflows, explicit state, conditional routing (CrewAI)
- `[stretch]` Human-in-the-loop checkpoints; scheduling / triggers

## H. Observability & ops
- `[v1]` OpenTelemetry tracing (LiteLLM callbacks → Langfuse/OTel)
- `[v1]` Session replay (from event sourcing)
- `[stretch]` Eval harness

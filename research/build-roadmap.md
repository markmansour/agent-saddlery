# Build Roadmap

Phased order. Each phase ends with a devlog retrospective (blog draft).

**Two structural decisions baked in (2026-06-16, session 2):**
- **Tenancy-ready from Phase 0.** Every session, event, secret, and permission decision carries an
  `owner`/`principal` even while there's one local user. Multi-user is a confirmed destination; this
  makes it a reordering, not a rewrite.
- **Sandboxing is promoted by multi-user.** Per-user execution isolation *is* sandboxing, so it moves
  from "deferred" into the multi-user phase (P3). The runtime-abstraction *seam* is designed in at P0.

## Phase 0 — Walking skeleton (single local user, tenancy-ready)
Headless Python core: event stream + `step()` agent loop + an `LLMProvider` seam with a native
`AnthropicProvider` (streaming; the survey's "LiteLLM in core" was superseded — see `llm-providers.md`) +
built-in **file read/write + web search + web fetch + shell** tools. Emit **AG-UI** events. One **TUI**
(Ink) consuming the stream. **Shell behind a permission gate (ask/allowlist), not a sandbox.**
Every domain object carries an `owner`/`principal`. Design the **runtime-abstraction seam** (tools
call an execution interface) even though it runs locally. Goal: prove the protocol boundary end-to-end.

## Phase 1 — Tools, MCP & permissions
Typed tool system + **MCP client** (stdio) — the runtime extension surface. **Permission model**
(allow/deny/ask, layered) + **hooks**. Treat web/file content as untrusted; prompt-injection defense
starts now because shell is live. (MCP + hooks are the first two plugin primitives.)

## Phase 2 — Multi-frontend server
AG-UI server + REST/WebSocket API + Web UI (React/CopilotKit). TUI and Web share one protocol.
Event-sourced replay. Add the remaining **plugin primitives**: skills (instruction/workflow injection),
slash commands, agent definitions. Auth *scaffolding* (sessions bound to a principal) goes in here.

## Phase 3 — Multi-user (server) + execution isolation
The interdependent bundle — do it together:
- **AuthN/AuthZ**: accounts, login (OIDC/OAuth), sessions bound to principal.
- **Tenancy isolation** in the event store (a user sees only their sessions).
- **Per-user secret store** (encrypted at rest, scoped) — replaces env/keychain.
- **Per-user execution isolation** (sandboxing): container-per-user-session (Docker baseline) +
  filesystem/network egress policy. This is the runtime abstraction from P0 made real.
- **RBAC**: admin vs user; who can use which models/tools; who can install plugins.
- **Cost attribution + quotas** per user; **audit log** surfaced from the event store.
- Prompt-injection hardening (trusted/quarantined LLM split for untrusted content).

## Phase 4 — Plugin packaging & distribution
**Plugin manifest** bundling {skills, hooks, MCP servers, agents, commands} + install/enable/disable
lifecycle + versioning (Claude Code / OpenHands SDK model). Local install (path/git) first. Then the
multi-tenant **install-trust model**: shared (admin-installed) vs. per-user plugins, isolation between
tenants' plugins.

## Phase 5 — Stretch
ACP (IDE), CrewAI-style Flows/workflows, multi-agent, desktop GUI, public plugin marketplace,
stronger isolation tiers (gVisor / Firecracker-Kata / managed E2B-Daytona).

---

### Sequencing notes
- **Protocol-first.** AG-UI is wired in P0 so every later frontend is additive.
- **Shell forces security early.** Real code execution from day one → permission gate + prompt-injection
  defense ahead of the full sandbox.
- **Multi-user is a coherent milestone, not scattered features.** Auth, tenancy, per-user secrets,
  sandboxing, and RBAC are interdependent; shipping one without the others leaves a security hole. If
  the shared server is wanted sooner, pull P3 forward — the `principal`-from-P0 decision makes that a
  reorder, not a rewrite. See `multi-user-tenancy.md`.
- **Plugins sit on top of primitives.** Can't bundle skills/hooks/MCP/agents/commands until they exist
  (P1–P2), so the bundle format lands P4.

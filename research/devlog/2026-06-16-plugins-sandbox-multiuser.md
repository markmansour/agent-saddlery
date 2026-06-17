# 2026-06-16 (session 2) — Plugins, sandboxing, and the multi-user pivot

## What we set out to do
Place three things on the roadmap that the survey had under-specified: the **plugin model**, the timing
of **execution/sandboxing**, and the impact of making this a **multi-user server**.

## Decisions & rationale
- **Plugins are packaging, not a rival to MCP.** Read the Claude Code and OpenHands SDK plugin docs —
  both are the same idea: a manifest bundling {skills, hooks, MCP servers, agents, commands} + an
  install/enable/disable lifecycle + versioning + marketplace. MCP is *one thing a plugin contains*.
  So primitives come first (MCP/hooks in P1; skills/commands/agents in P2) and the **bundle format
  lands P4** — you can't bundle primitives that don't exist.
- **Multi-user is a confirmed destination.** This changes the shape from "single-user local tool with a
  server" to "multi-tenant server." The Python-core + AG-UI + TS-frontends split already makes the
  server the boundary, so it's additive — *if* we carry tenancy from day one.
- **The one cheap decision: `owner`/`principal` on every session, event, secret, permission decision
  from Phase 0**, even with one local user. Event-sourcing makes per-owner partitioning natural;
  retrofitting a `user_id` later is brutal.
- **Multi-user promotes sandboxing.** A shared-host shell behind an allowlist is not a boundary between
  users — per-user execution isolation *is* sandboxing. So it moves from "deferred Phase 4" into the
  **Phase 3 multi-user bundle**; the runtime-abstraction *seam* is designed in at P0.

## Dead-ends / tensions
- Wanted plugins to be a single roadmap item, but they decompose into "primitives" (spread across
  P1–P2) and "packaging" (P4). Forcing them into one phase would have either delayed MCP or shipped an
  empty bundle format.
- Tempted to keep sandboxing deferred to stay lean — but multi-user makes "shell on the host behind an
  allowlist" a cross-tenant data-leak, not a guard. Resolved by coupling sandboxing to the multi-user
  phase rather than treating it as independent.

## What we learned
- Multi-user isn't a feature, it's a **milestone of interdependent features** (auth + tenancy isolation
  + per-user secrets + sandboxing + RBAC). Shipping a subset leaves a security hole.
- The earlier architecture choices (event sourcing, headless server, AG-UI) all pay off here: the event
  log doubles as the per-user audit trail, and the server is already the tenant boundary.

## Open threads
- **Timing of multi-user:** build it at Phase 3 (recommended) or pull forward to stand up a shared
  server sooner? `principal`-from-P0 makes this a reorder, not a rewrite.
- Auth choice for Phase 3 (OIDC provider vs. self-hosted accounts).
- Per-user secret store: OS keychain doesn't fit multi-user — pick an encrypted-at-rest store (e.g.
  libsodium-sealed rows, or a real secrets manager) early enough that P0's env-based approach isn't load-bearing.
- Plugin install-trust model in multi-tenant: shared (admin) vs per-user, and isolation between them.

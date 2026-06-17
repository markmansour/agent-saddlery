# Multi-user / tenancy design

**Confirmed destination:** Agent Saddlery runs as a **server** where several people each have their own
sessions, secrets, and experience. This note records how that reshapes the design and why several
"deferred" items get promoted.

## The shape change
Single-user-local → **multi-tenant server**. The headless-Python-core + AG-UI + TS-frontends split
already makes the server the boundary, so the architecture is right; multi-user *adds layers* rather
than forcing a rewrite — **if** we carry tenancy from the start.

## The one cheap decision (do it in Phase 0)
**Every session, event, secret, and permission decision carries an `owner`/`principal`** — even while
there is exactly one local user. Event-sourcing makes per-owner partitioning natural. Retrofitting a
`user_id` across an event store and a permission engine later is brutal; threading it from day one is
nearly free.

## What multi-user adds, by layer

| Layer | Single-user today | Multi-user (Phase 3) |
|---|---|---|
| Identity | none | **AuthN/AuthZ** — accounts, login (OIDC/OAuth), sessions bound to a principal |
| Sessions | one event log | **Tenancy isolation** — user sees only their own sessions; store partitioned by owner |
| Secrets | env / OS keychain | **Per-user secret store**, encrypted at rest, scoped per user |
| Execution | host shell + allowlist | **Per-user container isolation** (sandboxing) |
| Permissions | user + project | + **server/admin layer**; **RBAC** (admin, model/tool access, plugin install) |
| Cost/quotas | n/a | Per-user **cost attribution** (LiteLLM per-key), rate limits, concurrency caps |
| Audit | nice-to-have | **Per-user audit trail** (event log already provides this) |
| Plugins | you install | **Who can install?** shared (admin) vs per-user; tenant isolation between plugins |

## Why this promotes sandboxing
A shared-host shell behind an allowlist is **not a boundary between users** — user A could read user B's
files and the server's secrets. **Per-user execution isolation *is* sandboxing.** So the runtime
abstraction (designed as a seam in Phase 0) becomes a real container-per-user-session boundary in
Phase 3. Stronger tiers (gVisor / Firecracker-Kata / E2B) remain stretch, layered behind the same seam.

## Why do it as one phase
Auth, tenancy isolation, per-user secrets, sandboxing, and RBAC are **interdependent**. Shipping auth
without execution isolation, or isolation without per-user secrets, leaves a real hole (one tenant
reaching another's data or compute). Phase 3 ships them together.

## Sequencing flexibility
Recommended: build Phases 0–2 single-user but **tenancy-ready**, then Phase 3 = the multi-user bundle.
If the shared server is wanted sooner, pull Phase 3 forward — the `principal`-from-Phase-0 decision makes
that a **reorder, not a rewrite**.

## References
- CrewAI AMP governance checklist (RBAC, secret manager, audit, SSO): see `reference-designs/crewai.md`
- Permission layering (server→user→session mirrors Claude Code's enterprise→user→project): `security/permissions-secrets.md`
- Execution isolation tiers: `security/sandboxing.md`

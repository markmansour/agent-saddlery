# Permissions & secrets

The **authorization** and **least-privilege** layer. Permission model from Claude Code; secrets/RBAC
backlog from CrewAI AMP.

## Permission model (copy Claude Code — see `../reference-designs/claude-code.md`)
- **Evaluation order:** hooks → deny → allow → ask. **Deny always wins**, even in bypass mode.
- **Layered settings:** Enterprise → User → Project (shared) → Project (local). For a single-user tool,
  start with **User + Project**.
- **Permission modes:** read-only (plan), normal (ask), auto-approve (allowlist only).
- **Hooks are the seam** — pre/post tool, can allow/deny/ask/modify-input/append-context. Our shell
  gate and prompt-injection checks both live here.

### Phase 0 concretely
Shell tool: every command hits the **ask gate** unless it matches a **user allowlist** (e.g. `ls`,
`cat`, `git status`). Deny list for obvious danger (`rm -rf`, `curl | sh`). Decision rendered in the
Ink TUI; remembered per-session optionally.

## Secrets & least privilege (CrewAI AMP checklist — mostly `[v1]`)
- **Secret-manager integration** — never bake API keys into config; pull from env / OS keychain / a
  secrets manager. Redact secrets from logs and from the event stream that frontends see.
- **Scoped tokens** — give tools the narrowest credential that works; per-tool, not a god key.
- **Audit log / provenance** — cheap given event sourcing: the event log *is* the audit trail. Record
  who/what/when for every tool call and permission decision.
- **Later (multi-user):** RBAC, SSO, PII detection/masking.

## What Agent Saddlery takes
- **Phase 0:** hooks-based permission gate for shell (ask + allow/deny lists); secrets from env/keychain,
  redacted from logs and AG-UI events.
- **Phase 3:** secret-manager integration, audit log surfaced from the event store, MCP supply-chain
  allowlist.

## Links
- Claude Code permissions: https://code.claude.com/docs/en/agent-sdk/permissions
- Permission hooks: https://www.dyad.sh/blog/claude-code-permission-hooks
- CrewAI AMP (governance checklist): https://docs.crewai.com/en/introduction

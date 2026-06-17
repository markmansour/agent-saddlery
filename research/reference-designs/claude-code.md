# Claude Code

**The permission model to copy.** Not open-source as a whole, but its permission/hooks design is
well-documented and is the cleanest single-user agent authorization model around.

## Permission evaluation order
A tool call is resolved in this fixed order:
1. **Hooks** run first — can allow, deny, or pass through to the next step.
2. **Deny rules** (from `disallowed_tools` / settings). **A deny match blocks the tool even in
   bypass-permissions mode.**
3. **Allow rules** (from `allowed_tools` / settings).
4. **Ask callback** (`can_use_tool`) — if nothing above resolved it, ask the user.

## Layered settings
Four layers, highest precedence first: **Enterprise managed → User → Project (shared, in git) →
Project (local, gitignored).** Lets policy be set centrally and overridden locally.

## Hooks — the policy seam
`PreToolUse` hooks fire after the model produces tool parameters, before the tool runs. They can:
- allow / deny / ask / defer the call,
- **modify the tool input**,
- **append additional context**.

This is the single most reusable idea for us: **hooks are where shell-command guarding, secret
redaction, and prompt-injection checks plug in**, without touching the agent loop.

## Permission modes
- **Plan mode** — read-only.
- **Don't-Ask / auto-deny** — denies everything not pre-approved.

## What Agent Saddlery takes
- The **hooks → deny → allow → ask** evaluation order, with **deny always winning**.
- **Hooks as the policy-injection point** — our shell permission gate (Phase 0) and prompt-injection
  defense (Phase 1) both live here.
- **Layered settings** (for us: user + project, skip enterprise for now).

## Links
- Permissions: https://code.claude.com/docs/en/agent-sdk/permissions
- Architecture writeup: https://www.penligent.ai/hackinglabs/inside-claude-code-the-architecture-behind-tools-memory-hooks-and-mcp/
- Permission hooks pattern: https://www.dyad.sh/blog/claude-code-permission-hooks

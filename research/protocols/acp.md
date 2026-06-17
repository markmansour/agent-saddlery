# ACP — Agent Client Protocol

Our **IDE integration path** (stretch). Created by Zed; an open standard so any agent works in any
editor.

## What it is
A protocol standardizing communication between **code editors** and **agents**. A local agent runs as a
**subprocess of the editor**, communicating via **JSON-RPC over stdio**. Current stable protocol
version is **1**; wire compatibility is negotiated by `protocolVersion` during `initialize`.

## Why it matters
Implement ACP once and the agent gains every ACP client's UI for free — multi-file editing, full
codebase context, diff review, agent-following. Clients/agents in the ecosystem include Zed, Kiro, and
CLIs like Claude Code, Codex, and Copilot. There's now an **ACP registry** (register once, available
everywhere).

## Relationship to our stack
- **ACP ≈ AG-UI, but editor-shaped.** Both connect an agent to a UI; ACP is JSON-RPC/stdio and editor-
  centric (subprocess model), AG-UI is event-stream/HTTP and app-centric.
- For Agent Saddlery, ACP is the **VS Code/Zed surface**. It can sit alongside AG-UI: the core stays
  protocol-agnostic, and an ACP adapter translates to/from our internal event stream.

## What Agent Saddlery takes (later)
- A thin **ACP adapter** over the headless core for IDE integration (Phase 5), reusing the same event
  stream that AG-UI consumes.

## Links
- Intro: https://agentclientprotocol.com/get-started/introduction
- Zed ACP: https://zed.dev/acp · registry: https://zed.dev/blog/acp-registry
- Repo: https://github.com/agentclientprotocol/agent-client-protocol
- Kiro ACP CLI docs: https://kiro.dev/docs/cli/acp/

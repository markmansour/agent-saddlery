# MCP — Model Context Protocol

Our **extension surface**. Tools, data, and prompts reach the agent through MCP, so adding capability
means adding an MCP server (Goose model) rather than editing the core.

## Three first-class context types
- **Tool** — an executable action (the model can call it).
- **Resource** — read-only contextual data.
- **Prompt** — a reusable template.

A server declares any mix of these.

## Transports (same JSON-RPC 2.0 message format on both)
- **stdio** — local subprocess server. Simplest; what Phase 1 uses.
- **streamable-HTTP** — remote server over HTTPS, with **OAuth 2.1 + PKCE**. Per the **2025-06-18**
  spec, servers are **OAuth Resource Servers** and clients must send **Resource Indicators (RFC 8707)**.

Because the message format is identical, tool definitions are portable between local and remote.

## Security — the part that matters for us
MCP's threats aren't signature-based; they target the model's reasoning:
- **Tool poisoning** — a malicious server describes a tool to manipulate the agent.
- **Prompt injection** — via tool descriptions or returned content.
Mitigations are behavioral/contextual: **server allowlist/pinning**, treat tool output as untrusted,
OAuth for remote servers, and review of tool descriptions. (See `../security/prompt-injection.md`.)

## What Agent Saddlery takes
- **MCP client in the core** (Phase 1), stdio first, streamable-HTTP + OAuth later.
- **Built-in tools and third-party tools through the same MCP interface.**
- **Pin the spec version** we target (note Goose's lag as the cautionary tale).
- **Supply-chain controls** (`[v1]`): allowlist of servers, no silent auto-loading of remote tools.

## Links
- Spec: https://modelcontextprotocol.io · authorization: https://modelcontextprotocol.info/specification/draft/basic/authorization/
- June-2025 auth update: https://auth0.com/blog/mcp-specs-update-all-about-auth/
- AuthN/AuthZ overview: https://stackoverflow.blog/2026/01/21/is-that-allowed-authentication-and-authorization-in-model-context-protocol/
- Security guide: https://www.sentinelone.com/cybersecurity-101/cybersecurity/mcp-security/

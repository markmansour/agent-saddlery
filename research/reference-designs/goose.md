# Block Goose

**The extensibility model to copy.** Goose (built in Rust) has the cleanest separation between core
runtime and extensions.

## Architecture
Modular: a **core agent loop**, a **provider abstraction layer** for LLMs, and an **extension system
built on MCP**. The core runtime is fully decoupled from the extension layer.

## Extension model — extensions *are* MCP servers
- Every extension (built-in or third-party) implements **MCP**, providing **tools, prompts, and
  resources** to the agent.
- Each built-in extension is a struct implementing the MCP methods async: `list_tools`, `call_tool`,
  `list_prompts`, `get_prompt`, `list_resources`, `read_resource`.
- Extension types differ in **initialization, transport, and lifecycle**.
- Templates exist in Python, TypeScript, and Rust. A minimal Python MCP server exposing one tool is
  ~40 lines.
- The payoff: the MCP server registry crossed 3,000+ entries (early 2026), and **every new server
  becomes available to Goose with zero changes to Goose itself.**

## What Agent Saddlery takes
- **Extensions = MCP servers.** Don't invent a bespoke plugin API; make the MCP client the extension
  surface. Built-in tools and third-party tools go through the same interface.
- **Core decoupled from extensions** — the agent loop never imports a specific tool; it talks MCP.

## Caveat
Goose has historically lagged MCP spec versions (was on the March spec, not the June 2025 update at
time of survey). Lesson: pin and track the MCP spec version you target.

## Links
- Extension types: https://deepwiki.com/block/goose/5.3-extension-types-and-configuration
- Creating extensions: https://www.mintlify.com/block/goose/guides/creating-extensions
- Repo: https://github.com/block/goose

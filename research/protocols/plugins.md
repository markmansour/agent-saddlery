# Plugins — packaging & distribution

**A plugin is a packaging layer, not an alternative to MCP.** Claude Code and the OpenHands SDK use the
*same* model: a manifest that **bundles** multiple extension types plus an install/lifecycle/distribution
story.

## What a plugin bundles
| Component | What it is | In our stack |
|---|---|---|
| **MCP servers** (`.mcp.json`) | external tool/resource/prompt servers | runtime extension surface (Phase 1) |
| **Hooks** (`hooks.json`) | pre/post tool-lifecycle event handlers | policy seam (Phase 1) |
| **Skills** (`SKILL.md` + frontmatter) | model-invoked instructions/workflows | plugin primitive (Phase 2) |
| **Agents** | specialized agent/subagent definitions | plugin primitive (Phase 2 / multi-agent stretch) |
| **Commands** | slash commands for the user | plugin primitive (Phase 2) |
| (CC extras) | LSP servers, background monitors, `bin/`, default settings | optional later |

Manifest: `.claude-plugin/plugin.json` (CC) / `.plugin/plugin.json` (OpenHands) — name, description,
version, author.

## Lifecycle & distribution
- **Load** from local path, git repo, or URL/zip.
- **Install → enable/disable independently** without reinstall; metadata tracked (`.installed.json`).
- **Versioning**: explicit `version`, else git commit SHA.
- **Marketplace**: curated + community catalogs; install by namespace (`/plugin-name:skill`).
  Namespacing prevents skill-name collisions across plugins.

## The key relationship
**MCP/hooks/skills/commands/agents are the *primitives*. A plugin is a bundle of primitives + a
lifecycle.** You cannot bundle what doesn't exist, so the plugin format lands *after* the primitives.

## Where it fits in Agent Saddlery
- **Phase 1–2:** build the primitives (MCP, hooks, then skills, commands, agent defs).
- **Phase 4:** the **plugin bundle format** + install/enable/disable lifecycle + versioning. Local
  install first.
- **Stretch:** marketplace/distribution.
- **Multi-user crossover:** in a multi-tenant server, plugin install needs a **trust model** — shared
  (admin-installed) vs per-user, with isolation so one tenant's plugin can't affect another. See
  `../multi-user-tenancy.md`.

## Links
- Claude Code plugins: https://code.claude.com/docs/en/plugins
- OpenHands SDK plugins: https://docs.openhands.dev/sdk/guides/plugins

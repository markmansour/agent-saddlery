# AG-UI — Agent–User Interaction Protocol

**Our core frontend↔core wire format.** Chosen so TUI, Web, desktop, and IDE all consume the same
event stream and later surfaces are additive.

## What it is
An open, lightweight, **event-based** protocol standardizing real-time communication between an agent
backend and user-facing apps. Transport: **WebSocket, SSE, or HTTP**. The client makes a single POST
to the agent endpoint, then listens to a **unified event stream**.

## The event model (~17 types)
Each event has a `type` and a minimal payload. Categories:
- **Messages** — e.g. `TEXT_MESSAGE_CONTENT` (token streaming).
- **Tool calls** — e.g. `TOOL_CALL_START` (and progress/end).
- **State** — e.g. `STATE_DELTA` (incremental state sync to the UI).
- **Lifecycle** — run start/finish signals.

The UI stays in sync with the agent: streaming tokens as generated, showing tool-execution progress,
reflecting live state changes.

## Ecosystem
CopilotKit is built entirely on AG-UI (everything flows through AG-UI events over SSE). Microsoft Agent
Framework integrates with it. This gives us a ready React frontend path for Phase 2.

## What Agent Saddlery takes
- **AG-UI as the boundary between the Python core and every frontend.** Our event stream (internal,
  event-sourced) maps onto AG-UI events on the wire.
- **Phase 0 subset is enough:** text content + tool-call start/end + state delta + run lifecycle. We
  don't need all 17 events to ship the TUI.
- **CopilotKit/React for the Web UI** (Phase 2) — don't hand-roll the frontend protocol plumbing.

## Design note
There are two protocols in play and they're complementary, not competing:
**MCP = agent↔tools/data**; **AG-UI = agent↔user/UI**; **ACP = editor↔agent** (see `acp.md`).

## Links
- Docs: https://docs.ag-ui.com/introduction
- 17 event types: https://www.copilotkit.ai/blog/master-the-17-ag-ui-event-types-for-building-agents-the-right-way
- Intro: https://www.copilotkit.ai/blog/introducing-ag-ui-the-protocol-where-agents-meet-users
- Repo: https://github.com/ag-ui-protocol/ag-ui
- Microsoft integration: https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/

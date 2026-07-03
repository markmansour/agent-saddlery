# Agent Saddlery TUI

Ink-based terminal user interface for Agent Saddlery. Communicates with the Python core via stdin/stdout JSON protocol.

## Setup

```bash
npm install
```

## Development

```bash
npm run dev
```

The TUI will spawn the Python core as a subprocess and pipe messages via JSON.

## Build

```bash
npm run build
npm start
```

## Protocol

**Inbound (TUI → Core):**
```json
{"type": "user_message", "content": "hello"}
```

**Outbound (Core → TUI):**
AG-UI events + logging events as JSON lines.

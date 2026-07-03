# TUI Design — Agent Saddlery Phase 0.3

**Status:** Design (implementation pending)  
**Date:** 2026-07-03  
**Scope:** Ink-based terminal UI for Phase 0.3, consuming AG-UI event stream from Phase 0.2 core.

**Linear issue:** MM-7 (blocked by MM-6 ✅)

## 1. Context & Goal

Phase 0.1 (echo loop) uses `CliSink` (text streaming to stdout). Phase 0.2 (MM-6) defines AG-UI wire protocol. Phase 0.3 (MM-7) builds a proper terminal UI that:
- **Reads** user input (multi-line, editing support)
- **Streams** assistant responses live as tokens arrive
- **Displays** conversation history with formatting
- **Shows** event log / status (optional, via logging)
- **Consumes** AG-UI events (same protocol as future Web/desktop UIs)

The TUI is a frontend in the Phase 0 architecture: headless Python core → AG-UI events → TUI (or Web, or IDE).

## 2. Goals / Non-Goals

**Goals**
- A usable chat interface for testing the core
- Consume AG-UI events (prepare for multi-frontend Phase 2)
- Live token streaming (responsive UX)
- Multi-line user input with editing
- Display conversation history
- Show errors and lifecycle markers (session start/finish, run start/finish)

**Non-Goals**
- Rich formatting (colors, tables, panels) — plain text is fine for Phase 0
- Mouse support
- Window resizing / responsive layout
- Persistence (history saved to disk)
- Configuration (fonts, colors, keybindings)

## 3. Technology Choice: Ink

**Why Ink (React for the terminal)?**
- React model fits chat UI naturally (state → render)
- Component-driven (reusable Message, Input, Status components)
- Handles input/output elegantly
- Used by Vercel CLI, GitHub CLI, others in production

**Alternative: Textual (Python TUI framework)**
- More Python-idiomatic, but less familiar to you
- Fine, but Ink is a better learning vehicle for multi-frontend architecture

**Not considered:** Plain curses (too low-level for this scope).

## 4. Architecture

```
┌─────────────────────────────────────┐
│  TUI (TypeScript + Ink)             │
│  - Input box                        │
│  - Message history                  │
│  - Status line                      │
└──────────────────┬──────────────────┘
                   │
                   │ stdin/stdout
                   │
┌──────────────────▼──────────────────┐
│  Python Core (saddlery)             │
│  - Session + Agent                  │
│  - AG-UI event stream               │
└─────────────────────────────────────┘
```

**Communication:**
- **Inbound:** TUI sends user messages via stdin (JSON or simple protocol)
- **Outbound:** Core sends AG-UI events via stdout (JSON, line-delimited)

## 5. Event Flow

```
User types "hello" in TUI
  ↓
TUI sends: {"type": "user_message", "content": "hello"}
  ↓
Core receives, processes via Agent
  ↓
Core emits: {"type": "event_emitted", "event_type": "run_started", ...}
Core emits: {"type": "event_emitted", "event_type": "assistant_message_delta", "text": "Hello"}
...
  ↓
TUI receives AG-UI events via stdout
  ↓
TUI renders: "Assistant: Hello [stream in progress]"
TUI renders: "Assistant: Hello world" [when RUN_FINISH arrives]
```

## 6. TUI Components (Ink React)

```typescript
// Main app
<ChatApp>
  <MessageHistory messages={messages} />
  <InputBox onSubmit={handleUserMessage} />
  <StatusLine status={status} />
</ChatApp>

// Components
<MessageHistory>
  {messages.map(m => (
    <Message key={m.id} role={m.role} content={m.content} />
  ))}
</MessageHistory>

<InputBox onSubmit={handler}>
  Multiline editor, readline support
</InputBox>

<StatusLine>
  Session ID, event count, or error message
</StatusLine>
```

## 7. Python ↔ TUI Protocol

### Inbound (TUI → Core)

```json
{"type": "user_message", "content": "hello world"}
```

**Transport:** stdin, one JSON object per line.

### Outbound (Core → TUI)

Already defined by AG-UI + internal event logging:

```json
{"level": "info", "event": "session_started", "session_id": "...", "principal": "local"}
{"level": "info", "event": "event_emitted", "event_type": "run_started", "event_data": {...}}
{"level": "debug", "event": "event_emitted", "event_type": "assistant_message_delta", "event_data": {"text": "Hello"}}
{"level": "info", "event": "event_emitted", "event_type": "run_finished", "event_data": {...}}
```

**Transport:** stdout, one JSON object per line.

## 8. Implementation Plan

### Phase 0.3a (Core changes)
- [ ] Add `InkSink` (or similar) that accepts user messages from stdin and emits AG-UI events to stdout
- [ ] Wire up in CLI or via subprocess bridge
- [ ] Tests: verify stdin input → AG-UI output mapping

### Phase 0.3b (TUI)
- [ ] `frontend/tui/` directory with TypeScript + Ink
- [ ] Read stdout from core, parse JSON events
- [ ] Render components (MessageHistory, InputBox, StatusLine)
- [ ] Handle user input → send to core via stdin
- [ ] Tests: React component snapshots, integration with mock core

### Phase 0.3c (Polish)
- [ ] Error handling (core crash, stream interruption)
- [ ] Keyboard shortcuts (Ctrl-D to exit, etc.)
- [ ] README with setup/run instructions
- [ ] Demo video or screenshot

## 9. Open Design Questions

1. **Single process or subprocess?**
   - Option A: TUI spawns core as subprocess (clean separation, easier testing)
   - Option B: TUI and core in same process (simpler, but tighter coupling)
   - **Recommendation:** Option A (subprocess). Prepares for Phase 2 (TUI + Web UI both talk to same server).

2. **Error display in TUI?**
   - Option A: Show error banner in chat (inline with messages)
   - Option B: Separate error log section
   - **Recommendation:** Option A (simpler). Parse `ERROR` events and show as assistant message.

3. **Conversation history UI?**
   - Scroll up to see old messages, or just current page?
   - **Recommendation:** Scroll support (full history in memory is fine for Phase 0).

4. **Logging visibility in TUI?**
   - Show structured logs (event_emitted, etc.) in a sidebar or separate view?
   - **Recommendation:** No. Keep TUI focused on chat. Run `SADDLERY_LOG_FORMAT=json python demo_with_logging.py | jq` in another terminal if debugging.

## 10. Success Criteria (done-check)

- [ ] TUI starts and connects to core
- [ ] User types message, core processes it, TUI displays response live
- [ ] Tokens stream in as they arrive (deltas visible)
- [ ] Multiple turns work (history persists in memory)
- [ ] Errors are shown gracefully
- [ ] `Ctrl-D` exits cleanly

## 11. Testing Strategy

**Unit (Ink components):**
- Snapshot tests for Message, InputBox, StatusLine
- Mock event stream, verify render output

**Integration:**
- Spawn core subprocess
- Send user message via stdin
- Verify AG-UI events on stdout
- Render in TUI, verify display

**Manual:**
- Run TUI, chat with agent, observe UX

## 12. Rollout Considerations

- **Dependency:** Ink requires Node.js + npm. Separate from Python env (good — clear separation).
- **Distribution:** Include `frontend/tui/package.json` and build instructions in README.
- **Backwards compat:** Phase 0.1 CLI (`uv run saddlery`) stays as-is. TUI is opt-in (`npm run tui` or similar).

## 13. Future (Phase 0.4+)

- **Web UI** (React, same AG-UI protocol) — will reuse event translation logic
- **Tool display** — when Phase 0.4 adds `TOOL_CALL_START` events, TUI shows tool calls
- **Conversation export** — save to JSON/Markdown
- **Theming** — colors, fonts, layout

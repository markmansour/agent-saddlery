# Agent Saddlery TUI

Ink-based terminal user interface for Agent Saddlery (Phase 0.3). Communicates with the Python core via stdin/stdout JSON protocol.

## Architecture

```
┌─────────────────────────────────────┐
│  TUI (React + Ink)                  │
│  - Message history                  │
│  - Input box (keypress handling)    │
│  - Status line (session, status)    │
└──────────────────┬──────────────────┘
                   │ stdin/stdout JSON
                   │
┌──────────────────▼──────────────────┐
│  Python Core (saddlery)             │
│  - Agent + LLM streaming            │
│  - AG-UI event stream               │
│  - JSON input reader                │
└─────────────────────────────────────┘
```

## Setup

```bash
npm install
```

## Development

Run the TUI with real core subprocess:

```bash
npm run dev
```

The TUI will:
1. Spawn Python core as subprocess (with `--json-input` and `SADDLERY_LOG_FORMAT=json`)
2. Extract session ID from first event
3. Display "Ready" in status line
4. Accept user input

## Testing

### Manual Integration Test

1. Build and run:
   ```bash
   npm run dev
   ```

2. When TUI starts and shows "Ready":
   - Type a message: `hello`
   - Press Enter
   - Watch tokens stream in real-time
   - Press Enter again for next turn

3. Verify:
   - ✅ User message appears in history
   - ✅ Tokens stream as deltas (interactive typing effect)
   - ✅ Status shows "Processing..." during run
   - ✅ Status returns to "Ready" when done
   - ✅ Multiple turns work (message history persists)

### Debugging

View core logs separately:

```bash
# Terminal 1: TUI
npm run dev

# Terminal 2: Watch core events (in backend/)
SADDLERY_LOG_FORMAT=json uv run python -m saddlery.cli.main --json-input | jq '.event_type'
```

Or run the Python demo directly:

```bash
cd ../../backend
uv run python demo_with_logging.py
```

## Build

```bash
npm run build
npm start
```

## Protocol

### TUI → Core (stdin, JSON)
```json
{"type": "user_message", "content": "hello world"}
```

### Core → TUI (stdout, JSON lines)
Core emits structured logging events with AG-UI semantics:
```json
{"event": "session_started", "session_id": "abc123", "principal": "local"}
{"event": "event_emitted", "event_type": "run_started", "event_data": {...}}
{"event": "event_emitted", "event_type": "assistant_message_delta", "event_data": {"text": "Hello"}}
{"event": "event_emitted", "event_type": "run_finished", "event_data": {...}}
```

## Keyboard Controls

- **Enter**: Submit message
- **Backspace**: Delete character
- **Escape**: Clear input
- **Ctrl-C**: Exit

## Components

- **ChatApp**: Manages state, subprocess lifecycle, event handling
- **MessageHistory**: Renders user and assistant messages
- **InputBox**: Handles keypress input, multiline support planned
- **StatusLine**: Shows session ID and status (Ready, Processing, Error, etc.)
- **CoreSubprocess**: Manages Python subprocess, JSON IPC, event parsing

## Future Work

- Multi-line input support
- Message formatting (bold, colors)
- Scroll support (full history)
- Save/export conversation
- Error recovery
- Configuration (model selection)

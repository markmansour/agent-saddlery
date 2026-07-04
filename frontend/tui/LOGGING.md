# TUI & Core Logging

## The Architecture

```
Terminal
  ↓
TUI (TypeScript/Ink)
  ├─ Displays user messages, responses, status
  └─ Spawns core subprocess
      ↓
      Core (Python)
      ├─ Reads user messages from stdin (from TUI)
      ├─ Processes via LLM
      └─ Writes events to stdout (to TUI)
```

**Key point:** Core is a subprocess of TUI. Its stdout is **piped to TUI**, not your terminal.

## Where to Find Logs

### 1. TUI Output (What You See)

```bash
cd frontend/tui
npm run dev
```

You see in the terminal:
- User messages you type
- Assistant responses (streaming)
- Status ("Ready", "Processing...", errors)

This is the **only output** when running normally.

### 2. Core Logs (Hidden in Subprocess)

To see core logs, you have two options:

#### Option A: Capture Subprocess Output (Recommended)

Modify `src/core/subprocess.ts` to log what the subprocess outputs:

```typescript
proc.stderr?.on("data", (data) => {
  console.error("[core stderr]", data.toString());
});

readline.on("line", (eventLine: string) => {
  console.log("[core event]", eventLine);  // ← Add this
  try {
    const event = JSON.parse(eventLine) as CoreEvent;
    this.handleEvent(event);
  } catch {
    // Ignore parse errors
  }
});
```

Then run:
```bash
npm run dev 2>&1 | tee tui.log
```

Now both TUI and core logs appear in terminal (and saved to `tui.log`).

#### Option B: Run Core Standalone (Breaks TUI Connection)

If you want to test the core without the TUI:

```bash
cd backend
SADDLERY_LOG_FORMAT=json PYTHONUNBUFFERED=1 uv run python -m saddlery.cli.main --json-input
```

Then send test messages:
```bash
echo '{"type": "user_message", "content": "hello"}' | nc localhost 5000
```

**But this won't work with TUI** — they're separate processes.

## Log Formats

### TUI Logs (TypeScript console)
```
[No messages yet. Start typing to begin.]
> hello
[session_id] Ready
```

### Core Logs (Python structlog)

**Dev format** (human-readable):
```
2026-07-04T00:30:42.456869Z [info     ] session_started   session_id=ef5b195c principal=local
```

**JSON format** (machine-readable):
```json
{"session_id": "ef5b195c", "principal": "local", "event": "session_started", "level": "info"}
```

## Debugging Workflows

### Problem: No response from TUI

1. **Check TUI is running:**
   ```bash
   npm run dev
   ```
   Should see "Ready" in status line.

2. **Type a message and watch:**
   - Does status change to "Processing..."?
   - Does a response appear?
   - Are there any error messages?

3. **Add debug logging to subprocess:**
   Edit `src/core/subprocess.ts` and add console.log to see raw events:
   ```typescript
   readline.on("line", (eventLine: string) => {
     console.log("[DEBUG] Raw event:", eventLine);  // ← Add this
     // ... rest of code
   });
   ```

4. **Recompile and test:**
   ```bash
   npm run build
   npm run dev
   ```

### Problem: Response is incomplete or wrong

1. **Add message state debugging:**
   Edit `src/components/ChatApp.tsx`:
   ```typescript
   core.on("assistant_delta", (text: string) => {
     console.log("[DEBUG] Delta received:", JSON.stringify(text));
     // ... rest of handler
   });
   ```

2. **Check state updates:**
   ```typescript
   setMessages((prev) => {
     const msg = prev[prev.length - 1];
     console.log("[DEBUG] Updating message:", msg?.id, "with text:", text);
     return /* ... */;
   });
   ```

3. **Rebuild and test:**
   ```bash
   npm run build
   npm run dev
   ```

### Problem: Subprocess won't start

Check core can run standalone:
```bash
cd backend
SADDLERY_LOG_FORMAT=json uv run python -m saddlery.cli.main --json-input < /dev/null
```

Should output session_started event. If not:
- Check Python environment: `uv sync`
- Check mock provider works: `uv run pytest tests/test_mm6_demo.py`
- Check CLI is importable: `uv run python -m saddlery.cli.main --help`

## Best Debugging Setup

### To see everything:

**Terminal 1:**
```bash
cd frontend/tui
npm run build
npm run dev 2>&1 | tee debug.log
```

Then type messages. Both TUI and (with the debug logging added) core events will appear.

**Terminal 2 (optional):**
```bash
tail -f frontend/tui/debug.log | grep "DEBUG"
```

Or to watch only for errors:
```bash
tail -f frontend/tui/debug.log | grep -E "error|Error|ERROR"
```

## Summary

- **TUI and core are connected via subprocess** — not separate systems
- **Core output is hidden** unless you add logging to `src/core/subprocess.ts`
- **To debug:** Add `console.log()` statements to subprocess event handler
- **To test core alone:** Run it separately with `uv run python -m saddlery.cli.main`
- **To see everything:** Rebuild TUI after adding debug logs, then pipe output to file

The key insight: They're not truly separate backends/frontends in the logging sense — the TUI **owns** the core subprocess and controls its lifecycle.

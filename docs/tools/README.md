# Tools

Tools are the agent's way of acting outside the LLM turn — reading a file, calling an API,
running a command. The seam is defined in
[`backend/saddlery/tools/base.py`](../../backend/saddlery/tools/base.py) and deliberately mirrors
[MCP](https://modelcontextprotocol.io)'s tool shape, so a Phase 1 MCP client can implement the
same `Tool` protocol without changing the agent loop.

## The `Tool` protocol

```python
class Tool(Protocol):
    name: str
    description: str
    input_schema: dict  # JSON Schema — MCP's inputSchema, snake_case on our side

    async def call(self, arguments: dict) -> ToolExecutionResult: ...
```

`ToolExecutionResult` is `{content: str, is_error: bool}`. **`call()` never raises** — any
failure (bad arguments, missing file, permission error) is caught internally and returned as
`ToolExecutionResult(content=..., is_error=True)`. The agent loop treats "unknown tool name" the
same way, so a failure in tool lookup or tool execution always shows up as data (a `ToolResult`
event), never as an unhandled exception.

## `ToolRegistry`

[`backend/saddlery/tools/registry.py`](../../backend/saddlery/tools/registry.py) holds tools by
name for lookup (`.get(name)`) and exports Anthropic-shaped specs (`.specs()` →
`{name, description, input_schema}`) for the `tools=[...]` API parameter.

## Available tools

### `read_file`

[`backend/saddlery/tools/read_file.py`](../../backend/saddlery/tools/read_file.py) —
`FileReadTool`. Reads a UTF-8 text file and returns its contents.

**Schema:**
```json
{
  "type": "object",
  "properties": {
    "path": {"type": "string", "description": "The path to the file to read, relative to the root."}
  },
  "required": ["path"]
}
```

**Safety constraints:**
- Constructed with a `root: Path` (defaults to `Path.cwd()`). All reads are resolved relative to
  this root.
- Path traversal is rejected: the resolved path must be `relative_to()` the resolved root, so
  `../../etc/passwd` or an absolute path outside root returns an error result, not a read.
- Directories are rejected (`is_dir()` check) rather than raising `IsADirectoryError`.
- Non-UTF-8 files return an error result (`UnicodeDecodeError` is caught, not propagated).

**Error results** (all `is_error=True`, never raised):
| Condition | Message |
|---|---|
| Missing `path` argument | `Missing required argument: path` |
| `path` not a string | `path must be a string, got <type>` |
| Path escapes root | `Path <path> escapes root directory.` |
| Path is a directory | `Path <path> is a directory, not a file.` |
| File not found | `File not found: <path>` |
| Permission denied | `Permission denied: <path>` |
| Not valid UTF-8 | `Failed to decode file as UTF-8: <error>` |

### `write_file`

[`backend/saddlery/tools/write_file.py`](../../backend/saddlery/tools/write_file.py) —
`FileWriteTool`. Writes text content to a file (UTF-8), creating or overwriting it.

**Schema:**
```json
{
  "type": "object",
  "properties": {
    "path": {"type": "string", "description": "The path to the file to write, relative to the root."},
    "content": {"type": "string", "description": "The text content to write to the file."}
  },
  "required": ["path", "content"]
}
```

**Safety constraints:**
- Constructed with a `root: Path` (defaults to `Path.cwd()`). All writes are resolved relative to
  this root.
- Path traversal is rejected: the resolved path must be `relative_to()` the resolved root, so
  `../../etc/passwd` or an absolute path outside root returns an error result, not a write.
- Directories are rejected (`is_dir()` check) rather than raising `IsADirectoryError`.
- Parent directories must exist — writes to nonexistent parent paths return an error.

**Error results** (all `is_error=True`, never raised):
| Condition | Message |
|---|---|
| Missing `path` argument | `Missing required argument: path` |
| Missing `content` argument | `Missing required argument: content` |
| `path` not a string | `path must be a string, got <type>` |
| `content` not a string | `content must be a string, got <type>` |
| Path escapes root | `Path <path> escapes root directory.` |
| Path is a directory | `Path <path> is a directory, not a file.` |
| Parent directory not found | `Parent directory not found for: <path>` |
| Permission denied | `Permission denied: <path>` |

## Permission gate

The `PermissionGate` (in [`backend/saddlery/permissions/gate.py`](../../backend/saddlery/permissions/gate.py))
guards tool execution with a four-stage decision pipeline:

**Evaluation order:** remembered decisions → hooks → deny list → allow list → ask

1. **Remembered decisions** — if the agent has already decided to allow or deny this tool for this
   principal in this session, reuse that decision (no re-prompting).
2. **Hooks** — run registered hook functions (none by default; a hook can pass, allow, deny, or ask).
3. **Deny list** — if the tool name matches an entry in `.saddlery/permissions.json`'s `"deny"` array,
   the tool is blocked.
4. **Allow list** — if the tool name matches an entry in `.saddlery/permissions.json`'s `"allow"` array,
   the tool is allowed.
5. **Ask** — if none of the above resolved the decision, emit a `PermissionRequest` event and suspend
   `Agent.run()` awaiting `resolve_permission(tool_call_id, decision)` from the TUI.

**Configuration (``.saddlery/permissions.json`):**

```json
{
  "allow": ["read_file"],
  "deny": []
}
```

All fields are optional; omitted fields default to empty arrays. Tools not listed fall through to
the ask stage, which is the safe default.

**In the TUI:** When a tool call is pending permission (`PermissionRequest` event), the user is
prompted to allow or deny it. The decision is sent back via `resolve_permission()`, then cached
via `PermissionGate.remember()` so the same principal is not re-prompted for the same tool in
this session.

**Events:**
- `PermissionRequest` — emitted when the ask stage is reached. Fields: `tool_call_id`, `tool_name`,
  `arguments`, `principal`.
- `PermissionDecision` — emitted after the user (or a hook) resolves the pending request.
  Fields: `tool_call_id`, `decision` ("allow" or "deny").

See [`docs/diagrams/permission-gate-sequence.md`](../diagrams/permission-gate-sequence.md) for the
full ask round-trip sequence.

## Adding a tool

1. Implement the `Tool` protocol (see `read_file.py` as a template): validate arguments
   defensively, catch all expected failure modes, and never let `call()` raise.
2. Register it in `ToolRegistry([...])` where the agent is built (currently in `build_agent()`).
3. Add tests covering: the happy path, each documented error condition, and any safety boundary
   (e.g. path traversal) — see `backend/tests/test_read_file.py`.

## Debugging tool calls

When running under the TUI (`frontend/tui`), two log files land in the TUI's working directory:

- **`tui.log`** — the TUI's own trace of the wire protocol, including tool round-trips:
  `[→ tool] read_file({"path": "..."})` when a `ToolCall` event arrives, and
  `[← tool] success: <content preview>` / `[← tool] error: <content preview>` when the matching
  `ToolResult` arrives (see `frontend/tui/src/core/subprocess.ts`).
- **`core.log`** — the core process's stderr, captured verbatim by the TUI. `LoggingSink`
  (`backend/saddlery/transport/cli.py`) logs `ToolCall` and `ToolResult` events here at INFO
  level: `tool_call_id`, `tool_name`, `arguments` for the call; `tool_call_id`, `is_error`,
  `content_preview` (first 100 chars), `source` for the result. Output is JSON by default
  (structlog, configured in `backend/saddlery/logging.py`); set `SADDLERY_LOG_FORMAT=dev` for a
  human-readable form instead.

Both logs show *what* was called and *what* came back (correlate by `tool_call_id` in `core.log`,
or by call order in `tui.log`), but neither currently shows *when* `tool.call()` started/finished
or how long it took — there's no timing instrumentation inside the agent loop's execution path
yet (tracked as a Phase 1 follow-up).

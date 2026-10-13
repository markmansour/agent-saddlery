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
    capability: Capability  # "read" | "write" | "exec" | "network"

    async def call(self, arguments: dict) -> ToolExecutionResult: ...
    def resource(self, arguments: dict) -> tuple[str, ...]: ...  # raises ResourceError
    def detail(self, arguments: dict) -> object | None: ...  # optional structured parse
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

Capability: `read`. Its resource is the path relative to the root. Under the gate, a bad path
(NUL byte, symlink loop, outside the root) returns `Invalid arguments: ...` before `call()` runs.

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
- The target is opened with `O_NOFOLLOW`, so a symlink at the final component is not followed.
- Capability: `write`. Its resource is the path relative to the root. A write approval covers
  that exact path only.

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

The `PermissionGate` ([`backend/saddlery/permissions/gate.py`](../../backend/saddlery/permissions/gate.py))
decides every tool call before it runs. The policy lives in the backend. The TUI renders prompts
and relays the answer. Design: [`docs/specs/2026-10-12-permission-policy-design.md`](../specs/2026-10-12-permission-policy-design.md).

**Evaluation order:** deny → hooks → remembered → allow → class default → ask

1. **Deny.** A static deny rule that matches blocks the call. A hook cannot override it. A shell
   command the classifier marked `rejected` is also denied here.
2. **Hooks.** The first result other than `pass` decides. A result outside
   `{allow, deny, ask, pass}` (including `None`) is treated as `deny`, and `Agent` runs a tool
   only on an explicit `allow`.
3. **Remembered.** An earlier approval or denial of this exact `(principal, tool, resource)`.
   It ranks below deny and hooks, so a past approval never overrides policy.
4. **Allow.** A matching allow rule allows the call, unless the call is tainted and its class is
   not `read`. Then it asks.
5. **Class default.** `read` allows. `write`, `exec` and `network` ask.
6. **Ask.** Emit a `PermissionRequest` and suspend `Agent.run()` until `resolve_permission()`
   delivers the user's answer.

### Capability classes

Every tool declares a `capability`. `ToolRegistry` raises at registration if it is missing or not
one of the four values, so `build_agent()` fails at startup. There is no default class.

| Class | Default | Remembered after approval | Tools |
|---|---|---|---|
| `read` | allow | n/a | `read_file` |
| `write` | ask | yes, per exact resource | `write_file` |
| `exec` | ask | never; every unmatched call asks | shell (MM-10, not built yet) |
| `network` | ask | never | none yet |

### Resources and rules

A tool names what a call acts on with `resource(arguments) -> tuple[str, ...]`. For file tools it
is the path relative to the root, split into parts. The path is resolved (symlinks followed),
rejected if it leaves the root, then each part is NFC-normalized and case-folded. A resource
shown in a prompt is therefore the folded form, for example `docs/a.md` for `Docs/A.md`.

A rule is a tool plus an optional token prefix. Matching folds every token of the rule and the
resource, and compares whole tokens: `["docs"]` matches `docs/a.md` but not `docs-private`.

```json
{
  "allow": [
    "read_file",
    {"tool": "write_file", "match": ["docs"]},
    {"tool": "shell", "match": ["git", "status"]}
  ],
  "deny": [
    {"tool": "write_file", "match": [".saddlery"]},
    {"tool": "shell", "match": ["rm", "-rf"]}
  ]
}
```

- A bare tool name covers the whole tool.
- `{"tool", "match", "unsafe_broad_allow"}` is the object form. `match` is a non-empty list of
  non-empty strings. On `read_file` and `write_file`, tokens may not contain `/` or be `.` or `..`.
- Remembered approvals use exact tuple equality, not prefix. Approving a write to `a.txt` does not
  approve `b.txt`.

### Configuration: `<root>/.saddlery/permissions.json`

`<root>` is `SADDLERY_ROOT` if set, otherwise the current directory. The TUI runs the core from
`backend/`, so it sets `SADDLERY_ROOT` to the directory where you launched it. An explicit
`SADDLERY_ROOT` wins. The file tools are confined to the same root.

Loading is strict. A missing file means no rules. Anything else wrong stops startup with
`permissions config error: ...` on stderr and exit code 2:

- invalid JSON, or a top level that is not an object
- unknown top-level keys (only `allow` and `deny`) or unknown keys in a rule
- a duplicate JSON key (it would silently drop rules)
- a rule that names an unregistered tool (`known_tools` is the registry's tool names)
- an invalid `match`
- a single-token `shell` allow rule for a broad executor (`bash`, `sh`, `zsh`, `python`,
  `python3`, `node`, `ruby`, `perl`, `env`, `xargs`, `find`, `sudo`, `awk`, `make`, `npm`) without
  `"unsafe_broad_allow": true`. The comparison case-folds the token. With the flag the rule loads
  and logs a warning.

Because the shell tool does not exist yet (MM-10), any rule naming `shell` currently fails
startup as an unknown tool.

### Shell commands

The classifier ([`permissions/shell.py`](../../backend/saddlery/permissions/shell.py)) returns an
immutable `ShellCommand(raw, argv, kind)`. A command is `simple` only if it is one program with
literal arguments. Operators (`; & | < > ( )`), backticks, `$`, backslash, newlines, globs, `~`,
`{`, a leading `NAME=value` and unparseable quoting make it `rejected`. The gate denies a
`rejected` command before hooks, with the result "Compound commands are not supported. Run each
command separately." There is no approve-once path. Deny rules also match the commands inside a
`bash -c "..."` string, as a best-effort tripwire, not a boundary. Rules apply to `simple`
commands only. The design requires the shell tool to run with `shell=False`.

### Taint

A call is tainted when a `ToolResult` has been appended to the session since the last
`UserMessage` (`Session.is_tainted()`, a fold over the event log). Taint changes one step: an
allow rule for a `write`, `exec` or `network` call asks instead of allowing. Deny, hooks and
remembered decisions are unaffected. `SessionRunner`
([`backend/saddlery/cli/runner.py`](../../backend/saddlery/cli/runner.py)) runs one turn at a time
per session and queues a message that arrives mid-run, so a new user message cannot reset taint
while a run still holds untrusted results.

Limit: taint resets on each user message. It is a heuristic, not provenance. Tracked in MM-210.

### Invalid arguments and changed targets

`Agent` builds the `PolicyRequest` from `tool.resource()`. A `ResourceError` (non-string path, a
path outside the root, a NUL byte, a symlink loop) becomes an `Invalid arguments: ...` error
`ToolResult`, and the run continues. After an approval, `Agent` computes the resource again. If it
changed, the call returns "Permission denied: the target changed after approval." `write_file`
also opens its target with `O_NOFOLLOW`.

### In the TUI

The prompt is built from the event's `capability`, `resource` and `tainted`, not from raw
arguments: `Allow write_file: docs/a.md? (follows untrusted content) [y/n]`. Shell resources join
with spaces, path resources with `/`. A missing `tainted` flag renders as tainted.

### Events

- `PermissionRequest`: emitted when the ask step is reached. Fields: `tool_call_id`, `tool_name`,
  `arguments`, `principal`, `capability`, `resource` (list of tokens), `tainted`.
- `PermissionDecision`: emitted after the user answers a pending request. Fields: `tool_call_id`,
  `decision` ("allow" or "deny"). A call resolved without asking (deny rule, allow rule, class
  default) emits neither event.

See [`docs/diagrams/permission-gate-sequence.md`](../diagrams/permission-gate-sequence.md) for the
ask round-trip.

## Adding a tool

1. Implement the `Tool` protocol (see `read_file.py` as a template): declare a `capability`
   (`read`, `write`, `exec` or `network`) and a `resource(arguments)` that raises `ResourceError`
   on bad input; validate arguments defensively, catch all expected failure modes, and never let `call()` raise.
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

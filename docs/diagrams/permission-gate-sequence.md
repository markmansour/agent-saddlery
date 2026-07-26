# Permission gate (MM-9) — sequence

Hand-authored. Extends the MM-8 tool round-trip: `PermissionGate.check()` runs between emitting
`ToolCall` and invoking `tool.call()`. An "ask" result suspends `Agent.run()` on an
`asyncio.Future` until `resolve_permission()` is called — see `Agent.run()` and
`docs/specs/2026-07-25-permission-gate-design.md`.

```mermaid
sequenceDiagram
    participant TUI
    participant Agent
    participant PermissionGate
    participant Tool
    participant EventSink

    Agent->>EventSink: emit(ToolCall)
    Agent->>PermissionGate: check(tool_name, arguments, principal)
    alt hook or list resolves to deny
        PermissionGate-->>Agent: "deny"
        Agent->>EventSink: emit(ToolResult(is_error=True, "Permission denied"))
    else hook or list resolves to allow
        PermissionGate-->>Agent: "allow"
        Agent->>Tool: call(arguments)
        Tool-->>Agent: ToolExecutionResult
        Agent->>EventSink: emit(ToolResult)
    else nothing resolves it
        PermissionGate-->>Agent: "ask"
        Agent->>EventSink: emit(PermissionRequest)
        Agent->>Agent: await future (suspended)
        TUI->>Agent: resolve_permission(tool_call_id, decision) [via stdin]
        Agent->>EventSink: emit(PermissionDecision)
        Agent->>PermissionGate: remember(tool_name, principal, decision)
        alt decision == allow
            Agent->>Tool: call(arguments)
            Tool-->>Agent: ToolExecutionResult
            Agent->>EventSink: emit(ToolResult)
        else decision == deny
            Agent->>EventSink: emit(ToolResult(is_error=True, "Permission denied"))
        end
    end
```

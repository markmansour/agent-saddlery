# Permission gate (MM-9, policy MM-212) — sequence

Hand-authored. Extends the MM-8 tool round-trip: `PermissionGate.check()` runs between emitting
`ToolCall` and invoking `tool.call()`. `Agent` builds a `PolicyRequest` (capability, resource,
taint, detail) from the tool and the session, and the gate decides from that alone. An "ask" result suspends `Agent.run()` on an
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
    Agent->>Tool: resource(arguments), detail(arguments)
    Agent->>PermissionGate: check(PolicyRequest)
    alt deny rule, hook or remembered resolves to deny
        PermissionGate-->>Agent: "deny"
        Agent->>EventSink: emit(ToolResult(is_error=True, "Permission denied"))
    else hook, remembered, allow rule or read default resolves to allow
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
        Agent->>PermissionGate: remember(request, decision)
        alt decision == allow
            Agent->>Tool: call(arguments)
            Tool-->>Agent: ToolExecutionResult
            Agent->>EventSink: emit(ToolResult)
        else decision == deny
            Agent->>EventSink: emit(ToolResult(is_error=True, "Permission denied"))
        end
    end
```

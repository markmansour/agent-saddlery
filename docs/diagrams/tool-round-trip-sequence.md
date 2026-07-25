# Tool round-trip (MM-8) — sequence

Hand-authored. `Agent.run()` loops (up to `max_tool_iterations`): stream a turn from the
provider, and if the model asks for tools, execute each one and loop back with the results
appended to the event log. Tool execution never raises — failures become `ToolResult(is_error=True)`,
same as an unknown tool name. Exceeding `max_tool_iterations` emits an `ErrorEvent`; `RunFinished`
always fires (see `Agent.run`).

```mermaid
sequenceDiagram
    participant CLI
    participant Agent
    participant Session
    participant LLMProvider
    participant ToolRegistry
    participant Tool
    participant EventSink

    CLI->>Agent: run(session, sink)
    Agent->>Session: append(RunStarted)
    Agent->>EventSink: emit(RunStarted)

    loop up to max_tool_iterations
        Agent->>Session: to_messages() (rebuild from event log)
        Agent->>LLMProvider: stream(messages, model, tools=registry.specs())
        loop each delta
            alt TextDelta
                LLMProvider-->>Agent: TextDelta(text)
                Agent->>Session: append(AssistantMessageDelta)
                Agent->>EventSink: emit(AssistantMessageDelta)
            else ToolCallDelta
                LLMProvider-->>Agent: ToolCallDelta(id, name, input)
            end
        end
        Agent->>Session: append(AssistantMessage) (if any text)
        Agent->>EventSink: emit(AssistantMessage)

        alt no tool calls
            Note over Agent: done — break loop
        else tool calls present
            loop each ToolCallDelta
                Agent->>Session: append(ToolCall)
                Agent->>EventSink: emit(ToolCall)
                Agent->>ToolRegistry: get(tool_name)
                alt tool found
                    Agent->>Tool: call(arguments)
                    Tool-->>Agent: ToolExecutionResult(content, is_error)
                else unknown tool
                    Note over Agent: content = "Error: unknown tool", is_error=True
                end
                Agent->>Session: append(ToolResult)
                Agent->>EventSink: emit(ToolResult)
            end
            Note over Agent: loop back — rebuild messages, call provider again
        end
    end

    Note over Agent: on exception, or max_tool_iterations exceeded → emit(ErrorEvent)
    Agent->>Session: append(RunFinished)
    Agent->>EventSink: emit(RunFinished)
```

# Echo loop (slice 0.1) — sequence

Hand-authored. The streaming turn: user message in → streamed assistant reply out.
Failures are recorded as an `ErrorEvent` rather than raised (see `Agent.run`).

```mermaid
sequenceDiagram
    participant CLI
    participant Agent
    participant Session
    participant LLMProvider
    participant EventSink

    CLI->>Agent: run(session, sink)
    Agent->>Session: append(RunStarted)
    Agent->>EventSink: emit(RunStarted)
    Agent->>LLMProvider: stream(messages, model)
    loop each delta
        LLMProvider-->>Agent: ProviderDelta(text)
        Agent->>Session: append(AssistantMessageDelta)
        Agent->>EventSink: emit(AssistantMessageDelta)
    end
    Agent->>Session: append(AssistantMessage)
    Agent->>EventSink: emit(AssistantMessage)
    Note over Agent: on exception → emit(ErrorEvent)
    Agent->>Session: append(RunFinished)
    Agent->>EventSink: emit(RunFinished)
```

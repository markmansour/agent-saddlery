# Logging Design — Agent Saddlery

**Status:** Design (not implemented)  
**Date:** 2026-07-03  
**Scope:** Lightweight structured logging for event emission, consumption, and debugging.

## 1. Context & Goal

Agent Saddlery has no logging infrastructure yet. As we move from Phase 0 (CLI) → Phase 2 (multi-frontend server), we need:
- **Event tracing**: see every internal + AG-UI event emitted/consumed
- **Debugging**: understand the flow when something goes wrong
- **Production observability**: structured logs for aggregation and alerting (Phase 3+)

This design adds structured logging without cluttering the core or adding heavyweight dependencies.

## 2. Goals / Non-Goals

**Goals**
- Trace all event emissions (internal and AG-UI)
- Debug transport/sink chains easily
- Prepare for multi-session logging (Phase 3, with context binding)
- Support both console (dev) and JSON (prod) output
- Minimal cognitive load on core code (one-liner integration)

**Non-Goals**
- Full OpenTelemetry integration (Phase 3+)
- Metrics/counters (Phase 3+)
- Log aggregation (Cloud Logging, etc.) — infrastructure decision, not code
- Log levels per module (can add later if needed)

## 3. Design Decisions

| Decision | Choice | Why |
|---|---|---|
| Library | **`structlog`** | Structured, contextual logging; plays well with async; JSON output for prod; widely used in Python agent frameworks |
| Output | **Console (dev) + JSON (prod)** | Dev uses colored, readable `dev` processor; prod uses JSON for aggregation |
| Integration | **Decorator + context binding** | Don't scatter `.log()` calls; bind context once at session start, events inherit it |
| Levels | **DEBUG for events, INFO for milestones** | Events are verbose; keep INFO for start/finish/errors only |
| Performance | **Lazy (deferred formatting)** | structlog doesn't format until needed; use `%s` templates, not f-strings |

## 4. Logging Architecture

### 4.1 Setup (in CLI entry point)

```python
import structlog

# One-time config
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()  # prod
        # or: structlog.dev.ConsoleRenderer()  # dev (via env var)
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)
```

### 4.2 Event Logging Decorator

A sink that wraps another sink and logs events:

```python
class LoggingSink(EventSink):
    """Logs internal events as structured data."""
    
    def __init__(self, sink: EventSink, context: dict[str, Any] | None = None):
        self._sink = sink
        self._log = structlog.get_logger()
        self._context = context or {}
    
    async def emit(self, event: Event) -> None:
        # Log with context (session_id, principal, etc. bound once at session start)
        # Use info level for run start/finish, debug for deltas
        level = "info" if event.type in ("run_started", "run_finished") else "debug"
        self._log.log(level, "event_emitted", 
                        event_type=event.type,
                        event=event.model_dump())  # Full JSON
        await self._sink.emit(event)
```

### 4.3 AG-UI Wire Logging

A sink that logs wire events separately:

```python
class LoggingAgUiSink(AgUiEventSink):
    """Logs AG-UI wire events as structured data."""
    
    def __init__(self, sink: AgUiEventSink, context: dict[str, Any] | None = None):
        self._sink = sink
        self._log = structlog.get_logger()
        self._context = context or {}
    
    async def emit(self, event: AgUiEvent) -> None:
        # Info for lifecycle, debug for content streaming
        level = "info" if event.type in ("RUN_START", "RUN_FINISH") else "debug"
        self._log.log(level, "agui_event_emitted",
                        agui_type=event.type,
                        event=event.model_dump())  # Full JSON
        await self._sink.emit(event)
```

### 4.4 Context Binding (Session Level)

At session start, bind context once so all downstream logs inherit it:

```python
async def _amain() -> int:
    principal = "local"
    session = Session(session_id=uuid.uuid4().hex, principal=principal)
    
    # Bind context for this session
    log = structlog.get_logger().bind(
        session_id=session.session_id,
        principal=principal,
    )
    log.info("session_started")
    
    # All sinks and downstream code now have this context
    # (if we pass the log context through, or use thread-local binding)
    
    agent = build_agent()
    sink = LoggingSink(CliSink(), context={"session_id": session.session_id})
    agui_sink = LoggingAgUiSink(AgUiRecordingSink(), context={"session_id": session.session_id})
    
    # ... rest of run loop
```

## 5. Log Output Examples

### Dev Console (structured, human-readable)

```
2026-07-03 10:45:12 [INFO] session_started session_id='a1b2c3' principal='local'
2026-07-03 10:45:12 [INFO] event_emitted event_type='run_started' event={'id': 'xyz', 'session_id': 'a1b2c3', 'principal': 'local', 'timestamp': '2026-07-03T10:45:12Z', 'type': 'run_started'}
2026-07-03 10:45:12 [INFO] agui_event_emitted agui_type='RUN_START' event={'type': 'RUN_START'}
2026-07-03 10:45:13 [DEBUG] event_emitted event_type='assistant_message_delta' event={'id': 'abc', 'session_id': 'a1b2c3', 'principal': 'local', 'timestamp': '2026-07-03T10:45:13Z', 'type': 'assistant_message_delta', 'text': 'Hello'}
2026-07-03 10:45:13 [DEBUG] agui_event_emitted agui_type='TEXT_MESSAGE_CONTENT' event={'type': 'TEXT_MESSAGE_CONTENT', 'content': 'Hello'}
2026-07-03 10:45:13 [INFO] event_emitted event_type='run_finished' event={'id': 'def', 'session_id': 'a1b2c3', 'principal': 'local', 'timestamp': '2026-07-03T10:45:13Z', 'type': 'run_finished'}
2026-07-03 10:45:13 [INFO] agui_event_emitted agui_type='RUN_FINISH' event={'type': 'RUN_FINISH'}
```

### Prod JSON (for aggregation)

```json
{"timestamp": "2026-07-03T10:45:12Z", "level": "info", "event": "session_started", "session_id": "a1b2c3", "principal": "local"}
{"timestamp": "2026-07-03T10:45:12Z", "level": "info", "event": "event_emitted", "event_type": "run_started", "event": {"id": "xyz", "session_id": "a1b2c3", "principal": "local", "timestamp": "2026-07-03T10:45:12Z", "type": "run_started"}}
{"timestamp": "2026-07-03T10:45:12Z", "level": "info", "event": "agui_event_emitted", "agui_type": "RUN_START", "event": {"type": "RUN_START"}}
{"timestamp": "2026-07-03T10:45:13Z", "level": "debug", "event": "event_emitted", "event_type": "assistant_message_delta", "event": {"id": "abc", "session_id": "a1b2c3", "principal": "local", "timestamp": "2026-07-03T10:45:13Z", "type": "assistant_message_delta", "text": "Hello"}}
{"timestamp": "2026-07-03T10:45:13Z", "level": "debug", "event": "agui_event_emitted", "agui_type": "TEXT_MESSAGE_CONTENT", "event": {"type": "TEXT_MESSAGE_CONTENT", "content": "Hello"}}
{"timestamp": "2026-07-03T10:45:13Z", "level": "info", "event": "event_emitted", "event_type": "run_finished", "event": {"id": "def", "session_id": "a1b2c3", "principal": "local", "timestamp": "2026-07-03T10:45:13Z", "type": "run_finished"}}
{"timestamp": "2026-07-03T10:45:13Z", "level": "info", "event": "agui_event_emitted", "agui_type": "RUN_FINISH", "event": {"type": "RUN_FINISH"}}
```

## 6. Rollout Plan

**Phase 0.2 (now, or defer):**
- Add `structlog` to `pyproject.toml`
- Implement `LoggingSink` and `LoggingAgUiSink`
- Wire up in CLI with env var switch: `SADDLERY_LOG_FORMAT=json|dev` (default: dev)
- Tests pass; no breaking changes

**Phase 0.3 (server transport):**
- Bind request context (user_id, request_id) at FastAPI middleware level
- All session logs inherit it automatically

**Phase 3 (multi-user):**
- Add audit logging (who did what)
- Connect to Cloud Logging / Datadog for prod observability

## 7. Implementation Checklist

- [ ] Add `structlog` to `pyproject.toml`
- [ ] Create `saddlery/logging.py` with setup and helper functions
- [ ] Implement `LoggingSink` in `saddlery/transport/`
- [ ] Implement `LoggingAgUiSink` in `saddlery/transport/`
- [ ] Wire up in CLI with env-var-driven config
- [ ] Add tests (mock logger, verify events are logged)
- [ ] Update README with logging docs (how to enable, what to look for)
- [ ] Add devlog entry documenting tradeoffs

## 8. Alternatives Considered

### A. Use Python's built-in `logging`
**Con:** Verbose config, not great for async, boilerplate-heavy. structlog wraps it better.

### B. Add logging calls scattered throughout core
**Con:** Clutters event emission code, hard to change log format, no context binding.

### C. Defer logging entirely to Phase 3
**Con:** Makes Phase 0.2 debugging harder; logging should be built in, not bolted on.

## 9. Decisions Locked In

1. **Default log level in dev:** INFO (key milestones only; less noise than DEBUG)
2. **Log to file or stdout:** Stdout only for now (Phase 3 can add file/aggregation)
3. **Log full JSON entries:** Yes, full event payload (complete traceability)
4. **Sampling:** No sampling needed for Phase 0.2 (can add in Phase 3 if needed)

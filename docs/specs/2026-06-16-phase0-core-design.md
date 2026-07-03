# Phase 0 Core — Design Spec

- **Status:** Approved (design); implementation not started
- **Date:** 2026-06-16
- **Scope:** The Phase 0 "walking skeleton" core architecture, with slice **0.1 Echo loop**
  ([MAR-5](https://linear.app/mark-mansour/issue/MAR-5)) as its first artifact.
- **Linear:** Milestone [Phase 0 — Walking skeleton](https://linear.app/mark-mansour/project/agent-saddlery-594c6b585b2b/overview)
  (issues [MAR-5](https://linear.app/mark-mansour/issue/MAR-5)…[MAR-13](https://linear.app/mark-mansour/issue/MAR-13))
- **Related research:** `research/reference-designs/openhands.md`, `research/protocols/ag-ui.md`,
  `research/llm-providers.md`, `research/multi-user-tenancy.md`

## 1. Context & goal

Agent Saddlery is a general-purpose agent harness with a headless Python core and multiple TS
frontends over the [AG-UI](https://docs.ag-ui.com/introduction) protocol (see repo `README.md`). This spec defines the **core skeleton** —
a lightly structured architecture designed to extend as later slices/phases land, without big
rewrites and without over-engineering up front. 0.1 instantiates the skeleton end to end: a streaming
chat echo loop with no tools.

## 2. Goals / non-goals

**Goals**
- A runnable streaming echo loop: user message in → streamed assistant reply out.
- Establish the core seams (events, session, llm provider, transport) so later slices *fill in*
  rather than restructure.
- Tenancy-ready: every session and event carries an `owner`/`principal`.

**Non-goals (deferred, by slice/phase)**
- Tools / tool-call loop (0.4+), permission gate (0.5), shell (0.6), web tools (0.7).
- Persistence / replay store (0.8) — in-memory only now.
- AG-UI wire encoding + server transport (0.2 / 0.3) — a CLI sink stands in.
- `OpenAICompatibleProvider` and gateway adapters — seam ready, not implemented now.
- Retries/backoff, fan-out sinks, pub/sub, multi-user auth.

## 3. Decisions (with rationale)

| Decision | Choice | Why |
|---|---|---|
| Build vs buy | **Hand-rolled minimal core**, OpenHands-shaped modules | Learning goal; no framework owns the loop; minimal deps |
| Scaffolding | **Define seams, fill one** | Lightly structured; later slices fill in, not restructure |
| State model | **Event log is source of truth, kept light** | 0.8 replay, audit, and per-`principal` tenancy become fill-ins, not rewrites |
| Event lib | **Pydantic v2** | Events are persisted + wire-serialized + validated + parsed via discriminated union; stack (anthropic SDK, FastAPI, AG-UI) is Pydantic-native. `msgspec` is the escape hatch if serialization is ever a measured bottleneck |
| Concurrency | **asyncio** from the start | Streaming + future FastAPI server (0.3) + concurrent sessions (Phase 3); sync→async later is a rewrite |
| Provider | **`LLMProvider` seam we own; `AnthropicProvider` first** | Native SDK keeps prompt caching, adaptive thinking (on capable models), correct thinking-block replay; pluggability lives in our seam. `OpenAICompatibleProvider` (≈ all OSS) and a gateway adapter are later impls behind the same seam |
| Default model | **`claude-haiku-4-5`** (cheap, for testing; configurable on the Agent) | Save spend during development; switch to Opus/Sonnet for quality. Haiku 4.5 has no adaptive-thinking/effort params, so the provider sets those only on thinking-capable models (Opus / Sonnet 4.6+) |
| Tenancy | **`principal` on every session + event** now | Cheap now, brutal to retrofit |

## 4. Repo layout (monorepo)

> **Superseded (2026-07-03):** `core/` → `backend/` and `frontends/` → `frontend/` per
> [ADR-0001](../adr/0001-repository-layout.md) ([MM-33](https://linear.app/mark-mansour/issue/MM-33)).
> The tree below is the original Phase 0 layout, kept as a point-in-time record.

```
agent-saddlery/
  core/                    # Python project (pyproject.toml)
    saddlery/
      events/              # typed event models (source of truth)
      session/             # event log + to_messages() fold + SessionStore seam
      llm/                 # LLMProvider seam + AnthropicProvider
      agent/               # immutable Agent + run() loop
      tools/               # SEAM placeholder (filled at 0.4)
      runtime/             # SEAM placeholder (execution interface, filled later)
      transport/           # EventSink seam: CliSink now, AG-UI/server later
      cli/                 # 0.1 entrypoint
    tests/
  frontends/               # TS — Ink TUI lands at 0.3
  docs/specs/              # PRDs/specs (this file)
  research/                # existing
```

`tools/`, `runtime/`, and the server side of `transport/` exist as **named, mostly-empty seams** —
nothing speculative inside them yet.

## 5. Module responsibilities

- **`events`** — Pydantic models. Base `Event` (`id`, `session_id`, `principal`, `timestamp`,
  `type`) + concrete types: `UserMessage`, `AssistantMessageDelta`, `AssistantMessage`,
  `RunStarted`, `RunFinished`, `ErrorEvent`. Append-only; canonical state.
- **`session`** — `Session` holds the event log + a pure **`to_messages()` fold** that derives the
  LLM message list from events. `SessionStore` protocol (`get_or_create`; persistence-style
  `load`/`append` at 0.8), in-memory impl now. `principal` on the session.
- **`llm`** — `LLMProvider` protocol + `AnthropicProvider` (native `anthropic` SDK, streaming).
  Default model `claude-haiku-4-5` (cheap for testing; configurable on the `Agent`). Provider-specific
  knobs (cache breakpoints; adaptive thinking only on thinking-capable models) live inside the impl.
- **`agent`** — immutable `Agent` (provider + system prompt). `run(session, sink)` folds → calls
  provider → appends streamed deltas as events → emits them.
- **`transport`** — `EventSink` protocol (`emit(event)`). 0.1 ships `CliSink` (prints deltas live).
  `AgUiSink` (internal events → ~17 AG-UI wire events) arrives at 0.2; SSE/WebSocket server at 0.3.

## 6. Key interfaces

```python
class LLMProvider(Protocol):
    def stream(self, messages: list[Message], *, model: str
               ) -> AsyncIterator[ProviderDelta]: ...
    # ProviderDelta = TextDelta | (later) ToolCallDelta | Stop/Usage
    # a `tools` param is added at slice 0.4

class SessionStore(Protocol):
    async def get_or_create(self, session_id, principal) -> Session: ...
    # persistence-style load/append arrive with the SQLite store at 0.8

class EventSink(Protocol):                       # outbound port (core → consumer)
    async def emit(self, event: Event) -> None: ...
```

- **`EventSink` is outbound only.** Inbound (a UI sending a message in) is the other half of the
  transport seam; in 0.1 the CLI reads stdin and appends a `UserMessage` directly.
- **Sink ≠ storage.** The event log (via `SessionStore`) is the durable truth; a sink is an
  ephemeral live subscriber for presentation/transport.

## 7. Data flow (0.1, no tools)

1. CLI reads a line → append `UserMessage` (with `principal`, `session_id`).
2. `Agent.run`: append `RunStarted` → `session.to_messages()` → `provider.stream(messages)`.
3. Each text delta → append `AssistantMessageDelta` **and** `sink.emit` (CLI prints live).
4. On completion → append final `AssistantMessage` + `RunFinished`.

The event log is the record; the CLI is just a sink subscribed to it. 0.2 swaps `CliSink` for
`AgUiSink` with no loop change.

## 8. Error handling

- Provider failures (auth, rate limit, network) are caught in `run()`, recorded as an `ErrorEvent`,
  emitted to the sink, and the run ends cleanly with `RunFinished`. Use typed SDK exceptions
  (`anthropic.RateLimitError`, …); never string-match.
- **Invariant:** every run produces a well-formed `RunStarted … RunFinished` bracket even on
  failure, so replay (0.8) is always consistent.
- Retries/backoff are out of scope for 0.1 (later provider-level concern).

## 9. Testing strategy

- **Unit:** `to_messages()` fold (pure); session append/read.
- **Loop:** a `FakeProvider` yields scripted deltas → assert the exact event sequence
  (`RunStarted → deltas → AssistantMessage → RunFinished`) and that a `RecordingSink` received them.
  No network. (The seams exist precisely to make this testable.)
- **Smoke:** one live `AnthropicProvider` test gated behind an API-key env var; off by default in CI.
- Matches [MAR-5](https://linear.app/mark-mansour/issue/MAR-5)'s done-check: "a turn produces ordered user→assistant events; tokens stream."

## 10. 0.1 scope (the first artifact = [MAR-5](https://linear.app/mark-mansour/issue/MAR-5))

**In:** `events` (the six types), `session` (in-memory + fold), `LLMProvider` + `AnthropicProvider`,
`Agent.run`, `CliSink`, `cli` entrypoint, `FakeProvider`/`RecordingSink` for tests, `principal`
threaded through. **Out:** everything in §2 non-goals.

## 11. Extensibility map

| Later work | Adds | Core change |
|---|---|---|
| 0.2 AG-UI / 0.3 TUI | `AgUiSink` + server transport | none to the loop |
| 0.4 tools | fill `tools`/`runtime` seam + handle `ToolCallDelta` | additive event types |
| 0.8 persistence/replay | SQLite `SessionStore` | none — the fold *is* replay |
| Phase 3 multi-user | auth at transport + per-`principal` store partition | `principal` already present |
| More providers | new `LLMProvider` impl (OpenAI-compat, gateway) | none |

## 12. Open questions / deferred

- `OpenAICompatibleProvider` (≈ entire OSS ecosystem) and a gateway adapter (LiteLLM/OpenRouter) —
  deferred; both are additional `LLMProvider` impls, no loop change.
- Retries/backoff, `MultiSink` fan-out, pub/sub for late-joining subscribers — when their use case
  arrives (Phase 2+).
- Python package name `saddlery` (proposed) — confirm at implementation.

## 13. References (third-party software)

- [AG-UI](https://docs.ag-ui.com/introduction) — agent↔UI event protocol
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) · [Claude API docs](https://docs.claude.com)
- [Pydantic](https://docs.pydantic.dev/) · [msgspec](https://jcristharif.com/msgspec/) (alternative event lib)
- [asyncio](https://docs.python.org/3/library/asyncio.html)
- [FastAPI](https://fastapi.tiangolo.com/) (0.3 server)
- [OpenHands SDK](https://github.com/OpenHands/agent-sdk) (architecture reference)
- [LiteLLM](https://github.com/BerriAI/litellm) · [OpenRouter](https://openrouter.ai) (future gateway) · [Ollama](https://ollama.com) · [vLLM](https://docs.vllm.ai) (OSS providers)
- [SQLite](https://www.sqlite.org/) (0.8 persistence)

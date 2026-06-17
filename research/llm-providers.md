# LLM provider abstraction

Pluggable LLM providers is a hard requirement. The pattern is a **vendor-agnostic model interface** so
one agent runs against any provider with no code change.

## LiteLLM (Python) — use this in the core
- **Unified interface to 100+ providers** (OpenAI, Anthropic, Vertex, Bedrock, Cohere, vLLM, NIM, …) in
  **OpenAI format**.
- **Router**: fallback, retry, load-balancing across deployments.
- **Cost & token tracking** built in.
- **Pluggable callbacks** → MLflow, Langfuse, Helicone, PromptLayer, **OpenTelemetry** (this is our
  observability hook, catalog item H).
- Ships as both an SDK and a proxy/gateway server.

## Vercel AI SDK (TypeScript) — the frontend-side equivalent
Vendor-agnostic model interface for TS, strong streaming + tool-calling ergonomics. Relevant if any
provider calls happen frontend-side, but **our provider calls live in the Python core**, so LiteLLM is
the primary choice.

## Pydantic AI
Uses `Model` classes for a vendor-SDK-agnostic API; a single agent is portable across vendors. There's a
`pydantic-ai-litellm` integration bridging it to LiteLLM's 100+ providers. Worth knowing if we adopt
Pydantic AI's typed-agent ergonomics on top of LiteLLM.

## What Agent Saddlery takes  *(revised 2026-06-16 — supersedes "LiteLLM in core")*
Decision **C** (see `docs/specs/2026-06-16-phase0-core-design.md`): pluggability lives in **our own
`LLMProvider` seam**, not in LiteLLM. Rationale: a unified OpenAI-format layer flattens Claude-specific
capabilities we want — prompt caching, adaptive thinking, correct thinking-block replay, `count_tokens`.
- **`AnthropicProvider`** (native `anthropic` SDK) is the first/default impl — Phase 0, streaming.
  Default model `claude-haiku-4-5` (cheap, for testing; switch to Opus/Sonnet for quality). Prompt
  caching and adaptive thinking on thinking-capable models (Opus / Sonnet 4.6+; Haiku 4.5 has neither).
- **`OpenAICompatibleProvider`** (one adapter, `base_url` + key) covers ≈ the entire OSS ecosystem
  (Ollama, vLLM, OpenRouter, Together, Groq, …) — added as a fast-follow behind the same seam.
- **Gateway adapter** (LiteLLM proxy or OpenRouter) — an *additional* `LLMProvider` impl for the 100+
  long tail and **per-user cost attribution** at the multi-user phase. LiteLLM's value (routing,
  fallback, cost tracking, OTel callbacks) lands here, as a gateway, not in the core.
- Because the seam is ours, each of these is a drop-in implementation, never a rewrite.

## Links
- LiteLLM repo: https://github.com/BerriAI/litellm · providers: https://docs.litellm.ai/docs/providers
- Pydantic AI providers: https://ai.pydantic.dev/api/providers/
- pydantic-ai-litellm: https://github.com/mochow13/pydantic-ai-litellm
- Vercel AI SDK gateway: https://vercel.com/docs/ai-gateway/ecosystem/framework-integrations/litellm

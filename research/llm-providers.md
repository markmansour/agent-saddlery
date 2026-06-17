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

## What Agent Saddlery takes
- **LiteLLM in the Python core** as the provider layer (Phase 0: one provider + streaming; Phase 1+:
  Router fallback/retry, cost tracking).
- **LiteLLM callbacks → OpenTelemetry/Langfuse** for tracing (Phase 3).
- Keep the provider behind our own thin interface so swapping LiteLLM out later stays cheap.

## Links
- LiteLLM repo: https://github.com/BerriAI/litellm · providers: https://docs.litellm.ai/docs/providers
- Pydantic AI providers: https://ai.pydantic.dev/api/providers/
- pydantic-ai-litellm: https://github.com/mochow13/pydantic-ai-litellm
- Vercel AI SDK gateway: https://vercel.com/docs/ai-gateway/ecosystem/framework-integrations/litellm

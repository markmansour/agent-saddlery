# Prompt injection defense

**The security story that bites without code execution.** Untrusted content (web pages, files, tool
output) carries instructions that hijack the agent. Because Phase 0 has shell, an injection can become
**execution** — so this moves to Phase 1, ahead of the full sandbox.

## Core principle
**Treat all tool outputs, web content, and file content as untrusted input** — never as instructions.
The agent's own task is the only trusted instruction source.

## The Dual-LLM pattern (Simon Willison, 2023)
A **privileged LLM** coordinates the task and can call tools; a **quarantined LLM** processes untrusted
content and has **no tool access**. Untrusted data never reaches the privileged model as instructions.

## CaMeL (Google DeepMind, 2025) — dual-LLM, hardened
- Privileged LLM generates **code in a sandboxed DSL** specifying which tools to call and how outputs
  flow between them; a quarantined LLM only parses data.
- Every value carries **capability metadata** defining how it may be used; a custom interpreter enforces
  **data-flow / provenance policy** and control-flow constraints.
- Results: blocked ~**67%** of benchmark attacks (often →0 for strong models like GPT-4o) even without
  highly specific policies. Cost: ~**2.7–2.8× tokens** (privileged LLM may retry to produce valid code).

## Design-pattern taxonomy (Willison, Jun 2025)
"Design Patterns for Securing LLM Agents against Prompt Injections" catalogs patterns beyond dual-LLM:
action-selector, plan-then-execute, map-reduce, context-minimization, etc. Worth reading before
committing to one approach.

## What Agent Saddlery takes
- **Phase 1:** mark provenance on every observation (which tool/URL/file produced it); treat it as data,
  not instruction, in the prompt assembly.
- **Hooks** (the permission seam) inspect tool inputs the model proposes after reading untrusted content
  — e.g. block a shell command that appears to originate from fetched web text.
- **Consider a quarantined-LLM step** for summarizing/extracting from web/file content before it informs
  any tool call. Full CaMeL-style capability enforcement is a later, optional hardening.

## Links
- Willison design patterns: https://simonwillison.net/2025/Jun/13/prompt-injection-design-patterns/
- CaMeL paper (computer-use): https://arxiv.org/abs/2601.09923
- CaMeL explainer: https://www.marktechpost.com/2025/03/26/google-deepmind-researchers-propose-camel-a-robust-defense-that-creates-a-protective-system-layer-around-the-llm-securing-it-even-when-underlying-models-may-be-susceptible-to-attacks/

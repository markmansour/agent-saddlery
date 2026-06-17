# Sandboxing code execution

**Deferred for Agent Saddlery** (Phase 4) — early shell runs locally behind the permission gate. This
captures the landscape for when untrusted/heavier execution arrives.

## The isolation tiers (weakest → strongest)
1. **Docker container** — baseline. Shared host kernel; a kernel exploit escapes. Fine for dev, not a
   real boundary against untrusted code.
2. **gVisor** — user-space kernel intercepts syscalls. Lighter than a VM. Note: its user-space kernel
   intercepts GPU calls and can block direct PCIe passthrough.
3. **Firecracker / Kata microVMs** — each execution gets its **own kernel** via hardware virtualization.
   A kernel exploit inside one microVM can't reach the host or other microVMs. **The production minimum
   for running untrusted code.** Supports VFIO device passthrough (real GPU access).
4. **Managed sandbox services** — built on the above:
   - **E2B** — open-source, Firecracker-backed, ~150ms cold start. Scaled from 40k sandboxes/month
     (early 2024) to 15M+/month (early 2025); ~half the Fortune 500. Prioritizes hardware-level security.
   - **Daytona** — pivoted to agent infra in early 2025, ~90ms cold start (fastest), **stateful** dev
     environments. Prioritizes persistent state over max isolation.

## Design implication
Build a **runtime abstraction** so the same agent runs **local-Docker in dev** and **microVM/managed in
prod** behind one interface (this is exactly OpenHands' local↔remote portability). Don't couple the
agent loop to any one backend.

## What Agent Saddlery does now vs later
- **Now (Phase 0):** shell runs on the host, single-user, **gated by ask/allowlist** (not isolated).
- **Later (Phase 4):** runtime abstraction → Docker → pluggable E2B/microVM when untrusted execution
  (e.g. running code from the web, multi-user, or agent-authored programs) becomes real.

## Links
- Awesome-sandbox list: https://github.com/restyler/awesome-sandbox
- Daytona vs E2B (2026): https://northflank.com/blog/daytona-vs-e2b-ai-code-execution-sandboxes
- E2B/Daytona/Firecracker setup: https://www.spheron.network/blog/ai-agent-code-execution-sandbox-e2b-daytona-firecracker/
- How big tech sandboxes agents: https://medium.com/@earlperry562/how-every-major-tech-company-is-sandboxing-ai-agents-differently-f41b65f14d8a

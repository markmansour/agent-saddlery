# CrewAI (2026)

Informs the **workflow/orchestration** (stretch) and **security/governance** layers.

## Dual-layer architecture
- **Crews** — teams of autonomous agents that collaborate through **role-based delegation** and dynamic
  decision-making. The unit of work.
- **Flows** — event-driven workflows with **explicit state management** and **conditional routing**.
  A Flow is the "manager" / process definition: the steps, the logic, how data moves. This is the
  production architecture for multi-agent systems; Crews are the work delegated within a Flow.

Takeaway: separate the **orchestration graph** (Flows) from the **agent collaboration** (Crews). For us,
Flows map to the stretch "agent automation/workflows" goal — event-driven, stateful, conditionally routed.

## Enterprise AMP Suite — the governance checklist
The Agent Management Platform shows what a production, multi-user harness eventually needs:
- PII detection and masking
- Role-based access control (RBAC)
- Secret-manager integration
- Audit trails
- SSO
- Cloud and on-prem deployment

Scale claims: trusted by ~60% of the Fortune 500; ~450M agentic workflows/month. Treat AMP as the
**security/governance backlog** — most of it is `[v1]`/`[stretch]` for a single-user tool, but it names
the right line items (audit, secrets, RBAC).

## What Agent Saddlery takes
- **Flows** as the model for the workflow/automation stretch goal (vs. CrewAI's Crews, which are more
  about multi-agent role-play than our single powerful agent).
- The **AMP checklist** as the governance roadmap.

## Links
- Intro/docs: https://docs.crewai.com/en/introduction
- Repo: https://github.com/crewAIInc/crewAI
- AWS guidance: https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-frameworks/crewai.html
- Review (2026): https://cybernews.com/ai-tools/crewai-review/

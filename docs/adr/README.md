# Architecture Decision Records

This log records the *deliberate* architectural decisions for Agent Saddlery — the ones with
trade-offs worth capturing and revisiting. Each ADR states the context, the options weighed, the
decision, and its consequences. They are lightweight and immutable: to change a decision, add a new
ADR that supersedes the old one rather than editing history.

Format: a trimmed [Michael Nygard template](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
(Title, Status, Context, Decision, Options considered, Consequences).

**Status values:** `Proposed` (awaiting sign-off) · `Accepted` · `Superseded by ADR-NNNN` · `Rejected`.

## Log

| ADR | Title | Status |
|---|---|---|
| [0001](0001-repository-layout.md) | Repository layout and the `core/` naming | Accepted |

Related planning docs live in [`docs/specs/`](../specs/) (designs) and [`docs/plans/`](../plans/)
(step-by-step implementation); decisions that cut across specs land here. Tasks live in
[Linear](https://linear.app/mark-mansour/project/agent-saddlery-594c6b585b2b/overview).

# Devlog — Building Agent Saddlery

Chronological journey log. Raw material for a **first-person blog series** about building an
agent harness from scratch. Each session gets a dated entry; each phase boundary gets a
retrospective that's a blog draft.

Entry skeleton: **What we set out to do · Decisions & rationale · Dead-ends · What we learned · Open threads.**

## Definition of Done

The devlog kept falling behind because nothing in the workflow required it ([MM-32](https://linear.app/mark-mansour/issue/MM-32)).
It is now part of "done."

**Every vertical-slice issue's Definition of Done includes:**

- [ ] **Devlog entry written (or explicitly marked N/A).**

Write the entry at the finish/merge step, alongside the demo and test the project already
expects per slice. A slice is not done until its devlog entry lands (or the issue records why
it's N/A — e.g. pure chore, docs-only, or a mechanical refactor with nothing to learn from).

**Phase retrospectives.** Write a retrospective devlog entry — a blog-post draft — **per phase
at a minimum**, when a milestone closes. Also write one whenever a significant new body of work
lands that warrants its own reflection, even mid-phase. See [Phase retrospectives](#phase-retrospectives) below.

**Where this rule lives (auto-wired).** Tasks are tracked in [Linear](https://linear.app/mark-mansour/issue/MM-32),
not GitHub Issues, so the rule is wired into issue creation itself rather than a repo template.
The repo [`CLAUDE.md`](../../CLAUDE.md) instructs the `to-issues` / `triage` flows to add a
**Definition of Done checklist** to every vertical-slice issue, carrying the
`- [ ] Devlog entry written (or explicitly N/A)` item. Linear renders that checklist as tracked
sub-progress on the issue — visible and managed automatically, no hand-pasting. This README
stays the canonical statement of *why* the rule exists.

## Index
- [2026-06-16 — Survey & first decisions](2026-06-16-survey.md)
- [2026-06-16 (session 2) — Plugins, sandboxing, and the multi-user pivot](2026-06-16-plugins-sandbox-multiuser.md)
- [2026-06-16 — Building 0.1 (echo loop)](2026-06-16-0.1-echo-loop.md)
- [2026-06-24 — Python standards & enforcement](2026-06-24-python-standards.md)
- [2026-07-02 — Diagrams + nominal conformance (MM-29, MM-30)](2026-07-02-diagrams-nominal-conformance.md)
- [2026-07-03 — Executing the repo-layout rename (`core/` → `backend/`)](2026-07-03-repo-layout-rename.md)

## Phase retrospectives
- [2026-07-04 — Phase 0 Retrospective (Walking skeleton complete)](2026-07-04-phase-0-retrospective.md)

---

**Voice note:** the blog is Mark's, first person. The dated entries are the factual record;
the retrospectives are drafts. Claude prompts Mark for his own reflections, surprises, and
takeaways at each phase boundary so the posts read as a journey, not a changelog.
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

**Phase retrospectives.** When a milestone (phase) closes, write one retrospective devlog
entry that drafts the blog post for that phase. One retro per phase, at phase close. See
[Phase retrospectives](#phase-retrospectives) below.

**Where this rule lives.** Tasks are tracked in [Linear](https://linear.app/mark-mansour/issue/MM-32),
not GitHub Issues, so there is no repo issue template to carry the checkbox. This README is the
canonical statement of the rule. Whoever creates or triages an issue (via the `to-issues` and
`triage` skill flows) should paste the devlog-DoD checkbox into each vertical-slice issue's
Definition of Done.

> **Open question for Mark:** should the devlog-DoD checkbox be wired directly into a Linear
> issue template and/or the `to-issues` / `triage` skills so it's added automatically, rather
> than pasted by hand? Flagged in [MM-32](https://linear.app/mark-mansour/issue/MM-32).

## Index
- [2026-06-16 — Survey & first decisions](2026-06-16-survey.md)
- [2026-06-16 (session 2) — Plugins, sandboxing, and the multi-user pivot](2026-06-16-plugins-sandbox-multiuser.md)
- [2026-06-16 — Building 0.1 (echo loop)](2026-06-16-0.1-echo-loop.md)

## Phase retrospectives
- _(none yet — first one at the close of Phase 0)_

---

**Voice note:** the blog is Mark's, first person. The dated entries are the factual record;
the retrospectives are drafts. Claude prompts Mark for his own reflections, surprises, and
takeaways at each phase boundary so the posts read as a journey, not a changelog.

---
Mark's response:
* wire it in so that the task is managed automatically.
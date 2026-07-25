# Agent Saddlery — project instructions

## Issue creation (Linear)

Tasks live in [Linear](https://linear.app/mark-mansour/project/agent-saddlery-594c6b585b2b/overview),
not GitHub Issues. When creating vertical-slice issues — via the `to-issues` or `triage` flows,
or by hand — **auto-include a Definition of Done checklist** in the issue description so the
devlog obligation is tracked automatically, never hand-pasted or forgotten:

```markdown
## Definition of Done
- [ ] Demo — runs end-to-end
- [ ] Test — red → green
- [ ] Devlog entry written (or explicitly N/A)
```

- The **devlog item is mandatory** on every vertical slice. Mark it N/A only for a pure chore,
  docs-only change, or a mechanical refactor with nothing to learn from.
- Linear renders `- [ ]` items as tracked sub-progress, so the checklist is visible and managed
  on the issue itself — this is the "shown in Linear" format (a per-issue checklist, not a
  separate sub-issue, to avoid doubling the issue count).
- The *why*, and the retrospective cadence, live in
  [`research/devlog/README.md`](research/devlog/README.md) (§ Definition of Done). Retrospective
  devlog entries: **per phase at a minimum**, plus one for any significant new body of work.

Ratified in [MM-32](https://linear.app/mark-mansour/issue/MM-32).

## Commit conventions

**No AI attribution in this repo, in any commit.** Do not add a `Co-Authored-By: Claude …`
trailer to any commit message — a deliberate override of the global default, applying to every
commit, not just devlog entries.

**Pull request bodies carry no AI attribution.** Do not append the "🤖 Generated with Claude
Code" line (or any similar tool/authorship credit) to PR descriptions in this repo — a deliberate
override of the global default.

# 2026-07-03 — Executing the repo-layout rename (`core/` → `backend/`)

## What we set out to do
Execute [ADR-0001](../../docs/adr/0001-repository-layout.md) ([MM-36](https://linear.app/mark-mansour/issue/MM-36)):
rename the Python project directory `core/` → `backend/` and stand up a `frontend/` sibling, so the
tier axis (`backend` vs `frontend`) is obvious before the first TS frontend lands. The decision was
already made ([MM-33](https://linear.app/mark-mansour/issue/MM-33)); this was the mechanical follow-through.

## Decisions & rationale
- **One directory moves, nothing else.** `git mv core backend`. The package stays `saddlery`, so no
  imports change and `uv.lock` moves without regenerating. The blast radius is config paths, not code.
- **Living docs updated, archival docs annotated.** The CI workflow, `.pre-commit-config.yaml`,
  `Makefile`, `gen_diagrams.py`, `README.md`, and the Python conventions all now say `backend/`. The
  dated *plans* (echo-loop, python-standards) still say `core/` — they're point-in-time records, so I
  added a one-line note pointing at ADR-0001 rather than rewriting history.
- **`frontend/` as a placeholder, not empty.** Git doesn't track empty dirs, so `frontend/README.md`
  documents the convention and links the ADR. The directory earns its place by holding the decision.
- **Renamed `CORE_DIR` → `BACKEND_DIR`** in `gen_diagrams.py`. The path math (`parents[N]`) is
  relative and didn't change, but a constant named `CORE_DIR` pointing at `backend/` is a future trap.

## Dead-ends / things that bit
- **The moved venv was a landmine.** `git mv core backend` relocated the *untracked* `.venv` along
  with the tracked files. uv quietly "repaired" it enough to print `venv ok`, but the venv's baked-in
  interpreter still resolved to a stale pyenv 3.10.11 — so `pytest` collected under 3.10 and blew up on
  `from datetime import UTC` (3.11+), and `pyreverse`'s shebang pointed at the old `core/.venv` path and
  vanished. Lesson: **uv/virtualenv venvs are not relocatable.** `uv venv --clear` + `uv sync` rebuilt it
  clean (CPython 3.12.1) and everything went green. Don't move a venv — delete and re-sync.
- **The CI `paths:` filter is the easy-to-miss line.** Miss it and the Python job silently stops
  triggering on `backend/**` changes. The ADR called this out specifically; glad it did.

## What we learned
- The seams-and-package-name discipline paid off again: renaming the *directory* touched zero Python
  imports. The only real work was config plumbing + one venv rebuild.
- ADR-with-a-consequences-table → execution is close to paint-by-numbers. The migration checklist in
  ADR-0001 was the actual work plan.

## Open threads
- Archival plans keep their original `core/` paths by design (noted, not rewritten). If that ever grates,
  a bulk find-replace is a five-minute follow-up.
- First TS frontend (Ink TUI, Phase 0.3) lands under `frontend/` and validates the sibling convention.
- uv workspace still deferred (ADR-0001 Option D) until a second Python package exists.

## For the blog (Mark to fill in)
- _Your take: was the directory name actually worth an ADR + its own issue, or process for its own sake?
  And the venv-move gotcha — the kind of paper-cut that makes "just rename a folder" a 40-minute job._

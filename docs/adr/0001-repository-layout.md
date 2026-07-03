# ADR-0001 — Repository layout and the `core/` naming

- **Status:** Accepted (Mark Mansour, 2026-07-03) — Option B ratified; the rename executes in a follow-up ([MM-36](https://linear.app/mark-mansour/issue/MM-36))
- **Date:** 2026-07-02 (proposed) · 2026-07-03 (accepted)
- **Deciders:** Mark Mansour
- **Linear:** [MM-33](https://linear.app/mark-mansour/issue/MM-33) (surfaced during [MM-29](https://linear.app/mark-mansour/issue/MM-29))
- **Supersedes / relates to:** the informal layout in the
  [Phase 0 core spec](../specs/2026-06-16-phase0-core-design.md) §4

## Recommendation (lead)

**Rename `core/` → `backend/` and land TS frontends under `frontend/` (multiple apps as subfolders). Defer the uv workspace until a second Python package actually exists.**

`backend/` + `frontend/` is the smallest change that kills both smells, reads correctly to anyone who has seen a web repo, and matches the blueprint ([OpenHands](https://github.com/OpenHands/OpenHands) ships its Python package near root beside a `frontend/`). The Python package stays `saddlery` — only its parent directory changes (`core/saddlery/` → `backend/saddlery/`). No package rename, no import churn, no `uv.lock` regeneration.

If you want a single word instead of a rename, the fallback is **keep `core/` and adopt `core/` + `frontend/`** — cheaper still (zero moves), but it leaves the taxonomy asymmetry (a role-name beside a tech-name) that MM-33 was opened to fix.

## Context

The repo is a monorepo: a headless Python engine plus, soon, several TypeScript frontends over the [AG-UI](https://docs.ag-ui.com/introduction) protocol. Today the Python project lives in `core/`:

```
agent-saddlery/
  core/
    pyproject.toml
    uv.lock
    saddlery/            # the Python package
    scripts/             # dev tooling (gen_diagrams.py) — MM-29
    tests/
  docs/
  research/
```

The roadmap makes the first TS frontend imminent, and **the first sibling directory sets the naming convention for every frontend that follows** — React web, Ink TUI, Tauri desktop, VS Code extension. Naming this wrong once is cheap to fix now and annoying to fix after four frontends and their CI reference the pattern. Deciding now is the point of [MM-33](https://linear.app/mark-mansour/issue/MM-33).

### The two smells

1. **Taxonomy asymmetry.** `core/` names a *role* (the central engine). The planned siblings — `web/`, `tui/`, `desktop/` — name a *technology or surface*. Mixing a role-name with tech-names on the same level reads as an accident, not a system. A reader can't infer the set from any one member.
2. **Role dir nested over the package.** `core/saddlery/` stacks a role directory on top of the actual Python package. `core` and `saddlery` are two names for nearly the same thing (the engine), so the nesting is redundant. The [blueprint](https://github.com/OpenHands/OpenHands) puts its package (`openhands/`) near the repo root, not under a `core/` wrapper.

### Constraints from the roadmap

- **Many TS frontends, one Python engine.** The convention must scale to N frontends without re-litigating names.
- **Headless engine is the product.** The Python core is a library/server that frontends and (later) a REST/WebSocket transport consume — not an "app" in the deploy sense.
- **Tenancy-ready, multi-user later** ([README](../../README.md) locked decisions; Phase 3). Nothing in the layout should assume single-user or single-deployable.
- **A second Python package is plausible but not present.** A shared server, a plugin SDK, or a tools package (Phase 4) could each become its own distribution — the trigger for a workspace, not a reason to pre-build one now.

## Options considered

### Option A — Keep `core/` (+ `frontend/` siblings)

```
core/            # Python (saddlery/, tests/, scripts/, pyproject.toml)
frontend/        # or frontends/ — TS apps
```

- **Pros:** zero moves; every path, CI filter, and doc already works; matches the wording already written into the [Phase 0 spec](../specs/2026-06-16-phase0-core-design.md) and MAR-5 plan (`frontends/`).
- **Cons:** does not resolve either smell. `core/` (role) beside `frontend/` (tech/surface) is exactly the asymmetry MM-33 names, and `core/saddlery/` keeps the redundant nesting. Choosing this is choosing to close MM-33 as "won't fix."

### Option B — `backend/` + `frontend/` (recommended)

```
backend/         # Python engine (saddlery/, tests/, scripts/, pyproject.toml)
frontend/        # TS — one app now; web/, tui/, desktop/ as subfolders later
```

- **Pros:** two names from the same axis (tier), instantly legible to anyone who has seen a web repo; kills the asymmetry. Matches the [OpenHands](https://github.com/OpenHands/OpenHands) shape (Python near root + `frontend/`). Smallest concrete move — one directory rename, package name untouched. Multiple frontends nest cleanly under `frontend/` (`frontend/web`, `frontend/tui`, …) or, if you prefer, `frontend/` pluralizes to `frontends/`.
- **Cons:** "backend" faintly implies a deployed server, whereas the engine is first a library; the headless-engine purist may prefer `engine/`. One rename now (paths, CI, tooling — see Consequences). `core/saddlery/` becomes `backend/saddlery/`, still one level of nesting (the package under its tier dir) — acceptable and conventional, versus fully flat.

### Option C — `packages/` + `apps/`

```
packages/
  saddlery/      # the engine as a package
apps/
  web/  tui/     # frontends as deployables
```

- **Pros:** the standard JS/TS monorepo idiom (Turborepo/Nx/pnpm workspaces); scales to many packages *and* many apps; clean home for a future shared TS package under `packages/`.
- **Cons:** heaviest structure for today's reality (**one** package, **zero** apps) — two empty-ish container dirs up front. The `packages`/`apps` split is a JS-ecosystem convention; imposing it on a Python-first repo where the engine is the single package is ceremony ahead of need. Deepest nesting of the package (`packages/saddlery/`). Re-opens "is the engine a package or an app?" (it's both a library and, later, a server).

### Option D — uv workspace with members

```
pyproject.toml         # [tool.uv.workspace] members = ["backend", "..."]
uv.lock                # single shared lockfile at root
backend/
  pyproject.toml       # the saddlery member
frontend/              # TS, outside the uv workspace
```

- **Pros:** the direction the **newer** blueprint took — the [OpenHands agent-sdk](https://github.com/OpenHands/agent-sdk) is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) with members (`openhands-sdk`, `openhands-agent-server`, `openhands-tools`, `openhands-workspace`). One shared lockfile, consistent deps, clean isolation between Python packages, `--package` targeting. This is very likely the **eventual** end state once Phase 4 (plugin SDK) or a standalone server package arrives.
- **Cons:** **a workspace with one member is a workspace with no benefit.** uv's own [guidance](https://docs.astral.sh/uv/concepts/projects/workspaces/): workspaces are for *multiple interdependent packages*; with a single member you pay the structure (root `pyproject.toml`, moved lockfile, `--package` flags in every command, CI/tooling changes) for none of the payoff, and inherit its constraint (one `requires-python` intersection across members). Premature.

## Decision

Adopt **Option B — `backend/` + `frontend/`.** Keep the Python package named `saddlery`; move only its parent directory. Land the first TS frontend under `frontend/`, with room to grow into `frontend/web`, `frontend/tui`, `frontend/desktop`, `frontend/vscode` (or pluralize to `frontends/` — a one-line follow-up if preferred).

**Explicitly defer Option D (uv workspace)** to the moment a *second* Python distribution exists — a standalone server, a plugin SDK, or a tools package. That is the migration trigger. Structure B nests cleanly into a workspace later: `backend/` simply becomes the first `members` entry, so choosing B now does not foreclose D.

Reject **A** (leaves both smells open — closing MM-33 as won't-fix) and **C** (JS-idiom ceremony for a Python-first repo with one package and zero apps today).

### Why not `engine/`?

`engine/` is a defensible answer to the "backend implies a server" critique and reads well against "headless engine." It loses the instant `backend`/`frontend` pairing that makes the tier axis obvious at a glance, and it has no sibling to pair with (`engine/` + `frontend/` reintroduces a mild asymmetry). If Mark prefers `engine/`, that is a clean amendment to this ADR — the migration mechanics below are identical (swap the target name).

## Consequences

### What moves

- `core/` → `backend/` (single directory rename). `core/saddlery/`, `core/tests/`, `core/scripts/`, `core/pyproject.toml`, `core/uv.lock`, `core/.env` all move with it.
- **No package rename.** `saddlery`, its imports, and `[project.scripts] saddlery = "saddlery.cli.main:main"` are untouched. `uv.lock` moves but need not regenerate.

### Path / config fallout (all mechanical)

| File | Reference today | Change |
|---|---|---|
| [`.github/workflows/python-core.yml`](../../.github/workflows/python-core.yml) | `paths: ["core/**", …]`, `working-directory: core`, `scripts/gen_diagrams.py` | `core` → `backend` in the `paths:` filter (push + pull_request) and `working-directory` |
| [`Makefile`](../../Makefile) | `cd core && uv run python scripts/gen_diagrams.py` | `cd core` → `cd backend` |
| [`.pre-commit-config.yaml`](../../.pre-commit-config.yaml) | `cd core && …` in three hooks; comment "versions come from core/uv.lock" | `cd core` → `cd backend`; update comment |
| [`core/scripts/gen_diagrams.py`](../../core/scripts/gen_diagrams.py) | `CORE_DIR = _HERE.parents[1]`, `REPO_ROOT = _HERE.parents[2]`; banner text "core/scripts/gen_diagrams.py" | `parents[N]` math is relative and **unchanged by the rename** (still `scripts/` → `backend/` → repo root); update the two literal `core/scripts/…` strings in the banner |
| [`README.md`](../../README.md) | `core/` in run instructions, layout section, several links | `core/` → `backend/`; `uv run saddlery` from `backend/`; add a `docs/adr/` pointer (this PR) |
| [`CHANGELOG.md`](../../CHANGELOG.md) | "Python core + TypeScript frontends" | no change needed (describes the language split, not the dir) |
| [`docs/specs/2026-06-16-phase0-core-design.md`](../specs/2026-06-16-phase0-core-design.md) §4, `docs/plans/2026-06-16-mar5-echo-loop.md` | `core/` and `frontends/` in the layout block | update when the move lands (or add a note pointing here) |

- **`make diagrams`** keeps working after the two-line edit: the script's path math is relative (`scripts/` up to repo root), so only the banner strings and the `Makefile` `cd` need touching.
- **CI `paths:` filter** is the one easy-to-miss item — miss it and the Python job stops triggering on backend changes. It's in the table above precisely so it isn't missed.

### Non-consequences

- No import changes (`saddlery.*` stays).
- No `uv.lock` regeneration required (it moves as-is).
- No test changes beyond any that hard-code `core/` in a path (none found in the current suite; `gen_diagrams` tests exercise render functions, not the filesystem root).

### Sequencing

This ADR is a **decision only** — no directories move in the PR that adds it (per [MM-33](https://linear.app/mark-mansour/issue/MM-33): the deliverable is the proposal). On ratification, a follow-up issue executes the rename + the config edits above in one atomic PR, ideally **before the first TS frontend lands** so the sibling convention is set from day one.

## References

- [MM-33](https://linear.app/mark-mansour/issue/MM-33) · [MM-29](https://linear.app/mark-mansour/issue/MM-29) (Linear)
- [OpenHands](https://github.com/OpenHands/OpenHands) — blueprint; `openhands/` package near root + `frontend/`
- [OpenHands agent-sdk](https://github.com/OpenHands/agent-sdk) — newer redesign as a uv workspace with members
- [uv workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/) — Astral docs
- [Phase 0 core spec](../specs/2026-06-16-phase0-core-design.md) §4 (current informal layout)

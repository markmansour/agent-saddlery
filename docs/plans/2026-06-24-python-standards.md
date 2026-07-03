# Python Standards & Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `core/` Python standard explicit and enforced — curated ruff rules + formatter, strict `ty` type checking, a contributor convention doc, and pre-commit + CI gating (3.12/3.14 matrix).

**Architecture:** Config + docs + one CI workflow, plus mechanical fixes to whatever the new rules surface. No runtime behavior changes. pre-commit and CI both run the same gates through `uv run` so versions come from `uv.lock` and never drift.

**Tech Stack:** Python 3.12 (floor unchanged), uv, ruff 0.15.x, ty (Astral), pytest, pre-commit, GitHub Actions.

**Spec:** `docs/specs/2026-06-24-python-standards-design.md`

**Working directory:** All `uv` commands run from `core/`. Repo-root files (`.pre-commit-config.yaml`, `.github/workflows/`) are noted with full paths.

---

## File map

| File | Action | Responsibility |
|---|---|---|
| `core/pyproject.toml` | Modify | ruff rules + formatter, `ty` config + dev dep |
| `core/saddlery/**/*.py` | Modify (mechanical) | Conform to new rules (auto-fix + manual) |
| `core/tests/**/*.py` | Modify (mechanical) | Conform to new rules |
| `docs/conventions/python.md` | Create | Contributor-facing one-page standard |
| `.pre-commit-config.yaml` | Create (repo root) | Local gate: ruff format, ruff check, ty |
| `.github/workflows/python-core.yml` | Create | CI gate: ruff + ty + pytest on 3.12/3.14 |

**Baseline facts (verified 2026-06-24):** tests pass (16 passed, 1 skipped). The selected rule set surfaces 16 findings: `UP035`×3, `RUF100`×1, `UP007`×1, `UP017`×1 (6 safe auto-fixes); `TC001`×8 + `RUF015`×1 (unsafe auto-fixes); `PT012`×1 (manual). `ty` is not yet installed.

---

## Task 1: ruff lint rules + formatter config

**Files:**
- Modify: `core/pyproject.toml` (replace the `[tool.ruff]` block at lines 32-33)

- [ ] **Step 1: Replace the ruff config**

Replace:

```toml
[tool.ruff]
line-length = 100
```

with:

```toml
[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "C4", "N", "PT", "TC", "RUF"]

[tool.ruff.lint.per-file-ignores]
# Tests favour readability over lint strictness.
"tests/**" = ["PT", "RUF015"]

[tool.ruff.format]
# Black-compatible defaults; line-length inherited from [tool.ruff].
```

- [ ] **Step 2: Confirm the formatter has work to do, but do NOT apply yet**

Run: `uv run ruff format --check .`
Expected: lists files that "would be reformatted" (this is the diff Task 2 applies). A non-zero exit here is expected.

- [ ] **Step 3: Confirm lint findings match the plan baseline**

Run: `uv run ruff check . --statistics`
Expected: 16 errors — `TC001`×8, `UP035`×3, `PT012`×1, `RUF015`×1, `RUF100`×1, `UP007`×1, `UP017`×1. If counts differ, stop and reconcile before proceeding (the codebase changed since planning).

- [ ] **Step 4: Commit the config only**

```bash
git add core/pyproject.toml
git commit -m "build: select ruff lint rules and enable formatter for core"
```

---

## Task 2: Apply formatter + safe auto-fixes (mechanical)

This is a deliberately isolated mechanical commit — formatting and safe fixes only, so it is easy to review and easy to skip past in `git blame`.

**Files:**
- Modify: `core/saddlery/**/*.py`, `core/tests/**/*.py` (whatever the tools touch)

- [ ] **Step 1: Apply the formatter**

Run: `uv run ruff format .`
Expected: "N files reformatted, M files left unchanged".

- [ ] **Step 2: Apply safe auto-fixes**

Run: `uv run ruff check . --fix`
Expected: "Fixed 6 errors" (the `UP035`×3, `UP007`, `UP017`, `RUF100`). Remaining: 10 errors (`TC001`×8, `RUF015`×1, `PT012`×1).

- [ ] **Step 3: Run the test suite**

Run: `uv run pytest -q`
Expected: `16 passed, 1 skipped`.

- [ ] **Step 4: Commit**

```bash
git add -A core/
git commit -m "style: apply ruff formatter and safe auto-fixes to core"
```

---

## Task 3: Resolve remaining lint findings (reviewed)

`TC001`/`RUF015` fixes are classed "unsafe" because they move imports / rewrite expressions — apply them, then verify by running the tests. `PT012` is handled by hand.

**Files:**
- Modify: `core/saddlery/**/*.py` (8 `TC001` import moves, e.g. `core/saddlery/transport/recording.py:5`)
- Modify: `core/tests/test_agent.py:31` (`RUF015`)
- Modify: `core/tests/test_fake_provider.py:16` (`PT012`)

- [ ] **Step 1: Apply the unsafe auto-fixes**

Run: `uv run ruff check . --fix --unsafe-fixes`
Expected: fixes `TC001`×8 and `RUF015`×1. Each `TC001` wraps a first-party annotation-only import in an `if TYPE_CHECKING:` block — valid because every module already has `from __future__ import annotations`, so annotations are strings at runtime. Remaining: `PT012`×1.

- [ ] **Step 2: Run the tests to confirm the import moves did not break runtime**

Run: `uv run pytest -q`
Expected: `16 passed, 1 skipped`. (If an `ImportError` appears, a moved import was used at runtime, not only in annotations — move that one import back out of the `TYPE_CHECKING` block.)

- [ ] **Step 3: Fix the last finding (`PT012`) by hand**

`PT012` fires because the `pytest.raises` block in `core/tests/test_fake_provider.py` wraps a multi-line `async for`. The block is intentionally multi-statement (it must iterate to reach the raise), so silence it explicitly. Add a `# noqa: PT012` to the `with` line:

```python
    with pytest.raises(RuntimeError, match="boom"):  # noqa: PT012 - async-for is the unit under test
        async for delta in provider.stream([], model="x"):
            collected.append(delta.text)
```

- [ ] **Step 4: Verify a clean lint pass**

Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 5: Run the tests**

Run: `uv run pytest -q`
Expected: `16 passed, 1 skipped`.

- [ ] **Step 6: Commit**

```bash
git add -A core/
git commit -m "refactor: resolve remaining ruff findings in core"
```

---

## Task 4: Add `ty` and make it pass strict

`ty` is pre-1.0; its config surface is still moving. This task installs it, reads the *actual* config it supports, pins the strictest viable setting, and drives the codebase to a clean pass.

**Files:**
- Modify: `core/pyproject.toml` (`dev` dependency group, lines 14-19; add a `[tool.ty...]` block)
- Modify: `core/saddlery/**/*.py` (only if `ty` surfaces real type errors)

- [ ] **Step 1: Add `ty` to the dev dependency group**

In `core/pyproject.toml`, change the `dev` group from:

```toml
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.24",
    "ruff>=0.6",
]
```

to:

```toml
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.24",
    "ruff>=0.6",
    "ty>=0.0.1",
]
```

- [ ] **Step 2: Sync and confirm `ty` runs**

Run: `uv sync && uv run ty --version`
Expected: prints a `ty` version (no "Failed to spawn").

- [ ] **Step 3: Read `ty`'s real config surface before writing config**

Run: `uv run ty check --help`
Then inspect supported `[tool.ty]` keys (e.g. via the printed help / `ty`'s docs). Confirm the keys used in Step 4 exist in the installed version; adjust key names to match if `ty` has renamed them. Do not invent keys.

- [ ] **Step 4: Add the strictest viable `ty` config**

Append to `core/pyproject.toml` (adjust key names to match Step 3 findings):

```toml
[tool.ty.environment]
python-version = "3.12"

[tool.ty.terminal]
# Treat warnings as errors so CI fails on any diagnostic.
error-on-warning = true
```

If the installed `ty` exposes per-rule severity (`[tool.ty.rules]`), set any default-`warn` rules relevant to untyped/implicit-`Any` code to `error` here. Keep the config minimal — only what raises strictness above the default.

- [ ] **Step 5: Run `ty` and read the baseline**

Run: `uv run ty check`
Expected: either "All checks passed" or a small list of diagnostics (the code is already fully annotated, so few are expected).

- [ ] **Step 6: Fix any real type errors `ty` reports**

For each diagnostic, fix the underlying type issue (add/narrow an annotation, replace an implicit `Any`, etc.). Do **not** blanket-ignore. If a diagnostic is a genuine `ty` false positive, suppress that one line with `ty`'s ignore comment (confirm the exact syntax from Step 3, e.g. `# ty: ignore[rule-name]`) plus a one-line reason. Re-run `uv run ty check` until it passes.

- [ ] **Step 7: Confirm the full local gate is green**

Run: `uv run ruff format --check . && uv run ruff check . && uv run ty check && uv run pytest -q`
Expected: formatter clean, ruff "All checks passed!", `ty` passes, `16 passed, 1 skipped`.

- [ ] **Step 8: Commit**

```bash
git add -A core/
git commit -m "build: add ty strict type checking to core"
```

---

## Task 5: Write the convention doc

**Files:**
- Create: `docs/conventions/python.md`

- [ ] **Step 1: Write the doc**

Create `docs/conventions/python.md` with this content:

````markdown
# Python conventions (`core/`)

The standard for the `saddlery` package. Config lives in `core/pyproject.toml`;
this page is the human-readable version. Floor: Python 3.12.

## Run the gates

From `core/`:

```bash
uv run ruff format .        # format
uv run ruff check . --fix   # lint (+ safe fixes)
uv run ty check             # types
uv run pytest -q            # tests
```

pre-commit runs the first three on every commit; CI runs all four on 3.12 and 3.14.

## Type annotations

- Annotate every function signature — parameters and return type.
- Prefer [PEP 695](https://peps.python.org/pep-0695/) syntax: `class Box[T]:` and
  `type Json = ...` over `TypeVar` / `TypeAlias`.
- Keep `from __future__ import annotations` at the top of every module while we
  support 3.12/3.13 (redundant only on 3.14+).
- Import abstract types from `collections.abc`, not `typing`
  (`AsyncIterator`, `Sequence`, …). ruff `UP` enforces this.
- Annotation-only first-party imports go in an `if TYPE_CHECKING:` block. ruff
  `TC` enforces this; it also keeps the seam modules free of import cycles.
- No implicit `Any`. Prefer `object` + narrowing or a real generic. `ty` strict
  flags it.

## Choosing a data shape

| Use | When | Example |
|---|---|---|
| `typing.Protocol` | A pluggable seam / interface | `saddlery/llm/base.py` |
| Pydantic `BaseModel` | Validated or wire data | `saddlery/events.py` |
| Frozen `dataclass` | Immutable config | `saddlery/agent.py` |

## Errors

Failures inside the run loop are recorded as events, not raised to the caller
(see `Agent.run` in `saddlery/agent.py`). A justified broad `except` carries a
`# noqa: BLE001` with a one-line reason.

## Style

PEP 8 via ruff; line length 100. Naming follows ruff `N`. Don't hand-format —
let `ruff format` decide.
````

- [ ] **Step 2: Commit**

```bash
git add docs/conventions/python.md
git commit -m "docs: add Python conventions for core"
```

---

## Task 6: pre-commit hooks

Local hooks run through `uv run` so they use the exact versions in `uv.lock` (no separate hook-pinned versions to drift). They operate on `core/`.

**Files:**
- Create: `.pre-commit-config.yaml` (repo root)

- [ ] **Step 1: Write the pre-commit config**

Create `.pre-commit-config.yaml` at the repo root:

```yaml
# Hooks run the same gates as CI, via uv (versions come from core/uv.lock).
repos:
  - repo: local
    hooks:
      - id: ruff-format
        name: ruff format
        entry: bash -c 'cd core && uv run ruff format --check .'
        language: system
        types: [python]
        pass_filenames: false
      - id: ruff-check
        name: ruff check
        entry: bash -c 'cd core && uv run ruff check .'
        language: system
        types: [python]
        pass_filenames: false
      - id: ty
        name: ty check
        entry: bash -c 'cd core && uv run ty check'
        language: system
        types: [python]
        pass_filenames: false
```

- [ ] **Step 2: Install and run against all files**

Run: `uv run --project core pre-commit install && uv run --project core pre-commit run --all-files`

(If `pre-commit` is not in the dev group, add it: `uv add --project core --dev pre-commit`, then re-run.)

Expected: `ruff format`, `ruff check`, and `ty` hooks all pass.

- [ ] **Step 3: Commit**

```bash
git add .pre-commit-config.yaml core/pyproject.toml core/uv.lock
git commit -m "build: add pre-commit hooks for ruff and ty"
```

---

## Task 7: CI workflow

**Files:**
- Create: `.github/workflows/python-core.yml`

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/python-core.yml`:

```yaml
name: Python core

on:
  push:
    paths: ["core/**", ".github/workflows/python-core.yml"]
  pull_request:
    paths: ["core/**", ".github/workflows/python-core.yml"]

jobs:
  check:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.12", "3.14"]
    defaults:
      run:
        working-directory: core
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Sync dependencies
        run: uv sync --all-extras --dev

      - name: ruff format
        run: uv run ruff format --check .

      - name: ruff check
        run: uv run ruff check .

      - name: ty
        run: uv run ty check

      - name: pytest
        run: uv run pytest -q
```

- [ ] **Step 2: Validate the YAML locally**

Run: `uv run --project core python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('../.github/workflows/python-core.yml').read_text()); print('ok')"`
Expected: `ok`. (If PyYAML is absent, instead confirm by eye that indentation is consistent — 2 spaces, no tabs.)

- [ ] **Step 3: Commit and push**

```bash
git add .github/workflows/python-core.yml
git commit -m "ci: gate core on ruff, ty, and pytest (3.12/3.14)"
git push
```

- [ ] **Step 4: Confirm CI is green**

After the push, watch the run: `gh run watch` (or check the PR's checks). Expected: the `check (3.12)` and `check (3.14)` jobs both pass. If `3.14` fails on a forward-compat issue while `3.12` passes, capture the error and decide whether to fix or temporarily drop `3.14` from the matrix — the floor (3.12) is the must-pass lane.

---

## Self-review notes

- **Spec coverage:** §3 ruff rules → Task 1; §4 annotation conventions → Tasks 2-3 (mechanical conformance) + Task 5 (doc); §5 `ty` config → Task 4; §5 dev dep → Task 4 Step 1; §6 pre-commit → Task 6; §6 CI + 3.14 matrix → Task 7; §7 floor unchanged → no task touches `requires-python` (intentional); §8 sequencing → task order matches; §9 success criteria → Task 7 Step 4 + Task 4 Step 7.
- **`ty` config uncertainty** is handled explicitly in Task 4 Steps 3-4 (read real config before writing) rather than asserting keys that may not exist.
- **Floor stays `>=3.12`:** no step edits `requires-python`; 3.14 appears only as a CI matrix lane.

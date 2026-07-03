# Python Standards & Enforcement — Design Spec

- **Status:** Approved (design); implementation not started
- **Date:** 2026-06-24
- **Scope:** Coding standards, type-checking, lint/format tooling, and CI/pre-commit
  enforcement for the Python **`core/`** package (`saddlery`). Frontend (TS) standards are
  out of scope and get their own spec.
- **Related:** [PEP 8](https://peps.python.org/pep-0008/),
  [PEP 484](https://peps.python.org/pep-0484/) (type hints),
  [PEP 695](https://peps.python.org/pep-0695/) (type-parameter syntax),
  [PEP 649](https://peps.python.org/pep-0649/)/[PEP 749](https://peps.python.org/pep-0749/)
  (deferred annotations), [ruff](https://docs.astral.sh/ruff/),
  [ty](https://github.com/astral-sh/ty), [uv](https://docs.astral.sh/uv/),
  [pre-commit](https://pre-commit.com/)
- **Prior spec:** `docs/specs/2026-06-16-phase0-core-design.md`

## 1. Context & goal

`core/` is already fully type-annotated and idiomatic: `from __future__ import annotations`
throughout, `Protocol` seams, Pydantic models, frozen dataclasses, and ruff wired in. But the
standard is implicit and unenforced — ruff runs with only `line-length` set (no lint rules
selected), there is **no type checker**, and CI runs only the Claude review workflows. Nothing
blocks non-conforming code from landing.

Goal: make the existing-good standard **explicit and enforced** — a documented convention plus
an automated gate — so the codebase stays readable and maintainable as contributors and slices
accrue.

## 2. Goals / non-goals

**Goals**
- A selected ruff lint rule set + the ruff formatter, applied across `core/`.
- Strict type checking via `ty`, run in CI and pre-commit.
- A one-page contributor-facing convention doc at `docs/conventions/python.md`.
- A CI workflow that gates `ruff` + `ty` + `pytest` on every push/PR touching `core/`.
- Forward-compat signal via a CI matrix that also runs Python 3.14.

**Non-goals (deferred)**
- Raising the Python floor — `requires-python` stays `>=3.12` (see §7).
- TS / frontend standards and their tooling.
- Docstring-style enforcement (`D`) and annotation-presence rules (`ANN`) in app code — the
  rule set is curated, not maximal; revisit if drift appears.
- Changing any runtime behavior. This is config + docs + mechanical fixes only.

## 3. Decisions (with rationale)

| Decision | Choice | Why |
|---|---|---|
| Type checker | **`ty` (strictest)** | One Astral toolchain with ruff + uv; very fast. Pre-1.0 tradeoff accepted — annotations are the asset, the checker is swappable. |
| Strictness | **Strict from day one** | Codebase is already fully typed; strict is cheap now and expensive to retrofit later. |
| Lint/format | **ruff** (curated rules + formatter) | Already a dependency; single tool for lint + format; fast. |
| Enforcement | **pre-commit + CI gate** | Fast local loop; CI is the authoritative source of truth. |
| Python floor | **Keep `>=3.12`** | A floor is a compatibility contract; raise it only to consume a feature, not to chase latest. 3.12 already gives PEP 695 + modern typing. |
| Forward-compat | **CI matrix `[3.12, 3.14]`** | Catch breakage on latest without forcing it on consumers. |
| Spec/doc location | Spec in `docs/specs/`; convention in `docs/conventions/python.md` | Follow the existing repo layout. |

## 4. Type-annotation convention (the standard)

Codifies what the code already does, plus a few sharpenings:

- **Annotate every function signature** — parameters and return. Strict `ty` makes this
  effectively mandatory in app code.
- **Prefer PEP 695 syntax** (3.12+): `class Box[T]:` and `type Json = ...` over `TypeVar` /
  `TypeAlias`.
- **Keep `from __future__ import annotations`** while supporting 3.12/3.13. It is redundant only
  on 3.14+ (PEP 649/749 makes deferred evaluation the default); revisit when the floor moves.
- **One data shape per job**, matching current code:
  - `Protocol` for pluggable seams (`saddlery/llm/base.py`).
  - Pydantic `BaseModel` for validated / wire data (`saddlery/events.py`).
  - Frozen `dataclass` for immutable config (`saddlery/agent.py`).
- **Import abstract types from `collections.abc`, not `typing`.** Existing fix: `saddlery/llm/base.py`
  imports `AsyncIterator` from `typing` (deprecated since 3.9); the `UP` ruleset auto-fixes this.
- **Ban implicit `Any`** — prefer `object` + narrowing or real generics. Strict `ty` flags it.
- **Error handling** follows the codebase pattern: failures are recorded as events, not raised to
  the caller (`saddlery/agent.py` `run()`); justified broad excepts carry a `# noqa: BLE001`
  with a reason.

## 5. Tooling config (`core/pyproject.toml`)

- **ruff formatter** — black-compatible; `line-length` stays 100.
- **ruff lint rules** (replacing the bare `[tool.ruff]`):
  `E, F, I, UP, B, SIM, C4, N, PT, TC, RUF`.
  - `E,F` pycodestyle errors + pyflakes; `I` import sort; `UP` pyupgrade; `B` bugbear;
    `SIM` simplify; `C4` comprehensions; `N` naming; `PT` pytest style; `TC` type-checking
    imports; `RUF` ruff-native.
  - Per-file ignores relax noisy rules in `tests/` (e.g. `PT` strictness; no annotation pressure).
- **`ty`** — configured to its strictest available setting, target pinned to Python 3.12. Exact
  config keys are verified against the installed `ty` version during implementation (config
  surface is still moving pre-1.0); intent is "every diagnostic is an error."
- `ty` is added to the `dev` dependency group alongside `ruff`/`pytest`.

## 6. Enforcement

- **pre-commit** (`.pre-commit-config.yaml`, repo root): `ruff format --check`, `ruff check`,
  `ty check` — the fast local gate.
- **CI** (`.github/workflows/python-core.yml`): on push/PR touching `core/`, run
  `uv run ruff check` → `uv run ty check` → `uv run pytest`.
  - **Matrix `[3.12, 3.14]`** — same checks on both; floor stays 3.12.

## 7. Python version decision

Keep `requires-python = ">=3.12"`. Rationale:
- Establishing standards and bumping the runtime are independent changes with independent risk;
  do not bundle them.
- 3.12 already provides the modern typing surface (PEP 695 generics, `Self`, `@override`).
- Raising the floor only shrinks who can install the harness, with no current benefit.
- The one 3.14-relevant item (PEP 649/749 deferred annotations) changes nothing while 3.12/3.13
  are supported. The 3.14 CI matrix lane gives forward-compat signal without a floor bump.

## 8. Sequencing (implementation order)

1. Land tooling config in `pyproject.toml` (ruff rules + formatter, `ty`, dev dep).
2. Run `ruff format` + `ruff check --fix` across `core/` as one mechanical commit.
3. Fix residual `ty` errors (expected: few, given existing annotations).
4. Write `docs/conventions/python.md`.
5. Add pre-commit config + the CI workflow **last**, so CI is green the moment it exists.

## 9. Success criteria

- `uv run ruff check`, `uv run ruff format --check`, `uv run ty check`, and `uv run pytest` all
  pass on `core/` for both 3.12 and 3.14.
- pre-commit runs the same gates locally.
- `docs/conventions/python.md` exists and a contributor can follow it without reading config.
- No runtime behavior changed; the existing test suite passes unchanged.

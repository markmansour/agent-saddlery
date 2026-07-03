# 2026-06-24 — Python standards & enforcement

_(Backfill entry — process catch-up. This chunk shipped without a same-day devlog; written after the fact, first person, for me to edit.)_

## What we set out to do
Take the standard the `core/` code already followed implicitly and make it **explicit and enforced**.
The code was already good — `from __future__ import annotations` everywhere, [`Protocol`](https://docs.python.org/3/library/typing.html#typing.Protocol)
seams, Pydantic models, frozen dataclasses — but nothing held the line. [ruff](https://docs.astral.sh/ruff/)
ran with only `line-length` set (no lint rules), there was no type checker, and CI ran only the Claude
review workflows. Non-conforming code could land unchallenged. Goal: a documented convention plus an
automated gate. Spec: [`docs/specs/2026-06-24-python-standards-design.md`](../../docs/specs/2026-06-24-python-standards-design.md).

## Decisions & rationale
- **Type checker: [`ty`](https://github.com/astral-sh/ty), strict from day one.** One Astral toolchain
  with ruff + uv, very fast. It's pre-1.0, but the annotations are the asset — the checker is swappable.
  Strict is cheap on an already-typed codebase and expensive to retrofit later, so no gradual ramp.
- **Lint/format: ruff, curated rules.** `E, F, I, UP, B, SIM, C4, N, PT, TC, RUF` plus the formatter.
  Curated, not maximal — I deliberately left out docstring (`D`) and annotation-presence (`ANN`) rules
  in app code. Strict `ty` already forces signatures; adding `ANN` would be noise.
- **Everything gated.** [pre-commit](https://pre-commit.com/) for the fast local loop, CI as the
  authoritative source of truth. The [CI workflow](../../.github/workflows/python-core.yml) runs
  `ruff check` → `ty check` → `pytest` on every push/PR touching `core/`. Same three checks locally in
  [`.pre-commit-config.yaml`](../../.pre-commit-config.yaml).
- **Keep the Python floor at `>=3.12`.** A floor is a compatibility contract; raise it to consume a
  feature, not to chase latest. 3.12 already gives PEP 695 generics, `Self`, `@override`. Bumping the
  runtime and setting standards are independent changes with independent risk — don't bundle them.
- **CI matrix `[3.12, 3.14]`.** Forward-compat signal on the latest without forcing it on anyone who
  installs the harness. The one 3.14-relevant item (PEP 649/749 deferred annotations) changes nothing
  while 3.12/3.13 are supported.
- **Convention doc as its own page.** [`docs/conventions/python.md`](../../docs/conventions/python.md) —
  one page a contributor can follow without reading config: which data shape for which job (Protocol
  for seams, Pydantic for wire data, frozen dataclass for config), the annotation rules, the errors-as-
  events pattern.
- **Sequencing: gates last.** Land tooling config → run `ruff format` + `--fix` as one mechanical commit
  → fix residual `ty` errors → write the doc → add pre-commit + CI **last**, so CI is green the moment
  it exists. No red-on-arrival.

## Dead-ends / things that shifted
- **The structural→nominal typing thread starts here.** `ty` strict checks the seams, but the impls
  satisfied their `Protocol`s **structurally** — no base class, conformance implied by shape. Fine for
  correctness, invisible to any tool that reads inheritance. I noted it and moved on; it comes back and
  gets resolved in the diagrams work (see the [2026-07-02 entry](2026-07-02-diagrams-nominal-conformance.md)).
- **`ty` config surface is still moving pre-1.0.** The spec deferred exact config keys to "verified
  against the installed version during implementation." Intent over syntax: every diagnostic is an error.
- **A convention that had to match the code, not the ideal.** The broad-except rule: failures inside the
  run loop are recorded as events, not raised (`Agent.run`). A deliberate broad `except` carries a
  `# noqa: BLE001` with a reason. The doc had to describe what the code does, and one commit
  (`d3938dc`) reconciled the two rather than forcing the code to a purer rule.

## What we learned
- **Enforcing an already-good standard is mostly mechanical.** Because the code was already typed and
  idiomatic, `ty` strict surfaced few errors and the ruff auto-fixes were safe. The cost of "strict from
  day one" is real only if you defer it.
- **The gate is the standard.** A convention doc nobody runs is a suggestion. Wiring the same three
  commands into pre-commit and CI is what makes it load-bearing. The doc explains; the gate enforces.
- **Curate the rule set.** Maximal ruff is a fight with your own linter. Picking rules that match how the
  code already reads kept the mechanical commit small and the ongoing friction near zero.

## Open threads
- TS / frontend standards — out of scope here, their own spec later.
- The structural-vs-nominal seam question, left open for the diagrams work.
- Revisit `D`/`ANN` rules if annotation or docstring drift shows up.
- Drop `from __future__ import annotations` when the floor eventually moves to 3.14+.

## For the blog (Mark to fill in)
- _Your reflections: does "enforce the standard you already follow" feel like the right order, or should
  the gate have come before the code was good? How did strict `ty` from day one feel — cheap, or did it
  fight you? Anything you'd curate differently in the ruff set now that you've lived with it? And the
  structural typing itch — when did it start bothering you enough to fix?_

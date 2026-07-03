# 2026-07-02 — Diagrams + nominal conformance ([MM-29](https://linear.app/mark-mansour/issue/MM-29), [MM-30](https://linear.app/mark-mansour/issue/MM-30))

_(Backfill entry — process catch-up. Two chunks shipped without a same-day devlog; written after the fact, first person, for me to edit.)_

## What we set out to do
Make the growing `core/` legible with diagrams, in [Mermaid](https://mermaid.js.org/) so they render
inline on GitHub and Linear with no external renderer. Two issues, back to back:
- [MM-29](https://linear.app/mark-mansour/issue/MM-29) — autogenerate a class diagram and an ER
  (data-model) diagram, plus a hand-authored sequence diagram of the 0.1 echo loop.
  Spec: [`docs/specs/2026-07-02-diagrams-design.md`](../../docs/specs/2026-07-02-diagrams-design.md),
  plan: [`docs/plans/2026-07-02-diagrams.md`](../../docs/plans/2026-07-02-diagrams.md).
- [MM-30](https://linear.app/mark-mansour/issue/MM-30) — fix the generated class diagram's readability
  and lean into **nominal [`Protocol`](https://docs.python.org/3/library/typing.html#typing.Protocol)
  conformance** on the seams.
  Spec: [`docs/specs/2026-07-02-class-diagram-readability-design.md`](../../docs/specs/2026-07-02-class-diagram-readability-design.md),
  plan: [`docs/plans/2026-07-02-class-diagram-readability.md`](../../docs/plans/2026-07-02-class-diagram-readability.md).

## Decisions & rationale
- **Mermaid everywhere.** Fits the devlog + link-references workflow; nothing to install; renders where
  I read code. Output lives in [`docs/diagrams/`](../../docs/diagrams/) as markdown with fenced `mermaid`
  blocks (raw `.mmd` doesn't render on GitHub).
- **Class diagram: [pyreverse](https://pylint.readthedocs.io/en/latest/pyreverse.html) → Mermaid.**
  Ships with pylint, reads the typed code directly, emits `classDiagram`. The strict typing from the
  [Python-standards work](2026-06-24-python-standards.md) is what makes the code legible to a structure
  tool in the first place.
- **ER diagram: custom Pydantic-introspection script**, not erdantic (SVG output breaks Mermaid-only and
  needs Graphviz). `render_er` walks `.model_fields` into an `erDiagram`. Pure function, so it's
  unit-tested.
- **Sequence diagram: hand-authored.** Runtime tracing is unreliable, and drawing the *intended*
  interaction is the learning value. [`echo-loop-sequence.md`](../../docs/diagrams/echo-loop-sequence.md).
- **CI smoke-check, not a diff gate.** The generator must run clean (catches a generator broken by model
  changes), but no output diff — non-deterministic ordering can't cause a false CI failure. Diagrams are
  refreshed and committed by hand. One step in [`python-core.yml`](../../.github/workflows/python-core.yml).
- **`make diagrams` over `just`.** `make` is universally available; `just` would need adding locally and
  in CI for no gain. The real work is a `uv run` command.
- **Generator lives in `core/scripts/`** — inside the gated project (ruff/ty/pytest cover it), named
  `scripts` to avoid colliding with `saddlery/tools/`. See
  [`core/scripts/gen_diagrams.py`](../../core/scripts/gen_diagrams.py).

### The nominal-conformance decision (MM-30)
This is the through-line from the standards work. MM-29 shipped a class diagram with a hole: the seam
impls (`AnthropicProvider`, `FakeProvider`, `InMemorySessionStore`, `CliSink`, `RecordingSink`)
satisfied their `Protocol`s **structurally** — no base class — so pyreverse drew **no implements-edges**.
The diagram couldn't show that `AnthropicProvider` *is an* `LLMProvider`.

Two options:
- **A — nominal conformance:** make each impl subclass its `Protocol`.
- **B — synthetic edges:** teach the generator to inject fake realization edges.

**Chose A.** It's a real correctness win, not a diagram hack: subclassing means [`ty`](https://github.com/astral-sh/ty)
checks conformance at *definition time*, and pyreverse then emits the real edges for free. B would have
faked the picture while leaving conformance unverified. The cost of A is trivial — a nominal runtime
import of the protocol module (not `TYPE_CHECKING`, since it's used as a base class). Commit
`333fde2` added the bases; a new `test_seams_conformance.py` pins it. No behavior change — the existing
tests already instantiate these classes.

For readability, `reorder_class_diagram` post-processes pyreverse's output: relationship edges first,
then class blocks grouped by source module in a fixed flow order
(`agent → llm → session → transport → events → messages`) — top-down from the orchestrator to the data
it moves. Pure function, unit-tested. Result is in
[`class-core.md`](../../docs/diagrams/class-core.md): the `--|>` Protocol edges now render.

## Dead-ends / things that shifted
- **pyreverse can't group or order `mmd` output**, so grouping had to be post-processing on the text, not
  a pyreverse flag. `reorder_class_diagram` splits header / class-blocks / relationship-lines and
  re-emits.
- **Structural Protocols were the whole snag.** Python's `Protocol` is designed for structural typing —
  you get conformance without inheritance, which is the point of duck typing. But that's invisible to
  tools that read inheritance, and it means `ty` never checks conformance until a *use site* fails. MM-30
  is me deciding that on the seams — the load-bearing interfaces — I want nominal conformance for the
  definition-time check and the visible edge, even though structural would "work."
- **erdantic rejected** for the ER diagram (SVG + Graphviz); the small custom introspection script keeps
  it all-Mermaid and current.
- **No freshness/diff gate** — tempting, but non-deterministic ordering would cause false failures.
  Smoke-only.

## What we learned
- **Structural typing is a great default and a poor guarantee.** It's perfect for tests (a `FakeProvider`
  just needs the right shape) and wrong for a documented seam you want verified and visible. The fix
  isn't "abandon Protocols" — it's "subclass the ones that are load-bearing." Nominal where it's a
  contract, structural everywhere else.
- **Good typing compounds.** The strict-typing investment paid off again here: pyreverse produces a
  useful diagram *because* the code is annotated. Diagrams are a downstream benefit of the standards work.
- **A diagram bug can reveal a design smell.** The missing edges weren't a rendering problem — they were
  the tool honestly reporting that conformance was never declared. Fixing the diagram meant sharpening
  the code.
- **Generate the structure, draw the behavior.** Class + ER are mechanical and belong to a script;
  the sequence diagram is a decision about what matters and belongs in my hands.

## Open threads
- The pyreverse *package* diagram — a near-free follow-on, deferred from the first cut.
- Autogenerated sequence diagrams via runtime tracing — deliberately not doing this; revisit only if the
  hand-drawn ones drift.
- Whether any future non-seam class wants nominal conformance, or if the seams are the only place it
  earns its keep.

## For the blog (Mark to fill in)
- _Your reflections: the structural-vs-nominal call is the interesting one — did leaning nominal on the
  seams feel like giving up on duck typing, or like using each where it fits? Was "the diagram exposed a
  design gap" a satisfying moment or an annoying one? And on the meta level: how much of this diagram
  work is for understanding vs. for the blog's sake — is drawing the system teaching you things about it?_

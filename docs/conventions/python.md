# Python conventions (`backend/`)

The standard for the `saddlery` package. Config lives in `backend/pyproject.toml`;
this page is the human-readable version. Floor: Python 3.12.

## Run the gates

From `backend/`:

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
- Annotation-only imports go in an `if TYPE_CHECKING:` block. ruff `TC` enforces
  this; it also keeps the seam modules free of import cycles. Imports used at
  runtime (instantiation, `isinstance`, defaults) stay as normal imports.
- No implicit `Any`. Prefer `object` + narrowing or a real generic. `ty` flags it.

## Choosing a data shape

| Use | When | Example |
|---|---|---|
| `typing.Protocol` | A pluggable seam / interface | `saddlery/llm/base.py` |
| Pydantic `BaseModel` | Validated or wire data | `saddlery/events.py` |
| Frozen `dataclass` | Immutable config | `saddlery/agent.py` |

Events are a **closed discriminated union** (`Event` in `saddlery/events.py`,
`Field(discriminator="type")`). The `EventSink` seam and the session log are typed
as `Event`, so a new event type must be added to that union to flow through sinks.

## Errors

Failures inside the run loop are recorded as events, not raised to the caller
(see `Agent.run` in `saddlery/agent.py`). A deliberately broad `except` carries a
one-line comment explaining why.

## Style

PEP 8 via ruff; line length 100. Naming follows ruff `N`. Don't hand-format —
let `ruff format` decide.

# Class-Diagram Readability + Nominal Conformance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Declare nominal `Protocol` conformance on the first-party seam implementations, and post-process the generated class diagram so relationship edges come first and classes are grouped by module in flow order.

**Architecture:** Part 1 adds explicit Protocol bases to five classes (ty-checked conformance; pyreverse then draws the edges). Part 2 adds a pure `reorder_class_diagram` transform to `gen_diagrams.py`. Part 3 wires it into `main()` and regenerates the committed diagram.

**Tech Stack:** Python 3.12, uv, pydantic v2, pylint (pyreverse), pytest, ruff, ty.

**Spec:** `docs/specs/2026-07-02-class-diagram-readability-design.md` · **Linear:** [MM-30](https://linear.app/mark-mansour/issue/MM-30/class-diagram-readability-nominal-protocol-conformance)

**Prerequisite (execution setup):** On local `main`. Do NOT implement on `main`. First:
```bash
cd /Users/markmansour/Documents/Code/agent-saddlery
git checkout -b mark/mm-30-class-diagram
```
All `uv` commands run from `core/`.

---

## File map

| File | Action | Responsibility |
|---|---|---|
| `core/saddlery/llm/fake.py` | Modify | `FakeProvider(LLMProvider)` |
| `core/saddlery/llm/anthropic_provider.py` | Modify | `AnthropicProvider(LLMProvider)` |
| `core/saddlery/session.py` | Modify | `InMemorySessionStore(SessionStore)` |
| `core/saddlery/transport/cli.py` | Modify | `CliSink(EventSink)` |
| `core/saddlery/transport/recording.py` | Modify | `RecordingSink(EventSink)` |
| `core/tests/test_seams_conformance.py` | Create | assert nominal subclassing |
| `core/scripts/gen_diagrams.py` | Modify | `_group_key`, `GROUP_ORDER`, `reorder_class_diagram`, `_saddlery_class_modules`, `main()` wiring |
| `core/tests/test_gen_diagrams.py` | Modify | tests for the new generator functions |
| `docs/diagrams/class-core.md` | Modify (regenerated) | edges-first, grouped, with Protocol edges |

**Grounding facts (verified 2026-07-02):** The seams are `LLMProvider` (`llm/base.py`), `SessionStore` (`session.py`, same file as `InMemorySessionStore`), `EventSink` (`transport/base.py`). Implementations currently declare no base. `ty` already accepts them as their Protocol structurally (agent wiring passes), so nominal subclassing should conform. `fake.py`/`anthropic_provider.py` already import from `saddlery.llm.base` at runtime; `cli.py` imports from `saddlery.events` at runtime; `recording.py` imports `Event` only under `TYPE_CHECKING`.

---

## Task 1: Nominal Protocol conformance

**Files:**
- Create: `core/tests/test_seams_conformance.py`
- Modify: `core/saddlery/llm/fake.py`, `core/saddlery/llm/anthropic_provider.py`, `core/saddlery/session.py`, `core/saddlery/transport/cli.py`, `core/saddlery/transport/recording.py`

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_seams_conformance.py`:

```python
from __future__ import annotations

from saddlery.llm.anthropic_provider import AnthropicProvider
from saddlery.llm.base import LLMProvider
from saddlery.llm.fake import FakeProvider
from saddlery.session import InMemorySessionStore, SessionStore
from saddlery.transport.base import EventSink
from saddlery.transport.cli import CliSink
from saddlery.transport.recording import RecordingSink


def test_first_party_impls_nominally_subclass_their_protocol() -> None:
    # `in __mro__` checks *nominal* inheritance (not structural conformance,
    # which runtime_checkable issubclass would also accept).
    assert LLMProvider in FakeProvider.__mro__
    assert LLMProvider in AnthropicProvider.__mro__
    assert SessionStore in InMemorySessionStore.__mro__
    assert EventSink in CliSink.__mro__
    assert EventSink in RecordingSink.__mro__
```

- [ ] **Step 2: Run it to verify it fails**

Run (from `core/`): `uv run pytest tests/test_seams_conformance.py -q`
Expected: FAIL — `assert LLMProvider in FakeProvider.__mro__` is False (no nominal base yet).

- [ ] **Step 3: Add the Protocol bases**

In `core/saddlery/llm/fake.py`, change the runtime import and class line:
```python
from saddlery.llm.base import ProviderDelta, TextDelta
```
→
```python
from saddlery.llm.base import LLMProvider, ProviderDelta, TextDelta
```
and
```python
class FakeProvider:
```
→
```python
class FakeProvider(LLMProvider):
```

In `core/saddlery/llm/anthropic_provider.py`:
```python
from saddlery.llm.base import ProviderDelta, TextDelta
```
→
```python
from saddlery.llm.base import LLMProvider, ProviderDelta, TextDelta
```
and
```python
class AnthropicProvider:
```
→
```python
class AnthropicProvider(LLMProvider):
```

In `core/saddlery/session.py`, `SessionStore` is defined in the same file, so only the class line changes:
```python
class InMemorySessionStore:
```
→
```python
class InMemorySessionStore(SessionStore):
```

In `core/saddlery/transport/cli.py`, add a runtime import and change the class line. Change:
```python
from saddlery.events import AssistantMessageDelta, ErrorEvent, Event, RunFinished
```
→
```python
from saddlery.events import AssistantMessageDelta, ErrorEvent, Event, RunFinished
from saddlery.transport.base import EventSink
```
and
```python
class CliSink:
```
→
```python
class CliSink(EventSink):
```

In `core/saddlery/transport/recording.py`, add a runtime import (it currently imports `Event` only under `TYPE_CHECKING`). Change:
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from saddlery.events import Event
```
→
```python
from typing import TYPE_CHECKING

from saddlery.transport.base import EventSink

if TYPE_CHECKING:
    from saddlery.events import Event
```
and
```python
class RecordingSink:
```
→
```python
class RecordingSink(EventSink):
```

- [ ] **Step 4: Run the conformance test**

Run (from `core/`): `uv run pytest tests/test_seams_conformance.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Run the full gate (ty verifies conformance; existing tests verify no breakage)**

Run (from `core/`): `uv run ruff check . && uv run ty check && uv run pytest -q`
Expected: ruff `All checks passed!`; ty `All checks passed!` (this is the conformance check — if it reports a signature mismatch on any impl, fix that impl's method signature to match its Protocol, do not weaken the Protocol); all tests pass.

If `ruff format --check .` flags anything, run `uv run ruff format .` and re-check.

- [ ] **Step 6: Commit**

```bash
git add core/saddlery/ core/tests/test_seams_conformance.py
git commit -m "refactor(seams): declare nominal Protocol conformance on first-party impls"
```

---

## Task 2: `_group_key` + `reorder_class_diagram` (TDD)

**Files:**
- Modify: `core/scripts/gen_diagrams.py`
- Modify: `core/tests/test_gen_diagrams.py`

- [ ] **Step 1: Write the failing tests**

Append to `core/tests/test_gen_diagrams.py` (and add `_group_key, reorder_class_diagram` to the existing `from scripts.gen_diagrams import ...` line, keeping it sorted):

```python
def test_group_key_extracts_component_after_saddlery() -> None:
    assert _group_key("saddlery.events") == "events"
    assert _group_key("saddlery.llm.base") == "llm"
    assert _group_key("saddlery.transport.cli") == "transport"
    assert _group_key("saddlery") == ""
    assert _group_key("other.mod") == ""


def test_reorder_puts_relationships_first() -> None:
    mmd = (
        "classDiagram\n"
        "  class Agent {\n    model : str\n  }\n"
        "  class LLMProvider {\n    stream() None\n  }\n"
        "  Agent --> LLMProvider : provider\n"
    )
    out = reorder_class_diagram(
        mmd, {"Agent": "saddlery.agent", "LLMProvider": "saddlery.llm.base"}
    )
    lines = out.splitlines()
    assert lines[0] == "classDiagram"
    assert lines[1].strip() == "Agent --> LLMProvider : provider"
    assert out.index("Agent --> LLMProvider") < out.index("class Agent")


def test_reorder_groups_by_module_flow_order() -> None:
    mmd = (
        "classDiagram\n"
        "  class BaseEvent {\n    id : str\n  }\n"
        "  class Agent {\n    model : str\n  }\n"
        "  class LLMProvider {\n    stream() None\n  }\n"
    )
    class_module = {
        "BaseEvent": "saddlery.events",
        "Agent": "saddlery.agent",
        "LLMProvider": "saddlery.llm.base",
    }
    out = reorder_class_diagram(mmd, class_module)
    assert out.index("class Agent") < out.index("class LLMProvider") < out.index("class BaseEvent")


def test_reorder_unknown_module_goes_last() -> None:
    mmd = (
        "classDiagram\n"
        "  class Agent {\n    model : str\n  }\n"
        "  class Mystery {\n    x : int\n  }\n"
    )
    out = reorder_class_diagram(mmd, {"Agent": "saddlery.agent"})
    assert out.index("class Agent") < out.index("class Mystery")
```

- [ ] **Step 2: Run to verify they fail**

Run (from `core/`): `uv run pytest tests/test_gen_diagrams.py -q`
Expected: FAIL — `ImportError: cannot import name '_group_key'`.

- [ ] **Step 3: Implement the functions**

In `core/scripts/gen_diagrams.py`, add the constant near the other module constants:

```python
GROUP_ORDER: list[str] = ["agent", "llm", "session", "transport", "events", "messages"]
```

and add these functions (place them above `main()`):

```python
def _group_key(module: str) -> str:
    """The sub-package under `saddlery` (e.g. 'saddlery.llm.base' -> 'llm')."""
    prefix = "saddlery."
    if not module.startswith(prefix):
        return ""
    return module[len(prefix) :].split(".")[0]


def reorder_class_diagram(mmd: str, class_module: dict[str, str]) -> str:
    """Reshape pyreverse Mermaid: relationships first, then classes grouped by module.

    Class blocks are ordered by `GROUP_ORDER` (unknown modules last), then by name.
    Relationship lines keep pyreverse's order and move above the class blocks.
    """
    lines = mmd.splitlines()
    blocks: list[tuple[str, list[str]]] = []
    rels: list[str] = []
    i = 0
    while i < len(lines) and lines[i].strip() != "classDiagram":
        i += 1
    i += 1  # skip the header
    while i < len(lines):
        line = lines[i]
        match = re.match(r"\s*class\s+(\w+)", line)
        if match:
            block = [line]
            i += 1
            if "{" in line and "}" not in line:
                while i < len(lines) and "}" not in lines[i]:
                    block.append(lines[i])
                    i += 1
                if i < len(lines):
                    block.append(lines[i])
                    i += 1
            blocks.append((match.group(1), block))
        elif line.strip():
            rels.append(line)
            i += 1
        else:
            i += 1

    def rank(name: str) -> int:
        key = _group_key(class_module.get(name, ""))
        return GROUP_ORDER.index(key) if key in GROUP_ORDER else len(GROUP_ORDER)

    blocks.sort(key=lambda nb: (rank(nb[0]), nb[0]))
    out = ["classDiagram", *rels]
    for _, block in blocks:
        out.extend(block)
    return "\n".join(out) + "\n"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run (from `core/`): `uv run pytest tests/test_gen_diagrams.py -q`
Expected: PASS (all tests, including the 4 new ones).

- [ ] **Step 5: Run the gate**

Run (from `core/`): `uv run ruff format --check . && uv run ruff check . && uv run ty check`
Expected: clean; `All checks passed!` for ruff and ty. (If format flags, run `uv run ruff format .` and re-check.)

- [ ] **Step 6: Commit**

```bash
git add core/scripts/gen_diagrams.py core/tests/test_gen_diagrams.py
git commit -m "feat(scripts): reorder class diagram — relationships first, grouped by module"
```

---

## Task 3: Wire `main()` + regenerate the diagram

**Files:**
- Modify: `core/scripts/gen_diagrams.py`
- Modify: `core/tests/test_gen_diagrams.py`
- Modify (regenerated): `docs/diagrams/class-core.md`

- [ ] **Step 1: Write a failing test for the module map**

Append to `core/tests/test_gen_diagrams.py` (add `_saddlery_class_modules` to the `from scripts.gen_diagrams import ...` line):

```python
def test_saddlery_class_modules_maps_known_classes() -> None:
    mapping = _saddlery_class_modules()
    assert mapping["Agent"] == "saddlery.agent"
    assert mapping["LLMProvider"] == "saddlery.llm.base"
    assert mapping["BaseEvent"] == "saddlery.events"
```

- [ ] **Step 2: Run to verify it fails**

Run (from `core/`): `uv run pytest tests/test_gen_diagrams.py::test_saddlery_class_modules_maps_known_classes -q`
Expected: FAIL — `ImportError: cannot import name '_saddlery_class_modules'`.

- [ ] **Step 3: Implement `_saddlery_class_modules` and wire `main()`**

In `core/scripts/gen_diagrams.py`, add these imports at the top (with the other stdlib imports; ruff will sort):

```python
import importlib
import inspect
import pkgutil
```

Add the helper (place it above `main()`):

```python
def _saddlery_class_modules() -> dict[str, str]:
    """Map each saddlery class name to the module that defines it."""
    import saddlery

    mapping: dict[str, str] = {}
    for info in pkgutil.walk_packages(saddlery.__path__, prefix="saddlery."):
        module = importlib.import_module(info.name)
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ == info.name:
                mapping[name] = obj.__module__
    return mapping
```

Change `main()` to reorder the class diagram before wrapping:

```python
def main() -> None:
    DIAGRAMS_DIR.mkdir(parents=True, exist_ok=True)
    ordered = reorder_class_diagram(_pyreverse_class_mmd(), _saddlery_class_modules())
    (DIAGRAMS_DIR / "class-core.md").write_text(render_class_md(ordered))
    (DIAGRAMS_DIR / "events-er.md").write_text(
        _wrap_md("Core data model (events + messages)", render_er(ER_MODELS))
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run (from `core/`): `uv run pytest tests/test_gen_diagrams.py -q`
Expected: PASS (all tests).

- [ ] **Step 5: Regenerate the diagram**

Run (from `core/`): `uv run python scripts/gen_diagrams.py`
Then open `docs/diagrams/class-core.md` and confirm:
  - The relationship lines appear immediately after `classDiagram` (before any `class` block).
  - The new Protocol edges are present: `AnthropicProvider --|> LLMProvider`, `FakeProvider --|> LLMProvider`, `CliSink --|> EventSink`, `RecordingSink --|> EventSink`, `InMemorySessionStore --|> SessionStore`.
  - Class blocks are grouped in flow order: `agent` classes, then `llm`, `session`, `transport`, `events`, `messages`.

- [ ] **Step 6: Run the full gate**

Run (from `core/`): `uv run ruff format --check . && uv run ruff check . && uv run ty check && uv run pytest -q`
Expected: all clean/passing.

- [ ] **Step 7: Commit (code + regenerated diagram)**

```bash
git add core/scripts/gen_diagrams.py core/tests/test_gen_diagrams.py docs/diagrams/class-core.md
git commit -m "feat(scripts): group + order class diagram; regenerate with Protocol edges"
```

- [ ] **Step 8: Push and confirm CI**

```bash
git push -u origin mark/mm-30-class-diagram
```
Then: `gh run list --branch mark/mm-30-class-diagram --workflow python-core.yml --limit 1` and watch it (`gh run watch <run-id> --exit-status`). Expected: `check (3.12)` and `check (3.14)` pass, including the `diagrams (smoke)` step.

---

## Self-review notes

- **Spec coverage:** §4 nominal conformance (5 classes) → Task 1; §5 `_group_key`/`GROUP_ORDER`/`reorder_class_diagram` → Task 2; §5 `_saddlery_class_modules` + `main()` wiring → Task 3; §6 regenerate → Task 3 Step 5; §7 testing (reorder relationships-first / flow-order / unknown-last / `_group_key` / conformance) → Tasks 1-3; §8 success criteria → Task 1 Step 5 + Task 3 Steps 5-6, 8.
- **Type consistency:** `_group_key(str) -> str`, `reorder_class_diagram(str, dict[str, str]) -> str`, `_saddlery_class_modules() -> dict[str, str]`, `GROUP_ORDER: list[str]`, `main() -> None` — consistent across Tasks 2-3.
- **Sequencing:** Task 1 (Protocol edges exist) and Task 2 (reorder) both precede Task 3's regeneration, so the committed `class-core.md` reflects both.
- **No behavior change:** Task 1 adds only nominal bases; existing tests + `ty` conformance guard it. Generator changes don't touch `saddlery` runtime.

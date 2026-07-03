"""Generate Mermaid diagrams for the saddlery core.

Pure render functions are unit-tested; `main()` shells to pyreverse and writes
markdown files, and is covered by the CI smoke run.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic import BaseModel


def _type_token(annotation: str) -> str:
    """Collapse a (string) annotation into a Mermaid-safe attribute type token."""
    token = re.sub(r"\W+", "_", annotation).strip("_")
    return token or "object"


def _own_annotations(model: type[BaseModel]) -> dict[str, str]:
    """Only the fields declared on `model` itself (not inherited).

    Modules use `from __future__ import annotations`, so values are strings.
    """
    return dict(model.__dict__.get("__annotations__", {}))


def render_er(models: Sequence[type[BaseModel]]) -> str:
    """Render the given models as a Mermaid `erDiagram`.

    Each model becomes an entity listing its own fields; a model whose base is
    also in `models` gets an `is a` relationship to that base.
    """
    listed = set(models)
    lines = ["erDiagram"]
    for model in models:
        lines.append(f"  {model.__name__} {{")
        for name, annotation in _own_annotations(model).items():
            lines.append(f"    {_type_token(annotation)} {name}")
        lines.append("  }")
    for model in models:
        parent = next((b for b in model.__mro__[1:] if b in listed), None)
        if parent is not None:
            lines.append(f'  {parent.__name__} ||--|| {model.__name__} : "is a"')
    return "\n".join(lines) + "\n"

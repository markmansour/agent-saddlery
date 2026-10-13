"""ToolRegistry rejects tools that do not declare a valid capability."""

from __future__ import annotations

from typing import Any, ClassVar

import pytest

from saddlery.tools.registry import ToolRegistry


class _T:
    name = "t"
    description = "d"
    input_schema: ClassVar[dict] = {"type": "object", "properties": {}}

    async def call(self, arguments):  # pragma: no cover - never called
        raise AssertionError


def _untyped(tool: object) -> Any:
    return tool


def test_registry_rejects_tool_without_capability():
    with pytest.raises(ValueError, match="capability"):
        ToolRegistry([_untyped(_T())])


def test_registry_rejects_invalid_capability():
    tool: Any = _T()
    tool.capability = "sideways"
    with pytest.raises(ValueError, match="sideways"):
        ToolRegistry([tool])


def test_registry_accepts_each_valid_capability():
    for cap in ("read", "write", "exec", "network"):
        tool: Any = _T()
        tool.capability = cap
        assert ToolRegistry([tool]).get("t") is tool

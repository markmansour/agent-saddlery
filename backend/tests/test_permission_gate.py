"""Tests for PermissionGate: deny/allow/ask evaluation order."""

from __future__ import annotations

from saddlery.permissions.gate import PermissionGate


async def test_deny_wins_even_when_also_allowed():
    """Deny always wins, even if the same tool is also in the allow set."""
    gate = PermissionGate(allow={"write_file"}, deny={"write_file"})
    decision = await gate.check("write_file", {}, "local")
    assert decision == "deny"


async def test_allow_list_resolves_to_allow():
    gate = PermissionGate(allow={"read_file"}, deny=set())
    decision = await gate.check("read_file", {}, "local")
    assert decision == "allow"


async def test_unlisted_tool_falls_through_to_ask():
    gate = PermissionGate(allow=set(), deny=set())
    decision = await gate.check("write_file", {}, "local")
    assert decision == "ask"


async def test_deny_list_resolves_to_deny():
    gate = PermissionGate(allow=set(), deny={"shell"})
    decision = await gate.check("shell", {}, "local")
    assert decision == "deny"

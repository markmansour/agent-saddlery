"""Tests for PermissionGate: deny/allow/ask evaluation order."""

from __future__ import annotations

from saddlery.permissions.gate import HookResult, PermissionGate


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


async def test_hook_deny_overrides_allow_list():
    """A hook returning 'deny' wins even though the tool is in the allow list."""

    def always_deny(tool_name: str, arguments: dict, principal: str) -> HookResult:
        return "deny"

    gate = PermissionGate(allow={"write_file"}, deny=set(), hooks=[always_deny])
    decision = await gate.check("write_file", {}, "local")
    assert decision == "deny"


async def test_hook_pass_falls_through_to_deny_list():
    """A hook returning 'pass' means 'no opinion' — the deny list still applies."""

    def no_opinion(tool_name: str, arguments: dict, principal: str) -> HookResult:
        return "pass"

    gate = PermissionGate(allow=set(), deny={"shell"}, hooks=[no_opinion])
    decision = await gate.check("shell", {}, "local")
    assert decision == "deny"


async def test_hook_ask_short_circuits_even_with_allow_match():
    """A hook returning 'ask' wins over an allow-list match — hooks run first."""

    def force_ask(tool_name: str, arguments: dict, principal: str) -> HookResult:
        return "ask"

    gate = PermissionGate(allow={"write_file"}, deny=set(), hooks=[force_ask])
    decision = await gate.check("write_file", {}, "local")
    assert decision == "ask"


async def test_no_hooks_behaves_like_task_2():
    """hooks=None (the default) skips hook evaluation entirely."""
    gate = PermissionGate(allow={"read_file"}, deny=set())
    decision = await gate.check("read_file", {}, "local")
    assert decision == "allow"

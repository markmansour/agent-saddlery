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


async def test_remembered_decision_short_circuits_future_checks():
    """Once a decision is remembered for (principal, tool_name), check() returns it directly."""
    gate = PermissionGate(allow=set(), deny=set())  # unlisted -> would normally ask

    gate.remember("write_file", "local", "allow")
    decision = await gate.check("write_file", {}, "local")

    assert decision == "allow"


async def test_remembered_decision_is_scoped_per_principal():
    """A decision remembered for one principal does not apply to another."""
    gate = PermissionGate(allow=set(), deny=set())

    gate.remember("write_file", "local", "allow")
    decision = await gate.check("write_file", {}, "other-user")

    assert decision == "ask"  # not remembered for this principal


async def test_remembered_decision_is_scoped_per_tool():
    """A decision remembered for one tool does not apply to another tool."""
    gate = PermissionGate(allow=set(), deny=set())

    gate.remember("write_file", "local", "allow")
    decision = await gate.check("shell", {}, "local")

    assert decision == "ask"  # different tool, not remembered


async def test_remembered_deny_short_circuits_future_checks():
    gate = PermissionGate(allow={"write_file"}, deny=set())  # would normally allow

    gate.remember("write_file", "local", "deny")
    decision = await gate.check("write_file", {}, "local")

    assert decision == "deny"


async def test_hook_deny_beats_remembered_allow():
    """Approving a tool once must not switch off hooks: hooks still run first."""

    def protect_git(tool_name: str, arguments: dict, principal: str) -> HookResult:
        if tool_name == "write_file" and str(arguments.get("path", "")).startswith(".git/"):
            return "deny"
        return "pass"

    gate = PermissionGate(allow=set(), deny=set(), hooks=[protect_git])
    gate.remember("write_file", "local", "allow")  # the user approved a write earlier

    assert await gate.check("write_file", {"path": "a.txt"}, "local") == "allow"
    assert await gate.check("write_file", {"path": ".git/config"}, "local") == "deny"


async def test_deny_list_beats_remembered_allow():
    """Deny always wins, including over a remembered allow."""
    gate = PermissionGate(allow=set(), deny={"write_file"})
    gate.remember("write_file", "local", "allow")

    assert await gate.check("write_file", {}, "local") == "deny"

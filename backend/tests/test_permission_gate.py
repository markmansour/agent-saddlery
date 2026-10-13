"""PermissionGate: deny → hooks → remembered → allow (taint-aware) → class default → ask."""

from __future__ import annotations

from typing import cast

from saddlery.permissions.gate import Hook, HookResult, PermissionGate, PolicyRequest
from saddlery.permissions.rules import Rule
from saddlery.permissions.shell import classify


def req(
    tool="write_file",
    *,
    capability="write",
    resource=("a.txt",),
    arguments=None,
    principal="local",
    tainted=False,
    detail=None,
) -> PolicyRequest:
    return PolicyRequest(
        tool_name=tool,
        arguments=arguments or {},
        principal=principal,
        capability=capability,
        resource=resource,
        tainted=tainted,
        detail=detail,
    )


def shell_req(raw: str, **kwargs) -> PolicyRequest:
    cmd = classify(raw)
    return req("shell", capability="exec", resource=cmd.argv or (), detail=cmd, **kwargs)


# --- static rules and class defaults -------------------------------------------------


async def test_deny_wins_even_when_also_allowed():
    gate = PermissionGate(allow={"write_file"}, deny={"write_file"})
    assert await gate.check(req()) == "deny"


async def test_allow_list_resolves_to_allow():
    gate = PermissionGate(allow={"read_file"})
    assert await gate.check(req("read_file", capability="read")) == "allow"


async def test_unlisted_write_asks():
    assert await PermissionGate().check(req()) == "ask"


async def test_unlisted_exec_asks():
    assert await PermissionGate().check(req("shell", capability="exec")) == "ask"


async def test_unlisted_read_is_allowed_by_class_default():
    assert await PermissionGate().check(req("read_file", capability="read")) == "allow"


async def test_deny_list_resolves_to_deny():
    assert await PermissionGate(deny={"shell"}).check(req("shell", capability="exec")) == "deny"


async def test_scoped_deny_blocks_under_prefix_only():
    gate = PermissionGate(allow={"write_file"}, deny=[Rule("write_file", ("docs",))])
    assert await gate.check(req(resource=("docs", "a.md"))) == "deny"
    assert await gate.check(req(resource=("docs-private", "a.md"))) == "allow"


async def test_scoped_deny_matches_case_variants():
    gate = PermissionGate(allow={"write_file"}, deny=[Rule("write_file", ("docs",))])
    assert await gate.check(req(resource=("Docs", "A.md"))) == "deny"


async def test_scoped_allow_does_not_allow_other_resources():
    gate = PermissionGate(allow=[Rule("shell", ("git", "status"))])
    assert await gate.check(shell_req("git status -s")) == "allow"
    assert await gate.check(shell_req("git push")) == "ask"


# --- hooks ----------------------------------------------------------------------------


async def test_hook_deny_overrides_allow_list():
    def always_deny(request: PolicyRequest) -> HookResult:
        return "deny"

    gate = PermissionGate(allow={"write_file"}, hooks=[always_deny])
    assert await gate.check(req()) == "deny"


async def test_hook_pass_falls_through_to_the_rest():
    def no_opinion(request: PolicyRequest) -> HookResult:
        return "pass"

    gate = PermissionGate(allow={"write_file"}, hooks=[no_opinion])
    assert await gate.check(req()) == "allow"


async def test_hook_ask_wins_over_allow_match():
    def force_ask(request: PolicyRequest) -> HookResult:
        return "ask"

    gate = PermissionGate(allow={"write_file"}, hooks=[force_ask])
    assert await gate.check(req()) == "ask"


async def test_hook_allow_cannot_override_static_deny():
    def always_allow(request: PolicyRequest) -> HookResult:
        return "allow"

    gate = PermissionGate(deny=[Rule("shell", ("rm", "-rf"))], hooks=[always_allow])
    assert await gate.check(shell_req("rm -rf /")) == "deny"


async def test_hook_sees_the_whole_request_including_taint():
    seen: list[PolicyRequest] = []

    def spy(request: PolicyRequest) -> HookResult:
        seen.append(request)
        return "pass"

    gate = PermissionGate(hooks=[spy])
    request = req(tainted=True)
    await gate.check(request)
    assert seen == [request]
    assert seen[0].tainted is True


# --- remembered decisions -------------------------------------------------------------


async def test_remembered_allow_short_circuits_ask():
    gate = PermissionGate()
    gate.remember(req(), "allow")
    assert await gate.check(req()) == "allow"


async def test_remembered_decision_is_scoped_per_principal():
    gate = PermissionGate()
    gate.remember(req(), "allow")
    assert await gate.check(req(principal="other")) == "ask"


async def test_remembered_decision_is_scoped_per_tool():
    gate = PermissionGate()
    gate.remember(req(), "allow")
    assert await gate.check(req("other_tool")) == "ask"


async def test_remembered_decision_is_scoped_per_exact_resource():
    gate = PermissionGate()
    gate.remember(req(resource=("a.txt",)), "allow")
    assert await gate.check(req(resource=("a.txt",))) == "allow"
    assert await gate.check(req(resource=("b.txt",))) == "ask"
    assert await gate.check(req(resource=("a.txt", "x"))) == "ask"


async def test_remembered_deny_beats_allow_list():
    gate = PermissionGate(allow={"write_file"})
    gate.remember(req(), "deny")
    assert await gate.check(req()) == "deny"


async def test_hook_deny_beats_remembered_allow():
    def protect_git(request: PolicyRequest) -> HookResult:
        if str(request.arguments.get("path", "")).startswith(".git/"):
            return "deny"
        return "pass"

    gate = PermissionGate(hooks=[protect_git])
    gate.remember(req(arguments={"path": "a.txt"}), "allow")
    assert await gate.check(req(arguments={"path": "a.txt"})) == "allow"
    gate.remember(req(arguments={"path": ".git/config"}, resource=("a.txt",)), "allow")
    assert await gate.check(req(arguments={"path": ".git/config"})) == "deny"


async def test_static_deny_beats_remembered_allow():
    gate = PermissionGate(deny={"write_file"})
    gate.remember(req(), "allow")
    assert await gate.check(req()) == "deny"


async def test_exec_decisions_are_never_remembered():
    gate = PermissionGate()
    request = shell_req("git push")
    gate.remember(request, "allow")
    assert await gate.check(request) == "ask"


async def test_network_decisions_are_never_remembered():
    gate = PermissionGate()
    request = req("fetch", capability="network", resource=("example.com",))
    gate.remember(request, "allow")
    assert await gate.check(request) == "ask"


# --- taint ----------------------------------------------------------------------------


async def test_tainted_write_allow_match_downgrades_to_ask():
    gate = PermissionGate(allow={"write_file"})
    assert await gate.check(req(tainted=False)) == "allow"
    assert await gate.check(req(tainted=True)) == "ask"


async def test_tainted_exec_allow_match_downgrades_to_ask():
    gate = PermissionGate(allow=[Rule("shell", ("pytest",))])
    assert await gate.check(shell_req("pytest -x")) == "allow"
    assert await gate.check(shell_req("pytest -x", tainted=True)) == "ask"


async def test_tainted_read_stays_allowed():
    gate = PermissionGate(allow={"read_file"})
    assert await gate.check(req("read_file", capability="read", tainted=True)) == "allow"
    assert (
        await PermissionGate().check(req("read_file", capability="read", tainted=True)) == "allow"
    )


async def test_tainted_does_not_weaken_deny():
    gate = PermissionGate(deny={"write_file"})
    assert await gate.check(req(tainted=True)) == "deny"


async def test_remembered_decision_applies_while_tainted():
    gate = PermissionGate()
    gate.remember(req(), "allow")
    assert await gate.check(req(tainted=True)) == "allow"


# --- shell specifics ------------------------------------------------------------------


async def test_rejected_shell_command_is_denied():
    gate = PermissionGate(allow={"shell"})
    assert await gate.check(shell_req("ls; rm -rf ~")) == "deny"


async def test_rejected_shell_command_cannot_be_rescued_by_a_hook():
    def always_allow(request: PolicyRequest) -> HookResult:
        return "allow"

    gate = PermissionGate(hooks=[always_allow])
    assert await gate.check(shell_req("echo `id`")) == "deny"


async def test_deny_rule_sees_inside_bash_dash_c():
    gate = PermissionGate(deny=[Rule("shell", ("rm", "-rf"))])
    assert await gate.check(shell_req('bash -c "rm -rf /"')) == "deny"
    assert await gate.check(shell_req('sh -c "ls; rm -rf /"')) == "deny"


async def test_deny_rule_does_not_block_unrelated_shell_commands():
    gate = PermissionGate(deny=[Rule("shell", ("rm", "-rf"))])
    assert await gate.check(shell_req("ls -la")) == "ask"


# --- out-of-contract hook results -----------------------------------------------------


async def test_hook_returning_none_fails_closed():
    gate = PermissionGate(allow={"write_file"}, hooks=[cast("Hook", lambda r: None)])
    assert await gate.check(req()) == "deny"


async def test_hook_returning_a_typo_fails_closed():
    gate = PermissionGate(allow={"write_file"}, hooks=[cast("Hook", lambda r: "Deny")])
    assert await gate.check(req()) == "deny"

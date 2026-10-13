"""Rules match a tool plus a token prefix of the call's resource."""

from __future__ import annotations

from saddlery.permissions.rules import Rule, as_rule


def test_bare_rule_matches_every_resource_of_the_tool():
    rule = Rule("write_file")
    assert rule.matches("write_file", ("a.txt",), role="allow")
    assert rule.matches("write_file", (), role="allow")
    assert not rule.matches("read_file", ("a.txt",), role="allow")


def test_prefix_rule_matches_under_the_prefix():
    rule = Rule("write_file", ("docs",))
    assert rule.matches("write_file", ("docs", "a.md"), role="allow")
    assert rule.matches("write_file", ("docs",), role="allow")
    assert not rule.matches("write_file", ("src", "a.md"), role="allow")


def test_prefix_rule_matches_whole_tokens_only():
    rule = Rule("write_file", ("docs",))
    assert not rule.matches("write_file", ("docs-private", "a.md"), role="allow")


def test_matching_folds_case_and_unicode():
    rule = Rule("write_file", ("docs",))
    assert rule.matches("write_file", ("Docs", "A.md"), role="allow")
    assert Rule("write_file", ("café",)).matches("write_file", ("café", "x"), role="allow")


def test_shell_argv_prefix():
    rule = Rule("shell", ("git", "status"))
    assert rule.matches("shell", ("git", "status", "-s"), role="allow")
    assert not rule.matches("shell", ("git", "push"), role="allow")
    assert not rule.matches("shell", ("git",), role="allow")


def test_as_rule_wraps_a_bare_tool_name():
    assert as_rule("read_file") == Rule("read_file")
    rule = Rule("shell", ("ls",))
    assert as_rule(rule) is rule


# --- folding is scoped: deny rules and path-tool allow rules fold; other allows are exact ---


def test_shell_allow_rule_is_case_sensitive():
    rule = Rule("shell", ("git", "branch", "-d"))
    assert rule.matches("shell", ("git", "branch", "-d", "main"), role="allow")
    assert not rule.matches("shell", ("git", "branch", "-D", "main"), role="allow")


def test_shell_deny_rule_folds_case():
    assert Rule("shell", ("rm",)).matches("shell", ("RM", "-rf", "x"), role="deny")


def test_path_tool_allow_rule_folds_case():
    assert Rule("write_file", ("docs",)).matches("write_file", ("Docs", "A.md"), role="allow")


def test_path_tool_deny_rule_folds_case():
    assert Rule("write_file", ("docs",)).matches("write_file", ("DOCS",), role="deny")


def test_path_tools_defined_once():
    from saddlery.permissions import config, rules

    assert config.PATH_TOOLS is rules.PATH_TOOLS

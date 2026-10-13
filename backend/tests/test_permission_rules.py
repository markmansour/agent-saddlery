"""Rules match a tool plus a token prefix of the call's resource."""

from __future__ import annotations

from saddlery.permissions.rules import Rule, as_rule


def test_bare_rule_matches_every_resource_of_the_tool():
    rule = Rule("write_file")
    assert rule.matches("write_file", ("a.txt",))
    assert rule.matches("write_file", ())
    assert not rule.matches("read_file", ("a.txt",))


def test_prefix_rule_matches_under_the_prefix():
    rule = Rule("write_file", ("docs",))
    assert rule.matches("write_file", ("docs", "a.md"))
    assert rule.matches("write_file", ("docs",))
    assert not rule.matches("write_file", ("src", "a.md"))


def test_prefix_rule_matches_whole_tokens_only():
    rule = Rule("write_file", ("docs",))
    assert not rule.matches("write_file", ("docs-private", "a.md"))


def test_matching_folds_case_and_unicode():
    rule = Rule("write_file", ("docs",))
    assert rule.matches("write_file", ("Docs", "A.md"))
    assert Rule("write_file", ("café",)).matches("write_file", ("café", "x"))


def test_shell_argv_prefix():
    rule = Rule("shell", ("git", "status"))
    assert rule.matches("shell", ("git", "status", "-s"))
    assert not rule.matches("shell", ("git", "push"))
    assert not rule.matches("shell", ("git",))


def test_as_rule_wraps_a_bare_tool_name():
    assert as_rule("read_file") == Rule("read_file")
    rule = Rule("shell", ("ls",))
    assert as_rule(rule) is rule

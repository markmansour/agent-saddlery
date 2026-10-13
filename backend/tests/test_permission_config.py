"""Loading and validating .saddlery/permissions.json."""

from __future__ import annotations

import json

import pytest

from saddlery.permissions.config import ConfigError, load_permission_config
from saddlery.permissions.rules import Rule


def _write(tmp_path, data):
    path = tmp_path / "permissions.json"
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return path


def test_bare_tool_names_become_whole_tool_rules(tmp_path):
    cfg = load_permission_config(_write(tmp_path, {"allow": ["read_file"], "deny": ["shell"]}))
    assert cfg.allow == (Rule("read_file"),)
    assert cfg.deny == (Rule("shell"),)


def test_scoped_rules(tmp_path):
    data = {
        "allow": [{"tool": "shell", "match": ["git", "status"]}],
        "deny": [{"tool": "write_file", "match": ["docs"]}],
    }
    cfg = load_permission_config(_write(tmp_path, data))
    assert cfg.allow == (Rule("shell", ("git", "status")),)
    assert cfg.deny == (Rule("write_file", ("docs",)),)


def test_missing_file_gives_empty_config(tmp_path):
    cfg = load_permission_config(tmp_path / "nope.json")
    assert cfg.allow == () and cfg.deny == ()


def test_empty_object_gives_empty_config(tmp_path):
    cfg = load_permission_config(_write(tmp_path, {}))
    assert cfg.allow == () and cfg.deny == ()


@pytest.mark.parametrize(
    "data",
    [
        "{not json",
        "[]",
        {"allow": "read_file"},
        {"deny": [3]},
        {"allow": [{"match": ["ls"]}]},
        {"allow": [{"tool": "shell", "match": []}]},
        {"allow": [{"tool": "shell", "match": ["ls", ""]}]},
        {"allow": [{"tool": "shell", "match": "ls"}]},
        {"allow": [{"tool": "shell", "match": ["ls"], "surprise": True}]},
        {"allow": [{"tool": "write_file", "match": ["docs/a.md"]}]},
        {"allow": [{"tool": "write_file", "match": [".."]}]},
        {"allow": [{"tool": "write_file", "match": ["/etc"]}]},
        {"surprise": []},
    ],
)
def test_invalid_config_fails_startup(tmp_path, data):
    with pytest.raises(ConfigError):
        load_permission_config(_write(tmp_path, data))


def test_unknown_tool_fails_when_known_tools_given(tmp_path):
    path = _write(tmp_path, {"allow": ["wrte_file"]})
    with pytest.raises(ConfigError, match="wrte_file"):
        load_permission_config(path, known_tools={"read_file", "write_file"})


def test_known_tool_passes(tmp_path):
    path = _write(tmp_path, {"allow": ["write_file"]})
    cfg = load_permission_config(path, known_tools={"read_file", "write_file"})
    assert cfg.allow == (Rule("write_file"),)


@pytest.mark.parametrize("executor", ["bash", "python", "find", "sudo", "env", "xargs", "Python"])
def test_single_token_executor_allow_needs_opt_in(tmp_path, executor):
    path = _write(tmp_path, {"allow": [{"tool": "shell", "match": [executor]}]})
    with pytest.raises(ConfigError, match="unsafe_broad_allow"):
        load_permission_config(path)


def test_single_token_executor_allow_with_opt_in_loads(tmp_path):
    data = {"allow": [{"tool": "shell", "match": ["python"], "unsafe_broad_allow": True}]}
    cfg = load_permission_config(_write(tmp_path, data))
    assert cfg.allow == (Rule("shell", ("python",)),)


def test_two_token_executor_rule_is_fine(tmp_path):
    data = {"allow": [{"tool": "shell", "match": ["python", "-m", "pytest"]}]}
    assert load_permission_config(_write(tmp_path, data)).allow


def test_executor_deny_rule_is_fine(tmp_path):
    data = {"deny": [{"tool": "shell", "match": ["bash"]}]}
    assert load_permission_config(_write(tmp_path, data)).deny == (Rule("shell", ("bash",)),)

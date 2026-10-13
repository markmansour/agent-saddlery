import json

import pytest

from saddlery.agent import Agent
from saddlery.cli.input import parse_input_line
from saddlery.cli.main import build_agent
from saddlery.permissions.config import ConfigError
from saddlery.permissions.gate import PolicyRequest
from saddlery.tools.read_file import FileReadTool
from saddlery.tools.write_file import FileWriteTool


def test_parse_input_line_extracts_user_message():
    result = parse_input_line('{"type": "user_message", "content": "hello"}')
    assert result == ("user_message", {"content": "hello"})


def test_parse_input_line_extracts_permission_decision():
    result = parse_input_line(
        '{"type": "permission_decision", "tool_call_id": "call-1", "decision": "allow"}'
    )
    assert result == (
        "permission_decision",
        {"tool_call_id": "call-1", "decision": "allow"},
    )


def test_parse_input_line_returns_none_for_blank_line():
    assert parse_input_line("") is None
    assert parse_input_line("   ") is None


def test_parse_input_line_returns_none_for_malformed_json():
    assert parse_input_line("{not valid json") is None


def test_parse_input_line_returns_none_for_unknown_type():
    assert parse_input_line('{"type": "something_else"}') is None


def test_parse_input_line_returns_none_for_empty_user_message_content():
    result = parse_input_line('{"type": "user_message", "content": "   "}')
    assert result is None


def test_build_agent_returns_agent_with_default_model(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    agent = build_agent()
    assert isinstance(agent, Agent)
    assert agent.model == "claude-haiku-4-5"


def test_build_agent_registers_write_file_tool(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    agent = build_agent()
    assert agent.tools.get("write_file") is not None
    assert agent.tools.get("read_file") is not None


def test_build_agent_constructs_permission_gate(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    agent = build_agent()
    assert agent.permission_gate is not None


async def test_build_agent_roots_file_tools_at_saddlery_root(monkeypatch, tmp_path):
    """SADDLERY_ROOT, not the process cwd, decides where the file tools read and write."""
    (tmp_path / "hello.txt").write_text("hi there", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("SADDLERY_ROOT", str(tmp_path))
    monkeypatch.chdir(elsewhere)  # the TUI starts the backend in backend/, not the project

    agent = build_agent()

    read_tool = agent.tools.get("read_file")
    write_tool = agent.tools.get("write_file")
    assert isinstance(read_tool, FileReadTool)
    assert isinstance(write_tool, FileWriteTool)
    result = await read_tool.call({"path": "hello.txt"})
    assert not result.is_error
    assert result.content == "hi there"
    assert write_tool.root == tmp_path


async def test_build_agent_defaults_file_tool_root_to_cwd(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("SADDLERY_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)

    agent = build_agent()

    read_tool = agent.tools.get("read_file")
    assert isinstance(read_tool, FileReadTool)
    assert read_tool.root == tmp_path


def _write_perms(root, data):
    config_dir = root / ".saddlery"
    config_dir.mkdir()
    (config_dir / "permissions.json").write_text(
        data if isinstance(data, str) else json.dumps(data), encoding="utf-8"
    )


def _write_request(resource):
    return PolicyRequest(
        tool_name="write_file",
        arguments={},
        principal="local",
        capability="write",
        resource=resource,
        tainted=False,
    )


async def test_build_agent_loads_rules_from_the_root(monkeypatch, tmp_path):
    _write_perms(
        tmp_path, {"allow": ["write_file"], "deny": [{"tool": "write_file", "match": ["docs"]}]}
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("SADDLERY_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path.parent)  # config must come from the root, not the cwd

    gate = build_agent().permission_gate

    assert gate is not None
    assert await gate.check(_write_request(("src", "a.py"))) == "allow"
    assert await gate.check(_write_request(("docs", "a.md"))) == "deny"


def test_build_agent_fails_on_malformed_permissions(monkeypatch, tmp_path):
    _write_perms(tmp_path, "{not json")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("SADDLERY_ROOT", str(tmp_path))
    with pytest.raises(ConfigError):
        build_agent()


def test_build_agent_fails_on_rule_for_unknown_tool(monkeypatch, tmp_path):
    _write_perms(tmp_path, {"allow": ["wrte_file"]})
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("SADDLERY_ROOT", str(tmp_path))
    with pytest.raises(ConfigError, match="wrte_file"):
        build_agent()


async def test_amain_exits_2_and_reports_a_config_error(monkeypatch, tmp_path, capsys):
    from saddlery.cli import main as cli_main

    # configure_logging() would bind structlog globally to capsys's stream for later tests.
    monkeypatch.setattr(cli_main, "configure_logging", lambda: None)
    _write_perms(tmp_path, "{not json")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("SADDLERY_ROOT", str(tmp_path))

    assert await cli_main._amain() == 2
    assert "permissions config error" in capsys.readouterr().err


@pytest.mark.parametrize(
    "line",
    [
        '{"type": "permission_decision", "tool_call_id": "c1", "decision": "maybe"}',
        '{"type": "permission_decision", "tool_call_id": "c1", "decision": null}',
        '{"type": "permission_decision", "tool_call_id": "c1"}',
        '{"type": "permission_decision", "decision": "allow"}',
        '{"type": "permission_decision", "tool_call_id": 7, "decision": "allow"}',
    ],
)
def test_parse_input_line_rejects_invalid_permission_decisions(line):
    assert parse_input_line(line) is None


def test_parse_input_line_accepts_deny_decision():
    line = '{"type": "permission_decision", "tool_call_id": "c1", "decision": "deny"}'
    assert parse_input_line(line) == (
        "permission_decision",
        {"tool_call_id": "c1", "decision": "deny"},
    )

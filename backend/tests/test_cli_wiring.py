from saddlery.agent import Agent
from saddlery.cli.input import parse_input_line
from saddlery.cli.main import build_agent


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

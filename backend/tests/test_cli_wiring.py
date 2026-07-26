from saddlery.agent import Agent
from saddlery.cli.main import build_agent


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

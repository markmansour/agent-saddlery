from saddlery.agent import Agent
from saddlery.cli.main import build_agent


def test_build_agent_returns_agent_with_default_model(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    agent = build_agent()
    assert isinstance(agent, Agent)
    assert agent.model == "claude-haiku-4-5"

from __future__ import annotations

from saddlery.llm.anthropic_provider import AnthropicProvider
from saddlery.llm.base import LLMProvider
from saddlery.llm.fake import FakeProvider
from saddlery.session import InMemorySessionStore, SessionStore
from saddlery.transport.base import EventSink
from saddlery.transport.cli import CliSink
from saddlery.transport.recording import RecordingSink


def test_first_party_impls_nominally_subclass_their_protocol() -> None:
    # `in __mro__` checks *nominal* inheritance (not structural conformance,
    # which runtime_checkable issubclass would also accept).
    assert LLMProvider in FakeProvider.__mro__
    assert LLMProvider in AnthropicProvider.__mro__
    assert SessionStore in InMemorySessionStore.__mro__
    assert EventSink in CliSink.__mro__
    assert EventSink in RecordingSink.__mro__

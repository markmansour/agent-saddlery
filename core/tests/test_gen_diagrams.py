from __future__ import annotations

from saddlery.events import BaseEvent, ErrorEvent, UserMessage
from saddlery.messages import Message
from scripts.gen_diagrams import render_er


def test_render_er_emits_entities_fields_and_inheritance() -> None:
    out = render_er([BaseEvent, UserMessage, ErrorEvent, Message])

    assert out.startswith("erDiagram")
    # Base entity and its own fields (annotations are strings via __future__).
    assert "BaseEvent {" in out
    assert "str session_id" in out
    assert "datetime timestamp" in out
    # Subtype with its own fields.
    assert "UserMessage {" in out
    assert "str content" in out
    # Inheritance rendered as a relationship to the parent that is also in the list.
    assert 'BaseEvent ||--|| UserMessage : "is a"' in out
    assert 'BaseEvent ||--|| ErrorEvent : "is a"' in out
    # A model with no listed parent has no inheritance relation.
    assert "Message {" in out
    assert "|| Message :" not in out


def test_render_er_is_deterministic() -> None:
    models = [BaseEvent, UserMessage, Message]
    assert render_er(models) == render_er(models)

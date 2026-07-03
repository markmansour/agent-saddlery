from __future__ import annotations

from saddlery.events import BaseEvent, ErrorEvent, UserMessage
from saddlery.messages import Message
from scripts.gen_diagrams import (
    _group_key,
    _saddlery_class_modules,
    render_class_md,
    render_er,
    reorder_class_diagram,
)


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


def test_render_class_md_wraps_in_a_fenced_mermaid_block() -> None:
    out = render_class_md("classDiagram\n  class Agent")
    assert "```mermaid" in out
    assert "classDiagram" in out
    assert "do not edit" in out.lower()
    assert out.rstrip().endswith("```")


def test_group_key_extracts_component_after_saddlery() -> None:
    assert _group_key("saddlery.events") == "events"
    assert _group_key("saddlery.llm.base") == "llm"
    assert _group_key("saddlery.transport.cli") == "transport"
    assert _group_key("saddlery") == ""
    assert _group_key("other.mod") == ""


def test_reorder_puts_relationships_first() -> None:
    mmd = (
        "classDiagram\n"
        "  class Agent {\n    model : str\n  }\n"
        "  class LLMProvider {\n    stream() None\n  }\n"
        "  Agent --> LLMProvider : provider\n"
    )
    out = reorder_class_diagram(
        mmd, {"Agent": "saddlery.agent", "LLMProvider": "saddlery.llm.base"}
    )
    lines = out.splitlines()
    assert lines[0] == "classDiagram"
    assert lines[1].strip() == "Agent --> LLMProvider : provider"
    assert out.index("Agent --> LLMProvider") < out.index("class Agent")


def test_reorder_groups_by_module_flow_order() -> None:
    mmd = (
        "classDiagram\n"
        "  class BaseEvent {\n    id : str\n  }\n"
        "  class Agent {\n    model : str\n  }\n"
        "  class LLMProvider {\n    stream() None\n  }\n"
    )
    class_module = {
        "BaseEvent": "saddlery.events",
        "Agent": "saddlery.agent",
        "LLMProvider": "saddlery.llm.base",
    }
    out = reorder_class_diagram(mmd, class_module)
    assert out.index("class Agent") < out.index("class LLMProvider") < out.index("class BaseEvent")


def test_reorder_unknown_module_goes_last() -> None:
    mmd = (
        "classDiagram\n  class Agent {\n    model : str\n  }\n  class Mystery {\n    x : int\n  }\n"
    )
    out = reorder_class_diagram(mmd, {"Agent": "saddlery.agent"})
    assert out.index("class Agent") < out.index("class Mystery")


def test_saddlery_class_modules_maps_known_classes() -> None:
    mapping = _saddlery_class_modules()
    assert mapping["Agent"] == "saddlery.agent"
    assert mapping["LLMProvider"] == "saddlery.llm.base"
    assert mapping["BaseEvent"] == "saddlery.events"

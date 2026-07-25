from pydantic import TypeAdapter

from saddlery.messages import (
    ContentBlock,
    Message,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)


def test_message_with_plain_string_content():
    m = Message(role="user", content="hello")
    assert m.role == "user"
    assert m.content == "hello"


def test_message_with_text_block_list():
    blocks: list[ContentBlock] = [TextBlock(text="hello")]
    m = Message(role="assistant", content=blocks)
    assert m.role == "assistant"
    assert len(m.content) == 1
    assert isinstance(m.content[0], TextBlock)


def test_message_with_tool_use_block():
    blocks: list[ContentBlock] = [
        ToolUseBlock(id="t1", name="read_file", input={"path": "foo.txt"})
    ]
    m = Message(role="assistant", content=blocks)
    assert m.role == "assistant"
    assert len(m.content) == 1
    assert isinstance(m.content[0], ToolUseBlock)


def test_message_with_tool_result_block():
    blocks: list[ContentBlock] = [ToolResultBlock(tool_use_id="t1", content="file contents")]
    m = Message(role="user", content=blocks)
    assert m.role == "user"
    assert len(m.content) == 1
    assert isinstance(m.content[0], ToolResultBlock)
    assert m.content[0].is_error is False


def test_tool_result_block_with_error():
    block = ToolResultBlock(tool_use_id="t1", content="Error!", is_error=True)
    assert block.is_error is True


def test_message_with_mixed_blocks():
    blocks: list[ContentBlock] = [
        TextBlock(text="here's a file:"),
        ToolUseBlock(id="t1", name="read_file", input={"path": "foo.txt"}),
    ]
    m = Message(role="assistant", content=blocks)
    assert len(m.content) == 2
    assert isinstance(m.content[0], TextBlock)
    assert isinstance(m.content[1], ToolUseBlock)


def test_message_roundtrip_plain_content():
    original = Message(role="user", content="hello")
    json_str = original.model_dump_json()
    parsed = Message.model_validate_json(json_str)
    assert parsed.role == "user"
    assert parsed.content == "hello"


def test_message_roundtrip_block_list():
    block_content: list[ContentBlock] = [
        ToolUseBlock(id="t1", name="read_file", input={"path": "foo.txt"}),
    ]
    original = Message(
        role="assistant",
        content=block_content,
    )
    json_str = original.model_dump_json()
    parsed = Message.model_validate_json(json_str)
    assert len(parsed.content) == 1
    assert isinstance(parsed.content[0], ToolUseBlock)
    assert parsed.content[0].id == "t1"


def test_content_block_discriminator_tool_result():
    block_dict = {
        "type": "tool_result",
        "tool_use_id": "t1",
        "content": "file contents",
        "is_error": False,
    }
    block = TypeAdapter(ContentBlock).validate_python(block_dict)
    assert isinstance(block, ToolResultBlock)
    assert block.tool_use_id == "t1"


def test_content_block_discriminator_tool_use():
    block_dict = {
        "type": "tool_use",
        "id": "t1",
        "name": "read_file",
        "input": {"path": "foo.txt"},
    }
    block = TypeAdapter(ContentBlock).validate_python(block_dict)
    assert isinstance(block, ToolUseBlock)
    assert block.name == "read_file"

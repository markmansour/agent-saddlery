"""Tests for FileReadTool."""

from __future__ import annotations

import pytest

from saddlery.tools.read_file import FileReadTool


@pytest.mark.asyncio
async def test_read_existing_file(tmp_path):
    """FileReadTool reads an existing file successfully."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, world!")

    tool = FileReadTool(root=tmp_path)
    result = await tool.call({"path": "test.txt"})

    assert not result.is_error
    assert result.content == "Hello, world!"


@pytest.mark.asyncio
async def test_missing_file(tmp_path):
    """Missing file returns is_error=True with helpful message."""
    tool = FileReadTool(root=tmp_path)
    result = await tool.call({"path": "nonexistent.txt"})

    assert result.is_error
    assert "not found" in result.content.lower()


@pytest.mark.asyncio
async def test_path_traversal_rejected(tmp_path):
    """Path traversal (../../etc/passwd) returns is_error=True."""
    tool = FileReadTool(root=tmp_path)
    result = await tool.call({"path": "../../etc/passwd"})

    assert result.is_error
    assert "escapes" in result.content.lower() or "escape" in result.content.lower()


@pytest.mark.asyncio
async def test_absolute_path_rejected(tmp_path):
    """Absolute path returns is_error=True."""
    tool = FileReadTool(root=tmp_path)
    result = await tool.call({"path": "/etc/passwd"})

    assert result.is_error
    assert "escapes" in result.content.lower() or "escape" in result.content.lower()


@pytest.mark.asyncio
async def test_directory_path_rejected(tmp_path):
    """Directory path (not a file) returns is_error=True."""
    subdir = tmp_path / "subdir"
    subdir.mkdir()

    tool = FileReadTool(root=tmp_path)
    result = await tool.call({"path": "subdir"})

    assert result.is_error
    assert "directory" in result.content.lower()


@pytest.mark.asyncio
async def test_invalid_utf8_rejected(tmp_path):
    """Invalid UTF-8 returns is_error=True."""
    test_file = tmp_path / "binary.bin"
    test_file.write_bytes(b"\x80\x81\x82\x83")

    tool = FileReadTool(root=tmp_path)
    result = await tool.call({"path": "binary.bin"})

    assert result.is_error
    assert "utf-8" in result.content.lower() or "decode" in result.content.lower()


@pytest.mark.asyncio
async def test_missing_path_argument(tmp_path):
    """Missing 'path' argument returns is_error=True."""
    tool = FileReadTool(root=tmp_path)
    result = await tool.call({})

    assert result.is_error
    assert "path" in result.content.lower()


@pytest.mark.asyncio
async def test_invalid_arguments_type(tmp_path):
    """Non-dict arguments returns is_error=True."""
    tool = FileReadTool(root=tmp_path)
    result = await tool.call("not a dict")  # type: ignore

    assert result.is_error
    assert "dictionary" in result.content.lower()


@pytest.mark.asyncio
async def test_non_string_path_argument(tmp_path):
    """Non-string path argument returns is_error=True."""
    tool = FileReadTool(root=tmp_path)
    result = await tool.call({"path": 123})

    assert result.is_error
    assert "string" in result.content.lower()


@pytest.mark.asyncio
async def test_never_raises_exception(tmp_path):
    """FileReadTool.call() never raises, only returns is_error=True."""
    tool = FileReadTool(root=tmp_path)

    # Try various error conditions
    test_cases = [
        {},  # missing path
        {"path": "../../etc/passwd"},  # traversal
        {"path": "/etc/passwd"},  # absolute
        {"path": "nonexistent"},  # not found
        {"path": 123},  # wrong type
        "not a dict",  # wrong type for arguments
    ]

    for args in test_cases:
        try:
            result = await tool.call(args)  # type: ignore
            assert isinstance(result.content, str)
            assert isinstance(result.is_error, bool)
        except Exception as e:
            pytest.fail(f"call() raised {type(e).__name__}: {e} for args {args}")


@pytest.mark.asyncio
async def test_nested_file_read(tmp_path):
    """FileReadTool reads files in nested subdirectories."""
    subdir = tmp_path / "a" / "b"
    subdir.mkdir(parents=True)
    test_file = subdir / "test.txt"
    test_file.write_text("nested content")

    tool = FileReadTool(root=tmp_path)
    result = await tool.call({"path": "a/b/test.txt"})

    assert not result.is_error
    assert result.content == "nested content"


@pytest.mark.asyncio
async def test_multiline_file_read(tmp_path):
    """FileReadTool reads multiline files correctly."""
    test_file = tmp_path / "multiline.txt"
    content = "line 1\nline 2\nline 3"
    test_file.write_text(content)

    tool = FileReadTool(root=tmp_path)
    result = await tool.call({"path": "multiline.txt"})

    assert not result.is_error
    assert result.content == content


@pytest.mark.asyncio
async def test_empty_file_read(tmp_path):
    """FileReadTool reads empty files correctly."""
    test_file = tmp_path / "empty.txt"
    test_file.write_text("")

    tool = FileReadTool(root=tmp_path)
    result = await tool.call({"path": "empty.txt"})

    assert not result.is_error
    assert result.content == ""


@pytest.mark.asyncio
async def test_tool_attributes(tmp_path):
    """FileReadTool has correct name, description, and input_schema."""
    tool = FileReadTool(root=tmp_path)

    assert tool.name == "read_file"
    assert isinstance(tool.description, str)
    assert len(tool.description) > 0
    assert isinstance(tool.input_schema, dict)
    assert "properties" in tool.input_schema
    assert "path" in tool.input_schema["properties"]
    assert "required" in tool.input_schema
    assert "path" in tool.input_schema["required"]

"""Tests for FileWriteTool."""

from __future__ import annotations

import os
import sys

import pytest

from saddlery.tools.write_file import FileWriteTool


async def test_write_new_file(tmp_path):
    """FileWriteTool creates a new file with the given content."""
    tool = FileWriteTool(root=tmp_path)
    result = await tool.call({"path": "out.txt", "content": "hello"})

    assert not result.is_error
    assert (tmp_path / "out.txt").read_text() == "hello"


async def test_overwrite_existing_file(tmp_path):
    """FileWriteTool overwrites an existing file's content."""
    existing = tmp_path / "out.txt"
    existing.write_text("old content")

    tool = FileWriteTool(root=tmp_path)
    result = await tool.call({"path": "out.txt", "content": "new content"})

    assert not result.is_error
    assert existing.read_text() == "new content"


async def test_path_traversal_rejected(tmp_path):
    """Path traversal (../../etc/passwd) returns is_error=True and does not write."""
    tool = FileWriteTool(root=tmp_path)
    result = await tool.call({"path": "../../etc/passwd", "content": "pwned"})

    assert result.is_error
    assert "escape" in result.content.lower()


async def test_absolute_path_rejected(tmp_path):
    """Absolute path returns is_error=True and does not write."""
    tool = FileWriteTool(root=tmp_path)
    result = await tool.call({"path": "/etc/passwd", "content": "pwned"})

    assert result.is_error
    assert "escape" in result.content.lower()


async def test_missing_parent_directory_rejected(tmp_path):
    """Writing into a non-existent subdirectory returns is_error=True."""
    tool = FileWriteTool(root=tmp_path)
    result = await tool.call({"path": "no/such/dir/out.txt", "content": "hi"})

    assert result.is_error
    assert "not found" in result.content.lower() or "no such" in result.content.lower()


async def test_directory_path_rejected(tmp_path):
    """Writing to a path that is a directory returns is_error=True."""
    subdir = tmp_path / "subdir"
    subdir.mkdir()

    tool = FileWriteTool(root=tmp_path)
    result = await tool.call({"path": "subdir", "content": "hi"})

    assert result.is_error
    assert "directory" in result.content.lower()


async def test_missing_path_argument(tmp_path):
    tool = FileWriteTool(root=tmp_path)
    result = await tool.call({"content": "hi"})

    assert result.is_error
    assert "path" in result.content.lower()


async def test_missing_content_argument(tmp_path):
    tool = FileWriteTool(root=tmp_path)
    result = await tool.call({"path": "out.txt"})

    assert result.is_error
    assert "content" in result.content.lower()


async def test_non_string_content_argument(tmp_path):
    tool = FileWriteTool(root=tmp_path)
    result = await tool.call({"path": "out.txt", "content": 123})

    assert result.is_error
    assert "string" in result.content.lower()


async def test_invalid_arguments_type(tmp_path):
    tool = FileWriteTool(root=tmp_path)
    result = await tool.call("not a dict")  # type: ignore

    assert result.is_error
    assert "dictionary" in result.content.lower()


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="POSIX permission bits aren't enforced on Windows, and root bypasses them entirely",
)
async def test_os_permission_denied_rejected(tmp_path):
    """Writing into a directory without write permission returns is_error=True, not a crash.

    This is an OS-level filesystem PermissionError (e.g. a read-only directory) — a distinct
    failure mode from PermissionGate's allow/deny/ask decision (Task 2+), which governs whether
    the *call* happens at all. The gate can allow a write and the OS can still refuse it.
    """
    readonly_dir = tmp_path / "readonly"
    readonly_dir.mkdir()
    readonly_dir.chmod(0o555)
    try:
        tool = FileWriteTool(root=tmp_path)
        result = await tool.call({"path": "readonly/out.txt", "content": "x"})

        assert result.is_error
        assert "permission" in result.content.lower()
    finally:
        readonly_dir.chmod(0o755)  # restore so tmp_path cleanup can remove it


async def test_never_raises_exception(tmp_path):
    """FileWriteTool.call() never raises, only returns is_error=True."""
    tool = FileWriteTool(root=tmp_path)

    readonly_dir = tmp_path / "readonly2"
    readonly_dir.mkdir()
    readonly_dir.chmod(0o555)

    test_cases = [
        {},  # missing path and content
        {"path": "../../etc/passwd", "content": "x"},  # traversal
        {"path": "/etc/passwd", "content": "x"},  # absolute
        {"path": "no/such/dir/f.txt", "content": "x"},  # missing parent
        {"path": 123, "content": "x"},  # wrong type
        "not a dict",  # wrong type for arguments
    ]
    if sys.platform != "win32" and os.geteuid() != 0:
        # OS permission denied
        test_cases.append({"path": "readonly2/out.txt", "content": "x"})

    try:
        for args in test_cases:
            try:
                result = await tool.call(args)  # type: ignore
                assert isinstance(result.content, str)
                assert isinstance(result.is_error, bool)
            except Exception as e:
                raise AssertionError(
                    f"call() raised {type(e).__name__}: {e} for args {args}"
                ) from e
    finally:
        readonly_dir.chmod(0o755)


async def test_tool_attributes(tmp_path):
    tool = FileWriteTool(root=tmp_path)

    assert tool.name == "write_file"
    assert isinstance(tool.description, str)
    assert len(tool.description) > 0
    assert isinstance(tool.input_schema, dict)
    assert "properties" in tool.input_schema
    assert "path" in tool.input_schema["properties"]
    assert "content" in tool.input_schema["properties"]
    assert "required" in tool.input_schema
    assert "path" in tool.input_schema["required"]
    assert "content" in tool.input_schema["required"]


def test_write_file_declares_write_capability():
    assert FileWriteTool().capability == "write"


def test_write_file_resource_is_normalized_path_parts(tmp_path):
    tool = FileWriteTool(root=tmp_path)
    assert tool.resource({"path": "Docs/A.md", "content": "x"}) == ("docs", "a.md")

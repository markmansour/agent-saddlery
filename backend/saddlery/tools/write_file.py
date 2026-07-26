"""Concrete tool implementation: write_file."""

from __future__ import annotations

from pathlib import Path

from saddlery.tools.base import Tool, ToolExecutionResult


class FileWriteTool(Tool):
    """Write text content to a file (UTF-8), creating or overwriting it."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path.cwd()
        self.name = "write_file"
        self.description = "Write text content to a file, creating or overwriting it."
        self.input_schema = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to write, relative to the root.",
                },
                "content": {
                    "type": "string",
                    "description": "The text content to write to the file.",
                },
            },
            "required": ["path", "content"],
        }

    async def call(self, arguments: dict) -> ToolExecutionResult:
        """Write content to a file, or return an error if it fails.

        Never raises; all failures become is_error=True results.
        """
        try:
            if not isinstance(arguments, dict):
                return ToolExecutionResult("Arguments must be a dictionary.", is_error=True)

            if "path" not in arguments:
                return ToolExecutionResult("Missing required argument: path", is_error=True)
            if "content" not in arguments:
                return ToolExecutionResult("Missing required argument: content", is_error=True)

            path_str = arguments["path"]
            if not isinstance(path_str, str):
                return ToolExecutionResult(
                    f"path must be a string, got {type(path_str).__name__}",
                    is_error=True,
                )

            content = arguments["content"]
            if not isinstance(content, str):
                return ToolExecutionResult(
                    f"content must be a string, got {type(content).__name__}",
                    is_error=True,
                )

            # Resolve path relative to root and check for traversal
            target_path = (self.root / path_str).resolve()
            try:
                target_path.relative_to(self.root.resolve())
            except ValueError:
                return ToolExecutionResult(
                    f"Path {path_str} escapes root directory.",
                    is_error=True,
                )

            if target_path.is_dir():
                return ToolExecutionResult(
                    f"Path {path_str} is a directory, not a file.",
                    is_error=True,
                )

            target_path.write_text(content, encoding="utf-8")
            return ToolExecutionResult(f"Wrote {len(content)} bytes to {path_str}")

        except FileNotFoundError:
            return ToolExecutionResult(
                f"Parent directory not found for: {arguments.get('path', 'unknown')}",
                is_error=True,
            )
        except IsADirectoryError:
            return ToolExecutionResult(
                f"Path is a directory: {arguments.get('path', 'unknown')}",
                is_error=True,
            )
        except PermissionError:
            return ToolExecutionResult(
                f"Permission denied: {arguments.get('path', 'unknown')}",
                is_error=True,
            )
        except Exception as e:
            return ToolExecutionResult(
                f"Error writing file: {type(e).__name__}: {e}",
                is_error=True,
            )

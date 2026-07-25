"""Concrete tool implementation: read_file."""

from __future__ import annotations

from pathlib import Path

from saddlery.tools.base import Tool, ToolExecutionResult


class FileReadTool(Tool):
    """Read the contents of a text file (UTF-8)."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path.cwd()
        self.name = "read_file"
        self.description = "Read the contents of a text file."
        self.input_schema = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to read, relative to the root.",
                }
            },
            "required": ["path"],
        }

    async def call(self, arguments: dict) -> ToolExecutionResult:
        """Read a file and return its contents, or an error if it fails.

        Never raises; all failures become is_error=True results.
        """
        try:
            # Extract path from arguments
            if not isinstance(arguments, dict):
                return ToolExecutionResult("Arguments must be a dictionary.", is_error=True)

            if "path" not in arguments:
                return ToolExecutionResult("Missing required argument: path", is_error=True)

            path_str = arguments["path"]
            if not isinstance(path_str, str):
                return ToolExecutionResult(
                    f"path must be a string, got {type(path_str).__name__}",
                    is_error=True,
                )

            # Resolve path relative to root and check for traversal
            target_path = (self.root / path_str).resolve()
            try:
                target_path.relative_to(self.root.resolve())
            except ValueError:
                # Path is outside root (e.g., ../ or absolute path)
                return ToolExecutionResult(
                    f"Path {path_str} escapes root directory.",
                    is_error=True,
                )

            # Check that target is not a directory
            if target_path.is_dir():
                return ToolExecutionResult(
                    f"Path {path_str} is a directory, not a file.",
                    is_error=True,
                )

            # Read the file
            content = target_path.read_text(encoding="utf-8")
            return ToolExecutionResult(content)

        except FileNotFoundError:
            return ToolExecutionResult(
                f"File not found: {arguments.get('path', 'unknown')}",
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
        except UnicodeDecodeError as e:
            return ToolExecutionResult(
                f"Failed to decode file as UTF-8: {e}",
                is_error=True,
            )
        except Exception as e:
            # Catch any other unexpected errors
            return ToolExecutionResult(
                f"Error reading file: {type(e).__name__}: {e}",
                is_error=True,
            )

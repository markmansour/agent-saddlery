"""Canonical resource tuples for path-based tools."""

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING

from saddlery.tools.base import ResourceError

if TYPE_CHECKING:
    from pathlib import Path


def fold(token: str) -> str:
    """NFC-normalize and case-fold a token, for matching on every filesystem."""
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", token).casefold())


def path_resource(root: Path, arguments: object) -> tuple[str, ...]:
    """Resolve arguments['path'] against root; return its normalized parts relative to root."""
    if not isinstance(arguments, dict):
        raise ResourceError("Arguments must be a dictionary.")
    path_str = arguments.get("path")
    if not isinstance(path_str, str) or not path_str:
        raise ResourceError("path must be a non-empty string")
    try:
        target = (root / path_str).resolve()
        resolved_root = root.resolve()
    except (ValueError, OSError, RuntimeError) as exc:
        # NUL bytes (ValueError), symlink loops (RuntimeError/OSError) and the like.
        raise ResourceError(f"Invalid path {path_str!r}: {exc}") from None
    try:
        relative = target.relative_to(resolved_root)
    except ValueError:
        raise ResourceError(f"Path {path_str} escapes root directory.") from None
    return tuple(fold(part) for part in relative.parts)

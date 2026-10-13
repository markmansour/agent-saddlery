"""Fail-closed shell command classifier for the permission policy.

A command is *simple* only if it is provably one program with literal arguments. Anything
else is *rejected*. The shell tool never invokes a shell, so only simple commands ever run
and the argv recorded here is exactly what executes.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import Literal

_FORBIDDEN_CHARS = frozenset("`$\n\r\\*?~{")
_OPERATOR_CHARS = frozenset(";&|<>()")
_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
_SHELLS = frozenset({"bash", "sh", "zsh", "dash"})
_DASH_C = re.compile(r"-[A-Za-z]*c[A-Za-z]*")
_INNER_SPLIT = re.compile(r"[;&|\n\r`()<>]+")
_MAX_NESTING = 3


@dataclass(frozen=True)
class ShellCommand:
    raw: str
    argv: tuple[str, ...] | None
    kind: Literal["simple", "rejected"]


def classify(raw: str) -> ShellCommand:
    rejected = ShellCommand(raw=raw, argv=None, kind="rejected")
    if not raw.strip() or any(char in _FORBIDDEN_CHARS for char in raw):
        return rejected
    lexer = shlex.shlex(raw, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        return rejected
    if not tokens or _ASSIGNMENT.match(tokens[0]):
        return rejected
    if any(set(token) <= _OPERATOR_CHARS for token in tokens):
        return rejected
    return ShellCommand(raw=raw, argv=tuple(tokens), kind="simple")


def deny_candidates(cmd: ShellCommand) -> list[tuple[str, ...]]:
    """Argvs a deny rule should be matched against, best-effort.

    Includes the command's own argv and, for ``bash -c "..."`` style wrappers, the commands
    inside the string. Deny rules are a tripwire, not a boundary.
    """
    if cmd.argv is None:
        return []
    return _candidates(cmd.argv, 0)


def _candidates(argv: tuple[str, ...], depth: int) -> list[tuple[str, ...]]:
    found = [argv]
    if (
        depth < _MAX_NESTING
        and len(argv) >= 3
        and argv[0] in _SHELLS
        and _DASH_C.fullmatch(argv[1])
    ):
        for part in _INNER_SPLIT.split(argv[2]):
            tokens = _lenient_split(part.strip())
            if tokens:
                found.extend(_candidates(tokens, depth + 1))
    return found


def _lenient_split(text: str) -> tuple[str, ...]:
    try:
        return tuple(shlex.split(text))
    except ValueError:
        return tuple(text.split())

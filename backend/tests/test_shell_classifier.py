"""The shell classifier fails closed: only provably simple commands are simple."""

from __future__ import annotations

import pytest

from saddlery.permissions.shell import classify, deny_candidates

SIMPLE = [
    ("git status", ("git", "status")),
    ("ls -la", ("ls", "-la")),
    ('echo "a;b"', ("echo", "a;b")),
    ("pytest -x tests/", ("pytest", "-x", "tests/")),
    ("find . -delete", ("find", ".", "-delete")),
    ("sudo rm -rf /", ("sudo", "rm", "-rf", "/")),
    ("bash -c 'rm -rf /'", ("bash", "-c", "rm -rf /")),
    ("ls #notacomment", ("ls", "#notacomment")),
]

REJECTED = [
    "ls; rm -rf ~",
    "ls && pwd | wc",
    "a & b",
    "ls > out.txt",
    "cat <<EOF",
    "cat <(id)",
    "echo (a)",
    "echo `id`",
    'echo "$(id)"',
    "echo $HOME",
    "ls\nrm -rf x",
    "ls\\\n-la",
    "FOO=1 git status",
    "ls {a,b}",
    "ls *.py",
    "ls ?",
    "echo ~",
    'echo "unclosed',
    "",
    "   ",
]


@pytest.mark.parametrize(("raw", "argv"), SIMPLE)
def test_simple_commands(raw, argv):
    cmd = classify(raw)
    assert cmd.kind == "simple"
    assert cmd.argv == argv
    assert cmd.raw == raw


@pytest.mark.parametrize("raw", REJECTED)
def test_rejected_commands(raw):
    cmd = classify(raw)
    assert cmd.kind == "rejected"
    assert cmd.argv is None


def test_deny_candidates_of_plain_command_is_its_argv():
    assert deny_candidates(classify("git status")) == [("git", "status")]


def test_deny_candidates_look_inside_bash_dash_c():
    cands = deny_candidates(classify('bash -c "rm -rf /"'))
    assert ("bash", "-c", "rm -rf /") in cands
    assert ("rm", "-rf", "/") in cands


def test_deny_candidates_split_compound_inner_command():
    cands = deny_candidates(classify('sh -c "ls; rm -rf /"'))
    assert ("ls",) in cands
    assert ("rm", "-rf", "/") in cands


def test_deny_candidates_handle_combined_flags_and_nesting():
    cands = deny_candidates(classify("""bash -lc "sh -c 'rm -rf /'" """))
    assert ("rm", "-rf", "/") in cands


def test_deny_candidates_of_rejected_command_is_empty():
    assert deny_candidates(classify("ls; rm -rf /")) == []

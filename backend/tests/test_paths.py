"""Tests for canonical path resources."""

from __future__ import annotations

import unicodedata

import pytest

from saddlery.tools.base import ResourceError
from saddlery.tools.paths import fold, path_resource


def test_path_resource_returns_normalized_parts(tmp_path):
    assert path_resource(tmp_path, {"path": "docs/a.md"}) == ("docs", "a.md")


def test_path_resource_folds_case(tmp_path):
    assert path_resource(tmp_path, {"path": "Docs/A.MD"}) == ("docs", "a.md")


def test_path_resource_normalizes_unicode(tmp_path):
    nfd = unicodedata.normalize("NFD", "café.txt")
    nfc = unicodedata.normalize("NFC", "café.txt")
    assert path_resource(tmp_path, {"path": nfd}) == path_resource(tmp_path, {"path": nfc})


def test_path_resource_collapses_dotdot_inside_root(tmp_path):
    assert path_resource(tmp_path, {"path": "docs/../src/x.py"}) == ("src", "x.py")


def test_path_resource_rejects_escape(tmp_path):
    with pytest.raises(ResourceError):
        path_resource(tmp_path, {"path": "../outside.txt"})


def test_path_resource_rejects_absolute_outside_root(tmp_path):
    with pytest.raises(ResourceError):
        path_resource(tmp_path, {"path": "/etc/passwd"})


def test_path_resource_rejects_symlink_out_of_root(tmp_path):
    outside = tmp_path.parent / "outside_dir"
    outside.mkdir(exist_ok=True)
    (tmp_path / "link").symlink_to(outside)
    with pytest.raises(ResourceError):
        path_resource(tmp_path, {"path": "link/x.txt"})


@pytest.mark.parametrize("arguments", [None, [], {}, {"path": ""}, {"path": 3}])
def test_path_resource_rejects_bad_arguments(tmp_path, arguments):
    with pytest.raises(ResourceError):
        path_resource(tmp_path, arguments)


def test_fold_is_idempotent():
    assert fold(fold("Straße")) == fold("Straße")


def test_path_with_nul_byte_is_a_resource_error(tmp_path):
    with pytest.raises(ResourceError):
        path_resource(tmp_path, {"path": "a\x00b"})


def test_symlink_loop_is_a_resource_error(tmp_path):
    (tmp_path / "loop").symlink_to(tmp_path / "loop")
    with pytest.raises(ResourceError):
        path_resource(tmp_path, {"path": "loop/x"})

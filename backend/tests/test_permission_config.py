"""Tests for loading .saddlery/permissions.json."""

from __future__ import annotations

import json

from saddlery.permissions.config import load_permission_config


def test_loads_allow_and_deny_from_file(tmp_path):
    config_path = tmp_path / "permissions.json"
    config_path.write_text(json.dumps({"allow": ["read_file"], "deny": ["shell"]}))

    allow, deny = load_permission_config(config_path)

    assert allow == {"read_file"}
    assert deny == {"shell"}


def test_missing_file_returns_empty_sets(tmp_path):
    config_path = tmp_path / "does_not_exist.json"

    allow, deny = load_permission_config(config_path)

    assert allow == set()
    assert deny == set()


def test_missing_keys_default_to_empty_sets(tmp_path):
    config_path = tmp_path / "permissions.json"
    config_path.write_text(json.dumps({}))

    allow, deny = load_permission_config(config_path)

    assert allow == set()
    assert deny == set()


def test_malformed_json_returns_empty_sets(tmp_path):
    config_path = tmp_path / "permissions.json"
    config_path.write_text("{not valid json")

    allow, deny = load_permission_config(config_path)

    assert allow == set()
    assert deny == set()

"""Tests for identity resolution and master-key data-key wraps."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cli.config import RigConfig
from cli.snapshots import iter_workspace_hash_paths
from cli.vault_keys import (
    IDENTITY_DATA_KEY_VAR,
    SHARED_DATA_KEY_VAR,
    bootstrap_identity_keys,
    personal_vars_path,
    read_data_key_file,
    read_wrap_fields,
    resolve_identity,
    sanitize_identity,
    unlock_data_keys,
    unwrap_with_master_key,
    wrap_with_master_key,
    PERSONAL_DATA_KEY_PATH,
    SHARED_DATA_KEY_PATH,
)


@pytest.fixture(autouse=True)
def _clear_tmp_keys():
    for path in (PERSONAL_DATA_KEY_PATH, SHARED_DATA_KEY_PATH, "/tmp/.rig/.data-key"):
        if os.path.exists(path):
            os.unlink(path)
    yield
    for path in (PERSONAL_DATA_KEY_PATH, SHARED_DATA_KEY_PATH, "/tmp/.rig/.data-key"):
        if os.path.exists(path):
            os.unlink(path)


def test_sanitize_and_resolve_identity(tmp_path, monkeypatch):
    assert sanitize_identity("Alice") == "alice"
    assert sanitize_identity("Bob_1") == "bob_1"
    monkeypatch.setenv("RIG_IDENTITY", "from-env")
    assert resolve_identity() == "from-env"
    monkeypatch.delenv("RIG_IDENTITY")
    cfg = RigConfig(path=str(tmp_path / "cfg"))
    cfg.set_identity("cfg-user")
    assert resolve_identity(config=cfg) == "cfg-user"


def test_wrap_unwrap_roundtrip():
    blob = wrap_with_master_key("secret-data-key", "master-pass")
    assert blob.startswith("rig1$")
    assert unwrap_with_master_key(blob, "master-pass") == "secret-data-key"
    with pytest.raises(ValueError):
        unwrap_with_master_key(blob, "wrong")


def test_bootstrap_and_unlock(tmp_path, monkeypatch):
    monkeypatch.setenv("RIG_CONFIG", str(tmp_path / "cfg"))
    project = tmp_path / "ws"
    project.mkdir()
    (project / "rig.yml").write_text("kind: workspace\n")
    answers = iter(["tester"])
    secrets = iter(["master-one", "master-one"])
    ident, personal_path, shared_path = bootstrap_identity_keys(
        str(project),
        input_fn=lambda _p: next(answers),
        secret_fn=lambda _p: next(secrets),
        config=RigConfig(path=str(tmp_path / "cfg")),
    )
    assert ident == "tester"
    assert read_data_key_file(personal_path)
    assert read_data_key_file(shared_path)
    id_file = personal_vars_path(str(project), "tester")
    wraps = read_wrap_fields(id_file)
    assert IDENTITY_DATA_KEY_VAR in wraps
    assert SHARED_DATA_KEY_VAR in wraps

    # Clear tmp and unlock again
    for path in (PERSONAL_DATA_KEY_PATH, SHARED_DATA_KEY_PATH, "/tmp/.rig/.data-key"):
        os.unlink(path)
    unlock_data_keys(
        str(project),
        identity="tester",
        master_key="master-one",
    )
    assert read_data_key_file(PERSONAL_DATA_KEY_PATH)
    assert read_data_key_file(SHARED_DATA_KEY_PATH)


def test_snapshot_hash_skips_identity_vars(tmp_path):
    project = tmp_path / "ws"
    rig = project / ".rig"
    rig.mkdir(parents=True)
    (project / "rig.yml").write_text("kind: workspace\n")
    (rig / "vars.yml").write_text("x: 1\n")
    (rig / "vars.alice.yml").write_text('rig_identity_data_key: "rig1$x"\n')
    (rig / "workspace.yml").write_text("---\n")
    paths = [os.path.basename(p) for p in iter_workspace_hash_paths(str(project))]
    assert "vars.yml" in paths
    assert "vars.alice.yml" not in paths
    assert "workspace.yml" in paths

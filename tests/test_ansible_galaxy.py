"""Unit tests for Ansible Galaxy requirements/roles install helpers."""

import os
import sys
from unittest.mock import MagicMock, patch

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cli.remote_dev import AnsibleManager, ProjectConfig


def test_setup_requirements_writes_collections_and_roles(tmp_path):
    cfg = ProjectConfig(str(tmp_path))
    assert cfg.init(name="ws", agent_type="opencode")
    req_path = os.path.join(cfg.rig_dir, "requirements.yml")
    os.remove(req_path)

    mgr = AnsibleManager(cfg)
    mgr.configure(str(tmp_path))
    assert mgr.setup_requirements() is True
    payload = yaml.safe_load(open(req_path, encoding="utf-8"))
    names = {item["name"] for item in payload.get("collections", [])}
    role_names = {item["name"] for item in payload.get("roles", [])}
    assert "community.general" in names
    assert "ansible.posix" in names
    assert "geerlingguy.docker" in role_names
    # Second call is a no-op when file exists.
    assert mgr.setup_requirements() is True


def test_setup_roles_creates_default_role(tmp_path):
    cfg = ProjectConfig(str(tmp_path))
    assert cfg.init(name="ws", agent_type="opencode")
    mgr = AnsibleManager(cfg)
    mgr.configure(str(tmp_path))
    assert mgr.setup_roles() is True
    role_tasks = tmp_path / ".rig" / "roles" / "default_role" / "tasks" / "main.yml"
    assert role_tasks.is_file()


def test_install_roles_invokes_ansible_galaxy(tmp_path):
    cfg = ProjectConfig(str(tmp_path))
    assert cfg.init(name="ws", agent_type="opencode")
    mgr = AnsibleManager(cfg)
    mgr.configure(str(tmp_path))

    ok = MagicMock(returncode=0, stdout="ok", stderr="")
    with patch("cli.remote_dev.subprocess.run", return_value=ok) as run:
        assert mgr.install_roles() is True
    commands = [" ".join(call.args[0]) for call in run.call_args_list]
    assert any("ansible-galaxy collection install" in cmd for cmd in commands)
    assert any("ansible-galaxy role install" in cmd for cmd in commands)
    assert (tmp_path / ".rig" / "collections").is_dir()
    assert (tmp_path / ".rig" / "roles").is_dir()


def test_setup_bootstrap_wires_components(tmp_path):
    cfg = ProjectConfig(str(tmp_path))
    assert cfg.init(name="ws", agent_type="opencode")
    mgr = AnsibleManager(cfg)
    with patch.object(mgr, "install_roles", return_value=True) as install:
        assert mgr.setup_bootstrap("10.0.0.1", "/tmp/key") is True
        install.assert_called_once()
    assert (tmp_path / ".rig" / "inventory.yml").is_file()

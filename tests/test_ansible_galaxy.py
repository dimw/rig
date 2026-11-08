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


def test_setup_roles_creates_local_and_galaxy_dirs(tmp_path):
    cfg = ProjectConfig(str(tmp_path))
    assert cfg.init(name="ws", agent_type="opencode")
    mgr = AnsibleManager(cfg)
    mgr.configure(str(tmp_path))
    assert mgr.setup_roles() is True
    assert (tmp_path / ".rig" / "local_roles" / ".gitkeep").is_file()
    assert (tmp_path / ".rig" / "galaxy_roles").is_dir()
    assert not (tmp_path / ".rig" / "roles" / "default_role").exists()


def test_galaxy_roles_move_out_of_the_playbook_roles_dir(tmp_path):
    from cli.remote_dev import relocate_installed_galaxy_roles, roles_search_path

    cfg = ProjectConfig(str(tmp_path))
    assert cfg.init(name="ws", agent_type="opencode")
    legacy = tmp_path / ".rig" / "roles" / "geerlingguy.docker" / "meta"
    legacy.mkdir(parents=True)
    (legacy / ".galaxy_install_info").write_text("version: 1\n")
    handmade = tmp_path / ".rig" / "roles" / "kept"
    handmade.mkdir()
    (handmade / "tasks").mkdir()

    moved = relocate_installed_galaxy_roles(cfg.rig_dir)
    assert moved == ["geerlingguy.docker"]
    assert (tmp_path / ".rig" / "galaxy_roles" / "geerlingguy.docker" / "meta" / ".galaxy_install_info").is_file()
    assert handmade.is_dir()
    again = tmp_path / ".rig" / "roles" / "geerlingguy.docker" / "meta"
    again.mkdir(parents=True)
    (again / ".galaxy_install_info").write_text("version: 1\n")
    assert relocate_installed_galaxy_roles(cfg.rig_dir) == []
    assert again.is_dir()
    assert relocate_installed_galaxy_roles(str(tmp_path / "missing")) == []

    path = roles_search_path(cfg.rig_dir)
    assert path.split(os.pathsep)[0].endswith(os.path.join(".rig", "local_roles"))
    assert path.split(os.pathsep)[1].endswith(os.path.join(".rig", "galaxy_roles"))


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
    role_cmd = next(cmd for cmd in commands if "ansible-galaxy role install" in cmd)
    assert f"-p {tmp_path / '.rig' / 'galaxy_roles'}" in role_cmd
    assert "local_roles" in mgr.ansible_env["ANSIBLE_ROLES_PATH"].split(os.pathsep)[0]
    assert (tmp_path / ".rig" / "collections").is_dir()
    assert (tmp_path / ".rig" / "galaxy_roles").is_dir()


def test_setup_bootstrap_wires_components(tmp_path):
    cfg = ProjectConfig(str(tmp_path))
    assert cfg.init(name="ws", agent_type="opencode")
    mgr = AnsibleManager(cfg)
    with patch.object(mgr, "install_roles", return_value=True) as install:
        assert mgr.setup_bootstrap("10.0.0.1", "/tmp/key") is True
        install.assert_called_once()
    assert (tmp_path / ".rig" / "inventory.yml").is_file()

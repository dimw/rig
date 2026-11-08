"""Release tags become the PyPI version, and built archives must match."""

import io
import os
import sys
import tarfile
import zipfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.pypi_version import archive_metadata, check_dist, version_from_tag


@pytest.mark.parametrize(
    ("tag", "version"),
    [
        ("v1.2.3", "1.2.3"),
        ("1.2.3", "1.2.3"),
        ("V0.2.0", "0.2.0"),
        ("refs/tags/v1.2.3rc1", "1.2.3rc1"),
        ("v1.2.3.post1", "1.2.3.post1"),
        ("v1.2.3.dev1", "1.2.3.dev1"),
    ],
)
def test_version_from_tag(tag, version):
    assert version_from_tag(tag) == version


@pytest.mark.parametrize(
    "tag",
    ["", "v", "latest", "v1", "v1.2", "v01.2.3", "v1.2.3+local", "not-a-version"],
)
def test_version_from_tag_rejects_non_releases(tag):
    with pytest.raises(ValueError):
        version_from_tag(tag)


def _metadata(name: str, version: str) -> bytes:
    return f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n\n".encode()


def test_check_dist_accepts_matching_archives(tmp_path):
    wheel = tmp_path / "mystack_rig-1.2.3-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("mystack_rig-1.2.3.dist-info/METADATA", _metadata("mystack-rig", "1.2.3"))
    sdist = tmp_path / "mystack_rig-1.2.3.tar.gz"
    info = _metadata("mystack-rig", "1.2.3")
    with tarfile.open(sdist, "w:gz") as archive:
        member = tarfile.TarInfo("mystack_rig-1.2.3/PKG-INFO")
        member.size = len(info)
        archive.addfile(member, io.BytesIO(info))

    assert archive_metadata(wheel) == ("mystack-rig", "1.2.3")
    check_dist(tmp_path, "1.2.3")


def test_check_dist_rejects_a_version_mismatch(tmp_path):
    wheel = tmp_path / "mystack_rig-0.0.1-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("mystack_rig-0.0.1.dist-info/METADATA", _metadata("mystack-rig", "0.0.1"))
    sdist = tmp_path / "mystack_rig-0.0.1.tar.gz"
    info = _metadata("mystack-rig", "0.0.1")
    with tarfile.open(sdist, "w:gz") as archive:
        member = tarfile.TarInfo("mystack_rig-0.0.1/PKG-INFO")
        member.size = len(info)
        archive.addfile(member, io.BytesIO(info))

    with pytest.raises(ValueError, match="expected mystack-rig 1.2.3"):
        check_dist(tmp_path, "1.2.3")

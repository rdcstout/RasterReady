"""The release inventory must detect missing or altered recorded licenses."""

import base64
import hashlib
from importlib.metadata import PathDistribution

import pytest

from tools.collect_notices import recorded_notices


def wheel(tmp_path):
    info = tmp_path / "example-1.dist-info"
    info.mkdir()
    (info / "METADATA").write_text("Name: example\nVersion: 1\n")
    license_path = info / "licenses/LICENSE.txt"
    license_path.parent.mkdir()
    license_path.write_bytes(b"Example license\n")
    digest = base64.urlsafe_b64encode(hashlib.sha256(license_path.read_bytes()).digest())
    entry = "example-1.dist-info/licenses/LICENSE.txt"
    (info / "RECORD").write_text(f"{entry},sha256={digest.rstrip(b'=').decode()},16\n")
    return PathDistribution(info), license_path


def test_recorded_notice_exists_and_matches(tmp_path):
    dist, license_path = wheel(tmp_path)
    assert [source for source, _ in recorded_notices(dist)] == [license_path]


def test_missing_notice_cannot_disappear_from_inventory(tmp_path):
    dist, license_path = wheel(tmp_path)
    license_path.unlink()
    with pytest.raises(SystemExit, match="missing"):
        list(recorded_notices(dist))


def test_altered_notice_is_rejected(tmp_path):
    dist, license_path = wheel(tmp_path)
    license_path.write_bytes(b"Altered license\n")
    with pytest.raises(SystemExit, match="hash does not match"):
        list(recorded_notices(dist))


def test_notice_symlink_cannot_copy_outside_distribution(tmp_path):
    root = tmp_path / "site"
    root.mkdir()
    dist, license_path = wheel(root)
    external = tmp_path / "owned-external.txt"
    external.write_bytes(license_path.read_bytes())
    license_path.unlink()
    try:
        license_path.symlink_to(external)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows account lacks symbolic-link privilege")
        raise
    with pytest.raises(SystemExit, match="outside distribution"):
        list(recorded_notices(dist))

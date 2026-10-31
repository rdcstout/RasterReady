"""Source delivery must preserve files and detect missing or altered inputs."""

import hashlib
import io
import json
import tarfile

import pytest

from tools import package_dependency_sources as sources


def test_bundle_preserves_inputs_and_is_reproducible(tmp_path, monkeypatch):
    root = tmp_path / "source"
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    root.mkdir()
    (root / "third_party").mkdir()
    (root / "third_party/LICENSE").write_bytes(b"retained license\r\n")
    (root / "tools").mkdir()
    for name in (
        "DEVELOPMENT.md",
        "THIRD_PARTY_NOTICES.md",
        "requirements-heic-build.txt",
        "tools/heic_sources.py",
        "tools/build_heic_macos.py",
    ):
        (root / name).write_text("retained build material\n")
    original = b"upstream archive bytes"
    archive = inputs / "codec.tar.gz"
    archive.write_bytes(original)
    monkeypatch.setattr(
        sources,
        "source_catalog",
        lambda root: {
            "codec": {
                "url": "https://example.org/source",
                "sha256": hashlib.sha256(original).hexdigest(),
            }
        },
    )
    first = tmp_path / "first.tar"
    second = tmp_path / "second.tar"
    sources.package(inputs, first, "abc123", root)
    sources.package(inputs, second, "abc123", root)
    assert first.read_bytes() == second.read_bytes()
    assert archive.read_bytes() == original
    with tarfile.open(first) as bundle:
        manifest = json.load(bundle.extractfile("manifest.json"))
        assert manifest["release_ready"] is False
        assert manifest["source_revision"] == "abc123"
        assert bundle.extractfile("archives/codec.tar.gz").read() == original
        assert bundle.extractfile("third_party/LICENSE").read() == b"retained license\r\n"
    with pytest.raises(ValueError, match="existing files"):
        sources.package(inputs, first, "abc123", root)
    before = first.read_bytes()
    archive.write_bytes(b"changed archive")
    with pytest.raises(ValueError, match="mismatched"):
        sources.package(inputs, tmp_path / "bad.tar", "abc123", root)
    archive.unlink()
    with pytest.raises(ValueError, match="Missing"):
        sources.package(inputs, tmp_path / "missing.tar", "abc123", root)
    assert first.read_bytes() == before
    assert not (tmp_path / "bad.tar").exists()
    assert not (tmp_path / "missing.tar").exists()


@pytest.mark.parametrize("mode", ["altered", "duplicate", "symlink"])
def test_readback_rejects_corrupt_or_ambiguous_archive(tmp_path, mode):
    path = tmp_path / "bundle.tar"
    original = b"original bytes"
    with tarfile.open(path, "w:") as archive:
        info = tarfile.TarInfo("source")
        data = b"changed" if mode == "altered" else original
        if mode == "symlink":
            info.type = tarfile.SYMTYPE
            info.linkname = "elsewhere"
            archive.addfile(info)
        else:
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
            if mode == "duplicate":
                archive.addfile(info, io.BytesIO(data))
    with pytest.raises(ValueError):
        sources.verify_bundle(path, {"source": hashlib.sha256(original).hexdigest()})

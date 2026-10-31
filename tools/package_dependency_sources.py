"""Assemble retained Mac dependency source inputs; never certify release coverage."""

import argparse
import hashlib
import io
import json
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path

if __package__:
    from .heic_sources import SOURCES
else:
    from heic_sources import SOURCES

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_catalog(root=ROOT):
    qt = json.loads((root / "third_party/Qt/component-provenance.json").read_text())
    binding = json.loads((root / "third_party/Qt/python-bindings/provenance.json").read_text())
    raw = json.loads((root / "third_party/rawpy-macos/provenance.json").read_text())
    entries = {entry["repo"]: entry for entry in qt["source_archives"]}
    entries["qt-for-python"] = binding["source"]
    entries.update({entry["name"]: entry for entry in raw["source_archives"]})
    entries.update({entry["name"]: entry for entry in raw["build_sources"]})
    entries.update(
        {
            name: {
                "url": f"https://github.com/{repo}/archive/refs/tags/v{version}.tar.gz",
                "sha256": sha,
            }
            for name, (repo, version, sha) in SOURCES.items()
        }
    )
    return {
        name: {"url": entry["url"], "sha256": entry["sha256"]}
        for name, entry in sorted(entries.items())
    }


def verify_bundle(path, expected):
    """Read back every byte, rejecting unexpected, duplicate or special entries."""
    with tarfile.open(path, "r:") as archive:
        members = archive.getmembers()
        if len(members) != len(expected) or {m.name for m in members} != set(expected):
            raise ValueError("Source bundle member inventory does not match")
        for member in members:
            if not member.isfile():
                raise ValueError("Source bundle contains a non-file entry")
            with archive.extractfile(member) as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != expected[member.name]:
                raise ValueError(f"Source bundle hash mismatch: {member.name}")


def package(inputs, output, revision, root=ROOT):
    if output.exists():
        raise ValueError("Choose a new source bundle path; existing files are preserved")
    catalog = source_catalog(root)
    paths = {}
    for name, entry in catalog.items():
        path = inputs / f"{name}.tar.gz"
        if path.is_symlink() or not path.is_file() or digest(path) != entry["sha256"]:
            raise ValueError(f"Missing or mismatched retained source: {name}")
        paths[f"archives/{name}.tar.gz"] = path
    for path in sorted((root / "third_party").rglob("*")):
        if path.is_symlink():
            raise ValueError("Source supplements must not contain symbolic links")
        if path.is_file():
            paths[path.relative_to(root).as_posix()] = path
    for name in ("DEVELOPMENT.md", "THIRD_PARTY_NOTICES.md", "requirements-heic-build.txt"):
        paths[name] = root / name
    for name in ("heic_sources.py", "build_heic_macos.py"):
        paths[f"tools/{name}"] = root / "tools" / name
    hashes = {name: digest(path) for name, path in paths.items()}
    manifest = {
        "scope": "Retained Mac dependency source inputs and build guidance only",
        "source_revision": revision,
        "release_ready": False,
        "unresolved": [
            "Match source and build configuration to every final artifact component",
            "Complete remaining native attribution and source/replacement obligations",
            "Provide application source and final per-platform installer/runtime evidence separately",
        ],
        "sources": catalog,
        "files": hashes,
    }
    encoded = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    hashes = {**hashes, "manifest.json": hashlib.sha256(encoded).hexdigest()}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dependency-sources-", dir=output.parent) as staging:
        temporary = Path(staging) / "bundle.tar"
        with tarfile.open(temporary, "w:", format=tarfile.PAX_FORMAT) as archive:
            for name in sorted(hashes):
                info = tarfile.TarInfo(name)
                info.mode = 0o644
                if name == "manifest.json":
                    info.size = len(encoded)
                    archive.addfile(info, io.BytesIO(encoded))
                else:
                    info.size = paths[name].stat().st_size
                    with paths[name].open("rb") as stream:
                        archive.addfile(info, stream)
        verify_bundle(temporary, hashes)
        # Publish the verified local file without replacing an existing destination.
        os.link(temporary, output)
    return {"path": str(output), "sha256": digest(output), "members": len(hashes)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs", type=Path, help="Directory containing NAME.tar.gz source archives"
    )
    parser.add_argument("output", type=Path, help="New local .tar file; no upload is performed")
    args = parser.parse_args()
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=ROOT, text=True
    )
    if status.strip():
        raise SystemExit("Commit source changes before recording a bundle revision")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    print(json.dumps(package(args.inputs, args.output, revision), indent=2))


if __name__ == "__main__":
    main()

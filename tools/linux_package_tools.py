"""Pinned versioned AppImage build tools and runtime; no moving release assets."""

import hashlib
import json
import urllib.request
from pathlib import Path

TOOLS = {
    "appimagetool-x86_64.AppImage": (
        "https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage",
        "ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0",
    ),
    "runtime-x86_64": (
        "https://github.com/AppImage/type2-runtime/releases/download/20251108/runtime-x86_64",
        "2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d",
    ),
}


def verify(directory):
    for name, (_, expected) in TOOLS.items():
        with (directory / name).open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            raise ValueError(f"Pinned AppImage input hash differs: {name}")


def fetch(directory):
    if directory.exists() or directory.is_symlink():
        raise ValueError("Use a new tool directory; existing work is preserved")
    directory.mkdir(parents=True)
    for name, (url, expected) in TOOLS.items():
        with urllib.request.urlopen(url, timeout=60) as response:
            payload = response.read(50 * 1024 * 1024 + 1)
        if len(payload) > 50 * 1024 * 1024 or hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError(f"AppImage tool download size/hash mismatch: {name}")
        (directory / name).write_bytes(payload)
        (directory / name).chmod(0o755)
    verify(directory)
    (directory / "provenance.json").write_text(json.dumps(TOOLS, indent=2) + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    fetch(parser.parse_args().output.resolve())

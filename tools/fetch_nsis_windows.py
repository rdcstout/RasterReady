"""Fetch the pinned official NSIS Windows compiler into a new private directory."""

import argparse
import hashlib
import io
import json
import stat
import urllib.request
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

URL = "https://downloads.sourceforge.net/project/nsis/NSIS%203/3.13/nsis-3.13.zip"
SHA256 = "ba63dffc4410ee89193e1cb5a41989991bd77c61068da17e3156d136b7b0b3d8"


def fetch(output):
    if output.exists() or output.is_symlink():
        raise ValueError("Use a new NSIS tool directory; existing tools are preserved")
    with urllib.request.urlopen(URL, timeout=60) as response:
        payload = response.read(50 * 1024 * 1024 + 1)
    if len(payload) > 50 * 1024 * 1024 or hashlib.sha256(payload).hexdigest() != SHA256:
        raise ValueError("NSIS archive size or hash differs from the pinned official release")
    with ZipFile(io.BytesIO(payload)) as archive:
        for entry in archive.infolist():
            path = PurePosixPath(entry.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in entry.filename
                or ":" in entry.filename
            ):
                raise ValueError("Unsafe NSIS archive path")
            if stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError("Unexpected symlink in NSIS archive")
        output.mkdir(parents=True)
        (output / "nsis-3.13.zip").write_bytes(payload)
        archive.extractall(output)
    if not (output / "nsis-3.13/makensis.exe").is_file():
        raise ValueError("NSIS archive lacks the expected Windows compiler")
    (output / "provenance.json").write_text(
        json.dumps(
            {
                "version": "3.13",
                "url": URL,
                "sha256": SHA256,
                "checksum_source": "https://github.com/Homebrew/homebrew-core/blob/f4781b7a0139d0850095188418ffb12682475cb8/Formula/m/makensis.rb",
                "installed_globally": False,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"Verified NSIS 3.13 under {output}; no global installation performed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    fetch(parser.parse_args().output.resolve())

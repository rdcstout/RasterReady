"""Collect only DLLs recorded by a specific installed wheel distribution."""

import base64
import csv
import hashlib
import io
from pathlib import Path


def recorded_dlls(distribution):
    binaries = []
    # Distribution.files filters missing entries on current Python. Read the
    # original wheel inventory so an absent required DLL cannot silently vanish.
    record = distribution.read_text("RECORD")
    if record is None:
        raise ValueError("The Windows HEIC wheel has no installed RECORD inventory")
    for row in csv.reader(io.StringIO(record)):
        if len(row) != 3:
            raise ValueError("Malformed installed wheel RECORD")
        entry, expected_hash, _ = row
        path = Path(entry)
        if path.suffix.lower() != ".dll":
            continue
        if path.is_absolute() or ".." in path.parts or "\\" in entry or ":" in entry:
            raise ValueError(f"Unsafe wheel DLL path: {entry}")
        source = distribution.locate_file(entry)
        if not source.is_file():
            raise ValueError(f"Recorded wheel DLL is missing: {entry}")
        with source.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").digest()
        actual_hash = "sha256=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        if expected_hash != actual_hash:
            raise ValueError(f"Recorded wheel DLL hash does not match: {entry}")
        binaries.append((str(source), str(path.parent)))
    if not binaries:
        raise ValueError("The Windows HEIC distribution contains no recorded DLLs")
    return binaries

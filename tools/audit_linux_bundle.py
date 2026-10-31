"""Reject bundled ELF requirements newer than the declared Linux glibc baseline."""

import os
import re
import subprocess
from pathlib import Path

GLIBC_BASELINE = (2, 39)


def required_glibc(output):
    """Inspect version needs only; a library's exported versions are not requirements."""
    needs = False
    versions = set()
    for line in output.splitlines():
        if line.startswith("Version "):
            needs = line.startswith("Version needs section")
        if needs:
            versions.update(
                tuple(map(int, value.split(".")))
                for value in re.findall(r"\bName: GLIBC_([0-9]+(?:\.[0-9]+)+)\b", line)
            )
    return sorted(versions)


def audit(bundle, baseline=GLIBC_BASELINE):
    bundle = Path(bundle)
    files = []
    incompatible = []
    for path in sorted(bundle.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open("rb") as stream:
            if stream.read(4) != b"\x7fELF":
                continue
        result = subprocess.run(
            ["readelf", "--wide", "--version-info", str(path)],
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "LC_ALL": "C"},
        )
        versions = required_glibc(result.stdout)
        relative = path.relative_to(bundle).as_posix()
        files.append({"file": relative, "required_glibc": [list(v) for v in versions]})
        if versions and versions[-1] > baseline:
            incompatible.append(f"{relative}: GLIBC_{'.'.join(map(str, versions[-1]))}")
    if not files:
        raise ValueError("No ELF binaries found in Linux bundle")
    if incompatible:
        raise ValueError(
            f"Bundle exceeds glibc {'.'.join(map(str, baseline))}: "
            + "; ".join(incompatible)
            + ". Rebuild on the declared baseline distribution."
        )
    return {"glibc_baseline": list(baseline), "elf_files": files}

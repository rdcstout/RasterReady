"""Verify Mac bundle metadata and native deployment targets; not release acceptance."""

import argparse
import hashlib
import json
import plistlib
from pathlib import Path

from macholib.mach_o import LC_BUILD_VERSION, LC_VERSION_MIN_MACOSX
from macholib.MachO import MachO
from packaging.version import Version

MACHO_MAGICS = {
    b"\xcf\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xca\xfe\xba\xbe",
    b"\xbe\xba\xfe\xca",
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xce",
    b"\xca\xfe\xba\xbf",
    b"\xbf\xba\xfe\xca",
}


def audit(bundle, expected_version):
    plist_path = bundle / "Contents/Info.plist"
    info = plistlib.loads(plist_path.read_bytes())
    numeric = Version(expected_version).base_version
    expected = {
        "CFBundleIdentifier": "therapy.extrusion.rasterready",
        "CFBundleShortVersionString": numeric,
        "CFBundleVersion": numeric,
        "RasterReadyVersion": expected_version,
    }
    for key, value in expected.items():
        if info.get(key) != value:
            raise ValueError(f"Incorrect {key}: expected {value!r}, got {info.get(key)!r}")
    declared = Version(info["LSMinimumSystemVersion"])
    records = []
    for path in sorted(bundle.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open("rb") as stream:
            if stream.read(4) not in MACHO_MAGICS:
                continue
        for header in MachO(str(path)).headers:
            if header.header.cputype != 0x100000C:
                raise ValueError(f"Non-arm64 binary: {path.relative_to(bundle)}")
            minima = []
            for command, data, _ in header.commands:
                if command.cmd not in (LC_BUILD_VERSION, LC_VERSION_MIN_MACOSX):
                    continue
                if command.cmd == LC_BUILD_VERSION and data.platform != 1:
                    raise ValueError(f"Non-macOS binary: {path.relative_to(bundle)}")
                encoded = data.minos if command.cmd == LC_BUILD_VERSION else data.version
                minimum = f"{encoded >> 16}.{encoded >> 8 & 255}.{encoded & 255}"
                if Version(minimum) > declared:
                    raise ValueError(
                        f"{path.relative_to(bundle)} requires {minimum}, above declared {declared}"
                    )
                minima.append(minimum)
            if not minima:
                raise ValueError(f"No macOS deployment target: {path.relative_to(bundle)}")
            records.append(
                {
                    "path": str(path.relative_to(bundle)),
                    "minimum_versions": minima,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    executable = "Contents/MacOS/" + info["CFBundleExecutable"]
    if not records or executable not in {record["path"] for record in records}:
        raise ValueError("Bundle executable was not verified as a native arm64 binary")
    return {
        "scope": "Metadata, arm64 architecture and native deployment targets only",
        "release_ready": False,
        "version": expected_version,
        "declared_minimum_macos": str(declared),
        "info_plist_sha256": hashlib.sha256(plist_path.read_bytes()).hexdigest(),
        "native_binaries": records,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.bundle, args.version), indent=2))

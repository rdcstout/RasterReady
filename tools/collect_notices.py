"""Collect exact installed license texts as a release-preparation inventory.

This copies available notices only. It does not certify native-library coverage,
source availability, relinking rights, or suitability for distribution.
"""

import argparse
import base64
import csv
import hashlib
import io
import json
import shutil
import sys
import sysconfig
from importlib import metadata
from pathlib import Path

COMPONENTS = (
    "Pillow",
    "pillow-heif",
    "PySide6-Essentials",
    "shiboken6",
    "rawpy",
    "numpy",
    "packaging",
    "PyInstaller",
)


def is_notice(path):
    path = Path(path)
    name = path.name.lower()
    if path.suffix.lower() in {".py", ".pyc", ".pyo", ".so", ".dll", ".dylib"}:
        return False
    return (
        any(word in name for word in ("license", "copying", "notice"))
        or "rasterready_notices" in path.parts
        or any(part.lower() == "licenses" for part in path.parts)
    )


def recorded_notices(dist):
    """Read RECORD directly so missing installed notices cannot disappear."""
    record = dist.read_text("RECORD")
    if record is None:
        raise SystemExit(f"Installed distribution has no RECORD: {dist.metadata['Name']}")
    root = Path(dist.locate_file("")).resolve()
    seen = set()
    for row in csv.reader(io.StringIO(record)):
        if len(row) != 3:
            raise SystemExit("Malformed installed wheel RECORD")
        entry, expected_hash, _ = row
        if not is_notice(entry):
            continue
        path = Path(entry)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in entry
            or ":" in entry
            or entry in seen
        ):
            raise SystemExit(f"Unsafe or duplicate notice path: {entry}")
        seen.add(entry)
        source = Path(dist.locate_file(entry))
        if not source.resolve().is_relative_to(root) or not source.is_file():
            raise SystemExit(f"Recorded notice is missing or outside distribution: {entry}")
        digest = hashlib.sha256(source.read_bytes()).digest()
        actual_hash = "sha256=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        if expected_hash != actual_hash:
            raise SystemExit(f"Recorded notice hash does not match: {entry}")
        yield source, path


def collect(output):
    if output.exists():
        raise SystemExit("Use a new output directory; existing notice inventories are preserved.")
    output.mkdir(parents=True)
    manifest = {
        "scope": "Exact installed primary distributions and available license files only",
        "release_ready": False,
        "unresolved": [
            "Verify all native components in the exact final artifact, including Qt third-party code",
            "Supply matching native source/build information and verify applicable relinking obligations",
            "Complete platform-specific runtime, installer and distribution checks",
        ],
        "components": [],
    }

    def copy(source, relative):
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        return {
            "path": relative.as_posix(),
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        }

    manifest["application"] = {
        "name": "RasterReady",
        "notice": copy(
            Path(__file__).resolve().parents[1] / "LICENSE", Path("RasterReady") / "LICENSE.txt"
        ),
    }
    for name in COMPONENTS:
        dist = metadata.distribution(name)
        component = {"name": name, "version": dist.version, "notices": []}
        for source, entry in sorted(recorded_notices(dist), key=lambda item: str(item[1])):
            component["notices"].append(copy(source, Path(name) / entry))
        if not component["notices"]:
            manifest["unresolved"].append(
                f"{name} contains no notice texts; obtain exact upstream notices"
            )
        manifest["components"].append(component)
    python_license = next(
        (
            path
            for path in (
                Path(sys.base_prefix) / "LICENSE.txt",
                Path(sysconfig.get_path("stdlib")) / "LICENSE.txt",
            )
            if path.is_file()
        ),
        None,
    )
    if python_license is not None:
        manifest["python"] = {
            "version": sys.version.split()[0],
            "notice": copy(python_license, Path("Python") / "LICENSE.txt"),
        }
    else:
        manifest["unresolved"].append(
            "Python runtime license text not present at the expected path"
        )
    tabler = Path(__file__).resolve().parents[1] / "rasterready/assets/TABLER-LICENSE.txt"
    manifest["tabler"] = copy(tabler, Path("Tabler") / "LICENSE.txt")
    if any(metadata.version(name) != "6.12.0" for name in ("PySide6-Essentials", "shiboken6")):
        raise SystemExit("Match the Qt component supplement to the installed Qt version first")
    qt = Path(__file__).resolve().parents[1] / "third_party/Qt"
    manifest["qt_supplement"] = [
        copy(source, Path("Qt-upstream") / source.relative_to(qt))
        for source in sorted(qt.rglob("*"))
        if source.is_file()
    ]
    if sys.platform == "darwin" and metadata.version("rawpy") == "0.27.1":
        rawpy_notices = Path(__file__).resolve().parents[1] / "third_party/rawpy-macos"
        manifest["rawpy_macos_supplement"] = [
            copy(source, Path("rawpy-Mac-upstream") / source.relative_to(rawpy_notices))
            for source in sorted(rawpy_notices.rglob("*"))
            if source.is_file()
        ]
    (output / "inventory.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Collected notices into {output}; unresolved release requirements remain.")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    collect(parser.parse_args().output.resolve())

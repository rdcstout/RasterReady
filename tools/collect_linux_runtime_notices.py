"""Retain Debian/Ubuntu notices for unchanged system libraries in a Linux bundle."""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(bundle):
    internal = bundle / "_internal"
    if not internal.is_dir() or not shutil.which("dpkg-query"):
        raise ValueError("Use the documented Debian/Ubuntu Linux packaging environment")
    output = internal / "third_party_notices" / "Linux-system-runtime"
    if output.exists():
        raise ValueError("Runtime notice output already exists; use a fresh bundle")
    output.mkdir(parents=True)
    query = subprocess.check_output(
        [
            "dpkg-query",
            "-W",
            "-f",
            "${binary:Package}\t${Version}\t${source:Package}\t${source:Version}\n",
        ],
        text=True,
    )
    packages = {row.split("\t")[0]: row.split("\t") for row in query.splitlines()}
    records = []
    copied = {}
    unmatched = []
    for binary in sorted(internal.rglob("*")):
        if not binary.is_file() or binary.is_symlink():
            continue
        with binary.open("rb") as stream:
            if stream.read(4) != b"\x7fELF":
                continue
        if binary.name.startswith(("libreadline.so", "readline.")):
            raise ValueError("Unused interactive Readline must not be included in the GUI bundle")
        digest = sha256(binary)
        for directory in ("/usr/lib/x86_64-linux-gnu", "/lib/x86_64-linux-gnu", "/usr/local/lib"):
            source = Path(directory) / binary.name
            if not source.is_file() or sha256(source) != digest:
                continue
            result = subprocess.run(
                ["dpkg-query", "-S", str(source.resolve())], capture_output=True, text=True
            )
            if result.returncode:
                continue
            package = result.stdout.split(": /", 1)[0]
            details = packages[package]
            name = package.split(":", 1)[0]
            notice = Path("/usr/share/doc") / name / "copyright"
            if not notice.is_file():
                raise ValueError(f"System package has no retained copyright notice: {package}")
            if name not in copied:
                destination = output / name / "copyright"
                destination.parent.mkdir(parents=True)
                shutil.copyfile(notice, destination)
                copied[name] = {
                    "path": destination.relative_to(output).as_posix(),
                    "sha256": sha256(destination),
                }
            records.append(
                {
                    "payload": binary.relative_to(bundle).as_posix(),
                    "sha256": digest,
                    "binary_package": details[0],
                    "binary_version": details[1],
                    "source_package": details[2],
                    "source_version": details[3],
                    "notice": copied[name],
                }
            )
            break
        else:
            unmatched.append({"payload": binary.relative_to(bundle).as_posix(), "sha256": digest})
    # Debian copyright files reference these complete standard license texts.
    common = []
    for source in sorted(Path("/usr/share/common-licenses").iterdir()):
        if source.is_file():
            destination = output / "common-licenses" / source.name
            destination.parent.mkdir(exist_ok=True)
            shutil.copyfile(source, destination)
            common.append(
                {"path": destination.relative_to(output).as_posix(), "sha256": sha256(destination)}
            )
    manifest = {
        "scope": "SHA-256 matched Debian/Ubuntu system libraries; wheel components have separate notices",
        "system_libraries": records,
        "common_licenses": common,
        "wheel_or_other_libraries": unmatched,
        "source_materials": "Retain the exact source_package/source_version archives with release materials",
    }
    (output / "inventory.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Retained notices for {len(records)} system libraries from {len(copied)} packages")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    collect(parser.parse_args().bundle.resolve())

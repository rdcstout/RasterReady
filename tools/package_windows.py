"""Prepare an unsigned Windows installer; native acceptance and release gates remain."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from packaging.version import Version

if __package__:
    from .windows_version import audit
else:
    from windows_version import audit

ROOT = Path(__file__).resolve().parents[1]


def checked_path(path):
    text = str(path)
    if any(character in text for character in ("$", '"', "\n", "\r")):
        raise ValueError("Build paths must not contain quotes, dollar signs or newlines")
    return text


def inventory(bundle):
    files = []
    for path in sorted(bundle.rglob("*")):
        if path.is_symlink():
            raise ValueError("Windows packaging requires regular payload files, not symlinks")
        if path.is_file():
            relative = path.relative_to(bundle)
            if any(character in str(relative) for character in '$"\n\r:*?<>|'):
                raise ValueError(f"Unsupported Windows payload filename: {relative}")
            files.append((path, relative))
        elif not path.is_dir():
            raise ValueError("Special file in Windows bundle")
    if not files or not (bundle / "RasterReady.exe").is_file():
        raise ValueError("Supply a Windows bundle containing RasterReady.exe")
    return files


def write_file_lists(bundle, output):
    files = inventory(bundle)
    install = []
    uninstall = []
    remove_directories = []
    directories = set()
    for source, relative in files:
        destination = str(relative.parent).replace("/", "\\")
        install += [f'SetOutPath "$INSTDIR\\{destination}"', f'File "{checked_path(source)}"']
        windows_relative = relative.as_posix().replace("/", "\\")
        uninstall.append(f'Delete "$INSTDIR\\{windows_relative}"')
        directories.update(parent for parent in relative.parents if str(parent) != ".")
    # RMDir is nonrecursive; it cannot remove unrelated files inside these directories.
    for directory in sorted(directories, key=lambda path: (-len(path.parts), str(path))):
        windows_directory = directory.as_posix().replace("/", "\\")
        remove_directories.append(f'RMDir "$INSTDIR\\{windows_directory}"')
    for filename, lines in [
        ("install-files.nsh", install),
        ("uninstall-files.nsh", uninstall),
        ("remove-empty-dirs.nsh", remove_directories),
    ]:
        (output / filename).write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return files


def package(bundle, output, version, compiler, development):
    parsed = Version(version)
    if output.exists() or output.is_symlink() or output.is_relative_to(bundle):
        raise ValueError("Use a new output directory outside the bundle")
    if not development and (
        parsed.is_prerelease or parsed.is_devrelease or parsed.local or parsed.epoch
    ):
        raise ValueError("A candidate requires a stable public version")
    if not development and sys.platform != "win32":
        raise ValueError("Build Windows candidates on native Windows")
    executable_metadata = audit(bundle / "RasterReady.exe", version)
    flag = "/" if sys.platform == "win32" else "-"
    result = subprocess.run(
        [str(compiler), flag + "VERSION"], check=True, capture_output=True, text=True
    )
    if result.stdout.strip() != "v3.13":
        raise ValueError("Use the pinned NSIS 3.13 compiler")
    output.mkdir(parents=True)
    files = write_file_lists(bundle, output)
    suffix = "-development" if development else ""
    artifact = output / f"RasterReady-{parsed}-windows-x64{suffix}.exe"
    arguments = [str(compiler), flag + "WX", flag + "V2"]
    definitions = {
        "OUTPUT_FILE": artifact,
        "PRODUCT_ICON": ROOT / "rasterready/assets/RasterReady.ico",
        "APP_VERSION": str(parsed),
        "INSTALL_FILES": output / "install-files.nsh",
        "UNINSTALL_FILES": output / "uninstall-files.nsh",
        "REMOVE_DIRECTORIES": output / "remove-empty-dirs.nsh",
    }
    arguments += [
        flag + "D" + name + "=" + checked_path(value) for name, value in definitions.items()
    ]
    subprocess.run(arguments + [str(ROOT / "packaging/windows.nsi")], check=True)
    payload = []
    for source, relative in files:
        with source.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        payload.append({"path": str(relative), "sha256": digest})
    with artifact.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "artifact": artifact.name,
                "sha256": digest,
                "version": str(parsed),
                "kind": "unsigned-development-installer"
                if development
                else "unsigned-local-candidate",
                "release_ready": False,
                "payload": payload,
                "native_install_upgrade_uninstall_acceptance": False,
                "executable_metadata": executable_metadata,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"Prepared {artifact}; unsigned; exact-artifact acceptance and release approval remain.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--makensis", type=Path, required=True)
    parser.add_argument("--development", action="store_true")
    args = parser.parse_args()
    package(
        args.bundle.resolve(),
        args.output.resolve(),
        args.version,
        args.makensis.resolve(),
        args.development,
    )

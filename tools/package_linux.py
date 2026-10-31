"""Stage Linux packages; native DEB/AppImage builds and acceptance remain separate."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from linux_package_tools import verify
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]


def validate_bundle(bundle):
    main = bundle / "RasterReady"
    with main.open("rb") as stream:
        header = stream.read(20)
    if header[:6] != b"\x7fELF\x02\x01" or header[18:20] != b"\x3e\x00":
        raise ValueError("Supply an ELF64 little-endian x86_64 Linux bundle")
    if not os.access(main, os.X_OK):
        raise ValueError("The Linux application must be executable")
    for path in bundle.rglob("*"):
        if path.is_symlink():
            if Path(os.readlink(path)).is_absolute() or not path.resolve().is_relative_to(bundle):
                raise ValueError(f"Symlink escapes the relocatable bundle: {path}")
            if not path.exists():
                raise ValueError(f"Broken bundle symlink: {path}")
        elif not (path.is_file() or path.is_dir()):
            raise ValueError(f"Special file in bundle: {path}")


def stage(bundle, output, version):
    if output.exists() or output.is_symlink() or output.is_relative_to(bundle):
        raise ValueError("Use a new output directory outside the bundle")
    validate_bundle(bundle)
    parsed = Version(version)
    # A local development version sorts before the corresponding stable package.
    deb_version = str(parsed).replace(".dev", "~dev")
    if not all(character.isalnum() or character in ".+~" for character in deb_version):
        raise ValueError("Unsupported development Debian version")
    output.mkdir(parents=True)
    appdir = output / "RasterReady.AppDir"
    deb = output / "deb-root"
    for root in (appdir, deb):
        destination = root / "usr/lib/rasterready"
        destination.parent.mkdir(parents=True)
        shutil.copytree(bundle, destination, symlinks=True)
        desktop = root / "usr/share/applications/rasterready.desktop"
        desktop.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "packaging/rasterready.desktop", desktop)
        for size in (16, 24, 32, 48, 64, 128, 256, 512):
            icon = root / f"usr/share/icons/hicolor/{size}x{size}/apps/rasterready.png"
            icon.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / f"rasterready/assets/product-icon-{size}.png", icon)
        notices = root / "usr/share/doc/rasterready"
        notices.mkdir(parents=True)
        shutil.copyfile(
            ROOT / "rasterready/assets/TABLER-LICENSE.txt", notices / "TABLER-LICENSE.txt"
        )
    app_bin = appdir / "usr/bin"
    app_bin.mkdir()
    (app_bin / "rasterready").symlink_to("../lib/rasterready/RasterReady")
    (appdir / "rasterready.desktop").symlink_to("usr/share/applications/rasterready.desktop")
    (appdir / "rasterready.png").symlink_to("usr/share/icons/hicolor/256x256/apps/rasterready.png")
    (appdir / ".DirIcon").symlink_to("rasterready.png")
    (appdir / "AppRun").write_text(
        '#!/bin/sh\nAPPDIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1\n'
        'exec "$APPDIR/usr/lib/rasterready/RasterReady" "$@"\n'
    )
    (appdir / "AppRun").chmod(0o755)
    launcher = deb / "usr/bin/rasterready"
    launcher.parent.mkdir(parents=True)
    launcher.write_text('#!/bin/sh\nexec /usr/lib/rasterready/RasterReady "$@"\n')
    launcher.chmod(0o755)
    control = deb / "DEBIAN/control"
    control.parent.mkdir()
    control.write_text(
        f"Package: rasterready\nVersion: {deb_version}\nArchitecture: amd64\n"
        "Maintainer: RasterReady project\nSection: graphics\nPriority: optional\n"
        "Depends: libc6 (>= 2.39), libstdc++6, libgcc-s1, libegl1, libgl1, "
        "libxkbcommon-x11-0, libxcb-cursor0, libxcb-icccm4, libxcb-keysyms1, "
        "libxcb-randr0, libxcb-shape0, libxcb-xfixes0, libxcb-sync1, libxcb-xkb1\n"
        "Homepage: https://github.com/rdcstout/RasterReady\n"
        "Description: Local development trial for web image preparation\n"
        " PNG conversion with embedded metadata removed. Not a release package.\n"
    )
    manifest = {
        "version": str(parsed),
        "debian_version": deb_version,
        "kind": "development-staging",
        "release_ready": False,
        "product_icon": "Roger-selected red crop/photo mark (option 2)",
        "native_build_and_install_acceptance": False,
        "baseline": "Ubuntu 24.04 x64 trial; system dependency closure unverified",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return appdir, deb, manifest


def build(output, appdir, deb, manifest, tool_directory):
    if sys.platform != "linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise ValueError(
            "Native package building requires Linux x64; use --stage-only for inspection"
        )
    verify(tool_directory)
    desktop = appdir / "rasterready.desktop"
    subprocess.run(["desktop-file-validate", str(desktop)], check=True)
    name = f"RasterReady-{manifest['version']}-linux-x64-development"
    deb_file = output / f"{name}.deb"
    appimage = output / f"{name}.AppImage"
    subprocess.run(
        ["dpkg-deb", "--root-owner-group", "--build", str(deb), str(deb_file)], check=True
    )
    subprocess.run(["dpkg-deb", "--info", str(deb_file)], check=True)
    environment = os.environ.copy()
    # Extraction applies to the build tool only, never to acceptance of the result.
    environment.update(APPIMAGE_EXTRACT_AND_RUN="1", ARCH="x86_64", VERSION=manifest["version"])
    subprocess.run(
        [
            str(tool_directory / "appimagetool-x86_64.AppImage"),
            "--runtime-file",
            str(tool_directory / "runtime-x86_64"),
            str(appdir),
            str(appimage),
        ],
        env=environment,
        check=True,
    )
    appimage.chmod(0o755)
    manifest["artifacts"] = []
    for artifact in (deb_file, appimage):
        with artifact.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        manifest["artifacts"].append({"file": artifact.name, "sha256": digest})
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--development", action="store_true")
    parser.add_argument("--stage-only", action="store_true")
    parser.add_argument("--tool-directory", type=Path)
    args = parser.parse_args()
    if not args.development:
        parser.error("Metadata, dependency and native acceptance gates remain; development only")
    if not args.stage_only and args.tool_directory is None:
        parser.error("Native build requires the pinned --tool-directory")
    appdir, deb, manifest = stage(args.bundle.resolve(), args.output.resolve(), args.version)
    if not args.stage_only:
        build(args.output.resolve(), appdir, deb, manifest, args.tool_directory.resolve())
    print(f"Prepared development packaging under {args.output}; not release-ready.")

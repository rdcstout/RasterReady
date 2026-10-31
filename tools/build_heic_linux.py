"""Prepare a decoder-only HEIC wheel on native Linux x64; target execution pending.

Does not install the wheel, publish it, or certify final application compatibility.
Run in a dedicated build environment with a compiler, pkg-config and patchelf.
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

from heic_sources import SOURCES, decoder_configurations, fetch_sources, include_notices


def run(arguments, environment):
    subprocess.run([str(value) for value in arguments], env=environment, check=True)


def build(output, platform_tag):
    if sys.platform != "linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise SystemExit("This builder requires native Linux x64.")
    if output.exists():
        raise SystemExit("Choose a new output directory; existing builds are preserved.")
    for tool in ("cmake", "ninja", "auditwheel", "patchelf", "pkg-config", "c++"):
        if not shutil.which(tool):
            raise SystemExit(f"Missing native build requirement: {tool}")
    output.mkdir(parents=True)
    prefix = output / "prefix"
    environment = os.environ.copy()
    environment["LIBHEIF_ROOT"] = str(prefix)
    # Restrict dependency lookup to this build's prefix before system paths.
    environment["PKG_CONFIG_PATH"] = str(prefix / "lib/pkgconfig")
    environment["LD_LIBRARY_PATH"] = str(prefix / "lib")
    sources = fetch_sources(output)
    common = [
        "-G",
        "Ninja",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_INSTALL_PREFIX={prefix}",
        "-DCMAKE_INSTALL_LIBDIR=lib",
        "-DBUILD_SHARED_LIBS=ON",
        "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
    ]
    configurations = decoder_configurations(prefix)
    for name, options in configurations.items():
        source = output / f"{name}-{SOURCES[name][1]}"
        destination = output / f"{name}-build"
        run(["cmake", "-S", source, "-B", destination, *common, *options], environment)
        run(["cmake", "--build", destination, "-j", "4"], environment)
        run(["cmake", "--install", destination], environment)
    source = output / "pillow_heif-1.8.1"
    include_notices(output, source)
    constraints = Path(__file__).resolve().parents[1] / "requirements-heic-build.txt"
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--build-constraint",
            constraints,
            "--no-deps",
            "--wheel-dir",
            output / "unrepaired",
            source,
        ],
        environment,
    )
    wheels = list((output / "unrepaired").glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Expected exactly one freshly built HEIC wheel.")
    run(
        [
            "auditwheel",
            "repair",
            "--plat",
            platform_tag,
            "--wheel-dir",
            output / "wheels",
            wheels[0],
        ],
        environment,
    )
    wheels = list((output / "wheels").glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Expected exactly one repaired HEIC wheel.")
    wheel = wheels[0]
    with ZipFile(wheel) as archive:
        names = set(archive.namelist())
        required = {
            f"pillow_heif/rasterready_notices/{name}"
            for name in ("BUILD.txt", "libheif-COPYING.txt", "libde265-COPYING.txt")
        }
        libraries = {Path(name).name for name in names if ".so" in Path(name).name}
        native_libraries = {name for name in libraries if not name.startswith("_pillow_heif.")}
        if (
            not required <= names
            or len(native_libraries) != 2
            or not any(name.startswith("libheif-") for name in native_libraries)
            or not any(name.startswith("libde265-") for name in native_libraries)
        ):
            raise SystemExit("Repaired decoder library/notice inventory is unexpected.")
    manifest = {
        "sources": sources,
        "wheel": wheel.name,
        "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "platform": "linux-x64",
        "requested_wheel_platform": platform_tag,
        "release_ready": False,
        "validation": "Build only; fresh-environment decode and final artifact acceptance required.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "tools").mkdir()
    for name in ("build_heic_linux.py", "heic_sources.py"):
        shutil.copyfile(Path(__file__).with_name(name), output / "tools" / name)
    shutil.copyfile(constraints, output / constraints.name)
    print(f"Built {wheel}; not installed or published.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New directory for sources, build and wheel")
    parser.add_argument(
        "--platform-tag",
        default="manylinux_2_34_x86_64",
        choices=("manylinux_2_34_x86_64", "manylinux_2_39_x86_64"),
        help="Required ABI ceiling; repair must fail if compiled symbols exceed this baseline",
    )
    args = parser.parse_args()
    build(args.output.resolve(), args.platform_tag)

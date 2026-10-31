"""Prepare a decoder-only HEIC wheel on Windows x64; native execution pending.

Requires CPython 3.12 and Visual Studio 2022 or 2026 C++ build tools. Does not install or
publish the wheel. Uses a private prefix, not an existing MSYS2 installation.
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

if __package__:
    from .heic_sources import SOURCES, decoder_configurations, fetch_sources, include_notices
else:
    from heic_sources import SOURCES, decoder_configurations, fetch_sources, include_notices


def run(arguments, environment):
    subprocess.run([str(value) for value in arguments], env=environment, check=True)


def visual_studio(environment):
    """Select an installed supported C++ toolchain rather than assume VS 2022."""
    # os.environ is case-insensitive on Windows, but its copied dict is not.
    program_files = next(
        (value for key, value in environment.items() if key.upper() == "PROGRAMFILES(X86)"), None
    )
    if not program_files:
        raise SystemExit("Cannot locate the Visual Studio installer; install C++ build tools.")
    locator = Path(program_files) / "Microsoft Visual Studio/Installer/vswhere.exe"
    if not locator.is_file():
        raise SystemExit("Visual Studio vswhere.exe is missing; install C++ build tools.")
    result = subprocess.run(
        [
            str(locator),
            "-latest",
            "-products",
            "*",
            "-requires",
            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-format",
            "json",
            "-utf8",
        ],
        check=True,
        capture_output=True,
        encoding="utf-8-sig",
    )
    instances = json.loads(result.stdout)
    if len(instances) != 1:
        raise SystemExit("No installed Visual Studio C++ x64 toolchain was found.")
    instance = instances[0]
    major = instance["installationVersion"].split(".")[0]
    generator = {"17": "Visual Studio 17 2022", "18": "Visual Studio 18 2026"}.get(major)
    if generator is None:
        raise SystemExit(f"Unsupported Visual Studio version: {instance['installationVersion']}")
    location = Path(instance["installationPath"])
    if not location.is_dir():
        raise SystemExit("The detected Visual Studio installation directory does not exist.")
    return generator, location


def build(output):
    if sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise SystemExit("This builder requires native Windows x64.")
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Use CPython 3.12 for the application packaging environment.")
    if struct.calcsize("P") != 8:
        raise SystemExit("Use a 64-bit CPython environment for the x64 build.")
    if output.exists():
        raise SystemExit("Choose a new output directory; existing builds are preserved.")
    for tool in ("cmake", "delvewheel"):
        if not shutil.which(tool):
            raise SystemExit(f"Install requirements-heic-build.txt first: missing {tool}")
    output.mkdir(parents=True)
    prefix = output / "prefix"
    environment = os.environ.copy()
    environment["LIBHEIF_ROOT"] = str(prefix)
    # Upstream stages libheif headers from this named prefix. Supply only the
    # matching CMake install; no system MSYS2 files or include paths are used.
    environment["MSYS2_PREFIX"] = str(prefix)
    generator, compiler_instance = visual_studio(environment)
    sources = fetch_sources(output)
    common = [
        "-G",
        generator,
        "-A",
        "x64",
        f"-DCMAKE_GENERATOR_INSTANCE={compiler_instance}",
        f"-DCMAKE_INSTALL_PREFIX={prefix}",
        "-DCMAKE_INSTALL_LIBDIR=lib",
        "-DBUILD_SHARED_LIBS=ON",
    ]
    for name, options in decoder_configurations(prefix).items():
        source = output / f"{name}-{SOURCES[name][1]}"
        destination = output / f"{name}-build"
        run(["cmake", "-S", source, "-B", destination, *common, *options], environment)
        run(["cmake", "--build", destination, "--config", "Release", "-j", "4"], environment)
        run(["cmake", "--install", destination, "--config", "Release"], environment)
    # The Python extension links 'libheif'; CMake's heif target produces heif.lib.
    # Retain the original and supply a byte-identical import-library name alias.
    import_library = prefix / "lib/libheif.lib"
    if not import_library.exists():
        shutil.copyfile(prefix / "lib/heif.lib", import_library)
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
            "delvewheel",
            "repair",
            "--add-path",
            prefix / "bin",
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
    import pefile

    with ZipFile(wheel) as archive:
        names = set(archive.namelist())
        required = {
            f"pillow_heif/rasterready_notices/{name}"
            for name in ("BUILD.txt", "libheif-COPYING.txt", "libde265-COPYING.txt")
        }
        libraries = {Path(name).name.lower() for name in names if name.lower().endswith(".dll")}
        if (
            not required <= names
            or not any(name.startswith(("heif-", "libheif-")) for name in libraries)
            or not any(name.startswith("libde265-") for name in libraries)
            or any(
                not name.startswith(("heif-", "libheif-", "libde265-", "msvcp140", "vcruntime140"))
                for name in libraries
            )
        ):
            raise SystemExit("Repaired DLL/notice inventory is unexpected; inspect before using.")
        for name in names:
            if name.lower().endswith((".dll", ".pyd")):
                with pefile.PE(data=archive.read(name), fast_load=True) as binary:
                    if binary.FILE_HEADER.Machine != 0x8664:
                        raise SystemExit(f"Non-x64 PE binary in wheel: {name}")
    manifest = {
        "sources": sources,
        "wheel": wheel.name,
        "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "platform": "windows-x64",
        "cmake_generator": generator,
        "compiler_instance": str(compiler_instance),
        "dlls": sorted(libraries),
        "import_library_alias": "heif.lib copied as libheif.lib for upstream extension lookup",
        "release_ready": False,
        "validation": "Build only; clean-environment decode and final installer acceptance required.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "tools").mkdir()
    for name in ("build_heic_windows.py", "heic_sources.py"):
        shutil.copyfile(Path(__file__).with_name(name), output / "tools" / name)
    shutil.copyfile(constraints, output / constraints.name)
    print(f"Built {wheel}; not installed or published.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New directory for sources, build and wheel")
    build(parser.parse_args().output.resolve())

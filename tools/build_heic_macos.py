"""Build a self-contained, decoder-only HEIC wheel on Apple Silicon macOS.

Does not install the result, change the application environment, or publish files.
The output includes pinned corresponding sources and native library notices.
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

from heic_sources import SOURCES, fetch_sources, include_notices


def run(args, env):
    subprocess.run([str(arg) for arg in args], env=env, check=True)


def build(output):
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise SystemExit("This builder requires native Apple Silicon macOS.")
    if output.exists():
        raise SystemExit("Choose a new output directory; existing builds are preserved.")
    for tool in ("cmake", "ninja", "delocate-wheel"):
        if not shutil.which(tool):
            raise SystemExit(f"Install requirements-heic-build.txt first: missing {tool}")
    output.mkdir(parents=True)
    prefix = output / "prefix"
    env = os.environ.copy()
    sdk = subprocess.check_output(["xcrun", "--show-sdk-path"], text=True).strip()
    env.update(SDKROOT=sdk, MACOSX_DEPLOYMENT_TARGET="14.0", LIBHEIF_ROOT=str(prefix))
    sources = fetch_sources(output)
    common = [
        "-G",
        "Ninja",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_INSTALL_PREFIX={prefix}",
        "-DCMAKE_OSX_DEPLOYMENT_TARGET=14.0",
        "-DBUILD_SHARED_LIBS=ON",
    ]
    configurations = {
        "libde265": ["-DENABLE_SDL=OFF", "-DENABLE_DECODER=OFF", "-DENABLE_ENCODER=OFF"],
        "libheif": [
            f"-DCMAKE_PREFIX_PATH={prefix}",
            "-DWITH_LIBDE265=ON",
            "-DWITH_LIBDE265_PLUGIN=OFF",
            "-DENABLE_PLUGIN_LOADING=OFF",
            "-DWITH_X265=OFF",
            "-DWITH_X264=OFF",
            "-DWITH_AOM_ENCODER=OFF",
            "-DWITH_AOM_DECODER=OFF",
            "-DWITH_OpenH264_DECODER=OFF",
            "-DWITH_LIBSHARPYUV=OFF",
            "-DWITH_EXAMPLES=OFF",
            "-DWITH_GDK_PIXBUF=OFF",
            "-DBUILD_TESTING=OFF",
            "-DBUILD_DOCUMENTATION=OFF",
        ],
    }
    for name, options in configurations.items():
        source = output / f"{name}-{SOURCES[name][1]}"
        destination = output / f"{name}-build"
        run(["cmake", "-S", source, "-B", destination, *common, *options], env)
        run(["cmake", "--build", destination, "-j", "4"], env)
        run(["cmake", "--install", destination], env)
    # Upstream substitutes an installed CommandLineTools SDK, which can be too old
    # for arm64. Honor the SDKROOT explicitly selected above. No codec code changes.
    source = output / "pillow_heif-1.8.1"
    setup = source / "setup.py"
    original = setup.read_text()
    marker = "    def _get_macos_sdk_path():\n"
    if original.count(marker) != 1:
        raise SystemExit("Upstream SDK selector changed; inspect before patching.")
    replacement = (
        marker + '        if os.environ.get("SDKROOT"):\n            return os.environ["SDKROOT"]\n'
    )
    setup.write_text(original.replace(marker, replacement))
    (output / "sdkroot.patch").write_text(
        "--- setup.py\n+++ setup.py\n@@ -234,2 +234,4 @@\n"
        "     @staticmethod\n     def _get_macos_sdk_path():\n"
        '+        if os.environ.get("SDKROOT"):\n+            return os.environ["SDKROOT"]\n'
    )
    include_notices(output, source)
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--build-constraint",
            Path(__file__).resolve().parents[1] / "requirements-heic-build.txt",
            "--no-deps",
            "--wheel-dir",
            output / "unrepaired",
            source,
        ],
        env,
    )
    wheel = next((output / "unrepaired").glob("*.whl"))
    env["DYLD_LIBRARY_PATH"] = str(prefix / "lib")
    run(["delocate-wheel", "--require-archs", "arm64", "-w", output / "wheels", wheel], env)
    repaired = next((output / "wheels").glob("*.whl"))
    with ZipFile(repaired) as archive:
        names = set(archive.namelist())
        required = {
            "pillow_heif/rasterready_notices/libheif-COPYING.txt",
            "pillow_heif/rasterready_notices/libde265-COPYING.txt",
            "pillow_heif/rasterready_notices/BUILD.txt",
        }
        dylibs = {Path(name).name for name in names if name.endswith(".dylib")}
        if not required <= names or dylibs != {"libheif.1.23.6.dylib", "libde265.0.2.3.dylib"}:
            raise SystemExit("Repaired wheel library/notice inventory differs from expected.")
    manifest = {
        "sources": sources,
        "wheel": repaired.name,
        "sha256": hashlib.sha256(repaired.read_bytes()).hexdigest(),
        "platform": "macos-arm64",
        "minimum_macos": "14.0",
        "validation": "Build only; runtime and final packaged artifact acceptance remain required.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    # Keep the builder's relative constraints path valid in the source bundle.
    (output / "tools").mkdir()
    shutil.copyfile(__file__, output / "tools" / "build_heic_macos.py")
    shutil.copyfile(Path(__file__).with_name("heic_sources.py"), output / "tools/heic_sources.py")
    shutil.copyfile(
        Path(__file__).resolve().parents[1] / "requirements-heic-build.txt",
        output / "requirements-heic-build.txt",
    )
    print(f"Built {repaired}; not installed or published.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New directory for build, sources and wheel")
    build(parser.parse_args().output.resolve())

"""Build a local app bundle. Installer packaging and notarization are separate."""

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--decoder-only-heic",
        action="store_true",
        help="Require the custom HEIC decoder build and include its notices",
    )
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--codesign-identity", help="macOS Developer ID certificate name or SHA-1")
    args = parser.parse_args()
    if args.codesign_identity and sys.platform != "darwin":
        parser.error("--codesign-identity requires macOS")
    if sys.platform == "darwin" and platform.machine() != "arm64":
        parser.error("The Mac build targets Apple Silicon; run from an arm64 Python environment")
    if args.decoder_only_heic:
        import pillow_heif

        info = pillow_heif.libheif_info()
        notices = Path(pillow_heif.__file__).parent / "rasterready_notices"
        if (
            info["libheif"] != "1.23.6"
            or info["decoders"] != {"libde265": "libde265 HEVC decoder, version 1.1.3"}
            or set(info["encoders"]) - {"mask"}
            or not (notices / "libheif-COPYING.txt").is_file()
            or not (notices / "libde265-COPYING.txt").is_file()
        ):
            raise SystemExit("Install the verified decoder-only HEIC wheel before packaging.")
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--distpath",
        str(args.dist_dir.resolve()),
        "--workpath",
        str(ROOT / "build"),
        str(ROOT / "packaging/rasterready.spec"),
    ]
    environment = os.environ.copy()
    environment["RASTERREADY_DECODER_ONLY_HEIC"] = "1" if args.decoder_only_heic else "0"
    environment["RASTERREADY_CODESIGN_IDENTITY"] = args.codesign_identity or ""
    subprocess.run(command, cwd=ROOT, env=environment, check=True)
    if sys.platform == "darwin":
        from rasterready import __version__
        from tools.audit_macos_bundle import audit

        result = audit(args.dist_dir.resolve() / "RasterReady.app", __version__)
        print(
            f"Verified metadata and deployment targets for {len(result['native_binaries'])} binaries"
        )
    elif sys.platform == "win32":
        from rasterready import __version__
        from tools.windows_version import audit

        result = audit(args.dist_dir.resolve() / "RasterReady/RasterReady.exe", __version__)
        print(f"Verified Windows executable identity and version {result['version']}")
    elif sys.platform == "linux":
        from tools.collect_linux_runtime_notices import collect

        collect(args.dist_dir.resolve() / "RasterReady")


if __name__ == "__main__":
    main()

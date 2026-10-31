"""Create and inspect a local Mac DMG; never upload or declare release acceptance.

Development images are explicitly named and bypass final-icon/notarization gates.
Candidate preparation requires a stable, notarized app with the final product icon.
"""

import argparse
import hashlib
import json
import os
import plistlib
import re
import subprocess
import sys
from pathlib import Path

from audit_macos_bundle import audit
from packaging.version import Version


def run(arguments, capture=False):
    return subprocess.run(
        [str(argument) for argument in arguments],
        check=True,
        capture_output=capture,
        text=capture,
    )


def contents(bundle):
    records = {}
    for path in sorted(bundle.rglob("*")):
        relative = str(path.relative_to(bundle))
        if path.is_symlink():
            records[relative] = {"symlink": os.readlink(path)}
        elif path.is_file():
            with path.open("rb") as stream:
                records[relative] = {"sha256": hashlib.file_digest(stream, "sha256").hexdigest()}
        elif path.is_dir():
            records[relative] = {"directory": True}
        else:
            raise ValueError(f"Unexpected special file in application: {relative}")
    return records


def signature(bundle, require_developer_id):
    run(["codesign", "--verify", "--deep", "--strict", bundle])
    details = run(["codesign", "-dv", "--verbose=4", bundle], capture=True).stderr
    result = {
        "developer_id": "Authority=Developer ID Application:" in details,
        "hardened_runtime": "(runtime)" in details,
        "secure_timestamp": "Timestamp=" in details,
    }
    if require_developer_id and not all(result.values()):
        raise ValueError("Candidate app requires Developer ID, Hardened Runtime and a timestamp")
    return result


def package(bundle, output, version, source_revision, development=False, identity=None):
    if sys.platform != "darwin":
        raise SystemExit("DMG creation requires macOS")
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", source_revision):
        raise ValueError("Supply the actual app build's source revision as a Git commit hash")
    if bundle.name != "RasterReady.app" or not bundle.is_dir():
        raise ValueError("Supply the built RasterReady.app bundle")
    if output.exists() or output.is_symlink() or output.is_relative_to(bundle):
        raise ValueError("Use a new output directory outside the app; existing work is preserved")
    metadata = audit(bundle, version)
    app_signature = signature(bundle, require_developer_id=not development)
    if not development:
        parsed = Version(version)
        if parsed.is_prerelease or parsed.is_devrelease or parsed.local:
            raise ValueError("Stable candidate packaging requires a stable app version")
        info = plistlib.loads((bundle / "Contents/Info.plist").read_bytes())
        if (
            info.get("CFBundleIconFile") != "RasterReady.icns"
            or not (bundle / "Contents/Resources/RasterReady.icns").is_file()
        ):
            raise ValueError(
                "Integrate the selected final RasterReady.icns before candidate packaging"
            )
        if not identity:
            raise ValueError("Supply --codesign-identity for candidate disk-image signing")
        run(["xcrun", "stapler", "validate", bundle])
        run(["spctl", "--assess", "--type", "execute", bundle])
    original = contents(bundle)
    output.mkdir(parents=True)
    stage = output / "stage"
    stage.mkdir()
    staged_app = stage / "RasterReady.app"
    run(["ditto", bundle, staged_app])
    (stage / "Applications").symlink_to("/Applications")
    if contents(staged_app) != original:
        raise ValueError("Staged app differs from input; image creation stopped")
    signature(staged_app, require_developer_id=not development)
    suffix = "-development" if development else ""
    image = output / f"RasterReady-{version}-macos-arm64{suffix}.dmg"
    run(
        [
            "hdiutil",
            "create",
            "-srcfolder",
            stage,
            "-volname",
            f"RasterReady{suffix}",
            "-fs",
            "HFS+",
            "-format",
            "UDZO",
            image,
        ]
    )
    if identity:
        run(["codesign", "--sign", identity, "--timestamp", image])
        run(["codesign", "--verify", "--strict", image])
    run(["hdiutil", "verify", image])
    mount = output / "mounted"
    mount.mkdir()
    attached = False
    try:
        run(["hdiutil", "attach", "-readonly", "-noautoopen", "-mountpoint", mount, image])
        attached = True
        if (
            not (mount / "Applications").is_symlink()
            or os.readlink(mount / "Applications") != "/Applications"
        ):
            raise ValueError("Mounted image lacks the expected Applications shortcut")
        mounted_app = mount / "RasterReady.app"
        if contents(mounted_app) != original:
            raise ValueError("Mounted app differs from input")
        signature(mounted_app, require_developer_id=not development)
        if not development:
            run(["xcrun", "stapler", "validate", mounted_app])
            run(["spctl", "--assess", "--type", "execute", mounted_app])
        if not os.access(mounted_app / "Contents/MacOS/RasterReady", os.X_OK):
            raise ValueError("Mounted app executable is not executable")
    finally:
        if attached:
            run(["hdiutil", "detach", mount])
    with image.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    manifest = {
        "artifact": image.name,
        "sha256": digest,
        "bytes": image.stat().st_size,
        "version": version,
        "declared_app_source_revision": source_revision,
        "kind": "development" if development else "candidate-preparation",
        "release_ready": False,
        "app_signature": app_signature,
        "disk_image_signed": bool(identity),
        "native_metadata": metadata,
        "checks": [
            "image checksum",
            "read-only mount",
            "app content equality",
            "app signature",
            "Applications shortcut",
            "executable permission",
        ],
        "remaining": [
            "final DMG notarization/stapling when applicable",
            "normal installer runtime acceptance",
            "complete notices/source obligations",
            "explicit release authorization",
        ],
    }
    (output / "app-contents.json").write_text(json.dumps(original, indent=2) + "\n")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Prepared {image}; normal installation acceptance and release approval remain required.")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--development", action="store_true")
    parser.add_argument("--codesign-identity")
    args = parser.parse_args()
    package(
        args.bundle.resolve(),
        args.output.resolve(),
        args.version,
        args.source_revision,
        args.development,
        args.codesign_identity,
    )

# PyInstaller executes this file with its build classes and SPECPATH available.
import os
import runpy
import sys
import tempfile
from pathlib import Path

from packaging.version import Version
from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.building.osx import BUNDLE
from PyInstaller.utils.hooks import collect_data_files

root = Path(globals()["SPECPATH"]).parent
version = runpy.run_path(str(root / "rasterready/__init__.py"))["__version__"]
numeric_version = Version(version).base_version
macos = sys.platform == "darwin"
identity = os.environ.get("RASTERREADY_CODESIGN_IDENTITY") or None
datas = [(str(root / "rasterready/assets"), "rasterready/assets")]
# Keep this temporary inventory alive until COLLECT/BUNDLE finish copying it.
# Collect from this interpreter's exact installed packages on every build.
notice_staging = tempfile.TemporaryDirectory(prefix="rasterready-notices-")
collect_notices = runpy.run_path(str(root / "tools/collect_notices.py"))["collect"]
notice_directory = Path(notice_staging.name) / "third_party_notices"
collect_notices(notice_directory)
datas.append((str(notice_directory), "third_party_notices"))
binaries = []
windows_version = None
if sys.platform == "win32":
    from importlib import metadata

    from tools.windows_version import resource
    from tools.windows_wheel import recorded_dlls

    binaries = recorded_dlls(metadata.distribution("pillow-heif"))
    windows_version = resource(version)
if os.environ.get("RASTERREADY_DECODER_ONLY_HEIC") == "1":
    datas += collect_data_files("pillow_heif")

analysis = Analysis(
    [str(root / "launcher.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # No interactive Python console is provided; avoid its unused Readline dependency.
    excludes=["PySide6.QtQml", "PySide6.QtQuick", "readline"],
    noarchive=False,
    optimize=0,
)
archive = PYZ(analysis.pure)
executable = EXE(
    archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="RasterReady",
    debug=False,
    bootloader_ignore_signals=False,
    strip=macos,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="arm64" if macos else None,
    codesign_identity=identity,
    entitlements_file=None,
    version=windows_version,
    icon=str(root / "rasterready/assets/RasterReady.ico") if sys.platform == "win32" else None,
)
collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=macos,
    upx=False,
    name="RasterReady",
)
if macos:
    app = BUNDLE(
        collection,
        name="RasterReady.app",
        icon=str(root / "rasterready/assets/RasterReady.icns"),
        bundle_identifier="therapy.extrusion.rasterready",
        version=numeric_version,
        info_plist={
            "CFBundleVersion": numeric_version,
            "CFBundleDisplayName": "RasterReady",
            "CFBundleGetInfoString": f"RasterReady {version}",
            "RasterReadyVersion": version,
            # The pinned Qt Python bindings contain LC_BUILD_VERSION minos 26.0.
            "LSMinimumSystemVersion": "26.0",
            "NSHighResolutionCapable": True,
        },
    )

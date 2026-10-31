"""Windows executable version metadata and verification for native builds."""

import hashlib
from pathlib import Path

from packaging.version import Version


def details(value):
    version = Version(value)
    if version.epoch or version.local or len(version.release) > 4:
        raise ValueError(
            "Windows versions require at most four release parts, no epoch/local label"
        )
    numeric = version.release + (0,) * (4 - len(version.release))
    if any(part > 65535 for part in numeric):
        raise ValueError("Each Windows version part must fit an unsigned 16-bit integer")
    return {
        "numeric": numeric,
        "flags": 2 if version.is_prerelease else 0,
        "strings": {
            "CompanyName": "Extrusion Therapy",
            "FileDescription": "RasterReady image preparation",
            "FileVersion": str(version),
            "InternalName": "RasterReady",
            "OriginalFilename": "RasterReady.exe",
            "ProductName": "RasterReady",
            "ProductVersion": str(version),
        },
    }


def resource(value):
    # PyInstaller's Win32 resource writer is available only on a Windows host.
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo,
        StringFileInfo,
        StringStruct,
        StringTable,
        VarFileInfo,
        VarStruct,
        VSVersionInfo,
    )

    expected = details(value)
    return VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=expected["numeric"],
            prodvers=expected["numeric"],
            mask=0x3F,
            flags=expected["flags"],
            OS=0x40004,
            fileType=1,
            subtype=0,
            date=(0, 0),
        ),
        kids=[
            StringFileInfo(
                [
                    StringTable(
                        "040904B0", [StringStruct(k, v) for k, v in expected["strings"].items()]
                    )
                ]
            ),
            VarFileInfo([VarStruct("Translation", [1033, 1200])]),
        ],
    )


def audit(executable, value):
    """Inspect PE resources without executing the Windows program."""
    import pefile

    executable = Path(executable)
    expected = details(value)
    with pefile.PE(str(executable)) as binary:
        if binary.FILE_HEADER.Machine != 0x8664 or binary.FILE_HEADER.Characteristics & 0x2000:
            raise ValueError("Expected a Windows x64 executable")
        fixed = getattr(binary, "VS_FIXEDFILEINFO", [])
        if len(fixed) != 1:
            raise ValueError("Expected exactly one fixed Windows version resource")
        info = fixed[0]
        for prefix in ("File", "Product"):
            ms = getattr(info, prefix + "VersionMS")
            ls = getattr(info, prefix + "VersionLS")
            if (ms >> 16, ms & 65535, ls >> 16, ls & 65535) != expected["numeric"]:
                raise ValueError(f"Windows {prefix.lower()} numeric version does not match")
        if (
            info.Signature != 0xFEEF04BD
            or info.FileFlagsMask != 0x3F
            or info.FileFlags != expected["flags"]
            or info.FileType != 1
        ):
            raise ValueError("Windows version signature, flags or file type does not match")
        tables = [
            table
            for group in getattr(binary, "FileInfo", [])
            for item in group
            if item.Key == b"StringFileInfo"
            for table in item.StringTable
        ]
        if len(tables) != 1 or tables[0].LangID != b"040904B0":
            raise ValueError("Expected one English Unicode Windows version string table")
        strings = {k.decode("utf-8"): v.decode("utf-8") for k, v in tables[0].entries.items()}
        if strings != expected["strings"]:
            raise ValueError("Windows executable product/version strings do not match")
    return {
        "executable": executable.name,
        "sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "version": str(Version(value)),
        "numeric": list(expected["numeric"]),
        "strings": strings,
        "release_ready": False,
        "scope": "PE identity and version resources only; no signing or runtime acceptance",
    }

"""Pinned source inputs shared by native HEIC builders."""

import hashlib
import shutil
import tarfile
import urllib.request

SOURCES = {
    "libde265": (
        "strukturag/libde265",
        "1.1.3",
        "189baa08fd6d2dd34db099de411bd6b2e6bd5eb88e81236a3d0fa3826b9715c4",
    ),
    "libheif": (
        "strukturag/libheif",
        "1.23.6",
        "c9a00b0452f5c16d72ef71e5e40c0e90fbe2ad37148d27a1b2f9bb21546f5f03",
    ),
    "pillow_heif": (
        "bigcat88/pillow_heif",
        "1.8.1",
        "eb3108e2f62a55cd38322e22da6ba09cba0e3c6f6c6df9958eb846f84fc1a95e",
    ),
}


def fetch_sources(output):
    sources = {}
    for name, (repo, version, expected) in SOURCES.items():
        url = f"https://github.com/{repo}/archive/refs/tags/v{version}.tar.gz"
        archive = output / f"{name}-{version}.tar.gz"
        with urllib.request.urlopen(url, timeout=60) as response, archive.open("xb") as file:
            shutil.copyfileobj(response, file)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
            raise SystemExit(f"Source hash mismatch: {name}; build stopped.")
        with tarfile.open(archive) as file:
            file.extractall(output, filter="data")
        sources[name] = {"url": url, "sha256": expected}
    return sources


def include_notices(output, source):
    notices = source / "pillow_heif" / "rasterready_notices"
    notices.mkdir()
    for name in ("libheif", "libde265"):
        shutil.copyfile(
            output / f"{name}-{SOURCES[name][1]}" / "COPYING", notices / f"{name}-COPYING.txt"
        )
    (notices / "BUILD.txt").write_text(
        "RasterReady decoder-only native build: libheif 1.23.6 and libde265 1.1.3.\n"
        "No x265 library is included. Native decoder libraries use LGPLv3; see full texts.\n"
        "Upstream LICENSES_bundled.txt describes upstream wheels, not this custom library inventory.\n"
        "Corresponding source archives, hashes and platform build scripts accompany the build output.\n"
        "This notice does not select a license for RasterReady.\n"
    )
    with (source / "MANIFEST.in").open("a") as file:
        file.write("\nrecursive-include pillow_heif/rasterready_notices *.txt\n")
    with (source / "setup.cfg").open("a") as file:
        file.write("\n[options.package_data]\npillow_heif = rasterready_notices/*.txt\n")


def decoder_configurations(prefix):
    """Shared Linux/Windows codec options; plugins and other codecs are disabled."""
    return {
        "libde265": ["-DENABLE_SDL=OFF", "-DENABLE_DECODER=OFF", "-DENABLE_ENCODER=OFF"],
        "libheif": [
            f"-DCMAKE_PREFIX_PATH={prefix}",
            "-DWITH_LIBDE265=ON",
            "-DWITH_LIBDE265_PLUGIN=OFF",
            "-DENABLE_PLUGIN_LOADING=OFF",
            "-DWITH_EXAMPLES=OFF",
            "-DWITH_GDK_PIXBUF=OFF",
            "-DBUILD_TESTING=OFF",
            "-DBUILD_DOCUMENTATION=OFF",
            "-DWITH_LIBSHARPYUV=OFF",
            *[
                f"-DWITH_{codec}=OFF"
                for codec in (
                    "X265",
                    "X264",
                    "KVAZAAR",
                    "UVG266",
                    "VVDEC",
                    "VVENC",
                    "OpenH264_DECODER",
                    "DAV1D",
                    "AOM_DECODER",
                    "AOM_ENCODER",
                    "SvtEnc",
                    "RAV1E",
                    "JPEG_DECODER",
                    "JPEG_ENCODER",
                    "OpenJPEG_ENCODER",
                    "OpenJPEG_DECODER",
                    "FFMPEG_DECODER",
                    "OPENJPH_ENCODER",
                )
            ],
        ],
    }

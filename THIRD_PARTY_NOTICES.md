# Third-party components

RasterReady uses the following components. Their licenses do not select a license for RasterReady's own code.

| Component | Pinned version | License in installed distribution |
| --- | --- | --- |
| Pillow | 13.0.0 | MIT-CMU |
| pillow-heif | 1.8.1 | Python source BSD-3-Clause; supplied binary wheels identify GPLv2 terms and bundle x265. See the exact wheel’s `LICENSES_bundled.txt`. |
| PySide6 Essentials / Shiboken6 | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| rawpy | 0.27.1 | MIT; LibRaw has its own license |
| NumPy | 2.5.4 | BSD-3-Clause and bundled-component notices |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| Tabler Icons | commit `ed177a085b652fe04ec4f37ced867c94621e7840` | MIT |

UI icon originals and color-only derivatives are identified in `rasterready/assets/provenance.json`; [Tabler's license](rasterready/assets/TABLER-LICENSE.txt) is included there.

Before distributing installers, include the applicable full licenses and bundled-library notices from the exact wheels/packages used, including Python, Qt, LibRaw and native image codecs, and document corresponding source/relinking obligations. This source inventory alone is not a completed binary-distribution notice bundle. Build tooling includes PyInstaller, whose bootloader distribution exception and notices also apply. Release preparation must inspect the actual bundled components for each target OS.

`tools/collect_notices.py` copies the available installed license texts and hashes them into a new inventory directory. It reads each wheel's installed RECORD directly, verifies recorded notice hashes, and rejects missing or externally linked notices. It also includes the [Qt license supplement](third_party/Qt/README.md). The inspected Qt wheels lack license texts; rawpy's included notices do not cover all its bundled native dependencies. These gaps require component-level review, beyond collecting the package files. The inventory explicitly remains unready for release.

The [rawpy Mac supplement](third_party/rawpy-macos/README.md) retains matching native-library notices and source provenance for LibRaw, JasPer, Little CMS and libjpeg-turbo. It is included in Mac notice inventories with rawpy 0.27.1; final native coverage and source/relinking requirements remain under review. This software is based in part on the work of the Independent JPEG Group.

The Qt supplement also retains upstream attribution records and referenced license files for the relevant Qt 6.12.0 modules, including platform/configuration alternatives. Each retained file was verified against its exact-commit Git blob hash. This candidate collection still requires matching to each final package's actual components and build configuration; its presence alone does not complete distribution review.

HEIC packaging is under review: the current development wheel bundles libheif 1.23.6, libde265 1.1.3 and x265 4.3. A pinned Apple Silicon decoder-only builder is available in `tools/build_heic_macos.py`; it bundles libheif/libde265 and their full notices without x265. The default development dependency remains the upstream wheel. Final per-platform binary inventory and distribution obligations still require verification. Do not treat the Python package’s source license as the license of all bundled native code.

The [rawpy Windows supplement](third_party/rawpy-windows/README.md) covers the Windows wheel's builder-selected zlib 1.3.2, libjpeg-turbo 3.2.0, JasPer 4.2.9 and Little CMS 2.19.1, with pinned source and notice hashes. The collector includes those texts and the shared LibRaw notices on Windows. This corrects a gap in earlier development installers; their existing native acceptance remains valid for their recorded bytes, but they do not contain this newly added supplement. New packages require verification before distribution.

The [rawpy Linux supplement](third_party/rawpy-linux/README.md) retains the Linux wheel's native codec and GNU OpenMP notices. Linux builds also retain copyright files and standard license texts for hash-matched Ubuntu system libraries, with exact source package/version records. The Qt supplement includes the complete ICU 73.2 notices for the ICU libraries in the inspected Linux Qt wheel. These additions must be included in newly verified packages; older candidate hashes describe the earlier payloads.

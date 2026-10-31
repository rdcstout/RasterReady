# rawpy Windows native-library notices

These texts supplement rawpy 0.27.1 and its separately loaded `raw_r.dll`. The inspected CPython 3.12 x64 wheel's three native binaries match the retained Windows installer payload by SHA-256. Its upstream Windows builder uses vcpkg `2026.07.29` with the `x64-windows-static` triplet and installs zlib, libjpeg-turbo with JPEG8 support, JasPer and Little CMS. Those dependencies are incorporated into LibRaw; they are not separate DLLs in this wheel.

| Component | Builder-selected version | Retained text |
| --- | --- | --- |
| zlib | 1.3.2 | LICENSE |
| libjpeg-turbo | 3.2.0 | LICENSE.md and README.ijg |
| JasPer | 4.2.9 | LICENSE.txt |
| Little CMS | 2.19.1 | LICENSE |

[provenance.json](provenance.json) identifies the exact wheel binaries, upstream builder, source archives and notice hashes. Each component archive matches its vcpkg port's SHA-512 pin. These versions differ from the Mac wheel. The collector also includes the shared LibRaw 0.22.1 notices retained under [rawpy-macos/LibRaw](../rawpy-macos/LibRaw); those texts describe the same pinned LibRaw commit, without applying the Mac codec versions to Windows.

This software is based in part on the work of the Independent JPEG Group. Microsoft C/C++ and OpenMP runtime files have separate Microsoft redistribution terms; they are not covered by rawpy's MIT license or these codec notices. Final source/build retention and platform distribution checks are separate from collecting these texts.

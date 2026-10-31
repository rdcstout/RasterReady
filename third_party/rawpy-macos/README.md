# rawpy Mac native-library notices

These texts supplement rawpy 0.27.1's own MIT notice and its bundled LibRaw LGPL notice. They apply to the inspected upstream Apple Silicon wheel's native libraries, not automatically to Windows/Linux wheels. They do not choose a license for RasterReady.

| Component | Source | Included texts |
| --- | --- | --- |
| LibRaw 0.22.1 | commit `b860248a89d9082b8e0a1e202e516f46af9adb29` | Copyright summary, LGPL 2.1, alternative CDDL, DCB and X3F license headers, Adobe MIT text |
| JasPer 4.2.5 | rawpy's pinned archive | Complete JasPer license |
| Little CMS 2.11 | rawpy's pinned archive | Complete COPYING text |
| libjpeg-turbo 3.1.3 | rawpy's pinned archive | Complete LICENSE.md and IJG README |

[provenance.json](provenance.json) records the public source URLs, source archive hashes and each retained text's SHA-256. Three archives match rawpy's Mac builder's published SHA-256 pins. All 225 files from the LibRaw commit archive were checked against that commit's Git blob hashes. DCB/X3F texts are verbatim first C comments from the identified source files, including their original line endings; other archive texts are complete verbatim files. `LibRaw/Adobe-MIT.txt` reproduces the MIT text published by [Adobe](https://stlab.adobe.com/licenses.html), with the same 2005 copyright declared by LibRaw. The provenance record identifies that separate HTML source and extraction. This does not extend MIT terms to the full DNG SDK: Adobe states that its page covers Adobe Source Libraries, and exact borrowed-code mapping remains under review.

The Little CMS 2.11 archive identifies itself as 2.11 in `configure.ac`, but defines `LCMS_VERSION` as `2100` in `include/lcms2.h`; `cmsGetEncodedCMMversion` returns that constant. Thus the inspected library's `2100` result agrees with the pinned source and does not by itself establish that a 2.10 archive was used.

This is based in part on the work of the Independent JPEG Group.

The collector includes this supplement only on Mac with rawpy 0.27.1. This is not complete binary-distribution clearance: confirm final artifact components, remaining embedded-code notices, matching source/build material and applicable replacement/relinking requirements. Qt, other codec/runtime notices and installer components remain separate. Source archives are retained in the private build workspace; this directory contains notices and public provenance, not a complete corresponding-source archive.

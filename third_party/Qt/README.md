# Qt license supplement

The PySide6-Essentials and Shiboken6 6.12.0 wheels inspected during Mac packaging contain no license text files. These verbatim texts were retrieved from the matching upstream Qt for Python tag:

| File | Source | Git blob |
| --- | --- | --- |
| LGPL-3.0-only.txt | https://github.com/pyside/pyside-setup/blob/v6.12.0/LICENSES/LGPL-3.0-only.txt | `65c5ca88a67c30becee01c5a8816d964b03862f9` |
| GPL-3.0-only.txt | https://github.com/pyside/pyside-setup/blob/v6.12.0/LICENSES/GPL-3.0-only.txt | `94a9ed024d3859793618152ea559a168bbcbb5e2` |

LGPL version 3 incorporates GPL version 3, so both texts are retained. This supplement is not a complete Qt third-party notice inventory or a declaration that all distribution obligations have been fulfilled. Match all components in the final package to their notices, source and replacement/relinking instructions before distribution.

## Native component attribution candidates

`components/` retains 122 verbatim attribution, license and protocol files from the Qt 6.12.0 Base, Image Formats and SVG source review, covering 81 upstream attribution entries for QtCore, QtGui, QtNetwork, QtDBus, QtSvg, QtImageFormats and Linux Wayland platform protocols. The current Mac development bundle contains those frameworks and image/platform plugins; the Wayland candidates address Linux packaging. Each retained file matches its Git blob hash from an exact-commit upstream directory listing or untruncated Git tree; [component-provenance.json](component-provenance.json) records paths, source URLs, hashes and attribution candidates. Source archives are retained in the private build workspace.

This is a collection of candidates across platform/configuration alternatives, not a claim that every listed component was compiled into RasterReady. Qt SQL, Qt Test and build-test internals were excluded by their attribution module. Some records have no `LicenseFile`; their declared license identifier was resolved to the source repository's matching `LICENSES` text. Referenced paths, including FreeType's combined license file, were retained in their original directory layout. Some upstream JSON strings contain literal line breaks; these files remain verbatim.

The Wayland protocol records use `qtwaylandcompositor` as their documentation module, including records whose `QtUsage` explicitly identifies the client platform plugin. Qt Base's Wayland client build also references these protocol directories. They therefore remain in the candidate collection regardless of that documentation label. The 28 records and their three referenced license files retain the upstream copyrights and MIT, HPND or LGPL 2.1 terms. Two additional client protocol inputs, cursor-shape and xdg-toplevel-drag, have no attribution record in this source tree. Their complete XML files are retained to preserve their copyright and permission notices. Final Linux payload and configuration matching remains required; this does not claim that every protocol is enabled.

The collector includes this directory recursively. Final artifact review still needs the actual build configuration, source/build materials, replacement/relinking procedure and target-specific component matching, including additional libraries brought in by the wheels or installer. Retaining candidate notices does not certify those requirements or establish vulnerability clearance. It does not select RasterReady's own license.

## Qt for Python embedded-code notices

`python-bindings/` retains both Shiboken attribution records and their referenced Python 3.7.0 license files from Qt for Python 6.12.0, commit `f50facb83fc3dc5f3240c854668c7a6dd93871b2`. These cover the buffer-interface adaptation and signature support identified by upstream; they are separate from the license for RasterReady's Python runtime. The referenced `bufferprocs_py37.h` is retained in full, including its license comment and declarations, without compiling it into the application.

[Provenance](python-bindings/provenance.json) records the exact source archive, hashes and source URLs. All four retained source files were independently compared with their Git blob hashes at that commit. The collector includes these files automatically. The source archive is retained in the private build workspace; it has not been built, and the wheel build has not been independently reproduced. Final corresponding-source and replacement verification remain required.

## Linux ICU libraries

`platforms/linux-icu73.2/` retains the complete ICU 73.2 LICENSE and license.html from the matching upstream release. The inspected Linux Qt wheel includes ICU data, internationalization and common libraries; the version function in its common library identifies 73.2. Provenance records the three binary hashes and verified Git blob hashes of both notice files. These libraries are separate from Qt's Unicode table attributions; the existing Unicode license alone did not cover the complete ICU notice bundle.

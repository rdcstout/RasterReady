# rawpy Linux native-library notices

The inspected rawpy 0.27.1 CPython 3.12 Linux x64 wheel matches the retained DEB's rawpy extension, LibRaw and native codec/runtime libraries by SHA-256. Its upstream Linux builder pins JasPer 4.2.5, libjpeg-turbo 3.1.3 and Little CMS 2.11, matching the source archives retained for the Mac wheel. The collector reuses those complete texts and the shared LibRaw 0.22.1 notices from [rawpy-macos](../rawpy-macos), without copying its Mac-specific README or provenance claim.

The wheel also bundles GNU OpenMP. Its ELF build ID matches AlmaLinux's `libgomp-8.5.0-28.el8_10.alma.1.x86_64.rpm`. The matching GCC source RPM, including its build specification and patches, is retained with the private source inputs. [provenance.json](provenance.json) records the exact source URL/hash, binary build ID and component hashes. `GNU-OpenMP/` includes the complete GPL version 3 and GCC Runtime Library Exception 3.1 texts plus the matching `libgomp.h` source copyright/permission header.

This software is based in part on the work of the Independent JPEG Group. These notices supplement the wheel's own notices. Ubuntu system libraries, Qt, NumPy, Pillow and HEIC have separate inventories and source inputs; this supplement does not declare every distribution requirement complete.

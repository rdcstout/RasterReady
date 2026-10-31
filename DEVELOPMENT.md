# Developing RasterReady

Python 3.12 and the pinned dependencies in `pyproject.toml` / `requirements-dev.txt` are required. Run commands from the repository root. On Linux, Qt also needs a graphical desktop and the distribution's Qt/XCB runtime libraries (commonly `libegl1`, `libxkbcommon-x11-0` and `libxcb-cursor0` on Debian/Ubuntu). Headless tests use Qt's offscreen platform.

## Set up and run

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip==26.2.2
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m rasterready.app
```

On Windows, create the environment with `py -3.12 -m venv .venv` and replace `.venv/bin/python` with `.venv\Scripts\python.exe` in commands. No account, API key, server or uploaded image is required. Appearance and update preferences are stored with Qt's native user settings; do not commit them.

## Build

```sh
.venv/bin/python build.py
```

Run on the target OS/CPU. macOS produces `dist/RasterReady.app`; Windows produces `dist/RasterReady/RasterReady.exe`; Linux produces `dist/RasterReady/RasterReady`. This is a development bundle, without release signing, notarization, installer packaging or installer acceptance. PyInstaller does not cross-compile these bundles. Never substitute a build for target runtime acceptance.

## Validation

For application changes:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m compileall -q rasterready tests build.py launcher.py
.venv/bin/python -m pip_audit --local
```

Tests cover PNG metadata chunks, orientation, valid/invalid profiles, transparency, native image-codec roundtrips, size rules, preserved originals, international collision names, malformed files, special-file rejection, project paths, batch continuation/cancellation and themes. RAW unit tests exercise decoder options and input limits; real camera acceptance is a separate manual check. Update tests cover stable/channel/platform eligibility, version precedence, failures, response bounds, persistence, disabled checks and dismissal.

Inputs are limited to 1 GiB per file and 100 megapixels; outputs to 50 megapixels and 20,000 pixels per dimension. First-frame exports probe only a second frame rather than enumerating an entire animation. Output names are shortened when necessary to leave room for a collision suffix; long project names are rejected with an actionable error. Original names and data remain untouched. These limits reduce resource use; they are not a sandbox for native codecs.

For conversion/UI changes, use disposable files in an isolated project: native picker and drag/drop, mixed valid/damaged images, queue before project naming, transparency, rotated JPEG, an actual Sony RAW, cancellation, colliding names and project folder opening. Inspect saved dimensions and PNG chunks, not just row status. Confirm both themes, Follow system, keyboard focus and small-window scrolling. Inspect originals for unintended changes. Test a representative RAW for each newly claimed camera/mode; never infer universal camera support from synthetic tests.

For updates, test a manual request with connectivity and offline failure, weekly attempt persistence, disabling automatic checks and dismissal/re-check behavior. Network requests are bounded and asynchronous; they must not block image conversion. Automated tests use controlled replies. Do not publish a fake release to test detection.

## Automated checks

The source includes `.github/workflows/checks.yml` for Ubuntu 24.04 x64, Windows 2025 x64 and Apple Silicon macOS 26, using Python 3.12 in an isolated virtual environment. It runs tests, style/compile/dependency checks and a development bundle build. It has read-only repository permission and publishes no binaries or releases. Check the Actions results for the exact source commit; local checks do not establish results on another platform. Even a passing remote build does not replace exact installer runtime acceptance.

The Linux job includes a decoder-only HEIC build trial before its application tests and bundle build. It requests the Ubuntu 24.04 build baseline explicitly. The first native Linux CI trial completed the decoder build, tests, application bundle and development DEB/AppImage packaging; this does not establish a final Linux minimum or installer compatibility. The Windows job also includes its native decoder build trial before testing. The Mac CI development job still uses an upstream HEIC wheel. None of these jobs publishes release packages.

## Packaging and release

Release packaging is still in development. Target formats are a signed/notarized Apple Silicon DMG, Windows x64 installer, and Linux x64 DEB plus AppImage. Windows/Linux packaged runtime verification remains pending. Do not present the development build command as a completed installer pipeline.

Every PyInstaller build collects RasterReady's MIT license, available installed notices, Python's license, the Qt supplement, applicable rawpy supplement and Tabler's license from its packaging environment into `third_party_notices` in the app payload. The Help menu's **Third-party notices…** action displays a searchable, read-only viewer inside the app. Source runs show the source supplements instead. To inspect a separate inventory, run `python tools/collect_notices.py ../notice-inventory` with a new output directory. The inventory records versions and SHA-256 values and never overwrites an existing directory. Review its unresolved entries and [third-party guidance](THIRD_PARTY_NOTICES.md); inclusion does not certify complete native coverage or source/relinking compliance.

Before publishing, verify the selected product icon in final packages, complete dependency notices/source obligations, signing and package creation. Verify the exact candidate artifact on each compatible target via its normal install/launch path, a representative conversion, settings persistence and quit/relaunch. For AppImage, extraction-only testing is insufficient. Record source revision, version, artifact SHA-256, OS/CPU and actual results; unavailable or failed required checks block the affected artifact unless the maintainer explicitly approves that specific exception.

The stable update checker accepts only uploaded assets named `RasterReady-VERSION-macos-arm64.dmg`, `RasterReady-VERSION-windows-x64.exe`, or `RasterReady-VERSION-linux-x64.AppImage` / `.deb` in published stable releases in this repository. The tag is `vVERSION`; package versions use the version in `rasterready/__init__.py`. Release upload must follow target acceptance, never build success alone. Do not publish a tag, installer or activate an update channel without maintainer authorization. A source push is separate from a release.

Updates open the official release page for a user-controlled download; the app does not install packages. A shipped release must also provide byte-identical permanent-name copies and verified download links. After publication, download distributed assets and match their hashes to the tested candidates. Document recovery and signing verification when the final installer workflow is implemented.

### Decoder-only HEIC packaging on macOS

The standard development environment uses the upstream HEIC wheel, which includes an unused HEVC encoder. Before packaging an Apple Silicon candidate, build the decoder-only wheel in a separate directory:

```sh
.venv/bin/python -m pip install -r requirements-heic-build.txt
.venv/bin/python tools/build_heic_macos.py ../heic-build
```

The builder requires the current Xcode command-line toolchain and a new output directory. It verifies pinned source hashes, builds shared libheif/libde265 without the HEVC encoder, repairs library paths and checks the wheel's decoder-library and notice inventory. It retains source archives, the SDK selection patch, build script and wheel manifest. It does not install the wheel or publish anything. Its shared `tools/heic_sources.py` helper is retained with the builder. This is an Apple Silicon builder; Windows/Linux native execution remains pending.

Use a separate packaging virtual environment with the application's pinned dependencies. Install the resulting wheel there with `python -m pip install --no-deps --force-reinstall /absolute/path/to/heic-build/wheels/pillow_heif-1.8.1-cp312-cp312-macosx_14_0_arm64.whl`. Run the application tests from this checkout, then `python build.py --decoder-only-heic --dist-dir ../decoder-bundle`. That flag rejects the stock encoder-containing package and includes decoder notices. Final package acceptance and the complete third-party distribution/source bundle remain separate required checks; the wheel manifest is not release approval.

### Retaining Mac dependency source inputs

`tools/package_dependency_sources.py` assembles the retained Mac dependency archives, source supplements and build guidance into a local tar file. It reads the existing Qt/rawpy provenance and HEIC source pins; it does not download anything. Place the pinned archives in an input directory as `NAME.tar.gz`, using the names from `source_catalog()` in that module: `jasper`, `lcms`, `libde265`, `libheif`, `libjpeg-turbo`, `libraw`, `libraw-cmake`, `pillow_heif`, `qt-for-python`, `qtbase`, `qtimageformats` and `qtsvg`.

From a clean committed checkout with Python 3.12, run `python tools/package_dependency_sources.py /absolute/path/to/retained-inputs /absolute/path/to/new-dependency-sources.tar`. The tool checks every archive against its pinned SHA-256, includes the tracked source supplements and build instructions, and records the checkout revision and per-file hashes. It reads back all tar members before creating the destination and refuses to replace existing output. Identical inputs and revision produce identical bytes. Retain the printed bundle hash with artifact evidence.

This bundle covers retained dependency inputs, not the application's own source or a complete corresponding-source determination. The manifest explicitly remains `release_ready: false`. Before distribution, match source, configuration, patches, attribution and replacement materials to every component in the final artifact, provide application source separately, and complete the platform checks. Mac source selection does not establish Windows/Linux coverage.

### Replacing LibRaw on Mac

The rawpy Mac bundle keeps LibRaw separate at `Contents/Frameworks/rawpy/libraw_r.25.dylib`. A development-copy check rebuilt LibRaw commit `b860248a89d9082b8e0a1e202e516f46af9adb29` using [LibRaw-cmake commit 6e26c9e73677dc04f9eb236a97c6a4dc225ba7e8](https://github.com/LibRaw/LibRaw-cmake/tree/6e26c9e73677dc04f9eb236a97c6a4dc225ba7e8), with only a `LibRaw::version()` string marker changed. The CMake `raw_r` target used Release/shared arm64 code, macOS deployment target 14.0, JPEG8/LCMS2/zlib/X3F enabled and OpenMP/RawSpeed/JasPer/examples disabled. Matching JPEG headers, including generated `jconfig.h` and `jerror.h`, came from libjpeg-turbo 3.1.3; LCMS headers came from the pinned 2.11 source. The build linked against the original app's matching private JPEG and LCMS libraries. Source hashes are in the [rawpy supplement](third_party/rawpy-macos/provenance.json).

Replace the library only in a separate app copy. Preserve `@rpath/libraw_r.25.dylib` as its install name, remove build-time absolute RPATHs, and bind JPEG/LCMS to the copy's private libraries with `@loader_path/__dot__dylibs/` paths. Re-sign and verify the complete copied app before launch. The tested Developer ID/hardened-runtime copy loaded the rebuilt LibRaw and developed the Sony A7 III fixture into the same 1920×1283 metadata-free PNG as the original decoder; the original ARW and application were preserved. This is a limited Mac replacement check, not all-feature parity or general camera/format coverage. JasPer was excluded from this experiment; the production dependency set was not changed. A final release still needs matching source/build materials and artifact-specific verification.

### Replacing QtCore on Mac

A local Apple Silicon development-copy check rebuilt QtCore from Qt Base 6.12.0 commit `025bdad181de241e81bf853c8a2d7bf3d19261a9`, with only a `qVersion()` string marker changed. The source archive and hash are recorded in the [Qt provenance](third_party/Qt/component-provenance.json). With CMake/Ninja from `requirements-heic-build.txt` and the active Xcode SDK, the tested configuration was:

```sh
cmake -S qtbase-025bdad181de241e81bf853c8a2d7bf3d19261a9 -B qtcore-build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_DEPLOYMENT_TARGET=26.0 -DCMAKE_OSX_ARCHITECTURES=arm64 -DBUILD_SHARED_LIBS=ON -DQT_BUILD_TESTS=OFF -DQT_BUILD_EXAMPLES=OFF -DFEATURE_gui=OFF -DFEATURE_network=OFF -DFEATURE_dbus=OFF -DFEATURE_sql=OFF -DFEATURE_testlib=OFF -DFEATURE_icu=OFF -DFEATURE_system_pcre2=OFF -DFEATURE_system_zlib=OFF '-DCMAKE_IGNORE_PREFIX_PATH=/opt/homebrew;/usr/local'
cmake --build qtcore-build --target Core --parallel 4
```

The resulting `qtcore-build/lib/QtCore.framework/Versions/A/QtCore` replaced the binary at `Contents/Frameworks/PySide6/Qt/lib/QtCore.framework/Versions/A/QtCore` in a separate app copy. Preserve the original binary's install name, obtained with `otool -D`, when replacing it; the inspected PyInstaller bundle uses `@rpath/QtCore`. Re-sign the copied app and its nested code with an applicable identity and verify its complete signature before launch. The tested copy retained Developer ID, hardened runtime and a timestamp, passed strict/deep verification, loaded the rebuilt QtCore, rendered both themes and converted an owned HEIC to a pixel-identical clean PNG. The original app remained unchanged.

This verifies one QtCore replacement configuration on Mac. It does not reproduce every upstream wheel feature or verify replacement of all Qt modules, Python bindings, other architectures/platforms or unsigned/notarized modified apps. Compatible shared-library replacement and the final artifact's source/build materials remain release checks.

### Replacing a shared HEIC decoder on Mac

The decoder-only Mac bundle keeps libde265 separate at `Contents/Frameworks/pillow_heif/__dot__dylibs/libde265.0.2.3.dylib`. Libheif links to `@rpath/libde265.0.2.3.dylib`; the decoder is not statically incorporated into RasterReady. Rebuild from the pinned source with the shared-library options in `tools/build_heic_macos.py`, retaining the source, any changes and build commands. For replacement experiments, use a separate copy of the app, preserve the library's architecture and compatible ABI, and set its install name to that same `@rpath` value with `install_name_tool -id`. Replace only the copy's library. Changing signed bytes invalidates signatures, so sign the copied app and its nested code with your own applicable identity, then verify the complete signature before launching it. Preserve the original app as the recovery copy.

A local Apple Silicon check rebuilt libde265 1.1.3 with a version-string-only change, replaced it in a copied development app, and signed that copy with Developer ID, hardened runtime and a timestamp. Strict/deep signature verification passed. The running app mapped the replacement library and converted an owned HEIC to a pixel-identical, metadata-free PNG. This verifies that specific replacement route; it does not verify an unsigned replacement, notarization of modified apps, replacement of Qt/LibRaw, other operating systems or arbitrary ABI changes. For a release, supply the matching source/build materials and verify the applicable replacement procedure against the final artifact.


### Linux decoder build trial

`tools/build_heic_linux.py` builds a decoder-only wheel on native Linux x64. The Ubuntu 24.04 CI trial completed compilation, wheel repair, installation, codec tests and development app packaging. Final installer acceptance and runtime compatibility beyond that runner remain unverified.

On an isolated Linux x64 build system with a C++ compiler, pkg-config and patchelf available, install `requirements-heic-build.txt` into the build virtual environment. Run `python tools/build_heic_linux.py ../heic-linux` with a new directory. The default requested ceiling is `manylinux_2_34_x86_64`; the CI Ubuntu 24.04 trial explicitly requests `--platform-tag manylinux_2_39_x86_64`. Stop if compilation or repair fails. Do not bypass a compatibility failure by relabeling the wheel; use a compatible build host for the intended baseline.

The builder shares the Mac source pins, disables external codec plugins and all codecs except libde265, bundles matching native notices, and uses [auditwheel](https://github.com/pypa/auditwheel/tree/6.8.2) to repair shared-library paths. It retains source archives, builder/helper, constraints and a wheel hash manifest. It installs nothing into the app environment. A successful build would still require a clean packaging-environment install, actual HEIC fixture decoding, the app tests and a `build.py --decoder-only-heic` bundle, followed by normal DEB and AppImage acceptance. Windows native execution remains pending; its prepared route is described below.


### Windows decoder build trial

`tools/build_heic_windows.py` builds a decoder-only wheel for CPython 3.12 and Visual Studio 2022 or 2026 C++ build tools. Windows 2025 CI completed compilation, wheel repair, installation, codec tests, app bundling and development installer construction. Normal desktop and installer acceptance remain unverified. In a dedicated Windows build environment, install `requirements-heic-build.txt`, then try `python tools/build_heic_windows.py ../heic-windows` with a new directory. Stop on a compiler, repair or inventory failure; do not distribute an unverified wheel.

The builder detects an installed Visual Studio C++ x64 toolchain with `vswhere`, selecting the matching CMake generator and installation explicitly. CI stops on native command failures rather than continuing with a stock decoder. The prototype builds shared libde265/libheif with the same codec options as the Linux trial. Upstream's Python extension expects an MSYS2-style header prefix and an import library named `libheif.lib`. This trial supplies a private CMake prefix through that environment variable and copies CMake's `heif.lib` to a matching name; it does not use or change an existing MSYS2 installation. This compatibility route needs native confirmation.

[Delvewheel 1.13.2](https://pypi.org/project/delvewheel/1.13.2/) repairs the wheel's DLL dependencies. The builder checks for the decoder DLLs, rejects unexpected DLLs, verifies x64 PE headers, retains sources/notices/build instructions and emits a non-release manifest. Compiler runtime distribution notices remain part of final native-component review.

The Windows bundle spec collects HEIC DLLs from the installed wheel's `RECORD`, including DLLs beside its top-level extension. `tools/windows_wheel.py` checks each DLL's recorded hash and refuses missing or changed files. It collects no unrelated DLLs. This collection behavior was checked on Mac against the unmodified upstream Windows wheel; it does not establish a successful custom Windows build or application launch. After a native build, install the repaired wheel into a fresh packaging environment, verify actual HEIC fixture decoding and tests, build with `--decoder-only-heic`, and exercise the final Windows installer normally. The Windows CI job completed that build/test/bundle and installer-construction trial; it does not establish normal desktop or installer acceptance.


### Windows installer trial — native acceptance pending

The prepared Windows CI job also fetches a SHA-256-pinned official NSIS 3.13 archive with `tools/fetch_nsis_windows.py` and invokes `tools/package_windows.py` on the development bundle. The compiler is kept in a new build directory; no global compiler installation is needed. Supply the built bundle, a new output directory, its full version, the NSIS compiler path and `--development`; use the tool's `--help` for arguments. Current packaging refuses candidate mode and names outputs `RasterReady-VERSION-windows-x64-development.exe`. These installers are unsigned and must not be distributed as releases.

`packaging/windows.nsi` is designed for a fixed per-user installation in LocalAppData / Programs / RasterReady, current-user Start menu shortcuts and a Windows uninstall entry, without an administrator request. Upgrade removal occurs in the Install section after choosing Install; merely opening the installer does not run the old uninstaller. Uninstall uses generated exact application file paths and nonrecursive empty-directory removal. It does not target Downloads projects or appearance/update settings, and leaves unrelated files alone. These are implementation properties requiring native installation, cancellation, upgrade, locked-file and uninstall checks before release.

Compilation was checked on Mac with a pinned task-local NSIS compiler and an explicitly nonfunctional x64 bootloader/text fixture, including spaces and Unicode filenames. Compiler warnings are errors. Static inspection found the expected asInvoker execution level and no Authenticode signature. This checks the packaging mechanism; it is not a Windows RasterReady build or install test. The current packager also requires matching RasterReady executable metadata, so an unmodified bootloader alone no longer qualifies as an application payload. Native icon and version-resource verification, complete installer/native notices, native acceptance and release authorization remain pending.

### Windows executable metadata

On Windows, the bundle spec uses `tools/windows_version.py` to supply PyInstaller's version resource. It records RasterReady's product name, description, original executable filename, Extrusion Therapy as publisher and the full application version in both version strings. Numeric file/product versions use up to four release components padded with zeros: `0.1.0.dev0` becomes `0.1.0.0`, with the Windows prerelease flag set. Development and prerelease labels remain in the strings; the update checker continues to compare full PEP 440 versions. Epochs, local version labels, more than four release components and values above 65535 are refused rather than truncated.

After a Windows build, `build.py` inspects the actual x64 PE file's numeric versions, flags and identity strings and fails on a mismatch. The installer packager repeats that check against its requested version before compiling and records the executable's metadata/hash in its manifest. Windows CI exercised the native resource generation/build checks successfully. Portable version-boundary tests pass; a Windows-only serializer roundtrip test runs in the native CI job. Static Mac inspection confirmed that the existing unmodified bootloader fixture is rejected without changing it or creating installer output. This does not prove a successful Windows application build, file-properties appearance or native installation.


### Linux DEB/AppImage trial — native acceptance pending

`tools/package_linux.py` stages an ELF64 x86_64 PyInstaller bundle into an AppDir and Debian directory tree. It validates executable type and contained symlinks, includes a desktop entry and launchers, and preserves the bundle's files. The selected red product icon is installed at eight hicolor PNG sizes; AppDir uses a 256-pixel root icon with a matching `.DirIcon` link. Native desktop appearance remains unverified.

For an isolated staging inspection, supply the bundle, a new output directory, `--version`, `--development` and `--stage-only`. Staging has been checked on Mac using a nonfunctional Linux x64 bootloader/text fixture; an owned shell probe checked launcher quoting. No Linux application was executed. Existing output and escaping symlinks are refused.

The prepared Ubuntu 24.04 CI trial uses `tools/linux_package_tools.py` to fetch hash-pinned appimagetool 1.9.1 and type2-runtime 20251108. Both downloads were verified locally. Native Linux mode requires that `--tool-directory`, dpkg-deb and desktop-file-validate. It builds a root-owned DEB without a root build process and supplies the pinned runtime explicitly to appimagetool. Only the builder uses extraction mode; the resulting AppImage must later be tested through its normal executable path.

The DEB's current development metadata targets Ubuntu 24.04/glibc 2.39 with a provisional desktop-library dependency list. Final dependency closure, maintainer metadata, runtime notices/source obligations and install/remove behavior remain unverified. No maintainer email is invented. AppImage desktop/runtime compatibility is also unverified. The Ubuntu 24.04 CI trial built both development package formats; no usable DEB or AppImage release has been established through normal desktop acceptance. Package names contain `-development`, candidate mode is refused and manifests remain `release_ready: false`. After a native build, normal DEB installation and normal AppImage launch, image conversion, settings persistence, quit/relaunch and applicable upgrade/removal checks remain required before publication.


### Mac signing

To sign a development bundle with an available Developer ID Application identity, add `--codesign-identity "CERTIFICATE NAME OR SHA-1"` to `build.py` on macOS. PyInstaller applies the identity to collected native code and enables Hardened Runtime. No signing identity or private key is stored in source. Verify the produced bundle with `codesign --verify --deep --strict /path/to/RasterReady.app`, then run the actual bundle and exercise its image decoders. Signing alone does not establish notarization, Gatekeeper acceptance or readiness for publication. Final packaged-icon verification, notarization/stapling and DMG installation checks remain release preparation requirements.

### Local Mac disk images

`tools/package_macos_dmg.py` creates a compressed HFS+ image containing `RasterReady.app` and an Applications shortcut. Use `python tools/package_macos_dmg.py --help` for its arguments. Supply the app's full version and the actual source commit recorded for that build, plus a new output directory. It refuses an existing directory or an output inside the app.

The `--development` mode names the result `RasterReady-VERSION-macos-arm64-development.dmg`; it permits the current development version and unfinished icon/notarization state. This mode has been exercised locally: image checksum, read-only mount, copied application contents/signature, executable permission and Applications shortcut were verified. The image was detached. This is packaging-mechanism evidence, not normal installation/runtime acceptance or a distributable release.

Candidate mode is a prepared, unexecuted path. It requires a stable version, final `RasterReady.icns`, Developer ID signature with Hardened Runtime/timestamp, an app notarization ticket and Gatekeeper assessment, plus `--codesign-identity` for the image. It checks the copied app's ticket/assessment too. The resulting DMG still needs its own final notarization/stapling where applicable and exact normal installation/runtime acceptance. Do not use development mode to bypass these release requirements.

The tool preserves its staged payload and manifests with artifact hashes, app content hashes, metadata checks and the declared source commit. Every manifest remains `release_ready: false`. It uploads nothing, publishes no release and copies nothing into Applications. Final packaged-icon verification, complete notices/source obligations and release authorization remain separate gates.


### Bundle configuration

`build.py` uses the tracked `packaging/rasterready.spec`. The Mac build is arm64 only and declares macOS 26.0 as its minimum: the pinned Qt Python bindings contain Mach-O deployment targets of 26.0, even though the wheel filename has a lower platform tag. Validate actual binaries after dependency changes; a wheel tag alone does not establish runtime compatibility. The CI Mac runner is correspondingly `macos-26` ([GitHub runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)).

The Mac short/build versions use the numeric base of `rasterready.__version__`; `RasterReadyVersion` and the bundle information string retain the full development/prerelease version. For example, `0.1.0.dev0` produces numeric bundle versions `0.1.0` and a full version of `0.1.0.dev0`. This is development metadata, not a stable release declaration. Metadata is applied before signing; do not edit the signed bundle afterward. The spec disables UPX and keeps the existing decoder-data and native signing options. Final package runtime acceptance is still required.

After a Mac build, `build.py` runs `tools/audit_macos_bundle.py` and fails if the bundle versions disagree with the app, any native binary is not arm64, or a native deployment target exceeds the declared minimum. The audit can also be run separately: `python tools/audit_macos_bundle.py /path/to/RasterReady.app --version 0.1.0.dev0`. Its JSON output includes hashes and explicitly does not certify signing, notarization, runtime acceptance or release readiness.


### Selected product icon

The selected product icon is the red crop/photo/sparkle tile. `rasterready/assets/product-icon-selected.png` retains the original selection; `product-icon-master.png` retains the transparent preparation made with the built-in image tool. PNG sizes, `RasterReady.ico` and `RasterReady.icns` are format/size derivatives. The Qt app, Mac bundle, Windows executable/installer and Linux desktop package definitions reference these assets. Native verification of final packaged surfaces remains required.

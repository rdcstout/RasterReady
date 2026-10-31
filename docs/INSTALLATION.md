# Install and use RasterReady

**Release preview:** no installers are published yet. The instructions below describe the prepared 0.1.0 packages. Check the [releases page](https://github.com/rdcstout/RasterReady/releases) for availability. Published downloads will be free and include SHA-256 checksums, versioned packages, identical stable-name downloads, and matching source materials.

## macOS

Requires an Apple Silicon Mac running macOS 26 or newer. Open the DMG, drag RasterReady into Applications, and open it from Applications. The release candidate is Developer ID signed, notarized and stapled. Close RasterReady before replacing an existing copy with a newer download.

To remove the app, quit it and move RasterReady from Applications to Trash. Your finished images remain in Downloads.

## Windows

Use the x64 installer on Windows 11. Close RasterReady, run the installer and open it from the Start menu. It installs for your user without requiring an administrator account. The installer is unsigned; verify that your download came from this repository and matches the release checksum.

Use Settings → Apps → Installed apps → RasterReady to uninstall. Finished images are preserved.

## Linux

Use an x86-64 desktop with Ubuntu 24.04/glibc 2.39 or newer and compatible graphics libraries. Native desktop acceptance used Ubuntu 26.04.1; Ubuntu 24.04 was the build and ABI baseline, not a separately tested desktop.

### Debian/Ubuntu package

Open the DEB in your software installer, or install the stable-name file from its download directory:

```sh
sudo apt install ./RasterReady-linux-x64.deb
```

APT resolves the declared desktop runtime dependencies. Open RasterReady from the application launcher. Close the app before installing a newer package. Remove it through your package manager, or use `sudo apt remove rasterready`. Finished images remain in Downloads.

### AppImage

Make the downloaded AppImage executable in your file manager's permissions panel, then open it normally. From the download directory, the equivalent commands are:

```sh
chmod +x RasterReady-linux-x64.AppImage
./RasterReady-linux-x64.AppImage
```

[AppImage needs a working FUSE setup](https://docs.appimage.org/user-guide/troubleshooting/fuse.html) and compatible desktop graphics libraries. On Ubuntu 24.04 and newer the FUSE 2 compatibility library is provided by `libfuse2t64`. If the desktop reports a missing Qt platform dependency, install the matching distribution graphics packages; common requirements include `libegl1`, `libxkbcommon-x11-0`, `libxcb-cursor0`, `libwayland-client0`, `libwayland-cursor0`, and `libwayland-egl1`.

To update, quit RasterReady and replace the AppImage with the newer official download. Remove the AppImage to remove the app; finished images are separate.

## Prepare images

1. Enter a project name and choose a preset. Web presets preserve proportions and do not enlarge smaller inputs unless enabled.
2. Drop your images into the canvas or choose files. Review per-image warnings and results.
3. Open the project folder to retrieve PNGs directly from your system's **Downloads / project name** folder. Existing files receive a numeric suffix.

Original files are preserved. Orientation and color are handled before embedded metadata is removed. Visible details in a picture and filenames remain visible. Marketplace presets prepare dimensions; they do not verify listing content or guarantee platform acceptance. Sony RAW support depends on the camera and RAW mode.

Choose Light, Dark or Follow system from the appearance control. **Help → Check for Updates** opens compatible stable releases; optional weekly checks run only while the app is open. Installation stays under your control. No image data is uploaded.

### Supported formats and limits

Inputs include JPEG, PNG, HEIC/HEIF, AVIF, WebP, TIFF, BMP, GIF and Sony ARW/SRF/SR2. Animated files use their first frame. Unsigned 16-bit grayscale PNG/TIFF inputs are mapped to web tones. SVG and 32-bit images requiring tone mapping are unsupported.

Sony RAW inputs are developed to image data rather than exported only from an embedded preview. Representative A7 III, A7 IV and A7R IV files were tested; camera and RAW-mode support depends on LibRaw. Native Windows and Linux package checks used an A7 III file.

Orientation is applied and images are converted to sRGB before embedded metadata is removed. Transparency is preserved except where a preset calls for white output. Generic web widths, marketplace suggestions and custom fit/crop/padding are available. General suggestions are identified when platform rules have not been verified.

Inputs are limited to 1 GiB per file and 100 megapixels; outputs to 50 megapixels and 20,000 pixels per dimension. Per-image errors and warnings appear in the results list. Press Enter on a result or double-click it for full details.

The approved hero is promotional artwork based on an app screenshot.

## Recovery and help

If a conversion fails, preserve the original and review the image's result details. The app continues with other files. Do not upload personal images or identifying paths in a public report.

If an update fails, close the app and reinstall the last working official package from [previous releases](https://github.com/rdcstout/RasterReady/releases). Conversion outputs are not removed by reinstalling or uninstalling. Keep a working installer when you need to recover without internet access.

[Report an ordinary bug](https://github.com/rdcstout/RasterReady/issues) · [Report a security concern privately](../SECURITY.md)

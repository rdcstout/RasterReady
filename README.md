# RasterReady

Prepare images for websites and sales listings. Name a project, drop in a batch, and retrieve clean PNGs directly from **Downloads / your project name**. Originals stay untouched; existing outputs receive a numeric suffix.

RasterReady offers common web widths, marketplace suggestions, custom fit/crop/padding, Sony RAW development, and Light, Dark or system appearance. Images are oriented and converted to sRGB before embedded metadata is discarded. Transparency is preserved except where a preset calls for white output. Visible information in the picture or filename is still visible.

**In development. No installer release is available yet.** Target platforms are Apple Silicon macOS 26 or later, Windows x64 and Linux x64. Local Mac checks cover representative JPEG/PNG and Sony A7 III, A7 IV and A7R IV ARW files; Ubuntu 26.04 and Windows 11 package checks cover PNG and Sony A7 III conversion. Camera support depends on LibRaw and the camera's RAW mode.

## Use

1. Enter a project name and select a size preset.
2. Drop images onto the canvas or choose files. Conversion starts when a project name is present.
3. Review any per-image warnings, then open the project folder. Press Enter on a result or double-click it for full details.

Web presets fit images without cropping or enlarging by default. Marketplace presets include guidance and size warnings; they do not guarantee acceptance, remove an existing background, or verify listing content. General suggestions are identified when a platform's requirements have not been verified.

Supported inputs include JPEG, PNG, HEIC/HEIF, AVIF, WebP, TIFF, BMP, GIF and Sony ARW/SRF/SR2. Animated inputs use the first frame. Unsigned 16-bit grayscale PNG/TIFF inputs are mapped to web tones. SVG and 32-bit images requiring tone mapping are not supported in the current development build.

**Help → Check for Updates** checks compatible stable releases. Weekly checks can be disabled in Help. Checks contact GitHub without sending image data; no files are uploaded or installed automatically. Images are processed locally.

## Help and development

[Report an ordinary bug](https://github.com/rdcstout/RasterReady/issues), with a minimal sanitized example and version/commit. Read [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) and [DEVELOPMENT.md](DEVELOPMENT.md) for contribution, private reporting and build instructions.

RasterReady's own code is available under the [MIT License](LICENSE). Dependency licenses and release obligations are recorded in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Support Future Tools

You can optionally [support future Extrusion Therapy tools](https://buy.stripe.com/fZu3cw2Mnfr0d7N3ws1kA00).

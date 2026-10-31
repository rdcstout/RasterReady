# Synthetic HEIC test images

These five solid-color images were created for RasterReady tests, contain no user photographs and are part of the project source. The project license decision is pending. They were encoded locally with Pillow 13.0.0, pillow-heif 1.8.1, libheif 1.23.6 and x265 4.3. The encoder is a test-data creation tool, not an application requirement.

RGB is 32×32, RGB (210,40,50). Alpha is 16×16 with alpha 128. Rotated is encoded 16×8 with orientation 6 and a synthetic image-description tag. Profile contains a generated sRGB ICC profile. Grid is 1024×768 with 256-pixel tiles and a confirmed grid item. Tests consume these files using decoding only, so they also work against a build without an HEVC encoder.

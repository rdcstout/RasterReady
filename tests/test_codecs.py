from pathlib import Path
from shutil import copyfile

import pytest
from PIL import Image, ImageCms

from rasterready.core import Size, prepare

HEIC_FIXTURES = Path(__file__).parent / "fixtures" / "heic"


@pytest.mark.parametrize(
    "fmt,extension",
    [
        ("JPEG", "jpg"),
        ("PNG", "png"),
        ("WEBP", "webp"),
        ("TIFF", "tif"),
        ("BMP", "bmp"),
        ("GIF", "gif"),
        ("HEIF", "heic"),
        ("AVIF", "avif"),
        ("ICO", "ico"),
        ("TGA", "tga"),
        ("PPM", "ppm"),
    ],
)
def test_real_codec_roundtrip_to_metadata_free_png(tmp_path, fmt, extension):
    source = tmp_path / f"input.{extension}"
    if fmt == "HEIF":
        copyfile(HEIC_FIXTURES / "rgb.heic", source)
    else:
        Image.new("RGB", (32, 32), (210, 40, 50)).save(source, format=fmt)
    original = source.read_bytes()
    result = prepare(source, tmp_path, Size(16))
    with Image.open(result.output) as output:
        assert output.format == "PNG" and output.size == (16, 16)
        assert not output.info and not output.getexif()
        r, g, b = output.convert("RGB").getpixel((8, 8))
        assert r > 170 and g < 90 and b < 100
    assert source.read_bytes() == original


def test_palette_transparency_with_valid_rgb_profile(tmp_path):
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    source = tmp_path / "indexed.png"
    image = Image.new("P", (16, 16), 0)
    image.putpalette([255, 0, 0] * 256)
    image.save(source, transparency=0, icc_profile=profile)
    result = prepare(source, tmp_path, Size(8))
    with Image.open(result.output) as output:
        assert output.mode == "RGBA" and output.getpixel((0, 0))[3] == 0
        assert not output.info


def test_profile_conversion_preserves_partial_alpha(tmp_path):
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    source = tmp_path / "rgba.png"
    Image.new("RGBA", (16, 16), (190, 30, 50, 128)).save(source, icc_profile=profile)
    result = prepare(source, tmp_path, Size(8))
    with Image.open(result.output) as output:
        pixel = output.getpixel((0, 0))
        assert pixel[3] == 128
        assert all(abs(a - b) <= 2 for a, b in zip(pixel[:3], (190, 30, 50)))
        assert not output.info


def test_lab_profile_converts_neutral_to_srgb_before_metadata_removal(tmp_path):
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("LAB")).tobytes()
    source = tmp_path / "lab.tif"
    Image.new("LAB", (16, 16), (128, 128, 128)).save(source, icc_profile=profile)
    result = prepare(source, tmp_path, Size(8))
    with Image.open(result.output) as output:
        r, g, b = output.getpixel((0, 0))
        assert 100 < r < 140 and max(r, g, b) - min(r, g, b) <= 2
        assert not output.info and not output.getexif()


@pytest.mark.parametrize(
    "fmt,extension",
    [("PNG", "png"), ("WEBP", "webp"), ("TIFF", "tif"), ("HEIF", "heic"), ("AVIF", "avif")],
)
def test_codec_alpha_survives_web_export(tmp_path, fmt, extension):
    source = tmp_path / f"alpha.{extension}"
    if fmt == "HEIF":
        copyfile(HEIC_FIXTURES / "alpha.heic", source)
    else:
        Image.new("RGBA", (16, 16), (210, 40, 50, 128)).save(source, format=fmt)
    result = prepare(source, tmp_path, Size(8))
    with Image.open(result.output) as output:
        assert output.mode == "RGBA"
        assert abs(output.getpixel((0, 0))[3] - 128) <= 1
        assert not output.info


@pytest.mark.parametrize(
    "fmt,extension",
    [("JPEG", "jpg"), ("PNG", "png"), ("TIFF", "tif"), ("HEIF", "heic"), ("AVIF", "avif")],
)
def test_codec_orientation_is_applied_once(tmp_path, fmt, extension):
    source = tmp_path / f"rotated.{extension}"
    exif = Image.Exif()
    exif[274] = 6
    if fmt == "HEIF":
        copyfile(HEIC_FIXTURES / "rotated.heic", source)
    else:
        Image.new("RGB", (16, 8), (210, 40, 50)).save(source, format=fmt, exif=exif.tobytes())
    original = source.read_bytes()
    result = prepare(source, tmp_path, Size(8))
    assert (result.width, result.height) == (8, 16)
    with Image.open(result.output) as output:
        assert not output.getexif()
    assert source.read_bytes() == original


@pytest.mark.parametrize("name,expected", [("grid", (256, 192)), ("profile", (32, 32))])
def test_heic_grid_and_profile_decode_without_an_encoder(tmp_path, name, expected):
    source = HEIC_FIXTURES / f"{name}.heic"
    if name == "grid":
        assert b"grid" in source.read_bytes()
    result = prepare(source, tmp_path, Size(256))
    with Image.open(result.output) as output:
        assert output.size == expected
        assert not output.info and not output.getexif()
        r, g, b = output.getpixel((0, 0))
        assert r > 170 and g < 90 and b < 100


@pytest.mark.parametrize(
    "fmt,extension,mode,byteorder",
    [
        ("PNG", "png", "I;16", "little"),
        ("TIFF", "tif", "I;16", "little"),
        ("TIFF", "tif", "I;16B", "big"),
    ],
)
def test_16_bit_grayscale_preserves_tonal_range(tmp_path, fmt, extension, mode, byteorder):
    values = (0, 16384, 32768, 49152, 65535)
    image = Image.frombytes(mode, (5, 1), b"".join(v.to_bytes(2, byteorder) for v in values))
    source = tmp_path / f"gray.{extension}"
    image.save(source, format=fmt)
    original = source.read_bytes()
    result = prepare(source, tmp_path, Size(5))
    with Image.open(result.output) as output:
        assert [output.getpixel((x, 0))[0] for x in range(5)] == [0, 64, 128, 191, 255]
        assert not output.info and not output.getexif()
    assert source.read_bytes() == original


def test_16_bit_png_transparency_uses_original_sample(tmp_path):
    values = (0, 32767, 32768, 32769, 65535)
    source = tmp_path / "transparent-gray.png"
    Image.frombytes("I;16", (5, 1), b"".join(v.to_bytes(2, "little") for v in values)).save(
        source, transparency=32768
    )
    result = prepare(source, tmp_path, Size(5))
    with Image.open(result.output) as output:
        assert output.mode == "RGBA"
        assert [output.getpixel((x, 0))[3] for x in range(5)] == [255, 255, 0, 255, 255]
        assert output.getpixel((1, 0))[0] == 127
        assert output.getpixel((3, 0))[0] == 128
        assert not output.info


@pytest.mark.parametrize("mode", ["I", "F"])
def test_32_bit_images_report_tone_mapping_requirement(tmp_path, mode):
    source = tmp_path / "hdr.tif"
    Image.new(mode, (8, 8), 1).save(source)
    with pytest.raises(ValueError, match="tone mapping"):
        prepare(source, tmp_path, Size(8))
    assert not list(tmp_path.glob("*.png"))

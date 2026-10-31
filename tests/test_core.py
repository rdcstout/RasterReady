import struct

import pytest
from PIL import Image, PngImagePlugin

from rasterready.core import PreparationError, Size, prepare, project_folder, validate_project


@pytest.mark.parametrize(
    "name", ["../escape", "a/b", "a\\b", ".", "..", "NUL", "com1.png", "a.", "bad\x00name", ""]
)
def test_project_cannot_escape_or_use_reserved_names(name):
    with pytest.raises(PreparationError):
        validate_project(name)


def test_folder_is_directly_under_downloads(tmp_path):
    assert project_folder(tmp_path, "Website photos") == tmp_path / "Website photos"


def test_project_symlink_is_rejected(tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (tmp_path / "project").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(PreparationError):
        project_folder(tmp_path, "project")


def test_orientation_privacy_and_original_preserved(tmp_path):
    source = tmp_path / "camera.jpg"
    exif = Image.Exif()
    exif[274] = 6
    exif[315] = "Private photographer"
    exif[306] = "2026:01:01 12:00:00"
    Image.new("RGB", (120, 80), "red").save(source, exif=exif)
    original = source.read_bytes()
    result = prepare(source, tmp_path, Size(40))
    assert result.output.name == "camera.png"
    with Image.open(result.output) as image:
        assert image.size == (40, 60)
        assert not image.getexif()
        assert not image.info
    assert source.read_bytes() == original


def test_metadata_chunks_removed_and_existing_png_never_overwritten(tmp_path):
    source = tmp_path / "photo.png"
    text = PngImagePlugin.PngInfo()
    text.add_text("Location", "Private location")
    Image.new("RGBA", (20, 10), (10, 20, 30, 128)).save(source, pnginfo=text)
    original = source.read_bytes()
    first = prepare(source, tmp_path, Size(10))
    second = prepare(source, tmp_path, Size(10))
    assert first.output.name == "photo (2).png"
    assert second.output.name == "photo (3).png"
    assert source.read_bytes() == original
    data = first.output.read_bytes()
    offset = 8
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        assert data[offset + 4 : offset + 8] in {b"IHDR", b"IDAT", b"IEND"}
        offset += length + 12
    with Image.open(first.output) as image:
        assert image.getpixel((0, 0))[3] == 128


def test_palette_transparency_survives(tmp_path):
    source = tmp_path / "palette.png"
    image = Image.new("P", (8, 8), 0)
    image.putpalette([255, 0, 0] * 256)
    image.save(source, transparency=0)
    result = prepare(source, tmp_path, Size(4))
    with Image.open(result.output) as output:
        assert output.mode == "RGBA"
        assert output.getpixel((0, 0))[3] == 0


def test_resize_modes_and_no_accidental_upscale(tmp_path):
    source = tmp_path / "small.png"
    Image.new("RGB", (80, 40), "red").save(source)
    fit = prepare(source, tmp_path, Size(100, 100))
    assert (fit.width, fit.height) == (80, 40)
    pad = prepare(source, tmp_path, Size(100, 100, "pad"))
    with Image.open(pad.output) as image:
        assert image.size == (100, 100)
        assert image.getpixel((0, 0)) == (255, 255, 255, 255)
    with pytest.raises(PreparationError, match="too small"):
        prepare(source, tmp_path, Size(100, 100, "crop"))
    crop = prepare(source, tmp_path, Size(100, 100, "crop"), enlarge=True)
    assert (crop.width, crop.height) == (100, 100)


def test_invalid_file_creates_no_partial_output(tmp_path):
    source = tmp_path / "broken.jpg"
    source.write_text("not an image")
    with pytest.raises(PreparationError, match="Unsupported or damaged"):
        prepare(source, tmp_path, Size(100))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["broken.jpg"]


def test_corrupt_profile_reports_error_instead_of_silent_color_change(tmp_path):
    source = tmp_path / "bad-profile.png"
    Image.new("RGB", (10, 10)).save(source, icc_profile=b"invalid ICC")
    with pytest.raises(PreparationError, match="color profile"):
        prepare(source, tmp_path, Size(10))


def test_animated_image_reports_first_frame(tmp_path):
    source = tmp_path / "animation.gif"
    Image.new("RGB", (10, 10), "red").save(
        source, save_all=True, append_images=[Image.new("RGB", (10, 10), "blue")]
    )
    assert "first frame" in prepare(source, tmp_path, Size(10)).notes[0]

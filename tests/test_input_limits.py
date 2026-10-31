import os
import unicodedata

import pytest
from PIL import Image

from rasterready import core
from rasterready.core import PreparationError, Size, prepare, validate_project


def test_long_unicode_filename_can_be_exported_repeatedly(tmp_path):
    source = tmp_path / ("界" * 83 + ".png")
    Image.new("RGB", (8, 8), "red").save(source)
    original = source.read_bytes()
    outputs = [prepare(source, tmp_path, Size(4)).output for _ in range(2)]
    assert len(set(outputs)) == 2
    assert source.read_bytes() == original
    for output in outputs:
        assert len(unicodedata.normalize("NFD", output.name).encode()) < 255
        assert Image.open(output).size == (4, 4)


def test_decomposing_accents_leave_room_for_collision_suffix(tmp_path):
    source = tmp_path / ("é" * 80 + ".png")
    Image.new("RGB", (8, 8)).save(source)
    output = prepare(source, tmp_path, Size(4)).output
    assert len(unicodedata.normalize("NFD", output.name).encode()) < 255


@pytest.mark.parametrize("name", ["界" * 100, "é" * 100, "COM¹", "lpt².txt", "NUL .photos"])
def test_project_names_fail_before_filesystem_error(name):
    with pytest.raises(PreparationError):
        validate_project(name)


def test_source_size_rejected_before_decoder(tmp_path, monkeypatch):
    source = tmp_path / "oversize.png"
    source.write_bytes(b"x" * 33)
    monkeypatch.setattr(core, "MAX_SOURCE_BYTES", 32, raising=False)
    monkeypatch.setattr(
        core.Image, "open", lambda *_: pytest.fail("Decoder must not read oversized file")
    )
    with pytest.raises(PreparationError, match="file is too large"):
        prepare(source, tmp_path, Size(4))
    assert not list(tmp_path.glob("* (2).png"))


def test_folder_rejected_before_decoder(tmp_path, monkeypatch):
    monkeypatch.setattr(
        core.Image, "open", lambda *_: pytest.fail("Decoder must not open a folder")
    )
    with pytest.raises(PreparationError, match="regular image file"):
        prepare(tmp_path, tmp_path, Size(4))


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX special-file test")
def test_named_pipe_rejected_before_decoder(tmp_path, monkeypatch):
    source = tmp_path / "input.png"
    os.mkfifo(source)
    monkeypatch.setattr(
        core.Image, "open", lambda *_: pytest.fail("Decoder must not open a named pipe")
    )
    with pytest.raises(PreparationError, match="regular image file"):
        prepare(source, tmp_path, Size(4))


def test_first_frame_export_does_not_enumerate_entire_animation(tmp_path, monkeypatch):
    from PIL.GifImagePlugin import GifImageFile

    source = tmp_path / "animation.gif"
    Image.new("RGB", (8, 8), "red").save(
        source, save_all=True, append_images=[Image.new("RGB", (8, 8), "blue")]
    )
    monkeypatch.setattr(
        GifImageFile,
        "n_frames",
        property(lambda _: pytest.fail("Do not scan the entire animation")),
    )
    result = prepare(source, tmp_path, Size(4))
    assert any("first frame" in n for n in result.notes)
    with Image.open(result.output) as output:
        assert output.getpixel((0, 0)) == (255, 0, 0)


def test_save_failure_removes_partial_output_and_preserves_original(tmp_path, monkeypatch):
    source = tmp_path / "photo.png"
    Image.new("RGB", (8, 8), "red").save(source)
    original = source.read_bytes()

    def failed_save(_image, handle, **_kwargs):
        handle.write(b"partial PNG")
        raise OSError("disk full")

    monkeypatch.setattr(Image.Image, "save", failed_save)
    with pytest.raises(PreparationError, match="disk full"):
        prepare(source, tmp_path, Size(4))
    assert source.read_bytes() == original
    assert list(tmp_path.iterdir()) == [source]


def test_input_windows_device_name_gets_safe_output_name(tmp_path):
    source = tmp_path / "COM¹.png"
    Image.new("RGB", (8, 8), "red").save(source)
    output = prepare(source, tmp_path, Size(4)).output
    assert output.name == "image_COM¹.png"

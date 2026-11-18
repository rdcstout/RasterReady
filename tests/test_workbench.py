import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time

import pytest
from PIL import Image
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from rasterready.app import Batch, DropArea
from rasterready.core import prepare
from rasterready.enhance import Adjustments
from rasterready.presets import PRESETS
from rasterready.workbench import ExportOptions, Workbench


def test_preview_and_selected_preset_export(tmp_path):
    app = QApplication.instance() or QApplication([])
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    Image.new("RGBA", (80, 40), (100, 20, 50, 255)).save(first)
    Image.new("RGBA", (80, 40), (100, 20, 50, 0)).save(second)
    dialog = Workbench(None, DropArea())
    dialog.set_paths([first, second])
    dialog.photos.setCurrentRow(1)
    dialog.auto_adjust()
    dialog.rotation.setCurrentIndex(1)
    deadline = time.monotonic() + 5
    while dialog.preview.after is None and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(10)
    assert dialog.preview.after is not None
    assert (dialog.preview.after.width(), dialog.preview.after.height()) == (40, 80)
    dialog.photos.setCurrentRow(0)
    assert dialog.adjustments() == Adjustments()
    dialog.photos.setCurrentRow(1)
    assert dialog.adjustments().rotation == 1
    crop = dialog.crop_controls
    assert crop.presets[1:] == PRESETS
    crop.preset.setCurrentIndex(
        1 + next(i for i, item in enumerate(PRESETS) if item.key == "product2000")
    )
    crop.update_settings()
    assert not crop.isWindow()
    options = ExportOptions(None, dialog.paths, 1, dialog.edits, dialog.crops)
    options.filename.setText("Preview")
    options.format.setCurrentText("JPG")
    options.quality.setValue(90)
    options.scope.setCurrentIndex(1)
    options.accept()
    request = options.request
    assert request.paths == (second,)
    assert request.quality == 90
    assert request.crops[0].flatten
    batch = Batch(request, tmp_path)
    batch.run()
    assert not (tmp_path / "first.jpg").exists()
    with Image.open(tmp_path / "Preview.jpg") as output:
        assert output.format == "JPEG"
        assert output.size == (2000, 2000)
        assert output.getpixel((1000, 1000)) == (255, 255, 255)
    dialog.close()


@pytest.mark.parametrize("format, suffix", [("PNG", ".png"), ("TIFF", ".tiff")])
def test_as_enhanced_exports_keep_alpha_and_existing_file(tmp_path, format, suffix):
    source = tmp_path / "image.png"
    Image.new("RGBA", (20, 12), (50, 80, 100, 128)).save(source)
    original = source.read_bytes()
    first = prepare(
        source, tmp_path, None, adjustments=Adjustments(crop=(1, 1), scale=2), output_format=format
    )
    second = prepare(
        source, tmp_path, None, adjustments=Adjustments(exposure=1), output_format=format
    )
    assert first.output.suffix == second.output.suffix == suffix
    assert len({first.output, second.output, source}) == 3
    assert source.read_bytes() == original
    with Image.open(first.output) as output:
        assert output.size == (24, 24)
        assert output.format == format
        assert output.mode == "RGBA"
        assert output.getpixel((12, 12))[3] == 128


def test_batch_uses_named_sequence_and_skips_existing_files(tmp_path):
    from rasterready.workbench import CropSettings, ExportRequest

    paths = tuple(tmp_path / f"source-{n}.png" for n in range(4))
    for path in paths:
        Image.new("RGB", (20, 12), "red").save(path)
    output = tmp_path / "exports"
    output.mkdir()
    existing = output / "Listing 2.jpg"
    existing.write_bytes(b"keep me")
    request = ExportRequest(
        paths,
        "Listing",
        "JPEG",
        95,
        (Adjustments(),) * 4,
        (CropSettings(),) * 4,
    )
    batch = Batch(request, output)
    batch.run()
    assert existing.read_bytes() == b"keep me"
    assert {path.name for path in output.iterdir()} == {
        "Listing.jpg",
        "Listing 2.jpg",
        "Listing 3.jpg",
        "Listing 4.jpg",
        "Listing 5.jpg",
    }
    for name in ("Listing.jpg", "Listing 3.jpg", "Listing 4.jpg", "Listing 5.jpg"):
        with Image.open(output / name) as image:
            assert image.format == "JPEG"
    assert len(list(tmp_path.glob("source-*.png"))) == 4


def test_crop_settings_survive_selection_and_apply_to_all(tmp_path):
    from rasterready.workbench import CropSettings

    _app = QApplication.instance() or QApplication([])
    paths = [tmp_path / f"source-{n}.png" for n in range(2)]
    for path in paths:
        Image.new("RGB", (40, 30), "blue").save(path)
    editor = Workbench(None, DropArea())
    editor.set_paths(paths)
    preset = next(item for item in PRESETS if item.key == "product2000")
    editor.crops[0] = CropSettings(preset)
    editor.photos.setCurrentRow(1)
    assert editor.crops[1] == CropSettings()
    editor.photos.setCurrentRow(0)
    editor.apply_all()
    assert editor.crops[1].preset == preset
    editor.reset()
    assert editor.crops[0] == CropSettings()
    assert editor.crops[1].preset == preset
    editor.close()


@pytest.mark.parametrize("dimensions", [(120, 60), (60, 120)])
def test_square_preset_fills_edges_and_enlarges_small_photos(tmp_path, dimensions):
    from rasterready.workbench import CropSettings, ExportRequest

    _app = QApplication.instance() or QApplication([])
    source = tmp_path / "landscape.png"
    Image.new("RGB", dimensions, (20, 100, 60)).save(source)
    editor = Workbench(None, DropArea())
    editor.set_paths([source])
    controls = editor.crop_controls
    controls.preset.setCurrentIndex(
        1 + next(i for i, preset in enumerate(PRESETS) if preset.key == "product2000")
    )
    assert controls.enlarge.isChecked()
    assert not controls.enlarge.isEnabled()
    crop = editor.crops[0]
    assert crop.size.mode == "crop"
    request = ExportRequest((source,), "Square", "PNG", 95, (Adjustments(),), (crop,))
    Batch(request, tmp_path).run()
    with Image.open(tmp_path / "Square.png") as result:
        assert result.size == (2000, 2000)
        for point in [(0, 0), (1999, 0), (0, 1999), (1999, 1999), (1000, 1000)]:
            assert result.getpixel(point) == (20, 100, 60)
    assert CropSettings(crop.preset).allow_enlargement
    editor.close()


@pytest.mark.parametrize("portrait", [False, True])
def test_drag_reframes_preview_and_export_and_keeps_each_photo_position(tmp_path, portrait):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    from rasterready.workbench import ExportRequest

    app = QApplication.instance() or QApplication([])
    source = tmp_path / "stripes.png"
    picture = Image.new("RGB", (40, 120) if portrait else (120, 40))
    for n, color in enumerate(("red", "green", "blue")):
        box = (0, n * 40, 40, (n + 1) * 40) if portrait else (n * 40, 0, (n + 1) * 40, 40)
        picture.paste(color, box)
    picture.save(source)
    other = tmp_path / "other.png"
    picture.save(other)
    editor = Workbench(None, DropArea())
    editor.resize(1100, 800)
    editor.show()
    editor.set_paths([source, other])
    editor.crop_controls.preset.setCurrentIndex(
        1 + next(i for i, item in enumerate(PRESETS) if item.key == "product2000")
    )
    deadline = time.monotonic() + 5
    while (
        editor.preview.after is None or editor.running or editor.timer.isActive()
    ) and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(10)
    assert editor.preview.can_reposition
    preview = editor.preview
    origin = QPointF(preview.image_area(preview.after).center())
    app.sendEvent(
        preview,
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            origin,
            origin,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        ),
    )
    # Moving the image down/right reveals the top/left red band.
    target = origin + QPointF(0, 2000) if portrait else origin + QPointF(2000, 0)
    app.sendEvent(
        preview,
        QMouseEvent(
            QEvent.Type.MouseMove,
            target,
            target,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        ),
    )
    app.sendEvent(
        preview,
        QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            target,
            target,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        ),
    )
    deadline = time.monotonic() + 5
    while (editor.running or editor.timer.isActive()) and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(10)
    expected_center = (0.5, 0) if portrait else (0, 0.5)
    assert editor.crops[0].center == expected_center
    after = preview.after
    assert after.pixelColor(after.width() // 2, after.height() // 2).getRgb()[:3] == (255, 0, 0)
    request = ExportRequest((source,), "Reframed", "PNG", 95, (Adjustments(),), (editor.crops[0],))
    Batch(request, tmp_path).run()
    with Image.open(tmp_path / "Reframed.png") as result:
        assert result.size == (2000, 2000)
        assert result.getpixel((1000, 1000)) == (255, 0, 0)
    editor.photos.setCurrentRow(1)
    assert editor.crops[1].center == (0.5, 0.5)
    editor.photos.setCurrentRow(0)
    assert editor.crops[0].center == expected_center
    editor.recenter_crop()
    assert editor.crops[0].center == (0.5, 0.5)
    editor.close()

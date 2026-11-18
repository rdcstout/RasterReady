import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time

import pytest
from PIL import Image
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from rasterready.app import Batch, DropArea
from rasterready.core import Size, prepare
from rasterready.enhance import Adjustments
from rasterready.presets import PRESETS
from rasterready.workbench import ExportOptions, Workbench


def test_preview_and_selected_preset_export(tmp_path):
    app = QApplication.instance() or QApplication([])
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    Image.new("RGBA", (80, 40), (100, 20, 50, 255)).save(first)
    Image.new("RGBA", (80, 40), (100, 20, 50, 0)).save(second)
    custom = Size(1024)
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
    options = ExportOptions(None, "Preview", dialog.paths, 1, dialog.edits, -1, False, custom)
    assert options.presets[1:] == PRESETS
    options.preset.setCurrentIndex(
        1 + next(i for i, item in enumerate(PRESETS) if item.key == "product2000")
    )
    options.format.setCurrentText("JPEG")
    options.quality.setValue(90)
    options.scope.setCurrentIndex(1)
    options.accept()
    request = options.request
    assert request.paths == (second,)
    assert request.quality == 90
    assert request.flatten
    batch = Batch(request, tmp_path)
    batch.run()
    assert not (tmp_path / "first.jpg").exists()
    with Image.open(tmp_path / "second.jpg") as output:
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

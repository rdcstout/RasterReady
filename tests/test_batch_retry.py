import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time

import pytest
from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from rasterready import app as ui
from rasterready.presets import PRESETS


@pytest.mark.parametrize("problem", ["project", "size"])
def test_queued_files_can_retry_after_correcting_settings(tmp_path, monkeypatch, problem):
    application = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat)
    settings.setValue("updates/automatic", False)
    downloads = tmp_path / "Downloads"
    monkeypatch.setattr(ui.QStandardPaths, "writableLocation", lambda _: str(downloads))
    source = tmp_path / "photo.png"
    Image.new("RGB", (8, 4), "red").save(source)
    original = source.read_bytes()
    window = ui.Window(settings=settings)
    window.accept_files([source])
    dialog = ui.ExportOptions(window, window.paths, 0, window.editor.edits, window.editor.crops)
    dialog.filename.setText("invalid/name" if problem == "project" else "Website")
    crop_dialog = window.editor.crop_controls
    if problem == "size":
        crop_dialog.preset.setCurrentIndex(
            1 + next(i for i, p in enumerate(PRESETS) if p.key == "custom")
        )
        crop_dialog.mode.setCurrentIndex(1)
    try:
        invalid = dialog if problem == "project" else crop_dialog
        if problem == "project":
            invalid.accept()
        else:
            invalid.update_settings()
        assert invalid.message.text()
        assert window.worker is None
        assert not list(downloads.rglob("*.png"))
        assert not window.export.isHidden()
        assert window.export.isEnabled()
        if problem == "project":
            dialog.filename.setText("Website")
        else:
            crop_dialog.mode.setCurrentIndex(0)
            crop_dialog.update_settings()
            dialog.crops = tuple(window.editor.crops)
        dialog.accept()
        window.start(dialog.request)
        deadline = time.monotonic() + 5
        while window.worker is not None and time.monotonic() < deadline:
            application.processEvents()
            QTest.qWait(10)
        assert window.worker is None
        assert window.successes == 1
        assert window.table.item(0, 2).text() == "Ready"
        assert (downloads / "Website/Website.png").is_file()
        assert source.read_bytes() == original
    finally:
        if window.worker is not None:
            window.worker.cancel.set()
            window.worker.wait(5000)
            application.processEvents()
        window.close()

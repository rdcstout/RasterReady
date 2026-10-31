import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time
from threading import Event

import pytest
from PIL import Image
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from rasterready import app as ui


@pytest.fixture(autouse=True)
def isolated_preferences(tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat)
    settings.setValue("updates/automatic", False)
    monkeypatch.setattr(ui, "QSettings", lambda *_: settings)


def test_batch_continues_after_failure_and_uses_project_folder(tmp_path, monkeypatch):
    application = QApplication.instance() or QApplication([])
    downloads = tmp_path / "Downloads"
    monkeypatch.setattr(ui.QStandardPaths, "writableLocation", lambda _: str(downloads))
    bad = tmp_path / "bad.jpg"
    bad.write_text("broken")
    good = tmp_path / "good.png"
    Image.new("RGB", (120, 80), "red").save(good)
    window = ui.Window()
    window.project.setText("Test project")
    window.accept_files([bad, good])
    deadline = time.monotonic() + 10
    while window.worker is not None and time.monotonic() < deadline:
        application.processEvents()
        QTest.qWait(10)
    application.processEvents()
    assert window.worker is None
    assert window.successes == 1
    assert window.done == 2
    assert window.table.item(0, 2).text() == "Failed"
    assert "Unsupported or damaged" in window.table.item(0, 2).toolTip()
    assert window.table.item(1, 2).text() == "Ready"
    assert (downloads / "Test project" / "good.png").is_file()
    assert not (downloads / "Finished").exists()
    assert window.drop.isEnabled()
    window.close()


def test_theme_choice_persists_and_does_not_lose_project(tmp_path):
    _application = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    window = ui.Window(settings=settings)
    window.project.setText("My project")
    for index, name in ((1, "light"), (2, "dark")):
        window.appearance.setCurrentIndex(index)
        assert window.current_theme == name
        assert window.project.text() == "My project"
        assert window.settings.value("appearance") == name
        assert not window.drop.art.pixmap().isNull()
    window.close()
    reopened = ui.Window(settings=settings)
    assert reopened.current_theme == "dark"
    assert reopened.appearance.currentIndex() == 2
    reopened.appearance.setCurrentIndex(0)
    assert reopened.settings.value("appearance") == "system"
    reopened.close()


def test_files_wait_for_project_name_without_writing(tmp_path, monkeypatch):
    _application = QApplication.instance() or QApplication([])
    downloads = tmp_path / "Downloads"
    monkeypatch.setattr(ui.QStandardPaths, "writableLocation", lambda _: str(downloads))
    window = ui.Window()
    window.accept_files([tmp_path / "image.jpg"])
    assert window.worker is None
    assert window.export.isEnabled()
    assert not downloads.exists()
    window.close()


def test_cancellation_finishes_current_file_and_releases_batch(tmp_path, monkeypatch):
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        ui.QStandardPaths, "writableLocation", lambda _: str(tmp_path / "Downloads")
    )
    entered, resume = Event(), Event()
    real_prepare = ui.prepare

    def slow_first(*args):
        entered.set()
        if not resume.wait(5):
            raise RuntimeError("Test did not release conversion")
        return real_prepare(*args)

    monkeypatch.setattr(ui, "prepare", slow_first)
    files = [tmp_path / f"photo-{n}.png" for n in range(2)]
    for source in files:
        Image.new("RGB", (8, 8), "red").save(source)
    window = ui.Window()
    window.project.setText("Cancel test")
    window.accept_files(files)
    try:
        assert entered.wait(2)
        window.cancel()
    finally:
        resume.set()
    deadline = time.monotonic() + 5
    while window.worker is not None and time.monotonic() < deadline:
        application.processEvents()
        QTest.qWait(10)
    assert window.worker is None
    assert window.done == 2 and window.successes == 1
    assert window.table.item(1, 2).text() == "Cancelled"
    assert list((tmp_path / "Downloads" / "Cancel test").glob("*.png")) == [
        tmp_path / "Downloads" / "Cancel test" / "photo-0.png"
    ]
    # A second batch remains usable after the first thread has been released.
    window.accept_files([files[1]])
    while window.worker is not None and time.monotonic() < deadline:
        application.processEvents()
        QTest.qWait(10)
    assert window.worker is None and window.successes == 1
    window.close()


def test_failure_details_are_accessible_and_treated_as_plain_text(tmp_path, monkeypatch):
    _application = QApplication.instance() or QApplication([])
    window = ui.Window()
    window.accept_files([tmp_path / "<b>private</b>.jpg"])
    error = '<img src="private.png"> could not be read'
    window.completed(0, None, error)
    item = window.table.item(0, 2)
    assert item.data(Qt.ItemDataRole.AccessibleDescriptionRole) == error
    assert "&lt;img" in item.toolTip()
    captured = []
    monkeypatch.setattr(
        ui.QMessageBox, "exec", lambda box: captured.append((box.text(), box.textFormat()))
    )
    window.show()
    window.activateWindow()
    _application.processEvents()
    window.focus_results()
    QTest.keyClick(window.table, Qt.Key.Key_Return)
    assert captured == [(error, Qt.TextFormat.PlainText)]
    window.close()

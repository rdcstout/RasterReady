"""Dropped image imports must never acknowledge moving the source files."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time

import pytest
from PIL import Image, PngImagePlugin
from PySide6.QtCore import QMimeData, QPointF, QSettings, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from rasterready import app as ui


def test_drop_imports_batch_as_copy_even_when_sender_proposes_move(tmp_path, monkeypatch):
    application = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat)
    settings.setValue("updates/automatic", False)
    monkeypatch.setattr(
        ui.QStandardPaths, "writableLocation", lambda _: str(tmp_path / "Downloads")
    )
    paths = [tmp_path / "image one.png", tmp_path / "étoile.png"]
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("Location", "synthetic location marker")
    for path in paths:
        Image.new("RGB", (16, 8), "blue").save(path, pnginfo=metadata)
    originals = [path.read_bytes() for path in paths]
    window = ui.Window(settings=settings)
    window.project.setText("Dropped batch")
    window.show()
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths] + [QUrl("https://example.org/a.png")])
    actions = Qt.DropAction.CopyAction | Qt.DropAction.MoveAction
    enter = QDragEnterEvent(
        QPointF(10, 10), actions, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier
    )
    assert enter.proposedAction() == Qt.DropAction.MoveAction
    application.sendEvent(window.drop, enter)
    assert enter.isAccepted()
    assert enter.dropAction() == Qt.DropAction.CopyAction
    drop = QDropEvent(
        QPointF(10, 10), actions, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier
    )
    application.sendEvent(window.drop, drop)
    assert drop.isAccepted()
    assert drop.dropAction() == Qt.DropAction.CopyAction
    deadline = time.monotonic() + 5
    while window.worker is not None and time.monotonic() < deadline:
        application.processEvents()
        QTest.qWait(10)
    assert window.worker is None
    assert window.paths == paths
    assert window.done == window.successes == 2
    for path, original in zip(paths, originals):
        assert path.read_bytes() == original
        with Image.open(tmp_path / "Downloads" / "Dropped batch" / path.name) as output:
            assert output.size == (16, 8)
            assert not output.info and not output.getexif()
    window.close()


@pytest.mark.parametrize("kind", ["move-only", "remote", "disabled"])
def test_unsuitable_drop_is_rejected_without_emitting_files(tmp_path, kind):
    _application = QApplication.instance() or QApplication([])
    area = ui.DropArea()
    mime = QMimeData()
    mime.setUrls(
        [
            QUrl("https://example.org/a.png")
            if kind == "remote"
            else QUrl.fromLocalFile(str(tmp_path / "image.png"))
        ]
    )
    received = []
    area.files.connect(received.append)
    area.setEnabled(kind != "disabled")
    action = Qt.DropAction.MoveAction if kind == "move-only" else Qt.DropAction.CopyAction
    enter = QDragEnterEvent(
        QPointF(10, 10), action, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    )
    area.dragEnterEvent(enter)
    assert not enter.isAccepted()
    drop = QDropEvent(
        QPointF(10, 10), action, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    )
    area.dropEvent(drop)
    assert not drop.isAccepted()
    assert not received
    area.close()

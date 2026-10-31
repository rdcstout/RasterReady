import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from rasterready.app import Window
from rasterready.theme import PALETTES, apply


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_top_level_dialogs_use_matching_background_and_text(tmp_path, theme):
    application = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("updates/automatic", False)
    window = Window(settings=settings)
    original_palette = application.palette()
    try:
        apply(window, theme)
        picker = QFileDialog(window)
        picker.setOption(QFileDialog.Option.DontUseNativeDialog)
        message = QMessageBox(window)
        for dialog in (picker, message):
            dialog.ensurePolished()
            for role, token in (
                (QPalette.ColorRole.Window, "surface"),
                (QPalette.ColorRole.Base, "field"),
                (QPalette.ColorRole.Text, "text"),
                (QPalette.ColorRole.WindowText, "text"),
            ):
                assert dialog.palette().color(role).name() == PALETTES[theme][token]
            dialog.close()
    finally:
        window.close()
        application.setPalette(original_palette)

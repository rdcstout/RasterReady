import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLineEdit

from rasterready.notices import NoticesDialog


def test_notice_search_and_plain_text_display(tmp_path):
    application = QApplication.instance() or QApplication([])
    (tmp_path / "Qt").mkdir()
    text = '<img src="https://example.invalid/tracker">\nCopyright example\n'
    (tmp_path / "Qt/LICENSE.txt").write_text(text)
    (tmp_path / "OTHER.txt").write_text("Other notice")
    dialog = NoticesDialog(tmp_path)
    dialog.show()
    search = dialog.findChild(QLineEdit)
    search.setText("qt/license")
    application.processEvents()
    visible = [
        dialog.files.item(i)
        for i in range(dialog.files.count())
        if not dialog.files.item(i).isHidden()
    ]
    assert [item.text() for item in visible] == ["Qt/LICENSE.txt"]
    assert dialog.text.toPlainText() == text
    assert dialog.text.isReadOnly()
    search.setText("no such component")
    assert dialog.text.toPlainText() == "No matching notices."
    search.clear()
    assert dialog.files.currentItem() is not None
    assert dialog.text.toPlainText() != "No matching notices."
    dialog.close()

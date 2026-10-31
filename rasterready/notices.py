"""Read packaged license texts without launching an external application."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .theme import PALETTES


class NoticesDialog(QDialog):
    def __init__(self, directory, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Third-party notices")
        self.resize(960, 640)
        if parent is not None:
            c = PALETTES[parent.current_theme]
            self.setPalette(parent.palette())
            self.setStyleSheet(f"""
                QDialog {{ background: {c["surface"]}; }}
                QListWidget, QPlainTextEdit {{ background: {c["field"]}; color: {c["text"]};
                    border: 1px solid {c["outline"]}; selection-background-color: {c["tint"]};
                    selection-color: {c["text"]}; }}
            """)
        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        navigation = QWidget()
        sidebar = QVBoxLayout(navigation)
        search = QLineEdit()
        search.setPlaceholderText("Find a notice…")
        search.setAccessibleName("Find a notice")
        sidebar.addWidget(search)
        self.files = QListWidget()
        self.files.setAccessibleName("Notice files")
        sidebar.addWidget(self.files)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setAccessibleName("Notice text")
        splitter.addWidget(navigation)
        splitter.addWidget(self.text)
        splitter.setSizes([320, 640])
        root = directory.resolve()
        self.paths = {}
        if root.is_dir():
            for path in sorted(root.rglob("*")):
                if path.is_file() and path.resolve().is_relative_to(root):
                    name = path.relative_to(root).as_posix()
                    self.paths[name] = path
                    self.files.addItem(name)
        self.files.currentTextChanged.connect(self.show_notice)
        search.textChanged.connect(self.filter_notices)
        if self.files.count():
            self.files.setCurrentRow(0)
        else:
            self.text.setPlainText("No notice files were found in this installation.")

    def filter_notices(self, query):
        visible = []
        for index in range(self.files.count()):
            item = self.files.item(index)
            item.setHidden(query.casefold() not in item.text().casefold())
            if not item.isHidden():
                visible.append(item)
        if visible:
            if self.files.currentItem() not in visible:
                self.files.setCurrentItem(visible[0])
        else:
            self.files.setCurrentRow(-1)
            self.text.setPlainText("No matching notices.")

    def show_notice(self, name):
        try:
            text = self.paths[name].read_text(encoding="utf-8", errors="replace")
        except (OSError, KeyError):
            text = "This notice could not be read."
        self.text.setPlainText(text)

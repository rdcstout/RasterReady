"""Shared light/dark tokens and licensed Tabler UI icons."""

from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

PALETTES = {
    "light": dict(
        surface="#ffffff",
        canvas="#fafafb",
        field="#ffffff",
        text="#151820",
        muted="#616773",
        border="#e2e4e9",
        outline="#bfc4ce",
        accent="#df101b",
        hover="#c50b16",
        tint="#fff0f1",
        disabled="#9ca1ab",
        success="#087e35",
        warning="#8f5b00",
    ),
    "dark": dict(
        surface="#1b1d22",
        canvas="#22252c",
        field="#272a32",
        text="#f3f4f7",
        muted="#b0b5c1",
        border="#353943",
        outline="#555c6a",
        accent="#d91b2a",
        hover="#bd1020",
        tint="#45262c",
        disabled="#747b89",
        success="#64d48c",
        warning="#f2c46d",
    ),
}


def icon(name: str, color: str) -> QIcon:
    data = (Path(__file__).parent / "assets" / f"{name}.svg").read_text()
    renderer = QSvgRenderer(QByteArray(data.replace("currentColor", color).encode()))
    result = QIcon()
    for size in (16, 24, 32, 64, 128):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        result.addPixmap(pixmap)
    return result


def apply(window, name: str):
    c = PALETTES[name]
    arrow = (Path(__file__).parent / "assets" / f"chevron-down-{name}.svg").resolve().as_posix()
    check = (Path(__file__).parent / "assets" / "check-white.svg").resolve().as_posix()
    palette = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, c["surface"]),
        (QPalette.ColorRole.WindowText, c["text"]),
        (QPalette.ColorRole.Base, c["field"]),
        (QPalette.ColorRole.AlternateBase, c["canvas"]),
        (QPalette.ColorRole.Text, c["text"]),
        (QPalette.ColorRole.Button, c["field"]),
        (QPalette.ColorRole.ButtonText, c["text"]),
        (QPalette.ColorRole.Highlight, c["tint"]),
        (QPalette.ColorRole.HighlightedText, c["text"]),
        (QPalette.ColorRole.PlaceholderText, c["muted"]),
        (QPalette.ColorRole.ToolTipBase, c["surface"]),
        (QPalette.ColorRole.ToolTipText, c["text"]),
    ):
        palette.setColor(role, QColor(color))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.WindowText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(c["disabled"]))
    # Top-level dialogs inherit the application palette, not their parent's.
    # Keep their backgrounds consistent with the text stylesheet they inherit.
    QApplication.instance().setPalette(palette)
    window.setPalette(palette)
    window.setStyleSheet(f"""
      QWidget {{ font-size: 15px; color: {c["text"]}; }}
      QMainWindow, QWidget#body, QWidget#header, QWidget#setup {{ background: {c["surface"]}; }}
      QWidget#workspace {{ background: {c["canvas"]}; }}
      QMenuBar, QMenu {{ background: {c["surface"]}; color: {c["text"]}; }}
      QMenuBar::item:selected, QMenu::item:selected {{ background: {c["tint"]}; color: {c["text"]}; }}
      QMenu {{ border: 1px solid {c["outline"]}; }}
      QWidget#header {{ border-bottom: 1px solid {c["border"]}; }}
      QScrollArea#setupScroll {{ background: {c["surface"]}; border: none; border-right: 1px solid {c["border"]}; }}
      QScrollBar:vertical {{ background: {c["surface"]}; width: 12px; margin: 2px; }}
      QScrollBar::handle:vertical {{ background: {c["outline"]}; border-radius: 4px; min-height: 30px; }}
      QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
      QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
      QLabel {{ background: transparent; border: none; }}
      QLabel#wordmark {{ font-size: 27px; font-weight: 750; letter-spacing: -1px; }}
      QLabel#muted, QLabel#guidance {{ color: {c["muted"]}; }}
      QLabel#guidance {{ font-size: 12px; }}
      QLabel#dropTitle {{ font-size: 25px; font-weight: 700; letter-spacing: -0.5px; }}
      QLabel#dropHint {{ color: {c["muted"]}; font-size: 13px; }}
      QLabel#summary {{ font-size: 15px; font-weight: 600; }}
      QLineEdit, QComboBox, QSpinBox {{ background: {c["field"]}; border: 1px solid {c["outline"]};
        border-radius: 7px; padding: 10px 11px; selection-background-color: {c["accent"]}; selection-color: white; }}
      QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 2px solid {c["accent"]}; padding: 9px 10px; }}
      QComboBox::drop-down {{ border: none; width: 24px; }}
      QComboBox::down-arrow {{ image: url("{arrow}"); width: 14px; height: 14px; }}
      QComboBox QAbstractItemView {{ background: {c["surface"]}; color: {c["text"]}; selection-background-color: {c["tint"]}; }}
      QComboBox#theme {{ font-size: 12px; padding: 6px 9px; }}
      QCheckBox {{ spacing: 8px; padding: 4px 0; }}
      QCheckBox::indicator {{ width: 17px; height: 17px; border: 1px solid {c["outline"]};
        border-radius: 3px; background: {c["field"]}; }}
      QCheckBox::indicator:checked {{ background: {c["accent"]}; border-color: {c["accent"]}; image: url("{check}"); }}
      QCheckBox::indicator:disabled {{ border-color: {c["border"]}; }}
      QPushButton {{ background: {c["field"]}; border: 1px solid {c["outline"]}; border-radius: 7px;
        padding: 9px 14px; font-weight: 600; }}
      QPushButton:hover {{ border-color: {c["accent"]}; background: {c["tint"]}; }}
      QPushButton:focus {{ border: 2px solid {c["accent"]}; padding: 8px 13px; }}
      QPushButton[primary="true"] {{ background: {c["accent"]}; border-color: {c["accent"]}; color: white; }}
      QPushButton[primary="true"]:hover {{ background: {c["hover"]}; }}
      QPushButton:disabled {{ color: {c["disabled"]}; background: {c["canvas"]}; border-color: {c["border"]}; }}
      QPushButton#guide {{ font-size: 12px; font-weight: 400; border: none; color: {c["muted"]}; padding: 5px 0; text-align: left; }}
      QFrame#drop {{ background: {c["canvas"]}; border: 1px dashed {c["outline"]}; border-radius: 14px; }}
      QFrame#drop[dragActive="true"] {{ border: 2px dashed {c["accent"]}; background: {c["tint"]}; }}
      QFrame#drop:focus {{ border: 2px dashed {c["accent"]}; }}
      QTableWidget {{ background: {c["canvas"]}; border: none; gridline-color: {c["border"]}; outline: none; font-size: 14px; }}
      QTableWidget::item {{ padding: 8px 5px; border-bottom: 1px solid {c["border"]}; }}
      QTableWidget::item:selected {{ background: {c["tint"]}; color: {c["text"]}; }}
      QHeaderView::section {{ background: {c["canvas"]}; border: none; border-bottom: 1px solid {c["border"]};
        padding: 10px 5px; font-size: 12px; color: {c["muted"]}; text-align: left; }}
      QToolTip {{ background: {c["surface"]}; color: {c["text"]}; border: 1px solid {c["outline"]}; padding: 8px; }}
    """)
    window.drop.art.setPixmap(icon("photo", c["muted"]).pixmap(68, 68))
    window.open.setIcon(icon("folder-open", "#ffffff"))
    window.current_theme = name

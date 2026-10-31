"""Single-window batch workflow. All image work runs off the GUI thread."""

import sys
from html import escape
from pathlib import Path
from threading import Event

from PySide6.QtCore import QSettings, QSize, QStandardPaths, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import __version__, theme
from .core import PreparationError, Size, prepare, project_folder
from .notices import NoticesDialog
from .presets import PRESETS
from .update_ui import UpdateChecker


class Batch(QThread):
    completed = Signal(int, object, str)

    def __init__(self, paths, folder, size, enlarge, preset, parent=None):
        super().__init__(parent)
        self.paths, self.folder, self.size, self.enlarge = paths, folder, size, enlarge
        self.preset = preset
        self.cancel = Event()

    def run(self):
        for index, path in enumerate(self.paths):
            if self.cancel.is_set():
                self.completed.emit(index, None, "Cancelled")
                continue
            try:
                result = prepare(path, self.folder, self.size, self.enlarge, self.preset.flatten)
                notes = self.preset.review(result)
                from dataclasses import replace

                self.completed.emit(index, replace(result, notes=notes), "")
            except (PreparationError, OSError) as exc:
                self.completed.emit(index, None, str(exc))
            except Exception:
                self.completed.emit(
                    index,
                    None,
                    "Unexpected conversion failure. Try another image or report this problem.",
                )


class ResultsTable(QTableWidget):
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.currentItem():
            self.itemActivated.emit(self.currentItem())
            event.accept()
        else:
            super().keyPressEvent(event)


class DropArea(QFrame):
    files = Signal(list)
    clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("drop")
        self.setAccessibleName("Drop images or choose files")
        self.setMinimumHeight(265)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addStretch()
        self.art = QLabel()
        self.art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.art)
        title = QLabel("Drop images here")
        title.setObjectName("dropTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        choose = QPushButton("Choose files")
        choose.setProperty("primary", True)
        choose.setMinimumWidth(155)
        choose.setMinimumHeight(42)
        choose.clicked.connect(self.clicked.emit)
        layout.addWidget(choose, 0, Qt.AlignmentFlag.AlignHCenter)
        hint = QLabel("JPEG, PNG, HEIC, AVIF, Sony RAW")
        hint.setObjectName("dropHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()

    def _drag_active(self, active):
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)

    def _drop_paths(self, event):
        if not self.isEnabled() or not event.possibleActions() & Qt.DropAction.CopyAction:
            return []
        return [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]

    def dragEnterEvent(self, event):
        accepted = bool(self._drop_paths(event))
        self._drag_active(accepted)
        if accepted:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._drag_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._drag_active(False)
        paths = self._drop_paths(event)
        if not paths:
            event.ignore()
            return
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        self.files.emit(paths)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(event)


class Window(QMainWindow):
    def __init__(self, settings=None):
        super().__init__()
        self.setWindowTitle("RasterReady")
        self.resize(1040, 900)
        self.setMinimumSize(900, 700)
        self.settings = (
            settings if settings is not None else QSettings("ExtrusionTherapy", "RasterReady")
        )
        self.worker = None
        self.paths = []
        self.folder = None
        self.successes = 0
        self.done = 0
        body = QWidget()
        body.setObjectName("body")
        self.setCentralWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = QWidget()
        header.setObjectName("header")
        top = QHBoxLayout(header)
        top.setContentsMargins(28, 22, 28, 22)
        title = QLabel('Raster<span style="color:#df101b">Ready</span>')
        title.setObjectName("wordmark")
        top.addWidget(title)
        top.addStretch()
        self.appearance = QComboBox()
        self.appearance.setObjectName("theme")
        self.appearance.addItems(["Follow system", "Light", "Dark"])
        self.appearance.setAccessibleName("Appearance")
        self.appearance.setToolTip("Choose light, dark, or follow the system appearance")
        self.appearance.setCurrentIndex(
            {"system": 0, "light": 1, "dark": 2}.get(
                str(self.settings.value("appearance", "system")), 0
            )
        )
        top.addWidget(self.appearance)
        file_menu = self.menuBar().addMenu("File")
        self.choose_files_action = file_menu.addAction("Choose images…")
        self.choose_files_action.setShortcut("Ctrl+O")
        self.choose_files_action.triggered.connect(self.choose)
        view_menu = self.menuBar().addMenu("View")
        self.choose_preset_action = view_menu.addAction("Choose size preset…")
        self.choose_preset_action.setShortcut("Ctrl+Shift+P")
        self.choose_preset_action.triggered.connect(self.choose_preset)
        results_action = view_menu.addAction("Image results")
        results_action.setShortcut("Ctrl+Shift+R")
        results_action.triggered.connect(self.focus_results)
        appearance_menu = view_menu.addMenu("Appearance")
        self.appearance_actions = []
        group = QActionGroup(self)
        group.setExclusive(True)
        for index, (label, shortcut) in enumerate(
            (("Follow system", "Ctrl+Shift+0"), ("Light", "Ctrl+Shift+L"), ("Dark", "Ctrl+Shift+D"))
        ):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setShortcut(shortcut)
            group.addAction(action)
            appearance_menu.addAction(action)
            action.triggered.connect(lambda _checked, i=index: self.appearance.setCurrentIndex(i))
            self.appearance_actions.append(action)
        help_menu = self.menuBar().addMenu("Help")
        self.check_updates = help_menu.addAction("Check for Updates…")
        self.automatic_updates = help_menu.addAction("Check automatically every week")
        self.automatic_updates.setCheckable(True)
        self.automatic_updates.setChecked(self.settings.value("updates/automatic", True, type=bool))
        self.automatic_updates.toggled.connect(
            lambda enabled: self.settings.setValue("updates/automatic", enabled)
        )
        help_menu.addSeparator()
        help_menu.addAction("Third-party notices…", self.open_notices)
        layout.addWidget(header)
        self.update_banner = QWidget()
        banner = QHBoxLayout(self.update_banner)
        banner.setContentsMargins(28, 10, 28, 10)
        self.update_label = QLabel()
        self.update_label.setWordWrap(True)
        banner.addWidget(self.update_label, 1)
        self.update_link = QPushButton("View update")
        self.update_dismiss = QPushButton("Dismiss")
        banner.addWidget(self.update_link)
        banner.addWidget(self.update_dismiss)
        self.update_link.clicked.connect(self.open_update)
        self.update_dismiss.clicked.connect(self.dismiss_update)
        layout.addWidget(self.update_banner)
        self.update_banner.hide()
        self.available_update = None
        content = QHBoxLayout()
        content.setSpacing(0)
        content.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(content, 1)
        setup = QWidget()
        setup.setObjectName("setup")
        setup_layout = QVBoxLayout(setup)
        setup_layout.setContentsMargins(26, 28, 26, 26)
        setup_layout.setSpacing(10)
        setup_layout.addWidget(QLabel("Project name"))
        self.project = QLineEdit()
        self.project.setPlaceholderText("Name your project")
        self.project.setMaxLength(100)
        self.project.setAccessibleName("Project name")
        setup_layout.addWidget(self.project)
        setup_layout.addSpacing(15)
        setup_layout.addWidget(QLabel("Size preset"))
        self.preset = QComboBox()
        self.preset.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.preset.setMinimumContentsLength(10)
        self.preset.setMinimumWidth(0)
        for preset in PRESETS:
            self.preset.addItem(preset.label)
        self.preset.setCurrentIndex(2)
        self.preset.setAccessibleName("Size preset")
        setup_layout.addWidget(self.preset)
        self.custom = QWidget()
        row = QFormLayout(self.custom)
        row.setContentsMargins(0, 0, 0, 0)
        self.width = QSpinBox()
        self.width.setRange(1, 20000)
        self.width.setValue(1920)
        self.width.setAccessibleName("Custom width in pixels")
        self.height = QSpinBox()
        self.height.setRange(0, 20000)
        self.height.setSpecialValueText("Proportional")
        self.height.setAccessibleName("Custom height in pixels; zero means proportional")
        self.mode = QComboBox()
        self.mode.addItems(["Fit", "Crop", "White padding"])
        self.mode.setAccessibleName("Custom sizing mode")
        row.addRow("Width", self.width)
        row.addRow("Height", self.height)
        row.addRow("Sizing", self.mode)
        setup_layout.addWidget(self.custom)
        self.custom.setVisible(False)
        self.preset.currentIndexChanged.connect(
            lambda index: self.custom.setVisible(PRESETS[index].size is None)
        )
        self.guidance = QLabel()
        self.guidance.setWordWrap(True)
        self.guidance.setObjectName("guidance")
        setup_layout.addWidget(self.guidance)
        self.guide = QPushButton("Platform image guidance")
        self.guide.setObjectName("guide")
        self.guide.clicked.connect(self.open_guidance)
        setup_layout.addWidget(self.guide)
        self.preset.currentIndexChanged.connect(self.update_guidance)
        self.update_guidance()
        self.enlarge = QCheckBox("Allow enlargement")
        self.enlarge.setToolTip("Smaller images keep their size unless enlargement is enabled.")
        setup_layout.addWidget(self.enlarge)
        setup_layout.addSpacing(20)
        save_label = QLabel("Save to")
        save_label.setObjectName("muted")
        setup_layout.addWidget(save_label)
        self.location = QLabel("Downloads / project name")
        self.location.setTextFormat(Qt.TextFormat.PlainText)
        self.location.setWordWrap(True)
        self.location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        setup_layout.addWidget(self.location)
        privacy = QLabel("PNG output\nEmbedded metadata removed\nOriginals preserved")
        privacy.setObjectName("guidance")
        setup_layout.addSpacing(18)
        setup_layout.addWidget(privacy)
        setup_layout.addStretch()
        setup_scroll = QScrollArea()
        setup_scroll.setObjectName("setupScroll")
        setup_scroll.setWidgetResizable(True)
        setup_scroll.setWidget(setup)
        setup_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        setup_scroll.setFixedWidth(310)
        content.addWidget(setup_scroll)
        workspace = QWidget()
        workspace.setObjectName("workspace")
        right = QVBoxLayout(workspace)
        right.setContentsMargins(26, 26, 26, 22)
        right.setSpacing(18)
        content.addWidget(workspace, 1)
        self.drop = DropArea()
        self.drop.files.connect(self.accept_files)
        self.drop.clicked.connect(self.choose)
        right.addWidget(self.drop, 3)
        self.table = ResultsTable(0, 3)
        self.table.setHorizontalHeaderLabels(["Image", "Dimensions", "Result"])
        self.table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 110)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAccessibleName("Image conversion results")
        self.table.setAccessibleDescription(
            "Select a result and press Enter or double-click for its full details."
        )
        self.table.setToolTip(
            "Select a result and press Enter or double-click for its full details."
        )
        self.table.itemActivated.connect(self.show_details)
        self.table.setMinimumHeight(130)
        right.addWidget(self.table, 2)
        self.status = QLabel("Enter a project name, then drop your images.")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.status.setObjectName("summary")
        actions = QHBoxLayout()
        self.export = QPushButton("Prepare selected images")
        self.export.setEnabled(False)
        self.export.setVisible(False)
        self.export.clicked.connect(self.start)
        self.stop = QPushButton("Cancel remaining")
        self.stop.setEnabled(False)
        self.stop.setVisible(False)
        self.stop.clicked.connect(self.cancel)
        self.open = QPushButton("Open project folder")
        self.open.setEnabled(False)
        self.open.setProperty("primary", True)
        self.open.setMinimumHeight(42)
        self.open.setIconSize(QSize(20, 20))
        self.open.clicked.connect(self.open_folder)
        actions.addStretch()
        for button in (self.export, self.stop, self.open):
            actions.addWidget(button)
        footer = QVBoxLayout()
        footer.setSpacing(12)
        footer.addWidget(self.status)
        footer.addLayout(actions)
        right.addLayout(footer)
        self.project.textChanged.connect(self.update_destination)
        self.appearance.currentIndexChanged.connect(self.update_theme)
        QApplication.instance().styleHints().colorSchemeChanged.connect(
            lambda _: self.update_theme(persist=False)
        )
        self.update_theme(persist=False)
        self.project.setFocus()
        self.updater = UpdateChecker(self.settings, self)
        self.updater.result.connect(self.update_result)
        self.updater.busy.connect(lambda busy: self.check_updates.setEnabled(not busy))
        self.check_updates.triggered.connect(self.manual_update_check)

    def manual_update_check(self):
        self.statusBar().showMessage("Checking for updates…")
        self.updater.check(manual=True)

    def update_result(self, result, manual):
        if result.status == "newer":
            self.available_update = result
            self.update_label.setText(f"RasterReady {result.version} is available.")
            self.update_banner.show()
            self.statusBar().clearMessage()
        elif manual:
            messages = {
                "current": f"RasterReady {__version__}: no newer compatible stable release was found.",
                "unpublished": "No compatible stable release has been published yet.",
                "unknown": "Could not determine update status. Check your connection and try again later.",
            }
            self.statusBar().showMessage(messages[result.status])

    def open_update(self):
        if self.available_update:
            QDesktopServices.openUrl(QUrl(self.available_update.url))

    def dismiss_update(self):
        if self.available_update:
            self.settings.setValue("updates/dismissed", self.available_update.version)
        self.update_banner.hide()

    def choose(self):
        if self.worker is not None:
            return
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose images",
            "",
            "Images and Sony RAW (*.jpg *.jpeg *.png *.heic *.heif *.avif *.webp *.tif *.tiff *.bmp *.gif *.ico *.ppm *.pgm *.tga *.arw *.ARW *.srf *.SRF *.sr2 *.SR2);;All files (*)",
        )
        if files:
            self.accept_files([Path(path) for path in files])

    def choose_preset(self):
        if self.worker is None:
            self.preset.setFocus(Qt.FocusReason.ShortcutFocusReason)
            self.preset.showPopup()

    def focus_results(self):
        self.table.setFocus(Qt.FocusReason.ShortcutFocusReason)
        if self.table.rowCount():
            self.table.setCurrentCell(0, 0)
            self.table.selectRow(0)

    def accept_files(self, paths):
        if self.worker is not None:
            return
        self.paths = paths
        self.table.setRowCount(len(paths))
        for i, path in enumerate(paths):
            self.table.setItem(i, 0, QTableWidgetItem(path.name))
            self.table.item(i, 0).setToolTip(f"<qt>{escape(path.name)}</qt>")
            self.table.setItem(i, 1, QTableWidgetItem("—"))
            self.table.setItem(i, 2, QTableWidgetItem("Waiting"))
        self.export.setEnabled(bool(paths))
        if self.project.text().strip():
            self.start()
        else:
            self.status.setText("Enter a project name, then choose Prepare selected images.")
            self.export.setVisible(True)
            self.project.setFocus()

    def open_notices(self):
        if getattr(sys, "frozen", False):
            directory = Path(sys._MEIPASS) / "third_party_notices"
        else:
            directory = Path(__file__).resolve().parents[1] / "third_party"
        NoticesDialog(directory, self).exec()

    def start(self):
        if not self.paths or self.worker is not None:
            return
        try:
            downloads = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.DownloadLocation
            )
            if not downloads:
                raise PreparationError("The system Downloads folder could not be located.")
            Path(downloads).mkdir(parents=True, exist_ok=True)
            preset = PRESETS[self.preset.currentIndex()]
            size = preset.size
            if size is None:
                size = Size(
                    self.width.value(),
                    self.height.value() or None,
                    ["fit", "crop", "pad"][self.mode.currentIndex()],
                )
            size.validate()
            self.folder = project_folder(Path(downloads), self.project.text())
        except (PreparationError, OSError) as exc:
            self.status.setText(str(exc))
            self.export.setVisible(True)
            return
        self.location.setText("Downloads / " + self.folder.name)
        self.location.setToolTip(str(self.folder))
        self.open.setEnabled(True)
        self.successes = self.done = 0
        for i in range(len(self.paths)):
            self.table.item(i, 1).setText("—")
            self.table.item(i, 2).setText("Waiting")
        self.worker = Batch(
            tuple(self.paths), self.folder, size, self.enlarge.isChecked(), preset, self
        )
        self.worker.completed.connect(self.completed)
        self.worker.finished.connect(self.finished)
        self.set_busy(True)
        self.status.setText(f"Preparing {len(self.paths)} image(s)…")
        self.worker.start()

    def show_details(self, item):
        details = self.table.item(item.row(), 2).data(Qt.ItemDataRole.UserRole)
        if not details:
            return
        message = QMessageBox(self)
        message.setWindowTitle("Image details")
        message.setTextFormat(Qt.TextFormat.PlainText)
        message.setText(details)
        message.setStandardButtons(QMessageBox.StandardButton.Ok)
        message.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        message.exec()

    def completed(self, index, result, error):
        self.done += 1
        if result:
            self.successes += 1
            text = f"{result.output.name} · {result.width} × {result.height}"
            if result.notes:
                text += " · " + " ".join(result.notes)
            self.table.item(index, 1).setText(f"{result.width} × {result.height}")
            review = any(not n.startswith("RAW developed") for n in result.notes)
            self.table.item(index, 2).setText("Review" if review else "Ready")
            self.table.item(index, 2).setIcon(
                theme.icon(
                    "alert-circle" if review else "circle-check",
                    theme.PALETTES[self.current_theme]["warning" if review else "success"],
                )
            )
        else:
            text = error
            self.table.item(index, 2).setText("Cancelled" if error == "Cancelled" else "Failed")
            self.table.item(index, 2).setIcon(
                theme.icon("alert-circle", theme.PALETTES[self.current_theme]["accent"])
            )
        self.table.item(index, 2).setData(Qt.ItemDataRole.UserRole, text)
        for column in (0, 1, 2):
            self.table.item(index, column).setToolTip(f"<qt>{escape(text)}</qt>")
            self.table.item(index, column).setData(Qt.ItemDataRole.AccessibleDescriptionRole, text)
        self.status.setText(
            f"Processed {self.done} of {len(self.paths)} • {self.successes} PNG(s) saved"
        )

    def set_busy(self, busy):
        self.choose_files_action.setEnabled(not busy)
        self.choose_preset_action.setEnabled(not busy)
        for widget in (
            self.project,
            self.preset,
            self.custom,
            self.enlarge,
            self.drop,
            self.export,
        ):
            widget.setEnabled(not busy)
        self.stop.setEnabled(busy)
        self.stop.setVisible(busy)
        self.export.setVisible(False)

    def finished(self):
        worker, self.worker = self.worker, None
        if worker:
            worker.deleteLater()
        self.set_busy(False)
        failures = len(self.paths) - self.successes
        self.status.setText(
            f"{self.successes} PNG(s) ready"
            + (f" · {failures} failed or cancelled" if failures else "")
        )

    def update_destination(self):
        name = self.project.text().strip()
        self.location.setText("Downloads / " + (name or "project name"))
        self.open.setEnabled(self.folder is not None and self.folder.name == name)

    def update_theme(self, *_args, persist=True):
        choice = ("system", "light", "dark")[self.appearance.currentIndex()]
        self.appearance_actions[self.appearance.currentIndex()].setChecked(True)
        if persist:
            self.settings.setValue("appearance", choice)
        name = choice
        if name == "system":
            name = (
                "dark"
                if QApplication.instance().styleHints().colorScheme() == Qt.ColorScheme.Dark
                else "light"
            )
        theme.apply(self, name)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 2)
            if item and item.text() in {"Ready", "Review", "Failed", "Cancelled"}:
                state = item.text()
                key = (
                    "success" if state == "Ready" else "warning" if state == "Review" else "accent"
                )
                item.setIcon(
                    theme.icon(
                        "circle-check" if state == "Ready" else "alert-circle",
                        theme.PALETTES[name][key],
                    )
                )

    def cancel(self):
        if self.worker:
            self.worker.cancel.set()
            self.stop.setEnabled(False)
            self.status.setText("Finishing the current image; remaining images will be cancelled.")

    def open_folder(self):
        if self.folder and (
            not self.folder.is_dir()
            or not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.folder)))
        ):
            self.status.setText(
                "The project folder could not be opened. It may have been moved or removed."
            )

    def update_guidance(self):
        preset = PRESETS[self.preset.currentIndex()]
        self.guidance.setText(preset.guidance)
        self.guide.setVisible(bool(preset.source))

    def open_guidance(self):
        source = PRESETS[self.preset.currentIndex()].source
        if source:
            QDesktopServices.openUrl(QUrl(source))

    def closeEvent(self, event):
        if self.worker is not None:
            self.cancel()
            self.status.setText(
                "Finishing the current image. Close the window again when the batch stops."
            )
            event.ignore()
        else:
            self.updater.stop()
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Consistent custom controls across macOS, Windows, and Linux.
    app.setApplicationName("RasterReady")
    app.setOrganizationName("Extrusion Therapy")
    app.setWindowIcon(QIcon(str(Path(__file__).parent / "assets/product-icon.png")))
    window = Window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

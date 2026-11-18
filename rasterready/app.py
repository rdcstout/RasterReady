"""Photo editor and batch export. Image processing runs off the GUI thread."""

import sys
from dataclasses import replace
from html import escape
from pathlib import Path
from threading import Event

from PySide6.QtCore import QSettings, QSize, QStandardPaths, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import __version__, theme
from .core import PreparationError, prepare, project_folder
from .notices import NoticesDialog
from .update_ui import UpdateChecker
from .workbench import IMAGE_FILTER, ExportOptions, ExportRequest, Workbench


class Batch(QThread):
    completed = Signal(int, object, str)

    def __init__(self, request, folder, parent=None):
        super().__init__(parent)
        self.request = request
        self.folder = folder
        self.cancel = Event()

    def run(self):
        request = self.request
        for index, (path, edit, crop) in enumerate(
            zip(request.paths, request.adjustments, request.crops, strict=True)
        ):
            if self.cancel.is_set():
                self.completed.emit(index, None, "Cancelled")
                continue
            try:
                result = prepare(
                    path,
                    self.folder,
                    crop.size,
                    crop.allow_enlargement,
                    crop.flatten,
                    adjustments=edit,
                    output_format=request.format,
                    quality=request.quality,
                    output_name=request.name,
                    sequence=index + 1,
                    crop_center=crop.center,
                )
                self.completed.emit(index, replace(result, notes=crop.preset.review(result)), "")
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
        title = QLabel("Drop images here to start editing")
        title.setObjectName("dropTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        choose = QPushButton("Browse images")
        choose.setProperty("primary", True)
        choose.setMinimumWidth(155)
        choose.setMinimumHeight(42)
        choose.clicked.connect(self.clicked.emit)
        layout.addWidget(choose, 0, Qt.AlignmentFlag.AlignHCenter)
        hint = QLabel("JPEG · PNG · TIFF · WEBP · HEIC · AVIF · Sony RAW")
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
        self.resize(1200, 800)
        self.setMinimumSize(800, 570)
        self.settings = (
            settings if settings is not None else QSettings("ExtrusionTherapy", "RasterReady")
        )
        self.worker = None
        self.paths = []
        self.export_format = "PNG"
        self.quality = 95
        self.export_scope = False
        self.export_paths = ()
        self.folder = None
        self.successes = 0
        self.done = 0
        self.batch_format = "PNG"
        body = QWidget()
        body.setObjectName("body")
        self.setCentralWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = QWidget()
        header.setObjectName("header")
        top = QHBoxLayout(header)
        top.setContentsMargins(20, 11, 20, 11)
        title = QLabel('Raster<span style="color:#df101b">Ready</span>')
        title.setObjectName("wordmark")
        top.addWidget(title)
        self.browse = QPushButton("Open images")
        self.browse.clicked.connect(self.choose)
        top.addWidget(self.browse)
        top.addStretch()
        self.appearance = QComboBox()
        self.appearance.setObjectName("theme")
        self.appearance.addItems(["Follow system", "Light", "Dark"])
        self.appearance.setAccessibleName("Appearance")
        self.appearance.setToolTip("Choose light, dark, or follow the system appearance")
        self.appearance.setCurrentIndex(
            {"system": 0, "light": 1, "dark": 2}.get(
                str(self.settings.value("appearance", "dark")), 2
            )
        )
        top.addWidget(self.appearance)
        self.export = QPushButton("Export images…")
        self.export.setProperty("primary", True)
        self.export.setEnabled(False)
        self.export.clicked.connect(self.open_export)
        top.addWidget(self.export)
        file_menu = self.menuBar().addMenu("File")
        self.choose_files_action = file_menu.addAction("Choose images…")
        self.choose_files_action.setShortcut("Ctrl+O")
        self.choose_files_action.triggered.connect(self.choose)
        self.export_action = file_menu.addAction("Export images…")
        self.export_action.setShortcut("Ctrl+Shift+E")
        self.export_action.setEnabled(False)
        self.export_action.triggered.connect(self.open_export)
        view_menu = self.menuBar().addMenu("View")
        self.choose_preset_action = view_menu.addAction("Crop presets…")
        self.choose_preset_action.setShortcut("Ctrl+Shift+P")
        self.choose_preset_action.setEnabled(False)
        self.choose_preset_action.triggered.connect(self.open_crop)
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
            action.setData(index)
            self.appearance_actions.append(action)
        group.triggered.connect(self.set_appearance)
        help_menu = self.menuBar().addMenu("Help")
        self.check_updates = help_menu.addAction("Check for Updates…")
        self.automatic_updates = help_menu.addAction("Check automatically every week")
        self.automatic_updates.setCheckable(True)
        self.automatic_updates.setChecked(self.settings.value("updates/automatic", True, type=bool))
        self.automatic_updates.toggled.connect(self.save_automatic_updates)
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
        self.drop = DropArea()
        self.drop.files.connect(self.accept_files)
        self.drop.clicked.connect(self.choose)
        self.editor = Workbench(self, self.drop)
        layout.addWidget(self.editor, 1)
        self.setAcceptDrops(True)
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
        self.table.setFixedHeight(155)
        self.table.hide()
        layout.addWidget(self.table)
        self.status = QLabel("Open or drop images to get started.")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.status.setObjectName("summary")
        self.results = QPushButton("Export results")
        self.results.setEnabled(False)
        self.results.clicked.connect(self.toggle_results)
        self.stop = QPushButton("Cancel remaining")
        self.stop.hide()
        self.stop.clicked.connect(self.cancel)
        self.open = QPushButton("Open export folder")
        self.open.setEnabled(False)
        self.open.setIconSize(QSize(18, 18))
        self.open.clicked.connect(self.open_folder)
        footer = QWidget()
        footer.setObjectName("exportStatus")
        actions = QHBoxLayout(footer)
        actions.setContentsMargins(18, 8, 18, 8)
        actions.addWidget(self.status, 1)
        for button in (self.results, self.stop, self.open):
            actions.addWidget(button)
        layout.addWidget(footer)
        self.appearance.currentIndexChanged.connect(self.update_theme)
        QApplication.instance().styleHints().colorSchemeChanged.connect(self.system_theme_changed)
        self.update_theme(persist=False)
        self.browse.setFocus()
        self.updater = UpdateChecker(self.settings, self)
        self.updater.result.connect(self.update_result)
        self.updater.busy.connect(self.check_updates.setDisabled)
        self.check_updates.triggered.connect(self.manual_update_check)

    def set_appearance(self, action):
        self.appearance.setCurrentIndex(action.data())

    def save_automatic_updates(self, enabled):
        self.settings.setValue("updates/automatic", enabled)

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
            IMAGE_FILTER,
        )
        if files:
            self.accept_files([Path(path) for path in files])

    def dragEnterEvent(self, event):
        if self.worker is None and self.drop._drop_paths(event):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if self.worker is None and (paths := self.drop._drop_paths(event)):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            self.accept_files(paths)
        else:
            event.ignore()

    def toggle_results(self):
        self.table.setVisible(self.table.isHidden())

    def focus_results(self):
        if self.table.rowCount():
            self.table.show()
            self.table.setFocus(Qt.FocusReason.ShortcutFocusReason)
            self.table.setCurrentCell(0, 0)
            self.table.selectRow(0)

    def accept_files(self, paths):
        if self.worker is not None:
            return
        self.editor.set_paths([*self.paths, *paths])
        self.paths = self.editor.paths
        self.set_busy(False)
        self.status.setText(f"{len(self.paths)} image(s) in the queue")

    def set_results(self, paths):
        self.table.setRowCount(len(paths))
        for i, path in enumerate(paths):
            self.table.setItem(i, 0, QTableWidgetItem(path.name))
            self.table.item(i, 0).setToolTip(f"<qt>{escape(str(path))}</qt>")
            self.table.setItem(i, 1, QTableWidgetItem("—"))
            self.table.setItem(i, 2, QTableWidgetItem("Waiting"))

    def open_crop(self):
        if self.worker is None:
            self.editor.open_crop()

    def open_export(self):
        if not self.paths or self.worker is not None:
            return
        dialog = ExportOptions(
            self,
            self.paths,
            self.editor.photos.currentRow(),
            self.editor.edits,
            self.editor.crops,
            output_format=self.export_format,
            quality=self.quality,
            selected_only=self.export_scope,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.start(dialog.request)
        dialog.deleteLater()

    def open_notices(self):
        if getattr(sys, "frozen", False):
            directory = Path(sys._MEIPASS) / "third_party_notices"
        else:
            directory = Path(__file__).resolve().parents[1] / "third_party"
        NoticesDialog(directory, self).exec()

    def start(self, request: ExportRequest):
        if not request.paths or self.worker is not None:
            return
        self.export_format = request.format
        self.export_scope = len(request.paths) == 1 and len(self.paths) > 1
        self.quality = request.quality
        try:
            downloads = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.DownloadLocation
            )
            if not downloads:
                raise PreparationError("The system Downloads folder could not be located.")
            Path(downloads).mkdir(parents=True, exist_ok=True)
            for crop in request.crops:
                if crop.size is not None:
                    crop.size.validate()
            folder = project_folder(Path(downloads), request.name)
        except (PreparationError, OSError) as exc:
            self.status.setText(str(exc))
            return
        self.folder = folder
        self.open.setEnabled(True)
        self.open.setToolTip(str(self.folder))
        self.successes = self.done = 0
        self.export_paths = request.paths
        self.set_results(self.export_paths)
        self.results.setEnabled(True)
        self.batch_format = request.format
        self.worker = Batch(request, self.folder, self)
        self.worker.completed.connect(self.completed)
        self.worker.finished.connect(self.finished)
        self.set_busy(True)
        self.status.setText(f"Exporting {len(self.export_paths)} image(s)…")
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
            f"Processed {self.done} of {len(self.export_paths)} • {self.successes} {self.batch_format}(s) saved"
        )

    def set_busy(self, busy):
        self.choose_files_action.setEnabled(not busy)
        self.browse.setEnabled(not busy)
        can_export = bool(self.paths) and not busy
        self.export.setEnabled(can_export)
        self.export_action.setEnabled(can_export)
        self.choose_preset_action.setEnabled(can_export)
        self.drop.setEnabled(not busy)
        self.stop.setEnabled(busy)
        self.stop.setVisible(busy)

    def finished(self):
        worker, self.worker = self.worker, None
        if worker:
            worker.deleteLater()
        self.set_busy(False)
        failures = len(self.export_paths) - self.successes
        if failures:
            self.table.show()
        self.status.setText(
            f"{self.successes} {self.batch_format}(s) saved to Downloads / {self.folder.name}"
            + (f" · {failures} failed or cancelled" if failures else "")
        )

    def system_theme_changed(self, _scheme):
        self.update_theme(persist=False)

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

    def closeEvent(self, event):
        if self.worker is not None:
            self.cancel()
            self.status.setText(
                "Finishing the current image. Close the window again when the batch stops."
            )
            event.ignore()
        else:
            self.editor.stop_preview()
            self.updater.stop()
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Consistent custom controls across macOS, Windows, and Linux.
    app.setApplicationName("RasterReady")
    app.setOrganizationName("Extrusion Therapy")
    app.setWindowIcon(QIcon(str(Path(__file__).parent / "assets/product-icon.png")))
    window = Window()
    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

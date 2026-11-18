"""Photo Workbench preview and export controls inside RasterReady."""

from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, QRect, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .core import PreparationError, Size, load_pixels, validate_project
from .enhance import Adjustments
from .presets import PRESETS, Preset

IMAGE_FILTER = (
    "Images and Sony RAW (*.jpg *.jpeg *.png *.heic *.heif *.avif *.webp *.tif *.tiff "
    "*.bmp *.gif *.ico *.ppm *.pgm *.tga *.arw *.ARW *.srf *.SRF *.sr2 *.SR2);;All files (*)"
)
AS_ENHANCED = Preset("enhanced", "As enhanced", None)
CROPS = (None, (1, 1), (4, 3), (16, 9))


@dataclass(frozen=True)
class ExportRequest:
    paths: tuple[Path, ...]
    project: str
    preset: Preset
    size: Size | None
    enlarge: bool
    flatten: bool
    format: str
    quality: int
    adjustments: Adjustments


class PreviewSignals(QObject):
    finished = Signal(int, object, object, object, str)


class PreviewTask(QRunnable):
    def __init__(self, generation, path, settings, cached):
        super().__init__()
        self.generation = generation
        self.path = path
        self.settings = settings
        self.cached = cached
        self.signals = PreviewSignals()

    def run(self):
        try:
            source = self.cached
            if source is None:
                source, _ = load_pixels(self.path)
                source.thumbnail((1100, 800), Image.Resampling.LANCZOS)
            enhanced = self.settings.apply(source, preview=True)
            self.signals.finished.emit(
                self.generation, source, _qimage(source), _qimage(enhanced), ""
            )
        except (PreparationError, OSError, ValueError) as exc:
            self.signals.finished.emit(self.generation, None, None, None, str(exc))
        except Exception:
            self.signals.finished.emit(
                self.generation, None, None, None, "Could not render the preview."
            )


def _qimage(image):
    rgba = image.convert("RGBA")
    return QImage(rgba.tobytes(), rgba.width, rgba.height, QImage.Format.Format_RGBA8888).copy()


class SplitPreview(QWidget):
    def __init__(self):
        super().__init__()
        self.before = self.after = None
        self.position = 50
        self.setMinimumSize(340, 290)
        self.setAccessibleName("Before and after photo preview")

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().base())
        if self.before is None or self.after is None:
            return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        split = self.width() * self.position // 100
        for image, clip in (
            (self.before, QRect(0, 0, split, self.height())),
            (self.after, QRect(split, 0, self.width() - split, self.height())),
        ):
            size = image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            area = QRect(
                self.rect().center().x() - size.width() // 2,
                self.rect().center().y() - size.height() // 2,
                size.width(),
                size.height(),
            )
            painter.setClipRect(clip)
            painter.drawImage(area, image)
        painter.setClipping(False)
        if 0 < split < self.width():
            painter.setPen(self.palette().highlight().color())
            painter.drawLine(split, 0, split, self.height())


def _strength(minimum, maximum, value=0):
    spin = QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setValue(value)
    return spin


class ExportOptions(QDialog):
    def __init__(self, parent, project, paths, current, adjustments, preset_index, enlarge, custom):
        super().__init__(parent)
        self.setWindowTitle("Export settings")
        self.setMinimumWidth(490)
        self.request = None
        self.paths, self.current, self.adjustments = tuple(paths), current, adjustments
        form = QFormLayout(self)
        self.project = QLineEdit(project)
        self.project.setMaxLength(100)
        form.addRow("Project name", self.project)
        self.preset = QComboBox()
        self.presets = (AS_ENHANCED, *PRESETS)
        for item in self.presets:
            self.preset.addItem(item.label)
        form.addRow("Size preset", self.preset)
        self.custom = QWidget()
        sizing = QFormLayout(self.custom)
        sizing.setContentsMargins(0, 0, 0, 0)
        self.width = _strength(1, 20000, custom.width)
        self.height = _strength(0, 20000, custom.height or 0)
        self.height.setSpecialValueText("Proportional")
        self.mode = QComboBox()
        self.mode.addItems(["Fit", "Center crop", "White padding"])
        self.mode.setCurrentIndex(["fit", "crop", "pad"].index(custom.mode))
        sizing.addRow("Width", self.width)
        sizing.addRow("Height", self.height)
        sizing.addRow("Sizing", self.mode)
        form.addRow(self.custom)
        self.enlarge = QCheckBox("Allow enlargement")
        self.enlarge.setChecked(enlarge)
        form.addRow(self.enlarge)
        self.flatten = QCheckBox("Flatten transparency to white")
        form.addRow(self.flatten)
        self.format = QComboBox()
        self.format.addItems(["PNG", "JPEG", "TIFF"])
        form.addRow("Format", self.format)
        self.quality = _strength(1, 100, 95)
        self.quality_label = QLabel("JPEG quality")
        self.quality_label.setBuddy(self.quality)
        form.addRow(self.quality_label, self.quality)
        self.format.currentTextChanged.connect(self.update_quality)
        self.update_quality(self.format.currentText())
        self.scope = QComboBox()
        self.scope.addItems([f"All {len(paths)} images", "Selected image"])
        form.addRow("Export", self.scope)
        form.addRow(QLabel("Saves to Downloads / project name. Originals are preserved."))
        self.message = QLabel()
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.message.setWordWrap(True)
        form.addRow(self.message)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Export")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.preset.currentIndexChanged.connect(self.update_preset)
        self.mode.currentIndexChanged.connect(self.update_padding)
        self.preset.setCurrentIndex(preset_index + 1)
        self.update_preset(self.preset.currentIndex())

    def update_quality(self, text):
        self.quality.setVisible(text == "JPEG")
        self.quality_label.setVisible(text == "JPEG")

    def update_preset(self, index):
        self.custom.setVisible(self.presets[index].key == "custom")
        self.enlarge.setEnabled(index != 0)
        self.flatten.setChecked(self.presets[index].flatten)
        self.update_padding()

    def update_padding(self):
        preset = self.presets[self.preset.currentIndex()]
        padding = (preset.size is not None and preset.size.mode == "pad") or (
            preset.key == "custom" and self.mode.currentIndex() == 2
        )
        self.flatten.setEnabled(not padding)
        if padding:
            self.flatten.setChecked(True)

    def accept(self):
        preset = self.presets[self.preset.currentIndex()]
        size = preset.size
        if preset.key == "custom":
            size = Size(
                self.width.value(),
                self.height.value() or None,
                ["fit", "crop", "pad"][self.mode.currentIndex()],
            )
        try:
            project = validate_project(self.project.text())
            if size is not None:
                size.validate()
        except PreparationError as exc:
            self.message.setText(str(exc))
            return
        paths = self.paths if self.scope.currentIndex() == 0 else (self.paths[self.current],)
        self.request = ExportRequest(
            paths,
            project,
            preset,
            size,
            self.enlarge.isChecked(),
            self.flatten.isChecked(),
            self.format.currentText(),
            self.quality.value(),
            self.adjustments,
        )
        super().accept()


class Workbench(QDialog):
    def __init__(self, parent, paths, project, preset_index, enlarge, custom):
        super().__init__(parent)
        self.setWindowTitle("RasterReady — Enhance & Export")
        self.resize(940, 660)
        self.paths = []
        self.project, self.preset_index, self.enlarge, self.custom = (
            project,
            preset_index,
            enlarge,
            custom,
        )
        self.request = None
        self.generation = 0
        self.active_path = None
        self.cached = None
        self.running = False
        self.timer = QTimer(self, singleShot=True, interval=150)
        self.timer.timeout.connect(self.render)

        root = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        choose = QPushButton("Choose images…")
        choose.clicked.connect(self.choose)
        toolbar.addWidget(choose)
        self.photo = QComboBox()
        self.photo.setAccessibleName("Preview image")
        self.photo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.photo.setMinimumContentsLength(18)
        self.photo.currentIndexChanged.connect(self.queue_preview)
        toolbar.addWidget(self.photo, 1)
        self.export = QPushButton("Export…")
        self.export.setProperty("primary", True)
        self.export.clicked.connect(self.open_export)
        toolbar.addWidget(self.export)
        root.addLayout(toolbar)

        center = QHBoxLayout()
        self.preview = SplitPreview()
        center.addWidget(self.preview, 1)
        panel = QFormLayout()
        self.noise = _strength(0, 100)
        self.sharp = _strength(0, 100)
        self.exposure = QDoubleSpinBox()
        self.exposure.setRange(-2, 2)
        self.exposure.setSingleStep(0.1)
        self.warmth = _strength(-100, 100)
        self.rotation = QComboBox()
        self.rotation.addItems(["0°", "90°", "180°", "270°"])
        self.crop = QComboBox()
        self.crop.addItems(["Original", "1:1", "4:3", "16:9"])
        self.scale = QComboBox()
        self.scale.addItems(["1×", "2×", "4×", "6×"])
        for label, control in (
            ("Denoise", self.noise),
            ("Sharpen", self.sharp),
            ("Exposure", self.exposure),
            ("Warmth", self.warmth),
            ("Rotate clockwise", self.rotation),
            ("Crop", self.crop),
            ("Upscale", self.scale),
        ):
            panel.addRow(label, control)
            signal = (
                control.currentIndexChanged
                if isinstance(control, QComboBox)
                else control.valueChanged
            )
            signal.connect(self.queue_preview)
        auto = QPushButton("Auto adjust")
        auto.setToolTip("Apply a balanced denoise and sharpen preset.")
        auto.clicked.connect(self.auto_adjust)
        panel.addRow(auto)
        center.addLayout(panel)
        root.addLayout(center, 1)
        comparison = QHBoxLayout()
        comparison.addWidget(QLabel("Before"))
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setAccessibleName("Before and after split position")
        slider.setRange(0, 100)
        slider.setValue(50)
        slider.valueChanged.connect(self.set_split)
        comparison.addWidget(slider, 1)
        comparison.addWidget(QLabel("After"))
        root.addLayout(comparison)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.set_paths(paths)

    def set_paths(self, paths):
        self.paths = list(paths)
        self.photo.blockSignals(True)
        self.photo.clear()
        for path in self.paths:
            self.photo.addItem(path.name)
        self.photo.blockSignals(False)
        self.export.setEnabled(bool(self.paths))
        self.queue_preview()

    def choose(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Choose images", "", IMAGE_FILTER)
        if files:
            self.set_paths(Path(file) for file in files)

    def auto_adjust(self):
        self.noise.setValue(35)
        self.sharp.setValue(35)

    def adjustments(self):
        return Adjustments(
            noise=self.noise.value(),
            sharpness=self.sharp.value(),
            exposure=self.exposure.value(),
            warmth=self.warmth.value(),
            rotation=self.rotation.currentIndex(),
            crop=CROPS[self.crop.currentIndex()],
            scale=(1, 2, 4, 6)[self.scale.currentIndex()],
        )

    def set_split(self, value):
        self.preview.position = value
        self.preview.update()

    def queue_preview(self, *_):
        self.generation += 1
        path = self.paths[self.photo.currentIndex()] if self.paths else None
        if path != self.active_path:
            self.active_path = path
            self.cached = None
            self.preview.before = self.preview.after = None
            self.preview.update()
        self.status.setText("Preparing preview…" if path else "Choose images to start.")
        if path:
            self.timer.start()

    def render(self):
        if self.running or self.active_path is None:
            return
        self.running = True
        task = PreviewTask(self.generation, self.active_path, self.adjustments(), self.cached)
        task.signals.finished.connect(self.preview_ready, Qt.ConnectionType.QueuedConnection)
        QThreadPool.globalInstance().start(task)

    def preview_ready(self, generation, source, before, after, error):
        self.running = False
        if generation != self.generation:
            self.timer.start()
            return
        self.cached = source
        self.preview.before, self.preview.after = before, after
        self.preview.update()
        self.status.setText(
            error or "Adjustments apply to the images you export. Upscaling runs on export."
        )

    def open_export(self):
        dialog = ExportOptions(
            self,
            self.project,
            self.paths,
            self.photo.currentIndex(),
            self.adjustments(),
            self.preset_index,
            self.enlarge,
            self.custom,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.request = dialog.request
            self.accept()

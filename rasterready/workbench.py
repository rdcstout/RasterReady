"""Photo Workbench preview and export controls inside RasterReady."""

from dataclasses import dataclass
from html import escape
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, QRect, QRunnable, QSize, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .core import (
    PreparationError,
    Size,
    _resize,
    load_pixels,
    safe_output_name,
    validate_output_name,
)
from .enhance import Adjustments
from .presets import PRESETS, Preset

IMAGE_FILTER = (
    "Images and Sony RAW (*.jpg *.jpeg *.png *.heic *.heif *.avif *.webp *.tif *.tiff "
    "*.bmp *.gif *.ico *.ppm *.pgm *.tga *.arw *.ARW *.srf *.SRF *.sr2 *.SR2);;All files (*)"
)
AS_ENHANCED = Preset("enhanced", "Original sizing", None)
CROPS = (None, (1, 1), (4, 3), (16, 9))


@dataclass(frozen=True)
class CropSettings:
    preset: Preset = AS_ENHANCED
    custom: Size = Size(1920)
    enlarge: bool = False

    @property
    def size(self):
        return self.custom if self.preset.key == "custom" else self.preset.size

    @property
    def flatten(self):
        return self.preset.flatten or (self.size is not None and self.size.mode == "pad")


@dataclass(frozen=True)
class ExportRequest:
    paths: tuple[Path, ...]
    name: str
    format: str
    quality: int
    adjustments: tuple[Adjustments, ...]
    crops: tuple[CropSettings, ...]


class PreviewSignals(QObject):
    finished = Signal(int, object, object, object, str)


class PreviewTask(QRunnable):
    def __init__(self, generation, path, settings, crop, cached, signals):
        super().__init__()
        self.generation = generation
        self.path = path
        self.settings = settings
        self.crop = crop
        self.cached = cached
        self.signals = signals

    def run(self):
        try:
            if self.cached is None:
                source, _ = load_pixels(self.path)
                original = source.size
                source.thumbnail((1100, 800), Image.Resampling.LANCZOS)
            else:
                source, original = self.cached
            enhanced = self.settings.apply(source, preview=True)
            issue = ""
            if self.crop.size is not None:
                try:
                    self.crop.size.validate()
                    enhanced = self.resize_preview(source, original, enhanced)
                except PreparationError as exc:
                    issue = str(exc)
            if self.crop.flatten:
                flattened = Image.new("RGBA", enhanced.size, "white")
                flattened.alpha_composite(enhanced.convert("RGBA"))
                enhanced = flattened

            self.signals.finished.emit(
                self.generation, (source, original), _qimage(source), _qimage(enhanced), issue
            )
        except (PreparationError, OSError, ValueError) as exc:
            self.signals.finished.emit(self.generation, None, None, None, str(exc))
        except Exception:
            self.signals.finished.emit(
                self.generation, None, None, None, "Could not render the preview."
            )

    def resize_preview(self, thumbnail, original, image):
        size = self.crop.size
        factor = thumbnail.width / original[0] / self.settings.scale
        render_scale = min(factor, 1100 / size.width, 800 / (size.height or 1))
        if render_scale < factor:
            image = image.resize(
                tuple(max(1, round(n * render_scale / factor)) for n in image.size),
                Image.Resampling.LANCZOS,
            )
        bounds = Size(
            max(1, round(size.width * render_scale)),
            max(1, round(size.height * render_scale)) if size.height is not None else None,
            size.mode,
        )
        # Width-only and boxed fits never change framing. The size is applied
        # to the full-resolution pixels during export.
        if bounds.mode == "fit":
            return image
        return _resize(image, bounds, self.crop.enlarge)


def _qimage(image):
    rgba = image.convert("RGBA")
    return QImage(rgba.tobytes(), rgba.width, rgba.height, QImage.Format.Format_RGBA8888).copy()


class SplitPreview(QWidget):
    split_moved = Signal(int)

    def __init__(self):
        super().__init__()
        self.before = self.after = None
        self.position = 50
        self.zoom = 1
        self.interactive = True
        self.setMinimumSize(340, 290)
        self.setAccessibleName("Before and after photo preview")

    def mousePressEvent(self, event):
        if self.interactive and event.button() == Qt.MouseButton.LeftButton:
            self.move_split(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.interactive and event.buttons() & Qt.MouseButton.LeftButton:
            self.move_split(event)
        else:
            super().mouseMoveEvent(event)

    def move_split(self, event):
        value = round(100 * event.position().x() / self.width())
        self.split_moved.emit(max(0, min(100, value)))
        event.accept()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().alternateBase())
        if self.before is None or self.after is None:
            return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        split = self.width() * self.position // 100
        for image, clip in (
            (self.before, QRect(0, 0, split, self.height())),
            (self.after, QRect(split, 0, self.width() - split, self.height())),
        ):
            size = image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio) * self.zoom
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
            painter.setPen(self.palette().accent().color())
            painter.drawLine(split, 0, split, self.height())


def _strength(minimum, maximum, value=0):
    spin = QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setValue(value)
    return spin


class CropControls(QWidget):
    changed = Signal(object)

    def __init__(self, parent, crop):
        super().__init__(parent)
        self.restoring = False
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.preset = QComboBox()
        self.presets = (AS_ENHANCED, *PRESETS)
        for item in self.presets:
            self.preset.addItem(item.label)
        self.preset.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.preset.setMinimumContentsLength(10)
        self.preset.setAccessibleName("Crop size preset")
        form.addRow("Size preset", self.preset)
        self.guidance = QLabel()
        self.guidance.setObjectName("guidance")
        self.guidance.setWordWrap(True)
        form.addRow(self.guidance)
        self.guide = QPushButton("Platform image guidance")
        self.guide.setObjectName("guide")
        self.guide.clicked.connect(self.open_guidance)
        form.addRow(self.guide)
        self.custom = QWidget()
        sizing = QFormLayout(self.custom)
        sizing.setContentsMargins(0, 0, 0, 0)
        self.width = _strength(1, 20000, crop.custom.width)
        self.height = _strength(0, 20000, crop.custom.height or 0)
        self.height.setSpecialValueText("Proportional")
        self.mode = QComboBox()
        self.mode.addItems(["Fit", "Center crop", "White padding"])
        self.mode.setCurrentIndex(["fit", "crop", "pad"].index(crop.custom.mode))
        sizing.addRow("Width", self.width)
        sizing.addRow("Height", self.height)
        sizing.addRow("Sizing", self.mode)
        form.addRow(self.custom)
        self.enlarge = QCheckBox("Allow enlargement")
        self.enlarge.setChecked(crop.enlarge)
        form.addRow(self.enlarge)
        self.message = QLabel()
        self.message.setWordWrap(True)
        form.addRow(self.message)
        self.preset.currentIndexChanged.connect(self.update_preset)
        for field in (self.width, self.height):
            field.valueChanged.connect(self.update_settings)
        self.mode.currentIndexChanged.connect(self.update_settings)
        self.enlarge.toggled.connect(self.update_settings)
        self.set_settings(crop)

    def set_settings(self, crop):
        self.restoring = True
        self.width.setValue(crop.custom.width)
        self.height.setValue(crop.custom.height or 0)
        self.mode.setCurrentIndex(["fit", "crop", "pad"].index(crop.custom.mode))
        self.enlarge.setChecked(crop.enlarge)
        self.preset.setCurrentIndex(self.presets.index(crop.preset))
        self.update_preset(self.preset.currentIndex())
        self.restoring = False
        self.message.clear()
        self.message.hide()

    def update_preset(self, index):
        preset = self.presets[index]
        self.guidance.setText(
            "Use the dimensions after crop, rotation and upscaling."
            if index == 0
            else preset.guidance
        )
        self.guide.setVisible(bool(preset.source))
        self.custom.setVisible(preset.key == "custom")
        self.enlarge.setEnabled(index != 0)
        self.update_settings()

    def open_guidance(self):
        source = self.presets[self.preset.currentIndex()].source
        if source:
            QDesktopServices.openUrl(QUrl(source))

    def update_settings(self, *_):
        if self.restoring:
            return
        preset = self.presets[self.preset.currentIndex()]
        custom = Size(
            self.width.value(),
            self.height.value() or None,
            ["fit", "crop", "pad"][self.mode.currentIndex()],
        )
        crop = CropSettings(preset, custom, self.enlarge.isChecked())
        try:
            if crop.size is not None:
                crop.size.validate()
        except PreparationError as exc:
            self.message.setText(str(exc))
            self.message.show()
        else:
            self.message.clear()
            self.message.hide()
        self.changed.emit(crop)


def dialog_buttons(dialog, label):
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
    ok.setText(label)
    ok.setProperty("primary", True)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    return buttons


class ExportOptions(QDialog):
    def __init__(
        self,
        parent,
        paths,
        current,
        adjustments,
        crops,
        *,
        output_format="PNG",
        quality=95,
        selected_only=False,
    ):
        super().__init__(parent)
        self.setWindowTitle("Export images")
        self.setMinimumWidth(450)
        self.request = None
        self.paths, self.current = tuple(paths), current
        self.adjustments, self.crops = tuple(adjustments), tuple(crops)
        self.default_name = safe_output_name(paths[current].stem)
        form = QFormLayout(self)
        self.filename = QLineEdit(self.default_name)
        self.filename.setMaxLength(100)
        self.filename.selectAll()
        form.addRow("File name", self.filename)
        self.format = QComboBox()
        for label, value in (("JPG", "JPEG"), ("PNG", "PNG"), ("TIFF", "TIFF")):
            self.format.addItem(label, value)
        self.format.setCurrentIndex(self.format.findData(output_format))
        form.addRow("Format", self.format)
        self.quality = _strength(1, 100, quality)
        self.quality_label = QLabel("JPG quality")
        self.quality_label.setBuddy(self.quality)
        form.addRow(self.quality_label, self.quality)
        self.scope = QComboBox()
        self.scope.addItem(f"All {len(paths)} images" if len(paths) != 1 else "Current image")
        if len(paths) > 1:
            self.scope.addItem("Selected image")
        self.scope.setEnabled(len(paths) > 1)
        if len(paths) > 1 and selected_only:
            self.scope.setCurrentIndex(1)
        if len(paths) > 1:
            form.addRow("Images", self.scope)
        self.destination = QLabel()
        self.destination.setTextFormat(Qt.TextFormat.PlainText)
        self.destination.setWordWrap(True)
        form.addRow(self.destination)
        self.message = QLabel()
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.message.setWordWrap(True)
        form.addRow(self.message)
        form.addRow(dialog_buttons(self, "Export"))
        self.filename.textChanged.connect(self.update_summary)
        self.format.currentIndexChanged.connect(self.update_summary)
        self.scope.currentIndexChanged.connect(self.update_summary)
        self.update_summary()

    def output_name(self):
        name = self.filename.text().strip()
        if Path(name).suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}:
            name = Path(name).stem
        return validate_output_name(name)

    def update_summary(self, *_):
        jpeg = self.format.currentData() == "JPEG"
        self.quality.setVisible(jpeg)
        self.quality_label.setVisible(jpeg)
        self.message.clear()
        try:
            name = self.output_name()
        except PreparationError:
            self.destination.setText("Saves to a named folder in Downloads.")
            return
        ext = self.format.currentText().lower()
        sample = f"{name}.{ext}"
        if len(self.paths) > 1 and self.scope.currentIndex() == 0:
            sample += f", {name} 2.{ext}, …"
        self.destination.setText(f"Downloads / {name}\n{sample}")

    def accept(self):
        try:
            name = self.output_name()
        except PreparationError as exc:
            self.message.setText(str(exc))
            return
        indices = range(len(self.paths)) if self.scope.currentIndex() == 0 else (self.current,)
        self.request = ExportRequest(
            tuple(self.paths[i] for i in indices),
            name,
            self.format.currentData(),
            self.quality.value(),
            tuple(self.adjustments[i] for i in indices),
            tuple(self.crops[i] for i in indices),
        )
        super().accept()


class Workbench(QWidget):
    def __init__(self, parent, drop):
        super().__init__(parent)
        self.paths = []
        self.edits = []
        self.crops = []
        self.generation = 0
        self.active_path = None
        self.cached = None
        self.running = False
        self.pool = QThreadPool(self)
        self.signals = PreviewSignals(self)
        self.signals.finished.connect(self.preview_ready, Qt.ConnectionType.QueuedConnection)
        self.restoring = False
        self.timer = QTimer(self, singleShot=True, interval=150)
        self.timer.timeout.connect(self.render)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        content = QHBoxLayout()
        content.setSpacing(0)
        root.addLayout(content, 1)

        workspace = QWidget()
        workspace.setObjectName("workspace")
        canvas = QVBoxLayout(workspace)
        canvas.setContentsMargins(18, 14, 18, 14)
        self.pages = QStackedWidget()
        self.pages.addWidget(drop)
        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        toolbar = QHBoxLayout()
        self.name = QLabel()
        self.name.setTextFormat(Qt.TextFormat.PlainText)
        self.name.setObjectName("summary")
        self.name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(self.name, 1)
        self.compare = QComboBox()
        self.compare.addItems(["Enhanced", "Split view", "Original"])
        self.compare.setCurrentIndex(1)
        self.compare.setAccessibleName("Preview mode")
        self.compare.currentIndexChanged.connect(self.set_view)
        toolbar.addWidget(self.compare)
        self.zoom = _strength(50, 300, 100)
        self.zoom.setSuffix("%")
        self.zoom.setSingleStep(25)
        self.zoom.setAccessibleName("Preview zoom")
        self.zoom.valueChanged.connect(self.set_zoom)
        toolbar.addWidget(self.zoom)
        fit = QPushButton("Fit")
        fit.clicked.connect(self.fit_preview)
        toolbar.addWidget(fit)
        editor_layout.addLayout(toolbar)
        self.preview = SplitPreview()
        editor_layout.addWidget(self.preview, 1)
        comparison = QHBoxLayout()
        comparison.addWidget(QLabel("Before"))
        self.split = QSlider(Qt.Orientation.Horizontal)
        self.split.setAccessibleName("Before and after split position")
        self.split.setRange(0, 100)
        self.split.setValue(50)
        self.split.valueChanged.connect(self.set_view)
        self.preview.split_moved.connect(self.split.setValue)
        comparison.addWidget(self.split, 1)
        comparison.addWidget(QLabel("After"))
        editor_layout.addLayout(comparison)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setObjectName("guidance")
        self.status.setWordWrap(True)
        editor_layout.addWidget(self.status)
        self.pages.addWidget(editor)
        canvas.addWidget(self.pages, 1)
        content.addWidget(workspace, 1)

        sidebar = QWidget()
        sidebar.setObjectName("enhancements")
        controls = QVBoxLayout(sidebar)
        controls.setContentsMargins(18, 16, 18, 16)
        controls.setSpacing(14)
        title = QLabel("Enhancements")
        title.setObjectName("panelTitle")
        controls.addWidget(title)
        self.controls = QWidget()
        panel = QFormLayout(self.controls)
        panel.setContentsMargins(0, 0, 0, 0)
        panel.setSpacing(8)
        auto = QPushButton("Auto adjust")
        auto.setToolTip("Apply a balanced denoise and sharpen preset.")
        auto.clicked.connect(self.auto_adjust)
        controls.addWidget(auto)
        self.auto = auto
        self.noise = _strength(0, 100)
        self.sharp = _strength(0, 100)
        self.exposure = QDoubleSpinBox()
        self.exposure.setRange(-2, 2)
        self.exposure.setSingleStep(0.1)
        self.exposure.setDecimals(1)
        self.exposure_slider = QSlider(Qt.Orientation.Horizontal)
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
            ("Upscale", self.scale),
            ("Exposure", self.exposure),
            ("Warmth", self.warmth),
            ("Aspect ratio", self.crop),
            ("Rotate clockwise", self.rotation),
        ):
            if control is self.crop:
                heading = QLabel("Crop")
                heading.setObjectName("panelTitle")
                panel.addRow(heading)
            control.setAccessibleName(label)
            if isinstance(control, (QSpinBox, QDoubleSpinBox)):
                row = QWidget()
                fields = QHBoxLayout(row)
                fields.setContentsMargins(0, 0, 0, 0)
                if control is self.exposure:
                    slider = self.exposure_slider
                    slider.setRange(-20, 20)
                    slider.valueChanged.connect(self.set_exposure)
                    control.valueChanged.connect(self.sync_exposure)
                else:
                    slider = QSlider(Qt.Orientation.Horizontal)
                    slider.setRange(control.minimum(), control.maximum())
                    slider.valueChanged.connect(control.setValue)
                    control.valueChanged.connect(slider.setValue)
                slider.setAccessibleName(f"{label} slider")
                fields.addWidget(slider, 1)
                control.setFixedWidth(75)
                fields.addWidget(control)
                panel.addRow(label, row)
            else:
                panel.addRow(label, control)
            signal = (
                control.currentIndexChanged
                if isinstance(control, QComboBox)
                else control.valueChanged
            )
            signal.connect(self.save_edit)
        self.crop_controls = CropControls(self, CropSettings())
        self.crop_controls.changed.connect(self.save_crop)
        panel.addRow(self.crop_controls)
        buttons = QHBoxLayout()
        reset = QPushButton("Reset")
        reset.clicked.connect(self.reset)
        buttons.addWidget(reset)
        apply = QPushButton("Apply to all")
        apply.clicked.connect(self.apply_all)
        buttons.addWidget(apply)
        panel.addRow(buttons)
        controls.addWidget(self.controls)
        controls.addStretch()
        scroll = QScrollArea()
        scroll.setObjectName("enhancementScroll")
        scroll.setWidgetResizable(True)
        scroll.setWidget(sidebar)
        scroll.setFixedWidth(330)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content.addWidget(scroll)

        self.photos = QListWidget()
        self.photos.setObjectName("filmstrip")
        self.photos.setAccessibleName("Image queue")
        self.photos.setIconSize(QSize(45, 36))
        self.photos.setFlow(QListView.Flow.LeftToRight)
        self.photos.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.photos.setHorizontalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.photos.setFixedHeight(82)
        self.photos.setSpacing(8)
        self.photos.currentRowChanged.connect(self.select_photo)
        root.addWidget(self.photos)
        self.set_view()
        self.set_paths([])

    def set_paths(self, paths):
        previous = self.photos.currentRow()
        selected = self.paths[previous] if previous >= 0 else None
        edits = dict(zip(self.paths, self.edits, strict=True))
        crops = dict(zip(self.paths, self.crops, strict=True))
        self.paths = list(dict.fromkeys(paths))
        self.edits = [edits.get(path, Adjustments()) for path in self.paths]
        self.crops = [crops.get(path, CropSettings()) for path in self.paths]
        blocked = self.photos.blockSignals(True)
        icons = {path: self.photos.item(i).icon() for i, path in enumerate(edits)}
        self.photos.clear()
        for path in self.paths:
            item = QListWidgetItem(path.name)
            item.setSizeHint(QSize(162, 51))
            item.setToolTip(f"<qt>{escape(str(path))}</qt>")
            if path in icons:
                item.setIcon(icons[path])
            self.photos.addItem(item)
        index = self.paths.index(selected) if selected in self.paths else (0 if self.paths else -1)
        self.photos.setCurrentRow(index)
        self.photos.blockSignals(blocked)
        self.photos.setVisible(bool(self.paths))
        self.pages.setCurrentIndex(int(bool(self.paths)))
        self.controls.setEnabled(bool(self.paths))
        self.auto.setEnabled(bool(self.paths))
        self.select_photo(index)

    def select_photo(self, index):
        if index >= 0:
            self.set_adjustments(self.edits[index])
            self.crop_controls.set_settings(self.crops[index])
            path = self.paths[index]
            self.name.setText(path.name)
            self.name.setToolTip(f"<qt>{escape(str(path))}</qt>")
        self.queue_preview()

    def set_adjustments(self, edit):
        self.restoring = True
        for control, value in (
            (self.noise, edit.noise),
            (self.sharp, edit.sharpness),
            (self.exposure, edit.exposure),
            (self.warmth, edit.warmth),
        ):
            control.setValue(value)
        for control, index in (
            (self.rotation, edit.rotation),
            (self.crop, CROPS.index(edit.crop)),
            (self.scale, (1, 2, 4, 6).index(edit.scale)),
        ):
            control.setCurrentIndex(index)
        self.restoring = False

    def save_edit(self, *_):
        index = self.photos.currentRow()
        if index >= 0 and not self.restoring:
            self.edits[index] = self.adjustments()
            self.queue_preview()

    def open_crop(self):
        self.crop_controls.preset.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.crop_controls.preset.showPopup()

    def save_crop(self, crop):
        index = self.photos.currentRow()
        if index >= 0:
            self.crops[index] = crop
            self.queue_preview()

    def reset(self):
        index = self.photos.currentRow()
        self.crops[index] = CropSettings()
        self.crop_controls.set_settings(self.crops[index])
        self.set_adjustments(Adjustments())
        self.save_edit()

    def apply_all(self):
        edit = self.adjustments()
        self.edits[:] = [edit] * len(self.paths)
        self.crops[:] = [self.crops[self.photos.currentRow()]] * len(self.paths)
        self.status.setText(f"Applied adjustments to {len(self.paths)} images.")

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

    def set_view(self, *_):
        self.preview.position = (0, self.split.value(), 100)[self.compare.currentIndex()]
        self.preview.interactive = self.compare.currentIndex() == 1
        self.preview.setCursor(
            Qt.CursorShape.SplitHCursor if self.preview.interactive else Qt.CursorShape.ArrowCursor
        )
        self.split.setEnabled(self.preview.interactive)
        self.preview.update()

    def set_exposure(self, value):
        self.exposure.setValue(value / 10)

    def sync_exposure(self, value):
        self.exposure_slider.setValue(round(value * 10))

    def fit_preview(self):
        self.zoom.setValue(100)

    def set_zoom(self, value):
        self.preview.zoom = value / 100
        self.preview.update()

    def queue_preview(self):
        self.generation += 1
        index = self.photos.currentRow()
        path = self.paths[index] if index >= 0 else None
        if path != self.active_path:
            self.active_path = path
            self.cached = None
            self.preview.before = self.preview.after = None
            self.preview.update()
        if path is not None:
            self.status.setText("Preparing preview…")
            self.timer.start()
        else:
            self.timer.stop()

    def render(self):
        if self.running or self.active_path is None:
            return
        self.running = True
        task = PreviewTask(
            self.generation,
            self.active_path,
            self.adjustments(),
            self.crops[self.photos.currentRow()],
            self.cached,
            self.signals,
        )
        self.pool.start(task)

    def stop_preview(self):
        self.active_path = None
        self.generation += 1
        self.timer.stop()
        self.pool.waitForDone()

    def closeEvent(self, event):
        self.stop_preview()
        super().closeEvent(event)

    def preview_ready(self, generation, source, before, after, error):
        self.running = False
        if generation != self.generation:
            if self.active_path is not None:
                self.timer.start()
            return
        self.cached = source
        self.preview.before, self.preview.after = before, after
        if before is not None:
            item = self.photos.currentItem()
            if item is not None and item.icon().isNull():
                thumb = before.scaled(
                    QSize(45, 36),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                item.setIcon(QIcon(QPixmap.fromImage(thumb)))
        self.preview.update()
        self.status.setText(error or "Preview ready · Export uses full resolution")

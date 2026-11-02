"""Independent, opaque controls: never part of the click-through surface."""

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QCloseEvent, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

STYLE = """
QMainWindow, QWidget#body { background: #141c2b; color: #e6eefc; }
QWidget { font-family: "Segoe UI", "DejaVu Sans"; font-size: 12px; color: #e6eefc; }
QLabel#brand { font-size: 30px; font-weight: 600; color: #f2f7ff; }
QLabel#muted { color: #98aac4; font-size: 11px; }
QLabel#badge { color: #93d4ff; background: #233851; border-radius: 9px; padding: 5px 9px; }
QLabel#message { color: #a9d9ee; font-size: 11px; }
QFrame#preview { background: #1c273b; border: 1px dashed #3c5371; border-radius: 10px; }
QPushButton { background: #26354d; border: 1px solid #3b4f6d; border-radius: 7px;
              padding: 8px 9px; min-height: 16px; }
QPushButton:hover { background: #304665; border-color: #7fc8ff; }
QPushButton:pressed, QPushButton:checked { background: #354d72; border-color: #8cd3ff; }
QPushButton:disabled { color: #637590; border-color: #26354d; }
QPushButton#primary { background: #a1d8ff; color: #102336; font-weight: 600;
                      border-color: #a1d8ff; font-size: 14px; min-height: 26px; }
QPushButton#primary:hover { background: #c3e6ff; }
QPushButton#primary:disabled { background: #33485e; color: #8a9fb4; border-color: #33485e; }
QSpinBox, QDoubleSpinBox, QComboBox { background: #1e2b40; border: 1px solid #3a4d69;
    border-radius: 6px; padding: 6px; min-height: 20px; selection-background-color: #49668f; }
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: #94d4ff; }
QCheckBox { spacing: 7px; padding: 4px 0; }
QSlider::groove:horizontal { height: 5px; background: #344763; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #9bd6ff; border-radius: 2px; }
QSlider::handle:horizontal { background: #d4eeff; width: 16px; margin: -6px 0; border-radius: 8px; }
QScrollArea { border: 0; background: #141c2b; }
QScrollBar:vertical { background: #141c2b; width: 7px; }
QScrollBar::handle:vertical { background: #3b4f6c; border-radius: 3px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def muted(text):
    label = QLabel(text)
    label.setObjectName("muted")
    label.setWordWrap(True)
    return label


class ControlPanel(QMainWindow):
    closing = Signal()
    path_dropped = Signal(str)

    def __init__(self, controller):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.c = controller
        self.setWindowTitle("Screen · стеклянный референс")
        self.setAcceptDrops(True)
        self.setMinimumWidth(380)
        self.resize(400, 890)
        self.setStyleSheet(STYLE)
        body = QWidget()
        body.setObjectName("body")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)
        heading = QHBoxLayout()
        brand = QLabel("Screen")
        brand.setObjectName("brand")
        heading.addWidget(brand)
        heading.addStretch()
        self.badge = QLabel("НАСТРОЙКА")
        self.badge.setObjectName("badge")
        heading.addWidget(self.badge)
        layout.addLayout(heading)
        layout.addWidget(muted("Картинка поверх холста. Рисуй в своем редакторе."))

        preview = QFrame()
        preview.setObjectName("preview")
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(10, 10, 10, 10)
        self.thumbnail = QLabel("Перетащи картинку сюда\nили вставь через Ctrl+V")
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setFixedHeight(72)
        self.source_label = muted("PNG · JPEG · WebP · BMP · TIFF · GIF")
        self.source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.source_label.setTextFormat(Qt.TextFormat.PlainText)
        preview_layout.addWidget(self.thumbnail)
        preview_layout.addWidget(self.source_label)
        layout.addWidget(preview)
        self._row(
            layout, [("Открыть…", controller.choose_image), ("Вставить  Ctrl+V", controller.paste)]
        )

        self.mode_button = QPushButton("Начать обводку")
        self.mode_button.setObjectName("primary")
        self.mode_button.clicked.connect(controller.toggle_tracing)
        layout.addWidget(self.mode_button)
        layout.addWidget(muted("В обводке клики и перо проходят в программу под картинкой."))

        opacity_heading = QHBoxLayout()
        opacity_heading.addWidget(QLabel("Непрозрачность картинки"))
        self.opacity_value = QLabel("50%")
        opacity_heading.addStretch()
        opacity_heading.addWidget(self.opacity_value)
        layout.addLayout(opacity_heading)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(50)
        self.opacity_slider.setAccessibleName("Непрозрачность картинки")
        self.opacity_slider.valueChanged.connect(controller.set_opacity)
        layout.addWidget(self.opacity_slider)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        self.width_spin = QSpinBox()
        self.height_spin = QSpinBox()
        for spin, name in ((self.width_spin, "Ширина"), (self.height_spin, "Высота")):
            spin.setRange(24, 16384)
            spin.setSuffix(" px")
            spin.setKeyboardTracking(False)
            spin.setAccessibleName(name)
        grid.addWidget(muted("Ширина"), 0, 0)
        grid.addWidget(muted("Высота"), 0, 1)
        grid.addWidget(self.width_spin, 1, 0)
        grid.addWidget(self.height_spin, 1, 1)
        self.width_spin.valueChanged.connect(controller.set_width)
        self.height_spin.valueChanged.connect(controller.set_height)
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.1, 100000)
        self.scale_spin.setDecimals(1)
        self.scale_spin.setSingleStep(5)
        self.scale_spin.setSuffix(" %")
        self.scale_spin.setKeyboardTracking(False)
        self.scale_spin.setAccessibleName("Масштаб")
        self.scale_spin.valueChanged.connect(controller.set_scale)
        self.rotation_spin = QSpinBox()
        self.rotation_spin.setRange(-180, 180)
        self.rotation_spin.setSuffix("°")
        self.rotation_spin.setKeyboardTracking(False)
        self.rotation_spin.setAccessibleName("Поворот")
        self.rotation_spin.valueChanged.connect(controller.set_rotation)
        grid.addWidget(muted("Масштаб"), 2, 0)
        grid.addWidget(muted("Поворот"), 2, 1)
        grid.addWidget(self.scale_spin, 3, 0)
        grid.addWidget(self.rotation_spin, 3, 1)
        layout.addLayout(grid)
        self.aspect_check = QCheckBox("Сохранять пропорции")
        self.aspect_check.setChecked(True)
        self.aspect_check.toggled.connect(controller.set_aspect)
        layout.addWidget(self.aspect_check)
        flips = QHBoxLayout()
        self.flip_x_button = QPushButton("↔  Отразить")
        self.flip_y_button = QPushButton("↕  Отразить")
        for button in (self.flip_x_button, self.flip_y_button):
            button.setCheckable(True)
            flips.addWidget(button)
        self.flip_x_button.setToolTip("Отражение по горизонтали")
        self.flip_y_button.setToolTip("Отражение по вертикали")
        self.flip_x_button.toggled.connect(controller.set_flip_x)
        self.flip_y_button.toggled.connect(controller.set_flip_y)
        layout.addLayout(flips)

        self.monitor_combo = QComboBox()
        self.monitor_combo.setAccessibleName("Монитор для центрирования")
        layout.addWidget(self.monitor_combo)
        self._row(
            layout,
            [("По центру", controller.center_image), ("Вписать в экран", controller.fit_image)],
        )
        buttons = self._row(
            layout,
            [
                ("Сбросить", controller.reset_transform),
                ("Скрыть картинку", controller.toggle_visibility),
            ],
        )
        self.visibility_button = buttons[1]
        self._row(
            layout,
            [
                ("Сохранить проект…", controller.choose_save),
                ("Открыть проект…", controller.choose_project),
            ],
        )
        layout.addWidget(
            muted(
                "Мышь: перенос · колесо: масштаб\n"
                "Shift + ручка: сменить пропорции\n"
                "Стрелки: сдвиг на 1 px · Shift: на 10 px"
            )
        )
        self.hotkey_label = muted(
            "Ctrl+Alt+F8  ·  настройка / обводка\n"
            "Ctrl+Alt+F9  ·  показать / скрыть картинку\n"
            "Ctrl+Alt+F10  ·  показать / скрыть панель"
        )
        layout.addWidget(self.hotkey_label)
        self.message_label = QLabel("Открой картинку и совмести ее с холстом.")
        self.message_label.setObjectName("message")
        self.message_label.setWordWrap(True)
        self.message_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.message_label)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(body)
        self.setCentralWidget(scroll)
        self.image_controls = [
            self.mode_button,
            self.width_spin,
            self.height_spin,
            self.scale_spin,
            self.rotation_spin,
            self.flip_x_button,
            self.flip_y_button,
            self.visibility_button,
        ]
        self._shortcuts = []
        for key, callback in [
            ("Ctrl+O", controller.choose_image),
            ("Ctrl+V", controller.paste),
            ("Ctrl+S", controller.choose_save),
            ("Ctrl+Shift+O", controller.choose_project),
        ]:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def _row(self, layout, actions):
        row = QHBoxLayout()
        row.setSpacing(8)
        buttons = []
        for text, action in actions:
            button = QPushButton(text)
            button.clicked.connect(action)
            row.addWidget(button)
            buttons.append(button)
        layout.addLayout(row)
        return buttons

    def set_thumbnail(self, image, label):
        self.thumbnail.setPixmap(
            QPixmap.fromImage(image).scaled(
                300,
                72,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        text = f"{label} · {image.width()} × {image.height()}"
        self.source_label.setText(text if len(text) < 75 else text[:72] + "…")
        self.source_label.setToolTip(text)

    def sync(self):
        c, p = self.c, self.c.placement
        widgets = [
            self.width_spin,
            self.height_spin,
            self.scale_spin,
            self.rotation_spin,
            self.opacity_slider,
            self.aspect_check,
            self.flip_x_button,
            self.flip_y_button,
        ]
        blockers = [QSignalBlocker(w) for w in widgets]
        self.opacity_slider.setValue(round(c.opacity * 100))
        self.opacity_value.setText(f"{round(c.opacity * 100)}%")
        self.aspect_check.setChecked(c.keep_aspect)
        self.flip_x_button.setChecked(c.flip_x)
        self.flip_y_button.setChecked(c.flip_y)
        if p:
            self.width_spin.setValue(round(p.width))
            self.height_spin.setValue(round(p.height))
            self.scale_spin.setValue(p.width / c.image.width() * 100)
            self.rotation_spin.setValue(round(p.rotation))
        for widget in self.image_controls:
            widget.setEnabled(p is not None)
        self.badge.setText("ОБВОДКА" if c.tracing else "НАСТРОЙКА")
        self.mode_button.setText("Настроить картинку" if c.tracing else "Начать обводку")
        self.visibility_button.setText(
            "Скрыть картинку" if c.image_visible else "Показать картинку"
        )
        del blockers

    def closeEvent(self, event: QCloseEvent):
        self.closing.emit()
        event.accept()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and event.mimeData().urls()[0].isLocalFile():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasUrls() and event.mimeData().urls()[0].isLocalFile():
            self.path_dropped.emit(event.mimeData().urls()[0].toLocalFile())
            event.acceptProposedAction()

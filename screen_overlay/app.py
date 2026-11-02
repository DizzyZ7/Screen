"""Application state and coordination of independent controls and overlay windows."""

import sys
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QRectF, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QSystemTrayIcon

from .geometry import Placement
from .images import clipboard_image, load_image, validate_image
from .native import HotkeyManager, WindowsAPI
from .overlay import OverlayWindow
from .panel import ControlPanel
from .project import ReferenceProject, load_project, save_project


def make_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#152238"))
    painter.drawRoundedRect(2, 2, 60, 60, 15, 15)
    painter.setBrush(QColor("#355d86"))
    painter.setPen(QPen(QColor("#77b9e6"), 2.5))
    painter.drawRoundedRect(13, 12, 31, 31, 5, 5)
    painter.setBrush(QColor(166, 219, 255, 190))
    painter.drawRoundedRect(23, 23, 29, 29, 5, 5)
    painter.end()
    return QIcon(pixmap)


class Controller(QObject):
    def __init__(self, app: QApplication, settings=None, enable_native=True):
        super().__init__(app)
        from PySide6.QtGui import QImage

        self.app = app
        self.settings = settings if settings is not None else QSettings("DizzyZ7", "Screen")
        self.native = WindowsAPI() if enable_native and sys.platform == "win32" else None
        self.hotkeys = None
        self.tray = None
        self.closed = False
        self.image = QImage()
        self.placement: Placement | None = None
        self.tracing = False
        self._input_ready = True
        self.image_visible = True
        self.flip_x = self.flip_y = False
        try:
            self.opacity = max(0, min(100, self.settings.value("opacity", 50, type=int))) / 100
            self.keep_aspect = self.settings.value("keep_aspect", True, type=bool)
        except (TypeError, ValueError):
            self.opacity, self.keep_aspect = 0.5, True
        self.overlays: list[OverlayWindow] = []
        self._screen_connections = []
        self.icon = make_icon()
        self.panel = ControlPanel(self)
        self.panel.setWindowIcon(self.icon)
        self.panel.closing.connect(self.quit)
        self.panel.path_dropped.connect(self.open_path)
        self._rebuild_overlays()
        self.app.screenAdded.connect(self._schedule_rebuild)
        self.app.screenRemoved.connect(self._schedule_rebuild)
        self.app.aboutToQuit.connect(self.shutdown)
        self._callbacks = {
            "toggle_tracing": self.toggle_tracing,
            "toggle_visibility": self.toggle_visibility,
            "toggle_panel": self.toggle_panel,
        }
        if self.native:
            self.hotkeys = HotkeyManager(app, self._callbacks, self.native)
            self.hotkeys.start()
            if self.hotkeys.errors:
                self.panel.hotkey_label.setText(
                    "\n".join(self.hotkeys.errors) + "\nИспользуй панель или значок Screen в трее."
                )
        elif sys.platform != "win32":
            self.panel.hotkey_label.setText(
                "Глобальные клавиши доступны в версии для Windows.\n"
                "На этой платформе используй панель управления."
            )
        if enable_native and QSystemTrayIcon.isSystemTrayAvailable():
            self._create_tray()
        self._position_panel()
        self.panel.show()
        self.panel.raise_()
        self.refresh()

    def _position_panel(self):
        screen = self.app.primaryScreen() or self.app.screens()[0]
        area = screen.availableGeometry()
        self.panel.resize(400, min(890, max(400, area.height() - 48)))
        pos = self.settings.value("panel_pos")
        # Recover the whole control panel if a previous monitor was disconnected.
        if isinstance(pos, QPoint) and any(
            s.availableGeometry().contains(pos)
            and s.availableGeometry().contains(
                pos + QPoint(self.panel.width() - 1, min(100, self.panel.height() - 1))
            )
            for s in self.app.screens()
        ):
            self.panel.move(pos)
        else:
            self.panel.move(area.right() - self.panel.width() - 20, area.top() + 20)

    def _create_tray(self):
        self.tray = QSystemTrayIcon(self.icon, self)
        self.tray.setToolTip("Screen · референс для обводки")
        menu = QMenu(self.panel)
        for label, action in [
            ("Показать панель", self.show_panel),
            ("Настройка / обводка", self.toggle_tracing),
            ("Показать / скрыть картинку", self.toggle_visibility),
            ("Завершить Screen", self.quit),
        ]:
            item = QAction(label, menu)
            item.triggered.connect(action)
            menu.addAction(item)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: (
                self.show_panel()
                if reason
                in (
                    QSystemTrayIcon.ActivationReason.Trigger,
                    QSystemTrayIcon.ActivationReason.DoubleClick,
                )
                else None
            )
        )
        self.tray.show()

    def _schedule_rebuild(self, *args):
        QTimer.singleShot(0, self._rebuild_overlays)

    def _rebuild_overlays(self):
        if self.closed:
            return
        for screen, slot in self._screen_connections:
            try:
                screen.geometryChanged.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self._screen_connections.clear()
        for overlay in self.overlays:
            overlay.close()
            overlay.deleteLater()
        self.overlays.clear()
        previous = self.panel.monitor_combo.currentIndex()
        self.panel.monitor_combo.clear()
        for index, screen in enumerate(self.app.screens()):
            rect = screen.geometry()
            self.panel.monitor_combo.addItem(
                f"Экран {index + 1} · {rect.width()} × {rect.height()}"
            )
            overlay = OverlayWindow(screen, self.native)
            overlay.changed.connect(self.set_placement)
            overlay.mode_requested.connect(self.toggle_tracing)
            overlay.paste_requested.connect(self.paste)
            overlay.open_requested.connect(self.choose_image)
            overlay.path_dropped.connect(self.open_path)
            overlay.opacity_delta.connect(
                lambda delta: self.set_opacity(round(self.opacity * 100) + delta)
            )
            if not self.image.isNull():
                overlay.set_image(self.image)
            self.overlays.append(overlay)
            screen.geometryChanged.connect(self._schedule_rebuild)
            self._screen_connections.append((screen, self._schedule_rebuild))
        self.panel.monitor_combo.setCurrentIndex(max(0, min(previous, len(self.overlays) - 1)))
        self._recover_placement()
        desired = self.tracing
        self.tracing = False
        self.refresh()
        self.set_tracing(desired)
        if self.panel.isVisible():
            self.panel.raise_()

    def _selected_screen_rect(self):
        screens = self.app.screens()
        index = max(0, min(self.panel.monitor_combo.currentIndex(), len(screens) - 1))
        return screens[index].availableGeometry()

    def _recover_placement(self):
        if self.placement and not any(
            QRectF(*self.placement.bounds()).intersects(QRectF(s.geometry()))
            for s in self.app.screens()
        ):
            rect = self._selected_screen_rect()
            self.placement = replace(
                self.placement, center_x=rect.center().x(), center_y=rect.center().y()
            )

    def refresh(self):
        if self.closed:
            return
        shown = False
        for overlay in self.overlays:
            overlay.placement = self.placement
            overlay.opacity, overlay.keep_aspect = self.opacity, self.keep_aspect
            overlay.flip_x, overlay.flip_y = self.flip_x, self.flip_y
            if self.image_visible and self.placement:
                if not overlay.isVisible():
                    overlay.show()
                    shown = True
            else:
                overlay.hide()
            overlay.update()
        self.panel.sync()
        if shown and self.panel.isVisible():
            self.panel.raise_()

    def set_image(self, image, label="Изображение из буфера"):
        validated = validate_image(image)
        rect = self._selected_screen_rect()
        placement = Placement.fit(validated.width(), validated.height(), rect.getRect())
        if not self.set_tracing(False):
            raise ValueError(
                "Не удалось включить настройку картинки. Попробуй переключить режим еще раз."
            )
        self.image = validated
        self.flip_x = self.flip_y = False
        self.image_visible = True
        self.placement = placement
        for overlay in self.overlays:
            overlay.set_image(self.image)
        self.panel.set_thumbnail(self.image, label)
        self.panel.message_label.setText(
            "Совмести картинку с холстом, затем нажми «Начать обводку»."
        )
        self.refresh()

    def set_placement(self, placement):
        self.placement = placement
        self.refresh()

    def set_tracing(self, enabled):
        if self.closed or (enabled and self.placement is None):
            return False
        try:
            for overlay in self.overlays:
                overlay.set_tracing(enabled)
        except OSError as exc:
            # Hide all surfaces if Windows refuses input-mode changes: leave the desktop usable.
            self._input_ready = True
            for overlay in self.overlays:
                try:
                    overlay.set_tracing(self.tracing, force=True)
                except OSError:
                    self._input_ready = False
            self.image_visible = False
            self.show_error(f"Не удалось переключить ввод; картинка скрыта. {exc}")
            self.refresh()
            return False
        self.tracing = enabled
        self._input_ready = True
        self.refresh()
        return True

    def toggle_tracing(self):
        self.set_tracing(not self.tracing)

    def set_opacity(self, percent):
        self.opacity = max(0, min(100, percent)) / 100
        self.refresh()

    def set_aspect(self, enabled):
        self.keep_aspect = enabled
        self.refresh()

    def set_width(self, width):
        if self.placement:
            self.set_placement(self.placement.with_width(width, self.keep_aspect))

    def set_height(self, height):
        if self.placement:
            self.set_placement(self.placement.with_height(height, self.keep_aspect))

    def set_scale(self, percent):
        if self.placement:
            factor = self.image.width() * percent / 100 / self.placement.width
            self.set_placement(
                self.placement.zoom_at(factor, self.placement.center_x, self.placement.center_y)
            )

    def set_rotation(self, angle):
        if self.placement:
            self.set_placement(replace(self.placement, rotation=angle))

    def set_flip_x(self, enabled):
        self.flip_x = enabled
        self.refresh()

    def set_flip_y(self, enabled):
        self.flip_y = enabled
        self.refresh()

    def center_image(self):
        if self.placement:
            rect = self._selected_screen_rect()
            self.set_placement(
                replace(self.placement, center_x=rect.center().x(), center_y=rect.center().y())
            )

    def fit_image(self):
        if self.placement:
            self.set_placement(
                Placement.fit(
                    self.image.width(), self.image.height(), self._selected_screen_rect().getRect()
                )
            )

    def reset_transform(self):
        self.flip_x = self.flip_y = False
        self.fit_image()

    def toggle_visibility(self):
        if not self.image_visible and not self._input_ready and not self.set_tracing(self.tracing):
            return
        self.image_visible = not self.image_visible
        self.refresh()

    def show_panel(self):
        self.panel.showNormal()
        self.panel.raise_()
        self.panel.activateWindow()

    def toggle_panel(self):
        if self.panel.isVisible() and not self.panel.isMinimized():
            if (self.tray and self.tray.isVisible()) or (
                self.hotkeys and "toggle_panel" in self.hotkeys.registered
            ):
                self.panel.hide()
            else:
                self.panel.showMinimized()  # Taskbar recovery when neither tray nor global hotkey exists.
        else:
            self.show_panel()

    def show_error(self, message):
        self.panel.message_label.setText(str(message))
        self.show_panel()

    def open_path(self, path):
        try:
            path = Path(path)
            if path.suffix.lower() == ".screenref":
                project = load_project(path)
                self.set_image(project.image, path.name)
                self.placement, self.opacity = project.placement, project.opacity
                self.flip_x, self.flip_y, self.keep_aspect = (
                    project.flip_x,
                    project.flip_y,
                    project.keep_aspect,
                )
                self._recover_placement()
                self.refresh()
            else:
                self.set_image(load_image(path), path.name)
        except (ValueError, OSError) as exc:
            self.show_error(str(exc))

    def paste(self):
        try:
            self.set_image(clipboard_image(self.app.clipboard().mimeData()))
        except ValueError as exc:
            self.show_error(str(exc))

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self.panel,
            "Открыть картинку",
            "",
            "Изображения (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.gif);;Все файлы (*)",
        )
        if path:
            self.open_path(path)

    def choose_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self.panel, "Открыть проект Screen", "", "Проект Screen (*.screenref)"
        )
        if path:
            self.open_path(path)

    def save_to(self, path):
        if not self.placement:
            self.show_error("Сначала открой картинку.")
            return
        try:
            save_project(
                path,
                ReferenceProject(
                    self.image,
                    self.placement,
                    self.opacity,
                    self.flip_x,
                    self.flip_y,
                    self.keep_aspect,
                ),
            )
            self.panel.message_label.setText(
                "Проект сохранен вместе с картинкой и ее расположением."
            )
        except (ValueError, OSError) as exc:
            self.show_error(str(exc))

    def choose_save(self):
        if not self.placement:
            self.show_error("Сначала открой картинку.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self.panel,
            "Сохранить проект Screen",
            "Референс.screenref",
            "Проект Screen (*.screenref)",
        )
        if path:
            if not path.lower().endswith(".screenref"):
                path += ".screenref"
            self.save_to(path)

    def quit(self):
        self.shutdown()
        self.app.quit()

    def shutdown(self):
        if self.closed:
            return
        self.closed = True
        self.settings.setValue("opacity", round(self.opacity * 100))
        self.settings.setValue("keep_aspect", self.keep_aspect)
        self.settings.setValue("panel_pos", self.panel.pos())
        self.settings.sync()
        if self.hotkeys:
            self.hotkeys.close()
        if self.tray:
            self.tray.hide()
        for overlay in self.overlays:
            overlay.close()
            overlay.deleteLater()
        self.panel.hide()
        for signal, slot in (
            (self.app.screenAdded, self._schedule_rebuild),
            (self.app.screenRemoved, self._schedule_rebuild),
            (self.app.aboutToQuit, self.shutdown),
        ):
            signal.disconnect(slot)
        for screen, slot in self._screen_connections:
            try:
                screen.geometryChanged.disconnect(slot)
            except (RuntimeError, TypeError):
                pass

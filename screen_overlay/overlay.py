"""A transparent, independently DPI-scaled surface on one monitor."""

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QWidget

from .geometry import Placement


class OverlayWindow(QWidget):
    changed = Signal(object)
    mode_requested = Signal()
    paste_requested = Signal()
    open_requested = Signal()
    path_dropped = Signal(str)
    opacity_delta = Signal(int)

    def __init__(self, screen, native=None):
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setWindowTitle("Screen · референс")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.screen_ref = screen
        self.native = native
        self.placement: Placement | None = None
        self.pixmap = QPixmap()
        self.opacity = 0.5
        self.flip_x = self.flip_y = False
        self.keep_aspect = True
        self.tracing = False
        self._drag = None
        self.setGeometry(screen.geometry())
        # Bind before showing, so Qt chooses this monitor's DPI even for negative origins.
        self.winId()
        self.windowHandle().setScreen(screen)
        self.setGeometry(screen.geometry())

    def set_image(self, image: QImage):
        self.pixmap = QPixmap.fromImage(image)
        self.update()

    def set_tracing(self, enabled: bool, force=False):
        if enabled == self.tracing and not force:
            return
        if self.native:
            self.native.set_click_through(int(self.winId()), enabled)
        else:
            was_visible = self.isVisible()
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, enabled)
            if was_visible:
                self.show()
        self.tracing = enabled
        self._drag = None
        self.unsetCursor()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        if self.placement is None or self.pixmap.isNull():
            return
        p = self.placement
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.translate(-self.x(), -self.y())
        painter.save()
        painter.translate(p.center_x, p.center_y)
        painter.rotate(p.rotation)
        rect = QRectF(-p.width / 2, -p.height / 2, p.width, p.height)
        if not self.tracing:
            # Non-zero alpha gives transparent PNG regions a draggable hit-test surface.
            painter.fillRect(rect, QColor(100, 160, 250, 3))
        painter.setOpacity(self.opacity)
        painter.scale(-1 if self.flip_x else 1, -1 if self.flip_y else 1)
        painter.drawPixmap(rect, self.pixmap, QRectF(self.pixmap.rect()))
        painter.restore()
        if not self.tracing:
            pts = [
                QPointF(*p.local_to_world(x * p.width / 2, y * p.height / 2))
                for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))
            ]
            pen = QPen(QColor("#80c9ff"), 1.5, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolygon(QPolygonF(pts))
            painter.setPen(QPen(QColor("#132a41"), 1))
            painter.setBrush(QColor("#d9efff"))
            for x, y in p.handle_positions().values():
                painter.drawRoundedRect(QRectF(x - 5, y - 5, 10, 10), 2, 2)

    def _handle_at(self, x, y):
        if self.placement:
            for name, (hx, hy) in self.placement.handle_positions().items():
                if (x - hx) ** 2 + (y - hy) ** 2 <= 11**2:
                    return name
        return None

    def mousePressEvent(self, event):
        if self.tracing or not self.placement or event.button() != Qt.MouseButton.LeftButton:
            return event.ignore()
        x, y = event.globalPosition().toTuple()
        handle = self._handle_at(x, y)
        lx, ly = self.placement.world_to_local(x, y)
        inside = abs(lx) <= self.placement.width / 2 and abs(ly) <= self.placement.height / 2
        if handle or inside:
            self._drag = (handle or "move", self.placement, x, y)
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        if self.tracing or not self.placement:
            return
        x, y = event.globalPosition().toTuple()
        if self._drag:
            kind, original, start_x, start_y = self._drag
            if kind == "move":
                result = original.moved(x - start_x, y - start_y)
            else:
                lock = self.keep_aspect ^ bool(
                    event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                )
                result = original.resized(kind, x, y, lock)
            self.changed.emit(result)
        else:
            handle = self._handle_at(x, y)
            cursor = {
                "n": Qt.CursorShape.SizeVerCursor,
                "s": Qt.CursorShape.SizeVerCursor,
                "e": Qt.CursorShape.SizeHorCursor,
                "w": Qt.CursorShape.SizeHorCursor,
                "nw": Qt.CursorShape.SizeFDiagCursor,
                "se": Qt.CursorShape.SizeFDiagCursor,
                "ne": Qt.CursorShape.SizeBDiagCursor,
                "sw": Qt.CursorShape.SizeBDiagCursor,
            }
            self.setCursor(cursor.get(handle, Qt.CursorShape.SizeAllCursor))

    def mouseReleaseEvent(self, event):
        self._drag = None

    def wheelEvent(self, event):
        if self.tracing or not self.placement:
            return event.ignore()
        steps = max(-10, min(10, event.angleDelta().y() / 120))
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.opacity_delta.emit(round(steps * 5))
        else:
            self.changed.emit(self.placement.zoom_at(1.1**steps, *event.globalPosition().toTuple()))
        event.accept()

    def keyPressEvent(self, event):
        if self.tracing or not self.placement:
            return event.ignore()
        key, modifiers = event.key(), event.modifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_V:
                self.paste_requested.emit()
                return
            if key == Qt.Key.Key_O:
                self.open_requested.emit()
                return
        delta = {
            Qt.Key.Key_Left: (-1, 0),
            Qt.Key.Key_Right: (1, 0),
            Qt.Key.Key_Up: (0, -1),
            Qt.Key.Key_Down: (0, 1),
        }.get(key)
        if delta:
            step = 10 if modifiers & Qt.KeyboardModifier.ShiftModifier else 1
            self.changed.emit(self.placement.moved(delta[0] * step, delta[1] * step))
        elif key == Qt.Key.Key_Escape:
            self.mode_requested.emit()
        else:
            super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if (
            not self.tracing
            and event.mimeData().hasUrls()
            and event.mimeData().urls()[0].isLocalFile()
        ):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if (
            not self.tracing
            and event.mimeData().hasUrls()
            and event.mimeData().urls()[0].isLocalFile()
        ):
            self.path_dropped.emit(event.mimeData().urls()[0].toLocalFile())
            event.acceptProposedAction()

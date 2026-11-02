import os
import sys
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from screen_overlay.app import Controller
from screen_overlay.geometry import Placement
from screen_overlay.native import HotkeyManager, WindowsAPI

APP = QApplication.instance() or QApplication([])


@unittest.skipUnless(
    sys.platform == "win32" and os.environ.get("QT_QPA_PLATFORM") != "offscreen",
    "Requires a real Windows desktop",
)
class WindowsIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.api = WindowsAPI()

    def click_center(self, widget):
        import ctypes
        from ctypes import wintypes

        user32 = self.api.user32
        user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        hwnd = int(widget.winId())
        rect = wintypes.RECT()
        self.assertTrue(user32.GetClientRect(hwnd, ctypes.byref(rect)))
        # These are native client pixels, not Qt logical coordinates.
        point = wintypes.POINT((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
        self.assertTrue(user32.ClientToScreen(hwnd, ctypes.byref(point)))
        user32.SetCursorPos(point.x, point.y)
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        user32.mouse_event(0x0004, 0, 0, 0, 0)
        QTest.qWait(150)

    def test_panel_remains_clickable_when_reference_overlaps_it_after_mode_changes(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        controller = Controller(
            APP,
            settings=QSettings(str(Path(temp.name) / "s.ini"), QSettings.Format.IniFormat),
            enable_native=True,
        )
        self.addCleanup(controller.shutdown)
        image = QImage(1000, 1000, QImage.Format.Format_ARGB32)
        image.fill(QColor("red"))
        controller.set_image(image)
        controller.panel.move(80, 80)
        center = controller.panel.geometry().center()
        controller.set_placement(Placement(center.x(), center.y(), 1000, 1000))
        controller.panel.raise_()
        QTest.qWait(150)
        self.click_center(controller.panel.mode_button)
        self.assertTrue(controller.tracing)
        self.click_center(controller.panel.mode_button)
        self.assertFalse(controller.tracing)
        self.click_center(controller.panel.mode_button)
        self.assertTrue(controller.tracing)

    def test_clickthrough_style_and_real_pointer_pass_to_underlying_window(self):
        class Canvas(QWidget):
            clicks = 0

            def mousePressEvent(self, event):
                self.clicks += 1

        canvas = Canvas()
        canvas.setGeometry(100, 100, 300, 250)
        canvas.setStyleSheet("background: white;")
        canvas.show()
        self.addCleanup(canvas.close)
        with tempfile.TemporaryDirectory() as temp:
            controller = Controller(
                APP,
                settings=QSettings(str(Path(temp) / "s.ini"), QSettings.Format.IniFormat),
                enable_native=True,
            )
            self.addCleanup(controller.shutdown)
            image = QImage(200, 150, QImage.Format.Format_ARGB32)
            image.fill(QColor("red"))
            controller.set_image(image)
            controller.set_placement(Placement(250, 225, 200, 150))
            controller.panel.hide()
            QTest.qWait(200)
            self.click_center(canvas)
            self.assertEqual(canvas.clicks, 0, "Editing must intercept the same point first")
            controller.set_tracing(True)
            QTest.qWait(200)
            overlay = controller.overlays[0]
            style = self.api.get_style(int(overlay.winId()))
            self.assertTrue(style & self.api.WS_EX_TRANSPARENT)
            self.assertTrue(style & self.api.WS_EX_LAYERED)
            self.assertTrue(style & self.api.WS_EX_NOACTIVATE)
            self.click_center(canvas)
            self.assertEqual(canvas.clicks, 1)
            controller.set_tracing(False)
            self.assertFalse(self.api.get_style(int(overlay.winId())) & self.api.WS_EX_TRANSPARENT)
            self.click_center(canvas)
            self.assertEqual(canvas.clicks, 1, "Returning to editing must intercept input again")
            controller.shutdown()

    def test_hotkey_dispatch_conflict_and_cleanup(self):
        import ctypes

        fired = []
        manager = HotkeyManager(APP, {"toggle_tracing": lambda: fired.append("trace")}, self.api)
        manager.start()
        self.addCleanup(manager.close)
        self.assertIn("toggle_tracing", manager.registered, manager.errors)
        conflict = HotkeyManager(APP, {"toggle_tracing": lambda: None}, self.api, id_base=0x6200)
        conflict.start()
        self.addCleanup(conflict.close)
        self.assertTrue(conflict.errors)
        thread = ctypes.windll.kernel32.GetCurrentThreadId()
        self.api.user32.PostThreadMessageW(thread, 0x0312, manager.registered["toggle_tracing"], 0)
        QTest.qWait(100)
        self.assertEqual(fired, ["trace"])
        manager.close()
        conflict.close()
        retry = HotkeyManager(APP, {"toggle_tracing": lambda: None}, self.api)
        retry.start()
        self.addCleanup(retry.close)
        self.assertFalse(retry.errors)


if __name__ == "__main__":
    unittest.main()

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen" if os.name != "nt" else "windows")

from PySide6.QtCore import QPoint, QRect, QSettings, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from screen_overlay.app import Controller
from screen_overlay.geometry import Placement

APP = QApplication.instance() or QApplication([])


class GuiTests(unittest.TestCase):
    def test_visible_panel_is_raised_after_each_input_mode_transition(self):
        from unittest.mock import patch

        with patch.object(self.c.panel, "raise_") as raised:
            self.c.set_tracing(True)
            raised.assert_called()
            raised.reset_mock()
            self.c.set_tracing(False)
            raised.assert_called()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        settings = QSettings(str(Path(self.temp.name) / "settings.ini"), QSettings.Format.IniFormat)
        self.c = Controller(APP, settings=settings, enable_native=False)
        self.addCleanup(self.c.shutdown)
        self.image = QImage(200, 100, QImage.Format.Format_ARGB32)
        self.image.fill(QColor("#ff0000"))
        self.c.set_image(self.image, "Тестовый рисунок")
        self.c.set_placement(Placement(200, 200, 200, 100))
        APP.processEvents()

    def render_overlay(self):
        overlay = self.c.overlays[0]
        image = QImage(overlay.size(), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        overlay.render(painter, QPoint())
        painter.end()
        return image

    def test_opacity_is_only_on_image_and_background_is_clear(self):
        self.c.set_opacity(50)
        self.c.set_tracing(True)
        rendered = self.render_overlay()
        origin = self.c.overlays[0].pos()
        self.assertEqual(rendered.pixelColor(10, 10).alpha(), 0)
        color = rendered.pixelColor(200 - origin.x(), 200 - origin.y())
        self.assertAlmostEqual(color.alpha(), 128, delta=1)
        self.assertEqual(color.red(), 255)
        self.assertEqual(self.c.panel.windowOpacity(), 1)

    def test_empty_alpha_image_and_zero_opacity_still_have_edit_handles(self):
        self.image.fill(Qt.GlobalColor.transparent)
        self.c.set_image(self.image)
        self.c.set_placement(Placement(200, 200, 200, 100))
        self.c.set_opacity(0)
        self.c.set_tracing(False)
        pixel = self.render_overlay().pixelColor(100, 150)
        self.assertGreater(pixel.alpha(), 200)

    def test_panel_width_free_and_aspect_locked_height(self):
        self.c.panel.aspect_check.setChecked(False)
        self.c.panel.width_spin.setValue(400)
        self.assertEqual(self.c.placement.width, 400)
        self.assertEqual(self.c.placement.height, 100)
        self.c.panel.aspect_check.setChecked(True)
        self.c.panel.height_spin.setValue(200)
        self.assertEqual(self.c.placement.width, 800)
        self.assertEqual(self.c.placement.height, 200)

    def test_drag_and_arrow_nudge_change_shared_geometry(self):
        overlay = self.c.overlays[0]
        self.c.panel.hide()
        origin = overlay.pos()
        start = QPoint(200 - origin.x(), 200 - origin.y())
        QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(overlay, start + QPoint(30, 20))
        QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=start + QPoint(30, 20))
        self.assertAlmostEqual(self.c.placement.center_x, 230)
        self.assertAlmostEqual(self.c.placement.center_y, 220)
        QTest.keyClick(overlay, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(self.c.placement.center_x, 240)

    def test_trace_and_visibility_toggle_have_recovery(self):
        for _ in range(5):
            self.c.toggle_tracing()
            self.assertTrue(all(o.tracing == self.c.tracing for o in self.c.overlays))
        self.c.toggle_visibility()
        self.assertTrue(all(not o.isVisible() for o in self.c.overlays))
        self.c.toggle_visibility()
        self.assertTrue(all(o.isVisible() for o in self.c.overlays))
        self.c.show_panel()
        self.assertTrue(self.c.panel.isVisible())

    def test_failed_load_retains_image_and_placement(self):
        old = self.c.placement
        self.c.open_path(Path(self.temp.name) / "not-here.png")
        self.assertEqual(self.c.placement, old)
        self.assertEqual(self.c.image.size(), self.image.size())
        self.assertTrue(self.c.panel.message_label.text())

    def test_failed_placement_of_new_image_retains_previous_reference(self):
        image = QImage(16384, 1, QImage.Format.Format_ARGB32)
        image.fill(QColor("red"))
        path = Path(self.temp.name) / "too-thin.png"
        image.save(str(path))
        old = self.c.placement
        self.c.open_path(path)
        self.assertEqual(self.c.placement, old)
        self.assertEqual(self.c.image.size(), self.image.size())

    def test_partial_native_mode_failure_hides_and_recovers_consistently(self):
        from screen_overlay.overlay import OverlayWindow

        second = OverlayWindow(APP.screens()[0])
        self.c.overlays.append(second)

        class RefusingNative:
            fail = True

            def set_click_through(self, hwnd, enabled):
                if self.fail and enabled:
                    raise OSError("Simulated native failure")

        native = RefusingNative()
        second.native = native
        self.c.set_tracing(True)
        self.assertFalse(self.c.tracing)
        self.assertTrue(all(not o.isVisible() for o in self.c.overlays))
        self.assertTrue(all(not o.tracing for o in self.c.overlays))
        native.fail = False
        self.c.toggle_visibility()
        self.assertTrue(all(o.isVisible() for o in self.c.overlays))
        self.assertTrue(all(not o.tracing for o in self.c.overlays))

    def test_offscreen_project_is_recentered(self):
        from screen_overlay.project import ReferenceProject, save_project

        path = Path(self.temp.name) / "ref.screenref"
        save_project(path, ReferenceProject(self.image, Placement(-99999, -99999, 100, 50)))
        self.c.open_path(path)
        rect = QRect(*map(round, self.c.placement.bounds()))
        self.assertTrue(any(rect.intersects(s.geometry()) for s in APP.screens()))

    def test_reset_and_project_roundtrip(self):
        path = Path(self.temp.name) / "ref.screenref"
        self.c.flip_x = True
        self.c.set_placement(replace(self.c.placement, rotation=31))
        self.c.save_to(path)
        self.c.reset_transform()
        self.assertFalse(self.c.flip_x)
        self.assertEqual(self.c.placement.rotation, 0)
        self.c.open_path(path)
        self.assertTrue(self.c.flip_x)
        self.assertEqual(self.c.placement.rotation, 31)

    def test_shutdown_closes_every_overlay_and_is_idempotent(self):
        overlays = self.c.overlays[:]
        self.c.shutdown()
        self.c.shutdown()
        self.assertTrue(all(not o.isVisible() for o in overlays))
        self.assertFalse(self.c.panel.isVisible())


if __name__ == "__main__":
    unittest.main()

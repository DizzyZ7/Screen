import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen" if os.name != "nt" else "windows")

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from screen_overlay.geometry import Placement
from screen_overlay.project import ReferenceProject, load_project, save_project

APP = QApplication.instance() or QApplication([])


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "этюд.screenref"
        image = QImage(100, 50, QImage.Format.Format_ARGB32)
        image.fill(QColor(100, 120, 200, 96))
        self.project = ReferenceProject(
            image, Placement(-100, 250, 300, 150, 45), 0.35, True, False, False
        )

    def test_roundtrip_embeds_image_and_all_transform_settings(self):
        save_project(self.path, self.project)
        loaded = load_project(self.path)
        self.assertEqual(loaded.placement, self.project.placement)
        self.assertEqual(loaded.opacity, 0.35)
        self.assertTrue(loaded.flip_x)
        self.assertFalse(loaded.keep_aspect)
        self.assertEqual(loaded.image.pixelColor(1, 1), self.project.image.pixelColor(1, 1))

    def test_rejects_invalid_schema_numbers_boolean_and_base64(self):
        save_project(self.path, self.project)
        valid = json.loads(self.path.read_text())
        for field, value in [
            ("version", 99),
            ("opacity", float("nan")),
            ("flip_x", "yes"),
            ("image_png", "broken!"),
        ]:
            bad = dict(valid, **{field: value})
            self.path.write_text(json.dumps(bad))
            with self.assertRaises(ValueError, msg=field):
                load_project(self.path)
        bad = dict(valid, placement=dict(valid["placement"], width=True))
        self.path.write_text(json.dumps(bad))
        with self.assertRaises(ValueError):
            load_project(self.path)

    def test_failed_save_does_not_truncate_existing_project(self):
        save_project(self.path, self.project)
        original = self.path.read_bytes()
        bad = ReferenceProject(self.project.image, self.project.placement, 2.0)
        with self.assertRaises(ValueError):
            save_project(self.path, bad)
        self.assertEqual(self.path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()

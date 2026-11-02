import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen" if os.name != "nt" else "windows")

from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from screen_overlay.images import clipboard_image, load_image

APP = QApplication.instance() or QApplication([])


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "рисунок.png"
        self.image = QImage(128, 64, QImage.Format.Format_ARGB32)
        self.image.fill(QColor(255, 0, 0, 90))
        self.assertTrue(self.image.save(str(self.path)))

    def test_file_preserves_alpha_and_unicode_path(self):
        image = load_image(self.path)
        self.assertEqual(image.size(), self.image.size())
        self.assertEqual(image.pixelColor(0, 0).alpha(), 90)

    def test_clipboard_image_and_copied_local_file(self):
        mime = QMimeData()
        mime.setImageData(self.image)
        self.assertEqual(clipboard_image(mime).size(), self.image.size())
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(self.path))])
        self.assertEqual(clipboard_image(mime).size(), self.image.size())

    def test_remote_url_is_not_silently_downloaded(self):
        mime = QMimeData()
        mime.setUrls([QUrl("https://example.com/image.png")])
        with self.assertRaisesRegex(ValueError, "изображение"):
            clipboard_image(mime)

    def test_corrupt_missing_and_oversized_files(self):
        self.path.write_text("not an image")
        with self.assertRaises(ValueError):
            load_image(self.path)
        with self.assertRaises(ValueError):
            load_image(self.path.with_name("missing.png"))
        # A valid header with an excessive declared allocation must be rejected before decoding.
        import struct
        import zlib

        header = struct.pack(">IIBBBBB", 16384, 16384, 8, 6, 0, 0, 0)
        self.path.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + struct.pack(">I", len(header))
            + b"IHDR"
            + header
            + struct.pack(">I", zlib.crc32(b"IHDR" + header))
        )
        with self.assertRaises(ValueError):
            load_image(self.path)


if __name__ == "__main__":
    unittest.main()

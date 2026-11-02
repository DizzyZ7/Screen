import argparse
import json
import sys
import tempfile
import traceback
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QMessageBox

from screen_overlay import __version__
from screen_overlay.app import Controller


def main():
    parser = argparse.ArgumentParser(description="Screen — картинка поверх холста для обводки.")
    parser.add_argument("image", nargs="?", help="Файл картинки или проект .screenref")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--smoke-report", help=argparse.SUPPRESS)
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Screen")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("DizzyZ7")
    app.setQuitOnLastWindowClosed(False)
    # Smoke tests must not load or change the user's saved preferences.
    temp = tempfile.TemporaryDirectory() if args.smoke_test else None
    settings = (
        QSettings(str(Path(temp.name) / "smoke.ini"), QSettings.Format.IniFormat) if temp else None
    )
    controller = Controller(app, settings=settings)
    app.setWindowIcon(controller.icon)

    def on_exception(exc_type, exc, tb):
        controller.image_visible = False
        controller.refresh()
        if args.smoke_test:
            smoke_finish(False, "".join(traceback.format_exception(exc_type, exc, tb)))
        else:
            controller.show_error(f"Ошибка: {exc}. Картинка скрыта; можно открыть ее заново.")

    sys.excepthook = on_exception

    def smoke_finish(ok, error=""):
        if args.smoke_report:
            Path(args.smoke_report).write_text(
                json.dumps({"ok": ok, "error": error}), encoding="utf-8"
            )
        controller.shutdown()
        app.exit(0 if ok else 1)

    def smoke():
        try:
            image = QImage(160, 100, QImage.Format.Format_ARGB32)
            image.fill(QColor("#609bdc"))
            app.clipboard().setImage(image)
            controller.paste()
            assert controller.image.size() == image.size()
            controller.set_opacity(40)
            for _ in range(3):
                controller.set_tracing(True)
                assert controller.tracing and all(w.tracing for w in controller.overlays)
                controller.set_tracing(False)
            path = Path(temp.name) / "test.screenref"
            controller.save_to(path)
            controller.open_path(path)
            assert controller.opacity == 0.4
            controller.toggle_visibility()
            assert all(not w.isVisible() for w in controller.overlays)
            controller.toggle_visibility()
            assert all(w.isVisible() for w in controller.overlays)
            if controller.hotkeys:
                assert not controller.hotkeys.errors, controller.hotkeys.errors
            smoke_finish(True)
        except Exception:
            smoke_finish(False, traceback.format_exc())

    if args.image:
        controller.open_path(args.image)
    if args.smoke_test:
        QTimer.singleShot(150, smoke)
        QTimer.singleShot(15000, lambda: smoke_finish(False, "Smoke test timed out."))
    elif sys.platform != "win32":
        controller.panel.message_label.setText(
            "Это среда разработки. Полный режим со сквозными "
            "кликами и глобальными клавишами рассчитан на Windows."
        )
    result = app.exec()
    controller.shutdown()
    if temp:
        temp.cleanup()
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        app = QApplication.instance() or QApplication([])
        QMessageBox.critical(None, "Screen", f"Не удалось запустить Screen: {error}")
        raise SystemExit(1) from error

"""PyInstaller entry point; all application code remains in screen_overlay."""

from screen_overlay.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())

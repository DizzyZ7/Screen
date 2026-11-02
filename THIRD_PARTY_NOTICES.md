# Third-party components in Screen

Screen uses Qt 6 / Qt for Python (PySide6 Essentials and Shiboken6),
copyright The Qt Company Ltd. and other Qt contributors. The LGPLv3
licensing option applies to these unmodified shared libraries. Full copies
of LGPLv3 and GPLv3 accompany the portable build under `licenses/`.

- Qt / Qt for Python licensing: https://doc.qt.io/qtforpython-6/commercial/index.html
- Qt source and per-component notices: https://code.qt.io/cgit/qt/qtbase.git/
- Qt image format plugins and their notices: https://code.qt.io/cgit/qt/qtimageformats.git/
- PySide6 / Shiboken6 source: https://code.qt.io/cgit/pyside/pyside-setup.git/
- Exact Qt/PySide version: 6.12.0 (see the matching upstream tag and `requirements.txt`).

Qt DLLs and Python bindings are dynamically loaded from the portable
`_internal/` directory. They may be replaced with compatible modified
versions. Reverse engineering for debugging modifications to these LGPL
components is permitted. No Qt/PySide source has been modified by Screen.
Application code and rebuilding instructions are available in the Screen
repository: https://github.com/DizzyZ7/Screen .

The Windows bundle also contains the Python runtime (Python Software
Foundation license) and a PyInstaller bootloader (GPL with its bootloader
exception). Build-time package metadata and available license files are
copied to `licenses/` by `scripts/collect_notices.py`. Other components retain
their upstream notices and licenses, including the notices within the Qt
source repositories above.

These notices do not assign a new license to Screen's own source code.

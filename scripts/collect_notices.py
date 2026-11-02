"""Include license material available in the build runtime without runtime downloads."""

import importlib.metadata
import shutil
import sys
from pathlib import Path

destination = Path(sys.argv[1])
destination.mkdir(parents=True, exist_ok=True)
for package in ("PySide6-Essentials", "shiboken6", "pyinstaller", "altgraph"):
    dist = importlib.metadata.distribution(package)
    folder = destination / package
    folder.mkdir(exist_ok=True)
    metadata = dist.read_text("METADATA")
    if metadata:
        (folder / "METADATA.txt").write_text(metadata, encoding="utf-8")
    for relative in dist.files or []:
        if any(word in str(relative).lower() for word in ("license", "copying", "notice")):
            source = Path(dist.locate_file(relative))
            if source.is_file():
                target = folder / str(relative).replace("/", "_").replace("\\", "_")
                shutil.copyfile(source, target)
for base in (Path(sys.base_prefix), Path(sys.executable).parent):
    source = base / "LICENSE.txt"
    if source.is_file():
        shutil.copyfile(source, destination / "Python-LICENSE.txt")
        break

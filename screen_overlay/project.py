"""Versioned, self-contained reference projects; saves are atomic."""

import base64
import binascii
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QSaveFile
from PySide6.QtGui import QImage

from .geometry import Placement, finite
from .images import MAX_FILE_BYTES, image_from_bytes, validate_image


@dataclass(frozen=True)
class ReferenceProject:
    image: QImage
    placement: Placement
    opacity: float = 0.5
    flip_x: bool = False
    flip_y: bool = False
    keep_aspect: bool = True


def _settings(opacity, flip_x, flip_y, keep_aspect):
    if not 0 <= finite(opacity) <= 1:
        raise ValueError("Непрозрачность должна быть от 0 до 100%.")
    if any(type(v) is not bool for v in (flip_x, flip_y, keep_aspect)):
        raise ValueError("Поврежденные настройки отражения или пропорций.")


def save_project(path: str | Path, project: ReferenceProject):
    _settings(project.opacity, project.flip_x, project.flip_y, project.keep_aspect)
    image = validate_image(project.image)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise ValueError("Не удалось сохранить изображение в проект.")
    payload = json.dumps(
        {
            "version": 1,
            "placement": asdict(project.placement),
            "opacity": project.opacity,
            "flip_x": project.flip_x,
            "flip_y": project.flip_y,
            "keep_aspect": project.keep_aspect,
            "image_png": base64.b64encode(bytes(buffer.data())).decode("ascii"),
        },
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    if len(payload) > MAX_FILE_BYTES:
        raise ValueError("Проект превышает 64 МБ. Уменьши исходную картинку.")
    file = QSaveFile(str(path))
    if not file.open(QIODevice.OpenModeFlag.WriteOnly):
        raise ValueError("Не удалось создать проект. Проверь папку и права доступа.")
    if file.write(payload) != len(payload):
        file.cancelWriting()
        raise ValueError("Не удалось записать проект. Проверь свободное место.")
    if not file.commit():
        raise ValueError("Не удалось завершить сохранение проекта.")


def load_project(path: str | Path) -> ReferenceProject:
    try:
        path = Path(path)
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("Проект превышает 64 МБ.")
        # Read with a bound even if the file grows after stat().
        with path.open("rb") as file:
            raw = file.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            raise ValueError("Проект превышает 64 МБ.")
        data = json.loads(raw)
        if (
            not isinstance(data, dict)
            or type(data.get("version")) is not int
            or data["version"] != 1
        ):
            raise ValueError("Эта версия проекта не поддерживается.")
        placement = Placement(**data["placement"])
        _settings(data["opacity"], data["flip_x"], data["flip_y"], data["keep_aspect"])
        image = image_from_bytes(base64.b64decode(data["image_png"], validate=True))
        return ReferenceProject(
            image, placement, data["opacity"], data["flip_x"], data["flip_y"], data["keep_aspect"]
        )
    except (OSError, KeyError, TypeError, UnicodeError, binascii.Error, RecursionError) as exc:
        raise ValueError("Не удалось открыть проект: файл поврежден или недоступен.") from exc
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"Не удалось открыть проект: {exc}") from exc

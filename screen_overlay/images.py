"""Local-only image loading. No clipboard URLs are fetched over the network."""

from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QMimeData
from PySide6.QtGui import QImage, QImageReader, QPixmap

MAX_PIXELS = 32_000_000
MAX_SIDE = 16384
MAX_FILE_BYTES = 64 * 1024 * 1024
QImageReader.setAllocationLimit(256)


def validate_image(image: QImage) -> QImage:
    if image.isNull():
        raise ValueError("Не удалось прочитать изображение. Выбери PNG, JPEG, WebP, BMP или TIFF.")
    _check_size(image.width(), image.height())
    # Clipboard images may have a screen-dependent DPR. Placement uses explicit logical sizes.
    result = image.copy()
    result.setDevicePixelRatio(1)
    return result


def _check_size(width: int, height: int):
    if width <= 0 or height <= 0 or width * height > MAX_PIXELS or max(width, height) > MAX_SIDE:
        raise ValueError("Слишком большое изображение: максимум 32 Мп и 16384 px по стороне.")


def _read(reader: QImageReader) -> QImage:
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid():
        _check_size(size.width(), size.height())
    return validate_image(reader.read())


def load_image(path: str | Path) -> QImage:
    path = Path(path)
    try:
        if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("Файл отсутствует или превышает 64 МБ.")
        return _read(QImageReader(str(path)))
    except OSError as exc:
        raise ValueError("Не удалось открыть файл изображения.") from exc


def image_from_bytes(data: bytes) -> QImage:
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Данные изображения превышают 64 МБ.")
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    return _read(QImageReader(buffer))


def clipboard_image(mime: QMimeData) -> QImage:
    if mime.hasImage():
        data = mime.imageData()
        if isinstance(data, QPixmap):
            data = data.toImage()
        if isinstance(data, QImage):
            return validate_image(data)
    if mime.hasUrls():
        urls = mime.urls()
        if urls and urls[0].isLocalFile():
            return load_image(urls[0].toLocalFile())
    raise ValueError(
        "В буфере нет картинки. В браузере выбери «Копировать изображение», "
        "затем нажми Ctrl+V в панели Screen."
    )

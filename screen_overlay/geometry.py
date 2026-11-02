"""Geometry in Qt's global logical pixels, independent of the GUI toolkit."""

from dataclasses import asdict, dataclass, replace
from math import cos, isfinite, radians, sin

MIN_SIZE = 24.0
MAX_SIZE = 16384.0
HANDLES = ("nw", "n", "ne", "e", "se", "s", "sw", "w")


def finite(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("Ожидалось конечное число.")
    return float(value)


def bounded_size(value: float) -> float:
    return max(MIN_SIZE, min(MAX_SIZE, finite(value)))


@dataclass(frozen=True)
class Placement:
    center_x: float
    center_y: float
    width: float
    height: float
    rotation: float = 0.0

    def __post_init__(self):
        for name, value in asdict(self).items():
            finite(value)
            if name in ("center_x", "center_y") and abs(value) > 10_000_000:
                raise ValueError("Слишком большие координаты изображения.")
        if not (MIN_SIZE <= self.width <= MAX_SIZE and MIN_SIZE <= self.height <= MAX_SIZE):
            raise ValueError(f"Размер должен быть от {int(MIN_SIZE)} до {int(MAX_SIZE)} px.")
        object.__setattr__(self, "rotation", (self.rotation + 180) % 360 - 180)

    def local_to_world(self, x: float, y: float) -> tuple[float, float]:
        c, s = cos(radians(self.rotation)), sin(radians(self.rotation))
        return self.center_x + c * x - s * y, self.center_y + s * x + c * y

    def world_to_local(self, x: float, y: float) -> tuple[float, float]:
        c, s = cos(radians(self.rotation)), sin(radians(self.rotation))
        dx, dy = x - self.center_x, y - self.center_y
        return c * dx + s * dy, -s * dx + c * dy

    def moved(self, dx: float, dy: float) -> "Placement":
        return replace(
            self, center_x=self.center_x + finite(dx), center_y=self.center_y + finite(dy)
        )

    def zoom_at(self, factor: float, x: float, y: float) -> "Placement":
        finite(x)
        finite(y)
        factor = finite(factor)
        if factor <= 0:
            raise ValueError("Масштаб должен быть положительным.")
        factor = max(
            max(MIN_SIZE / self.width, MIN_SIZE / self.height),
            min(min(MAX_SIZE / self.width, MAX_SIZE / self.height), factor),
        )
        return replace(
            self,
            width=bounded_size(self.width * factor),
            height=bounded_size(self.height * factor),
            center_x=x + (self.center_x - x) * factor,
            center_y=y + (self.center_y - y) * factor,
        )

    def with_size(self, width: float, height: float) -> "Placement":
        return replace(self, width=bounded_size(width), height=bounded_size(height))

    def with_width(self, width: float, keep_aspect: bool) -> "Placement":
        if keep_aspect:
            return self.zoom_at(bounded_size(width) / self.width, self.center_x, self.center_y)
        return self.with_size(width, self.height)

    def with_height(self, height: float, keep_aspect: bool) -> "Placement":
        if keep_aspect:
            return self.zoom_at(bounded_size(height) / self.height, self.center_x, self.center_y)
        return self.with_size(self.width, height)

    def handle_positions(self) -> dict[str, tuple[float, float]]:
        return {
            h: self.local_to_world(
                (1 if "e" in h else -1 if "w" in h else 0) * self.width / 2,
                (1 if "s" in h else -1 if "n" in h else 0) * self.height / 2,
            )
            for h in HANDLES
        }

    def resized(self, handle: str, x: float, y: float, keep_aspect: bool) -> "Placement":
        if handle not in HANDLES:
            raise ValueError("Неизвестная ручка размера.")
        finite(x)
        finite(y)
        sx = 1 if "e" in handle else -1 if "w" in handle else 0
        sy = 1 if "s" in handle else -1 if "n" in handle else 0
        ax, ay = -sx * self.width / 2, -sy * self.height / 2
        lx, ly = self.world_to_local(x, y)
        raw_w = sx * (lx - ax) if sx else self.width
        raw_h = sy * (ly - ay) if sy else self.height
        if keep_aspect:
            if sx and sy:
                factor = (raw_w * self.width + raw_h * self.height) / (
                    self.width**2 + self.height**2
                )
            else:
                factor = raw_w / self.width if sx else raw_h / self.height
            factor = max(
                max(MIN_SIZE / self.width, MIN_SIZE / self.height),
                min(min(MAX_SIZE / self.width, MAX_SIZE / self.height), factor),
            )
            w, h = bounded_size(self.width * factor), bounded_size(self.height * factor)
        else:
            w, h = bounded_size(raw_w), bounded_size(raw_h)
        # Use the OLD transform to keep the opposite corner/edge midpoint fixed.
        cx, cy = self.local_to_world(ax + sx * w / 2, ay + sy * h / 2)
        return replace(self, center_x=cx, center_y=cy, width=w, height=h)

    def bounds(self) -> tuple[float, float, float, float]:
        pts = [
            self.local_to_world(x * self.width / 2, y * self.height / 2)
            for x in (-1, 1)
            for y in (-1, 1)
        ]
        xs, ys = zip(*pts, strict=True)
        return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)

    @classmethod
    def fit(cls, width: float, height: float, screen: tuple[int, int, int, int]) -> "Placement":
        width, height = finite(width), finite(height)
        if width <= 0 or height <= 0:
            raise ValueError("Изображение пустое.")
        x, y, sw, sh = screen
        factor = min(sw * 0.8 / width, sh * 0.8 / height, 1.0)
        factor = max(factor, MIN_SIZE / width, MIN_SIZE / height)
        if max(width, height) / min(width, height) > MAX_SIZE / MIN_SIZE:
            raise ValueError(
                "Слишком узкое изображение для этих пределов размера. "
                "Добавь поля к картинке перед открытием."
            )
        return cls(
            x + sw / 2, y + sh / 2, bounded_size(width * factor), bounded_size(height * factor)
        )

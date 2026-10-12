"""Базовые структуры: маски/патчи фигур, рисование масок с суперсэмплингом, композитинг."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw


@dataclass
class Mask:
    """Альфа-маска фигуры (L) и положение её левого верхнего угла на холсте."""
    img: Image.Image
    x: int
    y: int

    @property
    def area(self) -> int:
        return self.img.size[0] * self.img.size[1]


@dataclass
class Patch:
    """Фрагмент RGBA с положением на холсте. mode: 'normal' (alpha-over) или 'add' (аддитивно)."""
    img: Image.Image
    x: int
    y: int
    mode: str = "normal"


class MaskCanvas:
    """Рисование маски фигуры в абсолютных координатах холста с антиалиасингом (суперсэмплинг)."""

    def __init__(self, W: int, H: int, bbox: tuple[float, float, float, float]):
        self.x0 = max(0, int(math.floor(bbox[0])) - 1)
        self.y0 = max(0, int(math.floor(bbox[1])) - 1)
        self.x1 = min(W, int(math.ceil(bbox[2])) + 1)
        self.y1 = min(H, int(math.ceil(bbox[3])) + 1)
        self.w = self.x1 - self.x0
        self.h = self.y1 - self.y0
        self.empty = self.w <= 0 or self.h <= 0
        if self.empty:
            return
        area = self.w * self.h
        self.k = 4 if area < 1_000_000 else 3 if area < 4_000_000 else 2
        self.img = Image.new("L", (self.w * self.k, self.h * self.k), 0)
        self.d = ImageDraw.Draw(self.img)

    def _t(self, pts):
        k = self.k
        return [((x - self.x0) * k, (y - self.y0) * k) for x, y in pts]

    def polygon(self, pts, value: int = 255):
        self.d.polygon(self._t(pts), fill=value)

    def ellipse(self, cx, cy, rx, ry, value: int = 255):
        (x0, y0), (x1, y1) = self._t([(cx - rx, cy - ry), (cx + rx, cy + ry)])
        self.d.ellipse([x0, y0, x1, y1], fill=value)

    def line(self, p0, p1, width: float, value: int = 255, round_caps: bool = True):
        a, b = self._t([p0, p1])
        self.d.line([a, b], fill=value, width=max(1, int(round(width * self.k))))
        if round_caps:
            r = width / 2
            self.ellipse(p0[0], p0[1], r, r, value)
            self.ellipse(p1[0], p1[1], r, r, value)

    def finish(self) -> Mask | None:
        if self.empty:
            return None
        small = self.img.resize((self.w, self.h), Image.BOX)
        if small.getbbox() is None:
            return None
        return Mask(small, self.x0, self.y0)


def expanded_alpha(patch: Patch, pad: int) -> tuple[Image.Image, int, int]:
    """Альфа-канал патча, дополненный прозрачным полем pad px. Возвращает (L, x, y)."""
    a = patch.img.getchannel("A")
    out = Image.new("L", (a.size[0] + 2 * pad, a.size[1] + 2 * pad), 0)
    out.paste(a, (pad, pad))
    return out, patch.x - pad, patch.y - pad


def mean_color(patch: Patch) -> tuple[int, int, int]:
    """Средний цвет патча, взвешенный по альфе."""
    arr = np.asarray(patch.img, dtype=np.float32)
    a = arr[..., 3]
    total = float(a.sum())
    if total <= 0:
        return 255, 255, 255
    rgb = (arr[..., :3] * a[..., None]).sum(axis=(0, 1)) / total
    return int(rgb[0]), int(rgb[1]), int(rgb[2])


def composite(canvas: Image.Image, patch: Patch) -> None:
    """Накладывает патч на RGBA-холст (с обрезкой по границам)."""
    W, H = canvas.size
    pw, ph = patch.img.size
    x0, y0 = max(patch.x, 0), max(patch.y, 0)
    x1, y1 = min(patch.x + pw, W), min(patch.y + ph, H)
    if x1 <= x0 or y1 <= y0:
        return
    sub = patch.img.crop((x0 - patch.x, y0 - patch.y, x1 - patch.x, y1 - patch.y))
    if patch.mode == "add":
        region = np.asarray(canvas.crop((x0, y0, x1, y1)), dtype=np.float32)
        p = np.asarray(sub, dtype=np.float32)
        region[..., :3] += p[..., :3] * (p[..., 3:4] / 255.0)
        np.clip(region, 0, 255, out=region)
        canvas.paste(Image.fromarray(region.astype(np.uint8), "RGBA"), (x0, y0))
    else:
        canvas.alpha_composite(sub, (x0, y0))

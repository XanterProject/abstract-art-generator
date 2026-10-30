"""Художественные эффекты: глитч, калейдоскоп, лучи света, рябь, полутон, дуотон, контур."""
import numpy as np
from PIL import Image, ImageFilter

from palettes import parse_color
from patch import Patch, expanded_alpha, mean_color
from registry import SCOPE_ELEMENT, SCOPE_GLOBAL, register_effect


def _to_img(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def _remap(arr: np.ndarray, sx: np.ndarray, sy: np.ndarray) -> np.ndarray:
    """Билинейная выборка arr (H, W, 3) в точках (sx, sy); за границами — крайние пиксели."""
    h, w = arr.shape[:2]
    flat = arr.reshape(-1, arr.shape[2])
    out = np.empty(sx.shape + (arr.shape[2],), dtype=np.float32)
    # полосами по строкам: плоский индекс + np.take быстрее fancy-индексации, а временные массивы малы
    for i in range(0, sx.shape[0], 64):
        cx = np.clip(sx[i:i + 64], 0, w - 1.001)
        cy = np.clip(sy[i:i + 64], 0, h - 1.001)
        x0 = cx.astype(np.int32)
        y0 = cy.astype(np.int32)
        fx = (cx - x0)[..., None]
        fy = (cy - y0)[..., None]
        idx = y0 * w + x0
        p00 = np.take(flat, idx, axis=0)
        p01 = np.take(flat, idx + 1, axis=0)
        p10 = np.take(flat, idx + w, axis=0)
        p11 = np.take(flat, idx + (w + 1), axis=0)
        p00 += (p01 - p00) * fx
        p10 += (p11 - p10) * fx
        p00 += (p10 - p00) * fy
        out[i:i + 64] = p00
    return out


def _grid(w: int, h: int):
    return np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))


@register_effect("glitch", SCOPE_GLOBAL)
def glitch(img, rng, unit, slices=14, max_shift=60.0, channel_shift=8.0):
    """Цифровой сбой: горизонтальные полосы сдвигаются, цветовые каналы расходятся."""
    arr = np.asarray(img).copy()
    h, w = arr.shape[:2]
    for _ in range(max(int(slices), 0)):
        sh = max(int(rng.uniform(0.005, 0.06) * h), 1)
        y = int(rng.integers(0, max(h - sh, 1)))
        dx = int(rng.uniform(-1, 1) * max_shift * unit)
        arr[y:y + sh] = np.roll(arr[y:y + sh], dx, axis=1)
        if rng.random() < 0.4:
            c = int(rng.integers(0, 3))
            arr[y:y + sh, :, c] = np.roll(arr[y:y + sh, :, c], int(channel_shift * unit * 2), axis=1)
    s = int(round(channel_shift * unit))
    if s:
        arr[..., 0] = np.roll(arr[..., 0], s, axis=1)
        arr[..., 2] = np.roll(arr[..., 2], -s, axis=1)
    return Image.fromarray(arr, "RGB")


@register_effect("kaleidoscope", SCOPE_GLOBAL)
def kaleidoscope(img, rng, unit, segments=6, rotation=0.0, zoom=1.0):
    """Калейдоскоп: сектор исходного изображения зеркально повторяется вокруг центра."""
    arr = np.asarray(img, dtype=np.float32)
    h, w = arr.shape[:2]
    xs, ys = _grid(w, h)
    cx, cy = w / 2.0, h / 2.0
    dx, dy = xs - cx, ys - cy
    r = np.hypot(dx, dy)
    seg = np.float32(np.pi / max(int(segments), 1))  # полуширина сектора
    rot = np.float32(np.radians(rotation))
    a = np.arctan2(dy, dx) - rot
    a = np.abs(((a + seg) % (2 * seg)) - seg) + rot   # зеркальное сворачивание
    r = r / max(zoom, 0.1)
    return _to_img(_remap(arr, cx + r * np.cos(a), cy + r * np.sin(a)))


@register_effect("light_rays", SCOPE_GLOBAL)
def light_rays(img, rng, unit, threshold=150.0, length=0.6, intensity=0.8, x=-1.0, y=-1.0):
    """Лучи света из точки (x, y в долях 0..1; отрицательное значение — случайная точка)."""
    w, h = img.size
    px = float(x) if x >= 0 else rng.uniform(0.2, 0.8)
    py = float(y) if y >= 0 else rng.uniform(0.1, 0.5)
    k = 4
    sw, sh = max(w // k, 1), max(h // k, 1)
    small = np.asarray(img.resize((sw, sh), Image.Resampling.BILINEAR), dtype=np.float32)
    m = np.clip((small.mean(axis=2) - threshold) / max(255.0 - threshold, 1.0), 0, 1)[..., None]
    bright = Image.fromarray((small * m).astype(np.uint8), "RGB")
    cx, cy = px * sw, py * sh
    steps = 28
    acc = np.zeros((sh, sw, 3), dtype=np.float32)
    for i in range(1, steps + 1):
        s = 1.0 - (i / steps) * min(max(length, 0.05), 0.95)
        layer = bright.transform((sw, sh), Image.Transform.AFFINE,
                                 (s, 0, cx * (1 - s), 0, s, cy * (1 - s)), Image.Resampling.BILINEAR)
        acc += np.asarray(layer, dtype=np.float32) * (1.0 - i / (steps + 1))
    acc /= steps / 2.0
    rays = Image.fromarray(np.clip(acc, 0, 255).astype(np.uint8), "RGB").resize((w, h), Image.Resampling.BICUBIC)
    out = np.asarray(img, dtype=np.float32) + np.asarray(rays, dtype=np.float32) * intensity
    return _to_img(out)


@register_effect("ripple", SCOPE_GLOBAL)
def ripple(img, rng, unit, amplitude=14.0, wavelength=140.0, angle=0.0):
    """Волнистая рябь: синусоидальное смещение пикселей поперёк направления angle (градусы)."""
    arr = np.asarray(img, dtype=np.float32)
    h, w = arr.shape[:2]
    xs, ys = _grid(w, h)
    th = np.radians(angle)
    ux, uy = np.float32(np.cos(th)), np.float32(np.sin(th))
    phase = rng.uniform(0, 2 * np.pi)
    t = (xs * ux + ys * uy) * np.float32(2 * np.pi / max(wavelength * unit, 2.0)) + np.float32(phase)
    d = np.sin(t) * np.float32(amplitude * unit)
    return _to_img(_remap(arr, xs - uy * d, ys + ux * d))


@register_effect("halftone", SCOPE_GLOBAL)
def halftone(img, rng, unit, cell=18.0, mix=1.0, softness=0.35):
    """Полутон: изображение из круглых точек цвета ячейки, размер точки зависит от яркости."""
    w, h = img.size
    gw = max(int(round(w / max(cell * unit, 3.0))), 2)
    gh = max(int(round(h / max(cell * unit, 3.0))), 2)
    small = img.resize((gw, gh), Image.Resampling.BOX)
    cellcol = np.asarray(small.resize((w, h), Image.Resampling.NEAREST), dtype=np.float32)
    lum = np.asarray(small.convert("L").resize((w, h), Image.Resampling.NEAREST), dtype=np.float32) / 255.0
    xs, ys = _grid(w, h)
    fx = (xs * gw / w) % 1.0 - 0.5
    fy = (ys * gh / h) % 1.0 - 0.5
    dist = np.hypot(fx, fy)
    radius = 0.15 + 0.42 * np.sqrt(lum)
    edge = max(softness, 0.02) * 0.2
    dot = np.clip((radius - dist) / edge + 0.5, 0, 1)[..., None]
    out = cellcol * 0.12 * (1 - dot) + np.clip(cellcol * 1.15, 0, 255) * dot
    src = np.asarray(img, dtype=np.float32)
    return _to_img(src * (1 - mix) + out * mix)


@register_effect("duotone", SCOPE_GLOBAL)
def duotone(img, rng, unit, shadow="#1a0b3d", highlight="#ffb86b", amount=1.0):
    """Градиентная карта яркости: тени -> цвет shadow, света -> цвет highlight."""
    arr = np.asarray(img, dtype=np.float32)
    lum = (arr @ np.array([0.299, 0.587, 0.114], dtype=np.float32) / 255.0)[..., None]
    lo = np.array(parse_color(shadow), dtype=np.float32)
    hi = np.array(parse_color(highlight), dtype=np.float32)
    return _to_img(arr * (1 - amount) + (lo + (hi - lo) * lum) * amount)


@register_effect("outline", SCOPE_ELEMENT)
def outline(patch, rng, unit, width=5.0, opacity=0.9, color="auto"):
    """Контур вокруг фигуры. color='auto' — осветлённый цвет фигуры."""
    sigma = max(width * unit, 0.5)
    pad = int(sigma * 3) + 2
    a, x, y = expanded_alpha(patch, pad)
    grown = a.filter(ImageFilter.GaussianBlur(sigma / 2)).point(lambda v: 255 if v > 20 else 0)
    grown = grown.filter(ImageFilter.GaussianBlur(0.8))
    ring = np.clip(np.asarray(grown, dtype=np.float32) - np.asarray(a, dtype=np.float32), 0, 255) * opacity
    if color == "auto":
        r, g, b = mean_color(patch)
        rgb = tuple(int(c + (255 - c) * 0.55) for c in (r, g, b))
    else:
        rgb = parse_color(color)
    layer = Image.new("RGBA", a.size, tuple(rgb) + (0,))
    layer.putalpha(Image.fromarray(ring.astype(np.uint8), "L"))
    return [Patch(layer, x, y)]

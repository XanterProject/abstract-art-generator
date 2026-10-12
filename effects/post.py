"""Глобальные эффекты постобработки: размытие, зерно, виньетка, искажение, сдвиг оттенка, аберрация."""
import numpy as np
from PIL import Image, ImageFilter

from registry import SCOPE_GLOBAL, register_effect


@register_effect("blur", SCOPE_GLOBAL)
def blur(img, rng, unit, radius=4.0):
    return img.filter(ImageFilter.GaussianBlur(max(radius * unit, 0.1)))


@register_effect("grain", SCOPE_GLOBAL)
def grain(img, rng, unit, amount=0.05):
    """Монохромное плёночное зерно. amount ~ 0.02..0.15."""
    arr = np.asarray(img, dtype=np.float32)
    noise = rng.normal(0.0, amount * 255.0, arr.shape[:2]).astype(np.float32)[..., None]
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8), "RGB")


@register_effect("vignette", SCOPE_GLOBAL)
def vignette(img, rng, unit, strength=0.55, start=0.35):
    """Затемнение к краям. strength 0..1, start — с какого радиуса (0..1) начинается."""
    w, h = img.size
    xs = ((np.arange(w, dtype=np.float32) + 0.5) / w * 2 - 1)[None, :]
    ys = ((np.arange(h, dtype=np.float32) + 0.5) / h * 2 - 1)[:, None]
    r = np.sqrt(xs * xs + ys * ys) / np.float32(2 ** 0.5)
    t = np.clip((r - start) / max(1.0 - start, 1e-3), 0, 1)
    t = t * t * (3 - 2 * t)
    factor = (1.0 - strength * t)[..., None]
    out = np.asarray(img, dtype=np.float32) * factor
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")


@register_effect("warp", SCOPE_GLOBAL)
def warp(img, rng, unit, amount=40.0, cells=10):
    """Плавное «жидкое» искажение (сетка смещений + MESH-трансформация)."""
    w, h = img.size
    n = max(int(cells), 3)
    coarse = rng.uniform(-1, 1, (4, 4, 2))
    ts = np.linspace(0, 3, n + 1)
    i0 = np.minimum(ts.astype(int), 2)
    f = (ts - i0)[:, None]
    rows = coarse[i0] * (1 - f)[..., None] + coarse[i0 + 1] * f[..., None]       # (n+1, 4, 2)
    disp = rows[:, i0] * (1 - f.T)[..., None] + rows[:, i0 + 1] * f.T[..., None]  # (n+1, n+1, 2)
    disp = disp * amount * unit
    disp[0, :] = disp[-1, :] = 0
    disp[:, 0] = disp[:, -1] = 0
    xs = np.linspace(0, w, n + 1)
    ys = np.linspace(0, h, n + 1)
    mesh = []
    for j in range(n):
        for i in range(n):
            def src(ii, jj):
                return (float(xs[ii] + disp[jj, ii, 0]), float(ys[jj] + disp[jj, ii, 1]))
            quad = (*src(i, j), *src(i, j + 1), *src(i + 1, j + 1), *src(i + 1, j))
            mesh.append(((int(round(xs[i])), int(round(ys[j])), int(round(xs[i + 1])), int(round(ys[j + 1]))), quad))
    return img.transform((w, h), Image.Transform.MESH, mesh, resample=Image.Resampling.BILINEAR)


@register_effect("hue_shift", SCOPE_GLOBAL)
def hue_shift(img, rng, unit, degrees=25.0):
    hsv = np.asarray(img.convert("HSV")).copy()
    shift = int(round(degrees / 360.0 * 256))
    hsv[..., 0] = (hsv[..., 0].astype(np.int16) + shift) % 256
    return Image.fromarray(hsv, "HSV").convert("RGB")


def _shift_x(ch: np.ndarray, s: int) -> np.ndarray:
    if s == 0:
        return ch
    p = np.pad(ch, ((0, 0), (abs(s), abs(s))), mode="edge")
    start = abs(s) - s
    return p[:, start:start + ch.shape[1]]


@register_effect("aberration", SCOPE_GLOBAL)
def aberration(img, rng, unit, shift=5.0):
    """Хроматическая аберрация: красный и синий каналы смещаются в разные стороны."""
    s = int(round(shift * unit))
    arr = np.asarray(img).copy()
    arr[..., 0] = _shift_x(arr[..., 0], s)
    arr[..., 2] = _shift_x(arr[..., 2], -s)
    return Image.fromarray(arr, "RGB")

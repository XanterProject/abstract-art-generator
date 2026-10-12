"""Тень и свечение (поэлементные) и bloom (глобальное свечение)."""
import numpy as np
from PIL import Image, ImageFilter

from palettes import parse_color
from patch import Patch, expanded_alpha, mean_color
from registry import SCOPE_ELEMENT, SCOPE_GLOBAL, register_effect


def _solid_with_alpha(rgb, alpha: Image.Image) -> Image.Image:
    layer = Image.new("RGBA", alpha.size, tuple(rgb) + (0,))
    layer.putalpha(alpha)
    return layer


@register_effect("shadow", SCOPE_ELEMENT)
def shadow(patch, rng, unit, dx=12.0, dy=16.0, blur=14.0, opacity=0.55, color="#000000"):
    """Мягкая тень под фигурой. dx/dy — смещение, blur — размытие, opacity 0..1."""
    sigma = max(blur * unit, 0.1)
    pad = int(sigma * 3 + max(abs(dx), abs(dy)) * unit) + 2
    a, x, y = expanded_alpha(patch, pad)
    from PIL import ImageChops
    a = ImageChops.offset(a, int(round(dx * unit)), int(round(dy * unit)))
    a = a.filter(ImageFilter.GaussianBlur(sigma))
    lut = [int(min(255, i * opacity)) for i in range(256)]
    a = a.point(lut)
    return [Patch(_solid_with_alpha(parse_color(color), a), x, y)]


@register_effect("glow", SCOPE_ELEMENT)
def glow(patch, rng, unit, radius=26.0, strength=1.0, color="auto"):
    """Аддитивное свечение вокруг фигуры. color='auto' — цвет самой фигуры (чуть осветлённый)."""
    sigma = max(radius * unit, 0.1)
    pad = int(sigma * 3) + 2
    a, x, y = expanded_alpha(patch, pad)
    wide = np.asarray(a.filter(ImageFilter.GaussianBlur(sigma)), dtype=np.float32)
    tight = np.asarray(a.filter(ImageFilter.GaussianBlur(sigma / 3)), dtype=np.float32)
    halo = np.clip((wide * 0.6 + tight * 0.7) * strength, 0, 255).astype(np.uint8)
    if color == "auto":
        r, g, b = mean_color(patch)
        rgb = tuple(int(c + (255 - c) * 0.25) for c in (r, g, b))
    else:
        rgb = parse_color(color)
    return [Patch(_solid_with_alpha(rgb, Image.fromarray(halo, "L")), x, y, mode="add")]


@register_effect("bloom", SCOPE_GLOBAL)
def bloom(img, rng, unit, threshold=170.0, radius=30.0, intensity=0.9):
    """Глобальное свечение ярких областей."""
    arr = np.asarray(img, dtype=np.float32)
    lum = arr.mean(axis=2)
    m = np.clip((lum - threshold) / max(255.0 - threshold, 1.0), 0, 1)[..., None]
    bright = Image.fromarray((arr * m).astype(np.uint8), "RGB")
    sigma = max(radius * unit, 0.1)
    glow_a = np.asarray(bright.filter(ImageFilter.GaussianBlur(sigma)), dtype=np.float32)
    glow_b = np.asarray(bright.filter(ImageFilter.GaussianBlur(sigma * 2.5)), dtype=np.float32)
    out = arr + (glow_a * 0.7 + glow_b * 0.6) * intensity
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")

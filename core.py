"""Ядро: конфигурация и конвейер генерации (фон -> фигуры с поэлементными эффектами -> глобальные эффекты)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

import palettes
import registry
from patch import Mask, Patch, composite
from registry import SCOPE_ELEMENT, SCOPE_GLOBAL

DEFAULT_EFFECTS: list[tuple[str, dict]] = [("shadow", {}), ("vignette", {}), ("grain", {})]


@dataclass
class Config:
    size: tuple[int, int] = (1920, 1080)
    palette: str | None = None        # имя именованной палитры или None/'random'
    color: str | None = None          # доминирующий цвет '#rrggbb' (приоритетнее palette)
    hue: float | None = None          # доминирующий оттенок 0..360 (если не задан color)
    scheme: str = "analogous"
    dominance: float = 0.6
    bg: str = "auto"                  # auto | dark | light
    shapes: tuple[int, int] = (12, 32)
    shape_types: tuple[str, ...] = ()  # пусто = все зарегистрированные
    effects: list[tuple[str, dict]] = field(default_factory=lambda: list(DEFAULT_EFFECTS))


def build_palette(cfg: Config, rng) -> palettes.Palette:
    if cfg.color:
        return palettes.from_dominant(palettes.parse_color(cfg.color), rng, cfg.scheme, cfg.dominance, cfg.bg)
    if cfg.hue is not None:
        return palettes.from_hue(cfg.hue, rng, cfg.scheme, cfg.dominance, cfg.bg)
    if cfg.palette and cfg.palette != "random":
        return palettes.named(cfg.palette, rng, cfg.bg)
    return palettes.random_named(rng, cfg.bg)


def make_background(size: tuple[int, int], palette: palettes.Palette, rng) -> Image.Image:
    """Линейный или радиальный градиент между двумя цветами фона."""
    w, h = size
    c0 = np.asarray(palette.bg[0], dtype=np.float32)
    c1 = np.asarray(palette.bg[1], dtype=np.float32)
    xs = (np.arange(w, dtype=np.float32) + 0.5) / w - 0.5
    ys = (np.arange(h, dtype=np.float32) + 0.5) / h - 0.5
    if rng.random() < 0.5:
        ang = float(rng.uniform(0, 2 * math.pi))
        t = xs[None, :] * math.cos(ang) + ys[:, None] * math.sin(ang)
        t = (t - t.min()) / max(float(t.max() - t.min()), 1e-6)
    else:
        cx, cy = (float(rng.uniform(-0.2, 0.2)), float(rng.uniform(-0.2, 0.2)))
        t = np.sqrt((xs[None, :] - cx) ** 2 + (ys[:, None] - cy) ** 2)
        t = np.clip(t / max(float(t.max()), 1e-6), 0, 1)
    arr = c0 + (c1 - c0) * t[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def fill_mask(mask: Mask, palette: palettes.Palette, rng) -> Patch:
    """Заливка маски: сплошной цвет или линейный градиент двух цветов палитры, со случайной прозрачностью."""
    w, h = mask.img.size
    opacity = float(rng.uniform(0.55, 1.0))
    alpha = mask.img.point([int(i * opacity) for i in range(256)])
    c1 = palette.pick(rng)
    if rng.random() < 0.55:
        img = Image.new("RGBA", (w, h), c1 + (255,))
    else:
        c2 = palette.pick(rng)
        ang = float(rng.uniform(0, 2 * math.pi))
        ca, sa = math.cos(ang), math.sin(ang)
        xs = (np.arange(w, dtype=np.float32) - w / 2)[None, :]
        ys = (np.arange(h, dtype=np.float32) - h / 2)[:, None]
        span = max(abs(w * ca) + abs(h * sa), 1.0)
        t = np.clip((xs * ca + ys * sa) / span + 0.5, 0, 1)[..., None]
        arr = np.asarray(c1, np.float32) + (np.asarray(c2, np.float32) - np.asarray(c1, np.float32)) * t
        img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    img.putalpha(alpha)
    return Patch(img, mask.x, mask.y)


def _pick_shapes(rng, n: int, allowed: tuple[str, ...]):
    infos = [s for name, s in registry.SHAPES.items() if not allowed or name in allowed]
    if not infos:
        raise ValueError(f"нет доступных форм (запрошены: {', '.join(allowed) or 'все'})")
    p = np.asarray([s.weight for s in infos], dtype=float)
    p /= p.sum()
    return [infos[int(i)] for i in rng.choice(len(infos), size=n, p=p)]


def generate(cfg: Config, seed: int) -> tuple[Image.Image, dict]:
    """Генерирует одно изображение. Результат полностью определяется (cfg, seed)."""
    registry.load_plugins()
    rng = np.random.default_rng(seed)
    W, H = cfg.size
    unit = min(W, H) / 1000.0

    palette = build_palette(cfg, rng)
    canvas = make_background(cfg.size, palette, rng)

    lo, hi = cfg.shapes
    n = int(rng.integers(lo, max(lo, hi) + 1))
    masks = []
    for info in _pick_shapes(rng, n, cfg.shape_types):
        m = info.fn(rng, W, H, unit)
        if m is not None:
            masks.append(m)
    masks.sort(key=lambda m: m.area, reverse=True)  # крупные — на задний план

    element_fx = [(registry.EFFECTS[n_].fn, p) for n_, p in cfg.effects if registry.EFFECTS[n_].scope == SCOPE_ELEMENT]
    global_fx = [(registry.EFFECTS[n_].fn, p) for n_, p in cfg.effects if registry.EFFECTS[n_].scope == SCOPE_GLOBAL]

    for mask in masks:
        patch = fill_mask(mask, palette, rng)
        for fn, params in element_fx:
            for under in fn(patch, rng, unit, **params):
                composite(canvas, under)
        composite(canvas, patch)

    result = canvas.convert("RGB")
    for fn, params in global_fx:
        result = fn(result, rng, unit, **params)

    meta = {
        "seed": seed,
        "size": [W, H],
        "palette": palette.describe(),
        "shapes_drawn": len(masks),
        "effects": [[n_, p] for n_, p in cfg.effects],
    }
    return result, meta

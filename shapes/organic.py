"""Органические формы: блоб (гладкая случайная кривая) и волна (изогнутая лента)."""
import math

import numpy as np

from patch import MaskCanvas
from registry import register_shape
from ._util import bbox_of, log_uniform, random_center, rotate


@register_shape("blob", weight=1.6)
def blob(rng, W, H, unit):
    cx, cy = random_center(rng, W, H)
    r = log_uniform(rng, 50, 380) * unit
    theta = np.linspace(0, 2 * math.pi, 240, endpoint=False)
    wobble = np.ones_like(theta)
    for k in range(2, 6):
        amp = float(rng.uniform(0.0, 0.22)) / (k - 1)
        wobble += amp * np.sin(k * theta + rng.uniform(0, 2 * math.pi))
    rad = r * wobble
    pts = list(zip(cx + rad * np.cos(theta), cy + rad * np.sin(theta)))
    mc = MaskCanvas(W, H, bbox_of(pts))
    if mc.empty:
        return None
    mc.polygon(pts)
    return mc.finish()


@register_shape("wave", weight=0.7)
def wave(rng, W, H, unit):
    """Изогнутая лента, пересекающая холст под случайным углом."""
    diag = math.hypot(W, H)
    n = 160
    xs = np.linspace(-0.6 * diag, 0.6 * diag, n)
    f1, f2 = rng.uniform(0.6, 2.2), rng.uniform(2.0, 4.5)
    p1, p2 = rng.uniform(0, 2 * math.pi, 2)
    amp = log_uniform(rng, 25, 180) * unit
    base = amp * np.sin(2 * math.pi * f1 * xs / diag + p1) \
        + 0.35 * amp * np.sin(2 * math.pi * f2 * xs / diag + p2)
    thick = log_uniform(rng, 30, 220) * unit
    thick_v = thick * (1 + 0.4 * np.sin(2 * math.pi * rng.uniform(0.5, 2.0) * xs / diag + rng.uniform(0, 6.28)))
    off = float(rng.uniform(-0.35, 0.35)) * min(W, H)
    upper = list(zip(xs, base - thick_v / 2 + off))
    lower = list(zip(xs[::-1], (base + thick_v / 2 + off)[::-1]))
    pts = rotate(upper + lower, float(rng.uniform(0, math.pi)), 0.0, 0.0)
    pts = [(x + W / 2, y + H / 2) for x, y in pts]
    mc = MaskCanvas(W, H, bbox_of(pts))
    if mc.empty:
        return None
    mc.polygon(pts)
    return mc.finish()

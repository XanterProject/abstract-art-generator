"""Базовые формы: круг/эллипс, кольцо, многоугольник, звезда, линия."""
import math

import numpy as np

from patch import MaskCanvas
from registry import register_shape
from ._util import bbox_of, log_uniform, random_center, rotate


@register_shape("circle", weight=1.4)
def circle(rng, W, H, unit):
    cx, cy = random_center(rng, W, H)
    rx = log_uniform(rng, 25, 320) * unit
    ry = rx * float(rng.uniform(0.65, 1.0)) if rng.random() < 0.3 else rx
    mc = MaskCanvas(W, H, (cx - rx, cy - ry, cx + rx, cy + ry))
    if mc.empty:
        return None
    mc.ellipse(cx, cy, rx, ry)
    return mc.finish()


@register_shape("ring", weight=0.8)
def ring(rng, W, H, unit):
    cx, cy = random_center(rng, W, H)
    r = log_uniform(rng, 40, 340) * unit
    thickness = r * float(rng.uniform(0.06, 0.28))
    mc = MaskCanvas(W, H, (cx - r, cy - r, cx + r, cy + r))
    if mc.empty:
        return None
    mc.ellipse(cx, cy, r, r, 255)
    mc.ellipse(cx, cy, r - thickness, r - thickness, 0)
    return mc.finish()


@register_shape("polygon", weight=1.2)
def polygon(rng, W, H, unit):
    cx, cy = random_center(rng, W, H)
    n = int(rng.integers(3, 9))
    r = log_uniform(rng, 40, 380) * unit
    angles = np.sort(rng.uniform(0, 2 * math.pi, n))
    radii = r * rng.uniform(0.55, 1.0, n)
    pts = [(cx + ra * math.cos(a), cy + ra * math.sin(a)) for ra, a in zip(radii, angles)]
    mc = MaskCanvas(W, H, bbox_of(pts))
    if mc.empty:
        return None
    mc.polygon(pts)
    return mc.finish()


@register_shape("star", weight=0.6)
def star(rng, W, H, unit):
    cx, cy = random_center(rng, W, H)
    n = int(rng.integers(5, 10))
    r = log_uniform(rng, 40, 260) * unit
    inner = r * float(rng.uniform(0.35, 0.6))
    rot = float(rng.uniform(0, 2 * math.pi))
    pts = []
    for i in range(2 * n):
        rad = r if i % 2 == 0 else inner
        a = rot + math.pi * i / n
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    mc = MaskCanvas(W, H, bbox_of(pts))
    if mc.empty:
        return None
    mc.polygon(pts)
    return mc.finish()


@register_shape("line", weight=1.0)
def line(rng, W, H, unit):
    cx, cy = random_center(rng, W, H, margin=0.0)
    length = log_uniform(rng, 120, 900) * unit
    width = log_uniform(rng, 4, 60) * unit
    a = float(rng.uniform(0, math.pi))
    dx, dy = math.cos(a) * length / 2, math.sin(a) * length / 2
    p0, p1 = (cx - dx, cy - dy), (cx + dx, cy + dy)
    pad = width
    mc = MaskCanvas(W, H, (min(p0[0], p1[0]) - pad, min(p0[1], p1[1]) - pad,
                           max(p0[0], p1[0]) + pad, max(p0[1], p1[1]) + pad))
    if mc.empty:
        return None
    mc.line(p0, p1, width)
    return mc.finish()

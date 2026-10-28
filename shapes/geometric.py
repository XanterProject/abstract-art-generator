"""Новые формы: полумесяц, дуга, крест, цветок, шестерёнка, капля, спираль, зигзаг, скруглённый прямоугольник."""
import math

import numpy as np

from patch import MaskCanvas
from registry import register_shape
from ._util import bbox_of, log_uniform, random_center, rotate


def _poly_shape(rng, W, H, pts):
    mc = MaskCanvas(W, H, bbox_of(pts))
    if mc.empty:
        return None
    mc.polygon(pts)
    return mc.finish()


@register_shape("crescent", weight=0.6)
def crescent(rng, W, H, unit):
    cx, cy = random_center(rng, W, H)
    r = log_uniform(rng, 50, 300) * unit
    shift = r * float(rng.uniform(0.25, 0.6))
    scale = float(rng.uniform(0.7, 0.95))
    a = float(rng.uniform(0, 2 * math.pi))
    ox, oy = cx + shift * math.cos(a), cy + shift * math.sin(a)
    mc = MaskCanvas(W, H, (cx - r, cy - r, cx + r, cy + r))
    if mc.empty:
        return None
    mc.ellipse(cx, cy, r, r, 255)
    mc.ellipse(ox, oy, r * scale, r * scale, 0)
    return mc.finish()


@register_shape("arc", weight=0.7)
def arc(rng, W, H, unit):
    """Дуга: толстая незамкнутая окружность."""
    cx, cy = random_center(rng, W, H)
    r = log_uniform(rng, 60, 380) * unit
    thick = r * float(rng.uniform(0.05, 0.25))
    start = float(rng.uniform(0, 2 * math.pi))
    sweep = float(rng.uniform(0.6, 1.6)) * math.pi
    t = np.linspace(start, start + sweep, 120)
    outer = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in t]
    inner = [(cx + (r - thick) * math.cos(a), cy + (r - thick) * math.sin(a)) for a in t[::-1]]
    return _poly_shape(rng, W, H, outer + inner)


@register_shape("cross", weight=0.5)
def cross(rng, W, H, unit):
    cx, cy = random_center(rng, W, H)
    r = log_uniform(rng, 40, 260) * unit
    t = r * float(rng.uniform(0.2, 0.45))
    pts = [(-t, -r), (t, -r), (t, -t), (r, -t), (r, t), (t, t),
           (t, r), (-t, r), (-t, t), (-r, t), (-r, -t), (-t, -t)]
    pts = rotate(pts, float(rng.uniform(0, math.pi / 2)), 0.0, 0.0)
    return _poly_shape(rng, W, H, [(cx + x, cy + y) for x, y in pts])


@register_shape("flower", weight=0.8)
def flower(rng, W, H, unit):
    cx, cy = random_center(rng, W, H)
    r = log_uniform(rng, 50, 300) * unit
    petals = int(rng.integers(4, 11))
    depth = float(rng.uniform(0.2, 0.5))
    rot = float(rng.uniform(0, 2 * math.pi))
    theta = np.linspace(0, 2 * math.pi, 360, endpoint=False)
    rad = r * (1 - depth + depth * np.abs(np.cos(petals * theta / 2)))
    pts = list(zip(cx + rad * np.cos(theta + rot), cy + rad * np.sin(theta + rot)))
    return _poly_shape(rng, W, H, pts)


@register_shape("gear", weight=0.5)
def gear(rng, W, H, unit):
    cx, cy = random_center(rng, W, H)
    r = log_uniform(rng, 50, 280) * unit
    teeth = int(rng.integers(8, 20))
    tooth = r * float(rng.uniform(0.1, 0.25))
    rot = float(rng.uniform(0, 2 * math.pi))
    pts = []
    step = 2 * math.pi / teeth
    for i in range(teeth):
        a0 = rot + i * step
        for frac, rad in ((0.0, r - tooth), (0.2, r - tooth), (0.3, r), (0.7, r), (0.8, r - tooth)):
            a = a0 + frac * step
            pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    mc = MaskCanvas(W, H, bbox_of(pts))
    if mc.empty:
        return None
    mc.polygon(pts)
    mc.ellipse(cx, cy, r * 0.3, r * 0.3, 0)  # отверстие
    return mc.finish()


@register_shape("drop", weight=0.7)
def drop(rng, W, H, unit):
    cx, cy = random_center(rng, W, H)
    r = log_uniform(rng, 40, 240) * unit
    d = r * float(rng.uniform(1.5, 2.4))  # расстояние от центра до острия
    beta = math.acos(r / d)
    t = np.linspace(-math.pi / 2 + beta, 3 * math.pi / 2 - beta, 200)
    pts = [(0.0, -d)] + [(r * math.cos(a), r * math.sin(a)) for a in t]
    pts = rotate([(cx + x, cy + y) for x, y in pts], float(rng.uniform(0, 2 * math.pi)), cx, cy)
    return _poly_shape(rng, W, H, pts)


@register_shape("spiral", weight=0.5)
def spiral(rng, W, H, unit):
    cx, cy = random_center(rng, W, H)
    r = log_uniform(rng, 80, 340) * unit
    turns = float(rng.uniform(1.5, 3.5))
    width = r / turns * float(rng.uniform(0.25, 0.5))
    rot = float(rng.uniform(0, 2 * math.pi))
    t = np.linspace(0, 1, 260)
    ang = rot + t * turns * 2 * math.pi
    rad = r * (0.1 + 0.9 * t)
    pts = [(cx + ra * math.cos(a), cy + ra * math.sin(a)) for ra, a in zip(rad, ang)]
    mc = MaskCanvas(W, H, (cx - r - width, cy - r - width, cx + r + width, cy + r + width))
    if mc.empty:
        return None
    for p0, p1 in zip(pts[:-1], pts[1:]):
        mc.line(p0, p1, width)
    return mc.finish()


@register_shape("zigzag", weight=0.6)
def zigzag(rng, W, H, unit):
    cx, cy = random_center(rng, W, H, margin=0.0)
    n = int(rng.integers(4, 10))
    seg = log_uniform(rng, 50, 200) * unit
    amp = seg * float(rng.uniform(0.5, 1.2))
    width = log_uniform(rng, 8, 50) * unit
    a = float(rng.uniform(0, math.pi))
    pts = [((i - n / 2) * seg, amp * (0.5 if i % 2 else -0.5)) for i in range(n + 1)]
    pts = [(cx + x, cy + y) for x, y in rotate(pts, a, 0.0, 0.0)]
    x0, y0, x1, y1 = bbox_of(pts)
    mc = MaskCanvas(W, H, (x0 - width, y0 - width, x1 + width, y1 + width))
    if mc.empty:
        return None
    for p0, p1 in zip(pts[:-1], pts[1:]):
        mc.line(p0, p1, width)
    return mc.finish()


@register_shape("rounded_rect", weight=0.9)
def rounded_rect(rng, W, H, unit):
    cx, cy = random_center(rng, W, H)
    w = log_uniform(rng, 60, 420) * unit
    h = w * float(rng.uniform(0.35, 1.1))
    rad = min(w, h) * float(rng.uniform(0.1, 0.5))
    pts = []
    for (qx, qy, a0) in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
        for d in range(0, 91, 10):
            a = math.radians(a0 + d)
            pts.append((qx * (w - rad) + rad * math.cos(a), qy * (h - rad) + rad * math.sin(a)))
    pts = rotate(pts, float(rng.uniform(0, math.pi)), 0.0, 0.0)
    return _poly_shape(rng, W, H, [(cx + x, cy + y) for x, y in pts])

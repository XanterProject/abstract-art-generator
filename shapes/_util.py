import math

import numpy as np


def log_uniform(rng, lo: float, hi: float) -> float:
    return float(math.exp(rng.uniform(math.log(lo), math.log(hi))))


def random_center(rng, W: int, H: int, margin: float = 0.08) -> tuple[float, float]:
    """Центр фигуры; допускаем небольшой выход за границы холста."""
    return (float(rng.uniform(-margin * W, (1 + margin) * W)),
            float(rng.uniform(-margin * H, (1 + margin) * H)))


def bbox_of(points) -> tuple[float, float, float, float]:
    a = np.asarray(points)
    return float(a[:, 0].min()), float(a[:, 1].min()), float(a[:, 0].max()), float(a[:, 1].max())


def rotate(points, angle: float, cx: float, cy: float):
    c, s = math.cos(angle), math.sin(angle)
    return [(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c) for x, y in points]

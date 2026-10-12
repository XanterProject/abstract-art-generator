"""Палитры: именованные и генерируемые от доминирующего цвета/оттенка."""
from __future__ import annotations

import colorsys
from dataclasses import dataclass, field

import numpy as np

RGB = tuple[int, int, int]

NAMED: dict[str, list[str]] = {
    "sunset": ["#ff5e5b", "#ffa07a", "#ffd166", "#d7263d", "#6a0572"],
    "ocean": ["#03045e", "#0077b6", "#00b4d8", "#90e0ef", "#caf0f8"],
    "neon": ["#ff00e5", "#00f0ff", "#7cff00", "#fff700", "#8a2be2"],
    "forest": ["#1b4332", "#2d6a4f", "#52b788", "#95d5b2", "#d8f3dc"],
    "pastel": ["#ffadad", "#ffd6a5", "#fdffb6", "#caffbf", "#9bf6ff", "#bdb2ff"],
    "earth": ["#582f0e", "#936639", "#b08968", "#ddb892", "#e6ccb2"],
    "mono": ["#111111", "#444444", "#888888", "#cccccc", "#f5f5f5"],
    "fire": ["#370617", "#9d0208", "#dc2f02", "#f48c06", "#ffba08"],
    "aurora": ["#0b132b", "#1c2541", "#3a506b", "#5bc0be", "#6fffe9"],
    "candy": ["#ff6ec7", "#ffb3de", "#a0e7e5", "#b4f8c8", "#fbe7c6"],
    "cyberpunk": ["#0d0221", "#261447", "#ff2a6d", "#05d9e8", "#d1f7ff"],
    "retro": ["#264653", "#2a9d8f", "#e9c46a", "#f4a261", "#e76f51"],
}

SCHEMES = ("analogous", "complementary", "triadic", "split", "mono")
BG_MODES = ("auto", "dark", "light")


def parse_color(text: str) -> RGB:
    t = text.strip().lstrip("#")
    if len(t) == 3:
        t = "".join(c * 2 for c in t)
    if len(t) != 6:
        raise ValueError(f"цвет '{text}' должен быть в формате #rrggbb")
    try:
        return int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16)
    except ValueError:
        raise ValueError(f"цвет '{text}' должен быть в формате #rrggbb") from None


def to_hex(c: RGB) -> str:
    return "#%02x%02x%02x" % tuple(int(v) for v in c)


def _hls(h: float, l: float, s: float) -> RGB:
    r, g, b = colorsys.hls_to_rgb(h % 1.0, min(max(l, 0.0), 1.0), min(max(s, 0.0), 1.0))
    return int(round(r * 255)), int(round(g * 255)), int(round(b * 255))


def _to_hls(c: RGB) -> tuple[float, float, float]:
    return colorsys.rgb_to_hls(c[0] / 255, c[1] / 255, c[2] / 255)


@dataclass
class Palette:
    colors: list[RGB]
    weights: list[float]
    bg: tuple[RGB, RGB]
    name: str = "custom"
    dominant: RGB | None = None
    _p: np.ndarray = field(init=False, repr=False)

    def __post_init__(self):
        w = np.asarray(self.weights, dtype=float)
        self._p = w / w.sum()

    def pick(self, rng) -> RGB:
        return self.colors[int(rng.choice(len(self.colors), p=self._p))]

    def describe(self) -> dict:
        return {
            "name": self.name,
            "colors": [to_hex(c) for c in self.colors],
            "weights": [round(float(p), 3) for p in self._p],
            "background": [to_hex(c) for c in self.bg],
        }


def _make_background(colors: list[RGB], mode: str, rng) -> tuple[RGB, RGB]:
    if mode == "auto":
        mode = "dark" if rng.random() < 0.7 else "light"
    by_l = sorted(colors, key=lambda c: _to_hls(c)[1])
    if mode == "dark":
        pair = by_l[:2] if len(by_l) > 1 else by_l * 2
        out = []
        for c, cap in zip(pair, (0.07, 0.16)):
            h, l, s = _to_hls(c)
            out.append(_hls(h, min(l, cap), min(s, 0.6)))
        return out[0], out[1]
    pair = by_l[-2:][::-1] if len(by_l) > 1 else by_l * 2
    out = []
    for c, floor in zip(pair, (0.95, 0.88)):
        h, l, s = _to_hls(c)
        out.append(_hls(h, max(l, floor), min(s, 0.5)))
    return out[0], out[1]


def named(name: str, rng, bg: str = "auto") -> Palette:
    if name not in NAMED:
        raise ValueError(f"неизвестная палитра '{name}'. Доступны: {', '.join(NAMED)}, random")
    colors = [parse_color(h) for h in NAMED[name]]
    return Palette(colors, [1.0] * len(colors), _make_background(colors, bg, rng), name=name)


def random_named(rng, bg: str = "auto") -> Palette:
    names = list(NAMED)
    return named(names[int(rng.integers(len(names)))], rng, bg)


def from_dominant(color: RGB, rng, scheme: str = "analogous", dominance: float = 0.6,
                  bg: str = "auto") -> Palette:
    """Палитра, где около `dominance` доли цветов — оттенки заданного цвета, остальное — гармоничные акценты."""
    if scheme not in SCHEMES:
        raise ValueError(f"неизвестная схема '{scheme}'. Доступны: {', '.join(SCHEMES)}")
    dominance = min(max(dominance, 0.0), 1.0)
    h, l, s = _to_hls(color)
    l = min(max(l, 0.25), 0.7)  # слишком тёмный/светлый базовый цвет делает палитру плоской
    jitter = lambda a: float(rng.uniform(-a, a))  # noqa: E731

    colors: list[RGB] = []
    weights: list[float] = []

    if scheme == "mono":
        dominance = 1.0
        lights = (l * 0.5, l * 0.75, l, min(l * 1.2, 0.85), min(l * 1.45, 0.92))
        main = [_hls(h, ll, s * (0.9 + jitter(0.1))) for ll in lights]
    else:
        main = [_hls(h, l * 0.65, s), _hls(h, l, s), _hls(h + jitter(0.01), min(l * 1.3, 0.88), s * 0.9)]
    for c in main:
        colors.append(c)
        weights.append(dominance / len(main))

    if scheme != "mono":
        offsets = {
            "analogous": (-30, -15, 20, 35),
            "complementary": (180 - 12, 180, 180 + 12),
            "triadic": (120, 240, 120 + 15),
            "split": (150, 210, 180),
        }[scheme]
        accents = []
        for off in offsets:
            ah = h + (off + jitter(6)) / 360.0
            accents.append(_hls(ah, min(max(l + jitter(0.18), 0.3), 0.8), min(max(s * (0.85 + jitter(0.15)), 0.3), 1.0)))
        accents.append(_hls(h, 0.93, min(s, 0.35)))  # светлый «блик»
        share = (1.0 - dominance) / len(accents)
        for c in accents:
            colors.append(c)
            weights.append(max(share, 1e-6))

    return Palette(colors, weights, _make_background(colors, bg, rng),
                   name=f"dominant-{scheme}", dominant=color)


def from_hue(hue_deg: float, rng, scheme: str = "analogous", dominance: float = 0.6,
             bg: str = "auto", saturation: float = 0.8, lightness: float = 0.5) -> Palette:
    return from_dominant(_hls(hue_deg / 360.0, lightness, saturation), rng, scheme, dominance, bg)

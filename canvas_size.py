"""Размер холста: пресеты, произвольный WxH и случайный выбор."""
from __future__ import annotations

import re

PRESETS: dict[str, tuple[int, int]] = {
    "hd": (1280, 720),
    "fhd": (1920, 1080),
    "qhd": (2560, 1440),
    "4k": (3840, 2160),
    "square": (1024, 1024),
    "square2k": (2048, 2048),
    "a4": (2480, 3508),
    "a4l": (3508, 2480),
    "phone": (1080, 1920),
    "banner": (1500, 500),
}
RANDOM_POOL = ("hd", "fhd", "square", "phone", "banner", "a4")

MIN_SIDE = 64
MAX_SIDE = 16384
MAX_PIXELS = 100_000_000
WARN_PIXELS = 36_000_000

_WXH = re.compile(r"^\s*(\d+)\s*[xX×*]\s*(\d+)\s*$")


def is_random(text: str) -> bool:
    return text.strip().lower() == "random"


def _validate(w: int, h: int) -> tuple[int, int]:
    if w < MIN_SIDE or h < MIN_SIDE:
        raise ValueError(f"размер {w}x{h} слишком мал: минимум {MIN_SIDE}px по каждой стороне")
    if w > MAX_SIDE or h > MAX_SIDE:
        raise ValueError(f"размер {w}x{h} слишком велик: максимум {MAX_SIDE}px по стороне")
    if w * h > MAX_PIXELS:
        raise ValueError(f"размер {w}x{h} превышает лимит {MAX_PIXELS // 1_000_000} Мпикс")
    return w, h


def parse_size(text: str) -> tuple[int, int]:
    """'fhd' | '1500x900' -> (w, h). Для 'random' используйте resolve_size."""
    key = text.strip().lower()
    if key in PRESETS:
        return PRESETS[key]
    m = _WXH.match(text)
    if not m:
        raise ValueError(
            f"не удалось разобрать размер '{text}'. Примеры: fhd, 4k, 1500x900, random. "
            f"Пресеты: {', '.join(PRESETS)}"
        )
    return _validate(int(m.group(1)), int(m.group(2)))


def resolve_size(text: str, rng) -> tuple[int, int]:
    """Как parse_size, но 'random' выбирает пресет из RANDOM_POOL с помощью rng."""
    if is_random(text):
        return PRESETS[RANDOM_POOL[int(rng.integers(len(RANDOM_POOL)))]]
    return parse_size(text)


def size_warning(w: int, h: int) -> str | None:
    if w * h > WARN_PIXELS:
        return f"большой холст {w}x{h} ({w * h / 1e6:.0f} Мпикс): генерация будет медленной и затратной по памяти"
    return None

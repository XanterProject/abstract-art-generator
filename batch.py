"""Пакетная генерация: спецификация батча, задания, параллельный запуск."""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

import numpy as np

import canvas_size
import registry
from core import DEFAULT_EFFECTS, Config, generate

VARIATION_POOL = "glow,shadow,bloom,grain,vignette,warp,hue_shift,aberration"
FORMATS = {"png": "PNG", "jpg": "JPEG", "webp": "WEBP"}


@dataclass
class BatchSpec:
    """Всё, что задаёт батч (простые типы — удобно передавать в процессы и из GUI)."""
    size: str = "fhd"                 # пресет | WxH | random
    palette: str | None = None
    color: str | None = None
    hue: float | None = None
    scheme: str = "analogous"
    dominance: float = 0.6
    bg: str = "auto"
    shapes: tuple[int, int] = (12, 32)
    shape_types: tuple[str, ...] = ()
    effects: str | None = None        # строка эффектов; None = эффекты по умолчанию
    variations: bool = False          # случайный поднабор эффектов для каждого изображения
    fmt: str = "png"


def build_config(spec: BatchSpec, seed: int) -> Config:
    """Config для изображения с данным seed (размер и вариации выбираются детерминированно от seed)."""
    pick_rng = np.random.default_rng([seed, 7919])
    size = canvas_size.resolve_size(spec.size, pick_rng)
    if spec.variations:
        pool = registry.parse_effects(spec.effects or VARIATION_POOL)
        k = min(len(pool), int(pick_rng.integers(2, 5)))
        idx = sorted(pick_rng.choice(len(pool), size=k, replace=False).tolist())
        effects = [pool[i] for i in idx]
    elif spec.effects is None:
        effects = [(n, dict(p)) for n, p in DEFAULT_EFFECTS]
    else:
        effects = registry.parse_effects(spec.effects)
    return Config(size=size, palette=spec.palette, color=spec.color, hue=spec.hue, scheme=spec.scheme,
                  dominance=spec.dominance, bg=spec.bg, shapes=tuple(spec.shapes),
                  shape_types=tuple(spec.shape_types), effects=effects)


def render_job(spec: BatchSpec, index: int, seed: int, out_dir: str) -> dict:
    t0 = time.perf_counter()
    cfg = build_config(spec, seed)
    img, meta = generate(cfg, seed)
    ext = spec.fmt.lower()
    path = Path(out_dir) / f"prg_{index:04d}_s{seed}.{ext}"
    save_kwargs = {"quality": 95} if ext in ("jpg", "webp") else {}
    img.save(path, FORMATS[ext], **save_kwargs)
    meta["file"] = path.name
    meta["seconds"] = round(time.perf_counter() - t0, 2)
    meta["spec"] = asdict(spec)
    path.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def run_batch(spec: BatchSpec, count: int, seed: int, out_dir: str, workers: int | None = None,
              on_progress: Callable[[int, int, dict], None] | None = None) -> list[dict]:
    """Генерирует count изображений (seed, seed+1, ...). Возвращает список метаданных."""
    if spec.fmt.lower() not in FORMATS:
        raise ValueError(f"неизвестный формат '{spec.fmt}'. Доступны: {', '.join(FORMATS)}")
    # ранняя валидация: падаем до запуска процессов
    build_config(spec, seed)
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    workers = workers or min(count, os.cpu_count() or 1)
    results: list[dict] = []
    if workers <= 1 or count == 1:
        for i in range(count):
            meta = render_job(spec, i, seed + i, out_dir)
            results.append(meta)
            if on_progress:
                on_progress(len(results), count, meta)
        return results

    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(render_job, spec, i, seed + i, out_dir) for i in range(count)]
        for fut in as_completed(futures):
            meta = fut.result()
            results.append(meta)
            if on_progress:
                on_progress(len(results), count, meta)
    results.sort(key=lambda m: m["file"])
    return results

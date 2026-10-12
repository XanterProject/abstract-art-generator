"""Picture Random Generator (PRG) — генератор абстрактных изображений. Запуск: python main.py --help"""
from __future__ import annotations

import argparse
import secrets
import sys

import canvas_size
import palettes
import registry
from batch import FORMATS, BatchSpec, run_batch


def _range(text: str) -> tuple[int, int]:
    parts = text.replace("..", "-").split("-")
    try:
        lo, hi = (int(parts[0]), int(parts[-1]))
    except ValueError:
        raise argparse.ArgumentTypeError(f"ожидается 'N' или 'MIN-MAX', получено '{text}'") from None
    if lo < 1 or hi < lo:
        raise argparse.ArgumentTypeError("диапазон должен быть вида MIN-MAX, MIN >= 1")
    return lo, hi


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Генератор абстрактных изображений (без ИИ).")
    p.add_argument("--count", "-n", type=int, default=1, help="сколько изображений сгенерировать")
    p.add_argument("--size", default="fhd",
                   help="размер холста: пресет (hd, fhd, 4k, square, a4, phone, ...), WxH (1500x900) или random")
    p.add_argument("--seed", type=int, default=None, help="базовый seed (i-е изображение использует seed+i)")
    p.add_argument("--palette", default=None, help="именованная палитра или random")
    p.add_argument("--color", default=None, help="доминирующий цвет #rrggbb")
    p.add_argument("--hue", type=float, default=None, help="доминирующий оттенок 0..360")
    p.add_argument("--scheme", default="analogous", choices=palettes.SCHEMES, help="гармония акцентных цветов")
    p.add_argument("--dominance", type=float, default=0.6, help="доля доминирующего цвета 0..1")
    p.add_argument("--bg", default="auto", choices=palettes.BG_MODES, help="фон: тёмный/светлый/авто")
    p.add_argument("--shapes", type=_range, default=(12, 32), help="число фигур: N или MIN-MAX")
    p.add_argument("--shape-types", default="", help="список форм через запятую (по умолчанию все)")
    p.add_argument("--effects", default=None,
                   help="цепочка эффектов: 'glow:radius=20,shadow:dx=8:dy=8,grain' или none "
                        "(по умолчанию shadow,vignette,grain)")
    p.add_argument("--variations", action="store_true",
                   help="случайный поднабор эффектов для каждого изображения (из --effects, если задан)")
    p.add_argument("--format", dest="fmt", default="png", choices=list(FORMATS))
    p.add_argument("--workers", type=int, default=None, help="число процессов (по умолчанию = ядрам)")
    p.add_argument("--out", default="out", help="папка вывода")
    p.add_argument("--list", action="store_true", help="показать палитры, формы, эффекты и размеры")
    return p


def print_catalog() -> None:
    registry.load_plugins()
    print("Размеры:", ", ".join(f"{k}={w}x{h}" for k, (w, h) in canvas_size.PRESETS.items()), "| WxH | random")
    print("Палитры:", ", ".join(palettes.NAMED), "| random")
    print("Схемы (для --color/--hue):", ", ".join(palettes.SCHEMES))
    print("Формы:", ", ".join(registry.SHAPES))
    print("Эффекты:")
    for name, info in registry.describe_effects().items():
        params = ", ".join(f"{k}={v}" for k, v in info["params"].items())
        print(f"  {name:<11} [{info['scope']}]  {params}")


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        print_catalog()
        return 0
    try:
        spec = BatchSpec(
            size=args.size, palette=args.palette, color=args.color, hue=args.hue, scheme=args.scheme,
            dominance=args.dominance, bg=args.bg, shapes=args.shapes,
            shape_types=tuple(s for s in args.shape_types.split(",") if s), effects=args.effects,
            variations=args.variations, fmt=args.fmt,
        )
        if args.color:
            palettes.parse_color(args.color)
        if not canvas_size.is_random(args.size):
            w, h = canvas_size.parse_size(args.size)
            warn = canvas_size.size_warning(w, h)
            if warn:
                print("Внимание:", warn, file=sys.stderr)
        seed = args.seed if args.seed is not None else secrets.randbelow(2**31)
        print(f"seed={seed}, изображений: {args.count}, папка: {args.out}")

        def progress(done, total, meta):
            print(f"  [{done}/{total}] {meta['file']}  {meta['size'][0]}x{meta['size'][1]}  "
                  f"{meta['palette']['name']}  {meta['seconds']}s")

        run_batch(spec, args.count, seed, args.out, args.workers, progress)
    except ValueError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

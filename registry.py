"""Реестр плагинов: формы (shapes/) и эффекты (effects/).

Новый плагин = один файл в нужной папке с декоратором @register_shape / @register_effect.
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
from dataclasses import dataclass
from typing import Any, Callable

SCOPE_ELEMENT = "element"  # эффект применяется к каждой фигуре отдельно (тень, свечение)
SCOPE_GLOBAL = "global"    # эффект применяется ко всему холсту (зерно, виньетка, ...)


@dataclass
class ShapeInfo:
    name: str
    fn: Callable
    weight: float


@dataclass
class EffectInfo:
    name: str
    fn: Callable
    scope: str


SHAPES: dict[str, ShapeInfo] = {}
EFFECTS: dict[str, EffectInfo] = {}
_loaded = False


def register_shape(name: str, weight: float = 1.0):
    def deco(fn):
        SHAPES[name] = ShapeInfo(name, fn, weight)
        return fn
    return deco


def register_effect(name: str, scope: str = SCOPE_GLOBAL):
    if scope not in (SCOPE_ELEMENT, SCOPE_GLOBAL):
        raise ValueError(f"unknown effect scope: {scope}")

    def deco(fn):
        EFFECTS[name] = EffectInfo(name, fn, scope)
        return fn
    return deco


def load_plugins() -> None:
    """Импортирует все модули из пакетов shapes и effects (один раз)."""
    global _loaded
    if _loaded:
        return
    for pkg_name in ("shapes", "effects"):
        pkg = importlib.import_module(pkg_name)
        for mod in pkgutil.iter_modules(pkg.__path__):
            if not mod.name.startswith("_"):
                importlib.import_module(f"{pkg_name}.{mod.name}")
    _loaded = True


def effect_params(name: str) -> dict[str, Any]:
    """Параметры эффекта и их значения по умолчанию (по сигнатуре функции)."""
    load_plugins()
    sig = inspect.signature(EFFECTS[name].fn)
    params = list(sig.parameters.values())[3:]  # пропускаем (target, rng, unit)
    return {p.name: p.default for p in params}


def describe_effects() -> dict[str, dict]:
    load_plugins()
    return {n: {"scope": e.scope, "params": effect_params(n)} for n, e in sorted(EFFECTS.items())}


def _coerce(value: str, default: Any) -> Any:
    if isinstance(default, bool):
        return value.lower() in ("1", "true", "yes", "on")
    if isinstance(default, int):
        return int(float(value))
    if isinstance(default, float):
        return float(value)
    return value


def parse_effects(spec: str | None) -> list[tuple[str, dict]]:
    """'glow:radius=20,shadow:dx=8:dy=8,grain' -> [('glow', {...}), ...].

    Эффекты разделяются запятой, параметры — двоеточием.
    """
    load_plugins()
    if not spec or spec.strip().lower() in ("none", "-"):
        return []
    result: list[tuple[str, dict]] = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        name, *raw_params = chunk.split(":")
        name = name.strip()
        if name not in EFFECTS:
            raise ValueError(f"неизвестный эффект '{name}'. Доступны: {', '.join(sorted(EFFECTS))}")
        known = effect_params(name)
        params: dict[str, Any] = {}
        for raw in raw_params:
            if "=" not in raw:
                raise ValueError(f"параметр '{raw}' эффекта '{name}' должен иметь вид имя=значение")
            key, value = raw.split("=", 1)
            key = key.strip()
            if key not in known:
                raise ValueError(f"у эффекта '{name}' нет параметра '{key}'. Есть: {', '.join(known) or '—'}")
            try:
                params[key] = _coerce(value.strip(), known[key])
            except ValueError:
                raise ValueError(f"неверное значение '{value}' для {name}:{key}") from None
        result.append((name, params))
    return result

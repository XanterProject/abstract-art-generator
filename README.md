# Picture Random Generator (PRG)

Генератор абстрактных изображений на чистых алгоритмах (Pillow + NumPy), без ИИ.

## Установка
```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## Использование
```
python main.py --list                                   # палитры, формы, эффекты, размеры
python main.py --count 8 --size fhd --palette neon --effects "glow,shadow,grain" --out out
python main.py --count 4 --size 1500x900 --color "#3366ff" --scheme complementary
python main.py --count 10 --size random --variations --hue 30
python gui.py                                           # графический интерфейс
```

| Параметр | Описание |
|---|---|
| `--size` | пресет (`hd fhd qhd 4k square a4 phone banner ...`), `WxH` или `random` |
| `--palette` | именованная палитра или `random` |
| `--color` / `--hue` | доминирующий цвет `#rrggbb` / оттенок 0..360; `--scheme analogous\|complementary\|triadic\|split\|mono`, `--dominance 0..1` |
| `--bg` | `auto\|dark\|light` |
| `--shapes`, `--shape-types` | число фигур (`N` или `MIN-MAX`), список форм |
| `--effects` | `имя:параметр=значение:параметр=значение,имя2,...` (см. `--list`) |
| `--variations` | случайный поднабор эффектов для каждой картинки |
| `--seed`, `--count`, `--workers`, `--format`, `--out` | воспроизводимость и батч |

Каждая картинка пишется вместе с `.json` (seed, палитра, эффекты). Изображение `i` использует `seed+i`, поэтому
`--seed <seed_i> --count 1` воссоздаёт любую картинку. Размеры эффектов задаются относительно холста
(`min(W,H)/1000`), поэтому вид не зависит от разрешения.

## Свой плагин
Файл в `effects/` (или `shapes/`) — и он сразу доступен в CLI и GUI:
```python
from registry import register_effect, SCOPE_GLOBAL

@register_effect("invert", SCOPE_GLOBAL)
def invert(img, rng, unit, amount=1.0):
    ...
    return img
```

## Автосмена обоев (Windows, несколько мониторов)
Картинка генерируется под точное разрешение каждого монитора и ставится через `IDesktopWallpaper`.
Проще всего — блок «Обои рабочего стола» в `gui.py`. Из консоли:
```
python wallpaper.py start|stop|status      # фоновый процесс (без окна)
python wallpaper.py once                   # сменить один раз
python wallpaper.py autostart on|off       # ярлык в папке «Автозагрузка»
```
Настройки — `wallpaper.json` (интервал, палитра, цвет, эффекты…), лог — `wallpaper.log`,
картинки — `wallpapers/` (хранятся последние циклы).

## Тесты
```
.venv\Scripts\python -m pytest
```

## Лицензия
MIT — см. [LICENSE](LICENSE).

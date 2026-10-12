"""Автосмена обоев рабочего стола (Windows): новая сгенерированная картинка на каждый монитор.

  python wallpaper.py run        # фоновый цикл (меняет обои каждые N минут)
  python wallpaper.py once       # сменить обои один раз и выйти
  python wallpaper.py start|stop # запустить/остановить фоновый процесс
  python wallpaper.py autostart on|off
  python wallpaper.py status
Настройки — в wallpaper.json (перечитываются при каждой смене), лог — wallpaper.log.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import secrets
import subprocess
import sys
import time
import traceback
from ctypes import wintypes
from pathlib import Path

# Ограничиваем потоки математических библиотек (до импорта numpy) — не забираем все ядра.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

ROOT = Path(__file__).resolve().parent
FROZEN = getattr(sys, "frozen", False)  # собранный PyInstaller exe
# В exe файл лежит во временной папке распаковки — данные храним в профиле пользователя.
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "PRG" if FROZEN else ROOT
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG = DATA_DIR / "wallpaper.json"
LOG = DATA_DIR / "wallpaper.log"
STOP_FLAG = DATA_DIR / "wallpaper.stop"
NOW_FLAG = DATA_DIR / "wallpaper.now"
# Windows не принимает обои из AppData на некоторых профилях (COMError «файл не найден»),
# поэтому в exe картинки лежат в «Изображения\PRG\wallpapers».
OUT_DIR = Path.home() / "Pictures" / "PRG" / "wallpapers" if FROZEN else DATA_DIR / "wallpapers"
MUTEX_NAME = "Local\\PRG_WALLPAPER_RUNNING"
STARTUP_LINK_NAME = "PRG Wallpaper.lnk"

DEFAULTS = {
    "interval_min": 30,
    "palette": "random", "color": None, "hue": None,
    "scheme": "analogous", "dominance": 0.6, "bg": "auto",
    "shapes": [12, 32],
    "effects": "shadow,glow,vignette,grain",
    "variations": False,
    "keep": 4,          # сколько последних циклов (наборов картинок) хранить
}


# ---------- настройки / лог ----------
def load_config() -> dict:
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG.write_text(json.dumps({**DEFAULTS, **cfg}, ensure_ascii=False, indent=2), encoding="utf-8")


def log(msg: str) -> None:
    if LOG.exists() and LOG.stat().st_size > 200_000:
        LOG.write_text("", encoding="utf-8")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")


# ---------- мониторы и установка обоев (IDesktopWallpaper) ----------
def _desktop_wallpaper():
    import comtypes
    from comtypes import COMMETHOD, GUID, HRESULT, IUnknown
    from ctypes import POINTER

    class IDesktopWallpaper(IUnknown):
        _iid_ = GUID("{B92B56A9-8B55-4E14-9A89-0199BBB6F93B}")
        _methods_ = [
            COMMETHOD([], HRESULT, "SetWallpaper",
                      (["in"], wintypes.LPCWSTR, "monitorID"), (["in"], wintypes.LPCWSTR, "wallpaper")),
            COMMETHOD([], HRESULT, "GetWallpaper",
                      (["in"], wintypes.LPCWSTR, "monitorID"), (["out"], POINTER(wintypes.LPWSTR), "wallpaper")),
            COMMETHOD([], HRESULT, "GetMonitorDevicePathAt",
                      (["in"], wintypes.UINT, "monitorIndex"), (["out"], POINTER(wintypes.LPWSTR), "monitorID")),
            COMMETHOD([], HRESULT, "GetMonitorDevicePathCount", (["out"], POINTER(wintypes.UINT), "count")),
            COMMETHOD([], HRESULT, "GetMonitorRECT",
                      (["in"], wintypes.LPCWSTR, "monitorID"), (["out"], POINTER(wintypes.RECT), "displayRect")),
            COMMETHOD([], HRESULT, "SetBackgroundColor", (["in"], wintypes.DWORD, "color")),
            COMMETHOD([], HRESULT, "GetBackgroundColor", (["out"], POINTER(wintypes.DWORD), "color")),
            COMMETHOD([], HRESULT, "SetPosition", (["in"], ctypes.c_int, "position")),
        ]

    return comtypes.CoCreateInstance(GUID("{C2CF3110-460E-4FC1-B9D0-8A1C0C9CC4BD}"),
                                     interface=IDesktopWallpaper, clsctx=comtypes.CLSCTX_LOCAL_SERVER)


def list_monitors(dw) -> list[tuple[str, int, int]]:
    """[(id, ширина, высота)] подключённых мониторов, в физических пикселях."""
    result = []
    for i in range(dw.GetMonitorDevicePathCount()):
        mid = dw.GetMonitorDevicePathAt(i)
        if not mid:
            continue
        try:
            r = dw.GetMonitorRECT(mid)
        except Exception:  # noqa: BLE001 — монитор отключён
            continue
        result.append((mid, r.right - r.left, r.bottom - r.top))
    return result


# ---------- генерация ----------
def generate_for_monitors(cfg: dict, monitors) -> list[Path]:
    from batch import BatchSpec, build_config
    import palettes
    from core import generate

    palette = cfg["palette"]
    if cfg.get("color") is None and cfg.get("hue") is None and palette in (None, "random"):
        palette = secrets.choice(list(palettes.NAMED))  # одна палитра на оба монитора
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    paths = []
    for idx, (_, w, h) in enumerate(monitors):
        seed = secrets.randbelow(2**31)
        spec = BatchSpec(size=f"{w}x{h}", palette=palette, color=cfg.get("color"), hue=cfg.get("hue"),
                         scheme=cfg["scheme"], dominance=cfg["dominance"], bg=cfg["bg"],
                         shapes=tuple(cfg["shapes"]), effects=cfg["effects"] or "none",
                         variations=cfg["variations"])
        img, _ = generate(build_config(spec, seed), seed)
        path = OUT_DIR / f"wp_{stamp}_m{idx}_s{seed}.png"
        img.save(path, "PNG", compress_level=1)  # быстрее сжатие — меньше нагрузка на CPU
        paths.append(path)
    return paths


def cleanup(keep_cycles: int, monitors: int) -> None:
    files = sorted(OUT_DIR.glob("wp_*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[max(keep_cycles, 1) * max(monitors, 1):]:
        try:
            old.unlink()
        except OSError:
            pass


def lower_priority() -> None:
    """Фоновый режим процесса: низкий приоритет CPU, диска и памяти, чтобы смена обоев не тормозила систему."""
    try:
        k = _kernel32()
        k.GetCurrentProcess.restype = wintypes.HANDLE
        k.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k.SetPriorityClass.restype = wintypes.BOOL
        me = k.GetCurrentProcess()
        # фоновый режим (низкий приоритет CPU + диска + памяти); если не вышло — хотя бы IDLE
        if not k.SetPriorityClass(me, 0x00100000):  # PROCESS_MODE_BACKGROUND_BEGIN
            k.SetPriorityClass(me, 0x00000040)      # IDLE_PRIORITY_CLASS
    except Exception as e:  # noqa: BLE001
        log(f"не удалось понизить приоритет: {e}")


def change_once() -> None:
    import comtypes
    comtypes.CoInitialize()
    cfg = load_config()
    dw = _desktop_wallpaper()
    monitors = list_monitors(dw)
    if not monitors:
        raise RuntimeError("не найдено ни одного монитора")
    paths = generate_for_monitors(cfg, monitors)
    dw.SetPosition(4)  # DWPOS_FILL
    for (mid, _, _), path in zip(monitors, paths):
        dw.SetWallpaper(mid, str(path))
    cleanup(int(cfg["keep"]), len(monitors))
    log(f"обои сменены: {', '.join(p.name for p in paths)}")


# ---------- фоновый процесс ----------
def _kernel32():
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateMutexW.restype = wintypes.HANDLE
    k.OpenMutexW.restype = wintypes.HANDLE
    return k


def is_running() -> bool:
    k = _kernel32()
    h = k.OpenMutexW(0x00100000, False, MUTEX_NAME)  # SYNCHRONIZE
    if h:
        k.CloseHandle(h)
        return True
    return False


def run_loop() -> None:
    k = _kernel32()
    mutex = k.CreateMutexW(None, False, MUTEX_NAME)
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS — уже запущен
        return
    STOP_FLAG.unlink(missing_ok=True)
    NOW_FLAG.unlink(missing_ok=True)
    log("фоновый процесс запущен")
    first = True
    while True:
        try:
            change_once()
            failed = False
        except Exception:  # noqa: BLE001 — не падаем, пробуем снова
            log("ошибка смены обоев:\n" + traceback.format_exc())
            failed = True
        wait = 60 if failed else int(load_config()["interval_min"]) * 60
        for _ in range(max(wait, 5)):
            if STOP_FLAG.exists():
                STOP_FLAG.unlink(missing_ok=True)
                log("фоновый процесс остановлен")
                k.CloseHandle(mutex)
                return
            if NOW_FLAG.exists():
                NOW_FLAG.unlink(missing_ok=True)
                break
            time.sleep(1)
        first = False


def _pythonw() -> str:
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return str(w if w.exists() else exe)


def _launch_cmd(sub: str) -> list[str]:
    """Команда запуска подкоманды этого модуля: из исходников — pythonw wallpaper.py, из exe — PRG.exe wallpaper."""
    if FROZEN:
        return [sys.executable, "wallpaper", sub]
    return [_pythonw(), str(ROOT / "wallpaper.py"), sub]


def _spawn(sub: str, flags: int) -> None:
    # PYINSTALLER_RESET_ENVIRONMENT: дочерний exe должен быть независимым процессом со своей распаковкой,
    # иначе он потеряет файлы, когда завершится родитель.
    env = {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}
    subprocess.Popen(_launch_cmd(sub), cwd=DATA_DIR, creationflags=flags, close_fds=True, env=env)


def start_background() -> bool:
    if is_running():
        return False
    _spawn("run", 0x00000008 | 0x00000200 | 0x08000000)  # DETACHED | NEW_PROCESS_GROUP | NO_WINDOW
    return True


def stop_background(timeout: float = 5.0) -> bool:
    if not is_running():
        return False
    STOP_FLAG.write_text("1")
    end = time.time() + timeout
    while time.time() < end and is_running():
        time.sleep(0.2)
    return True


def change_now() -> None:
    """Если фоновый процесс работает — просим сменить обои сразу; иначе — разовая смена в отдельном процессе."""
    if is_running():
        NOW_FLAG.write_text("1")
    else:
        _spawn("once", 0x08000000)  # NO_WINDOW


# ---------- автозапуск (ярлык в папке «Автозагрузка») ----------
def _startup_link() -> Path:
    appdata = Path(subprocess.check_output(
        ["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Startup')"], text=True).strip())
    return appdata / STARTUP_LINK_NAME


def autostart_enabled() -> bool:
    return _startup_link().exists()


def set_autostart(enable: bool) -> None:
    link = _startup_link()
    if not enable:
        link.unlink(missing_ok=True)
        return
    ps = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:PRG_LNK);"
        "$s.TargetPath=$env:PRG_TARGET;$s.Arguments=$env:PRG_ARGS;$s.WorkingDirectory=$env:PRG_CWD;"
        "$s.IconLocation=$env:PRG_ICON;$s.Description='PRG wallpaper changer';$s.Save()"
    )
    cmd = _launch_cmd("run")
    icon = sys.executable if FROZEN else str(ROOT / "assets" / "prg.ico")
    env = {**os.environ, "PRG_LNK": str(link), "PRG_TARGET": cmd[0],
           "PRG_ARGS": " ".join(f'"{c}"' for c in cmd[1:]), "PRG_CWD": str(DATA_DIR), "PRG_ICON": icon}
    subprocess.check_call(["powershell", "-NoProfile", "-Command", ps], env=env)


def main(argv=None) -> int:
    try:  # физические пиксели мониторов, без масштабирования Windows
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # noqa: BLE001
        pass
    p = argparse.ArgumentParser(description="Автосмена обоев из сгенерированных изображений")
    p.add_argument("command", choices=["run", "once", "start", "stop", "autostart", "status"])
    p.add_argument("arg", nargs="?", choices=["on", "off"])
    a = p.parse_args(argv)
    if a.command in ("run", "once"):
        lower_priority()
    if a.command == "run":
        run_loop()
    elif a.command == "once":
        change_once()
    elif a.command == "start":
        print("запущен" if start_background() else "уже запущен")
    elif a.command == "stop":
        print("остановлен" if stop_background() else "не был запущен")
    elif a.command == "autostart":
        if a.arg is None:
            print("автозапуск:", "включён" if autostart_enabled() else "выключен")
        else:
            set_autostart(a.arg == "on")
            print("автозапуск:", "включён" if a.arg == "on" else "выключен")
    else:
        print("работает" if is_running() else "не запущен", "| автозапуск:",
              "включён" if autostart_enabled() else "выключен")
    return 0


if __name__ == "__main__":
    sys.exit(main())

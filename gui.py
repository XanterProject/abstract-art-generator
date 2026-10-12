"""Графический интерфейс PRG (Tkinter). Запуск: python gui.py

Тонкая обёртка над batch.BatchSpec / core.generate: вся логика генерации общая с CLI.
"""
from __future__ import annotations

import os
import queue
import secrets
import threading
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from PIL import Image, ImageTk

import canvas_size
import palettes
import registry
import wallpaper
from batch import BatchSpec, build_config, run_batch
from core import generate

PREVIEW_MAX = (640, 420)
DEFAULT_ON = {"shadow", "vignette", "grain"}
AUTO_OPEN_OVER = 4  # после батча больше стольких файлов папка открывается сама


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Picture Random Generator")
        registry.load_plugins()
        self._photo = None
        self._busy = False
        self._q: queue.Queue = queue.Queue()
        self.after(80, self._poll)

        left = ttk.Frame(self, padding=10)
        left.grid(row=0, column=0, sticky="ns")
        right = ttk.Frame(self, padding=10)
        right.grid(row=0, column=1, sticky="nsew")
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # --- размер
        box = ttk.LabelFrame(left, text="Размер холста", padding=6)
        box.pack(fill="x")
        self.size_var = tk.StringVar(value="fhd")
        presets = list(canvas_size.PRESETS) + ["random", "custom"]
        cb = ttk.Combobox(box, textvariable=self.size_var, values=presets, state="readonly", width=12)
        cb.grid(row=0, column=0, columnspan=4, sticky="w")
        cb.bind("<<ComboboxSelected>>", lambda e: self._on_size())
        self.w_var, self.h_var = tk.StringVar(value="1920"), tk.StringVar(value="1080")
        ttk.Label(box, text="Ш").grid(row=1, column=0)
        self.w_entry = ttk.Entry(box, textvariable=self.w_var, width=7)
        self.w_entry.grid(row=1, column=1)
        ttk.Label(box, text="В").grid(row=1, column=2)
        self.h_entry = ttk.Entry(box, textvariable=self.h_var, width=7)
        self.h_entry.grid(row=1, column=3)
        self._on_size()

        # --- цвет
        box = ttk.LabelFrame(left, text="Палитра / цвет", padding=6)
        box.pack(fill="x", pady=6)
        self.mode = tk.StringVar(value="palette")
        self.palette_var = tk.StringVar(value="random")
        ttk.Radiobutton(box, text="Палитра", variable=self.mode, value="palette").grid(row=0, column=0, sticky="w")
        ttk.Combobox(box, textvariable=self.palette_var, values=["random"] + list(palettes.NAMED),
                     state="readonly", width=12).grid(row=0, column=1, columnspan=2, sticky="w")
        ttk.Radiobutton(box, text="Доминанта", variable=self.mode, value="color").grid(row=1, column=0, sticky="w")
        self.color_var = tk.StringVar(value="#3366ff")
        self.swatch = tk.Label(box, width=3, bg=self.color_var.get(), relief="sunken")
        self.swatch.grid(row=1, column=1)
        ttk.Button(box, text="Выбрать…", command=self._pick_color).grid(row=1, column=2)
        self.scheme_var = tk.StringVar(value="analogous")
        ttk.Label(box, text="Схема").grid(row=2, column=0, sticky="w")
        ttk.Combobox(box, textvariable=self.scheme_var, values=palettes.SCHEMES, state="readonly",
                     width=12).grid(row=2, column=1, columnspan=2, sticky="w")
        self.dom_var = tk.DoubleVar(value=0.6)
        ttk.Label(box, text="Доля").grid(row=3, column=0, sticky="w")
        ttk.Scale(box, from_=0.2, to=1.0, variable=self.dom_var, length=110).grid(row=3, column=1, columnspan=2)
        self.bg_var = tk.StringVar(value="auto")
        ttk.Label(box, text="Фон").grid(row=4, column=0, sticky="w")
        ttk.Combobox(box, textvariable=self.bg_var, values=palettes.BG_MODES, state="readonly",
                     width=12).grid(row=4, column=1, columnspan=2, sticky="w")

        # --- эффекты (из реестра)
        box = ttk.LabelFrame(left, text="Эффекты", padding=6)
        box.pack(fill="x")
        self.fx_vars = {}
        for i, name in enumerate(registry.describe_effects()):
            v = tk.BooleanVar(value=name in DEFAULT_ON)
            self.fx_vars[name] = v
            ttk.Checkbutton(box, text=name, variable=v).grid(row=i // 2, column=i % 2, sticky="w", padx=4)
        self.var_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="Вариации (случайный поднабор)", variable=self.var_var).grid(
            row=10, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # --- батч
        box = ttk.LabelFrame(left, text="Генерация", padding=6)
        box.pack(fill="x", pady=6)
        self.seed_var = tk.StringVar(value=str(secrets.randbelow(2**31)))
        self.count_var = tk.StringVar(value="4")
        self.out_var = tk.StringVar(value="out")
        self.shapes_var = tk.StringVar(value="12-32")
        for r, (label, var) in enumerate((("Seed", self.seed_var), ("Кол-во", self.count_var),
                                          ("Фигур", self.shapes_var))):
            ttk.Label(box, text=label).grid(row=r, column=0, sticky="w")
            ttk.Entry(box, textvariable=var, width=14).grid(row=r, column=1, sticky="w")
        ttk.Button(box, text="🎲", width=3, command=lambda: self.seed_var.set(str(secrets.randbelow(2**31)))
                   ).grid(row=0, column=2)
        ttk.Label(box, text="Папка").grid(row=3, column=0, sticky="w")
        ttk.Entry(box, textvariable=self.out_var, width=14).grid(row=3, column=1, sticky="w")
        ttk.Button(box, text="…", width=3, command=self._pick_dir).grid(row=3, column=2)

        self.btn_prev = ttk.Button(left, text="Предпросмотр", command=self._preview)
        self.btn_prev.pack(fill="x")
        self.btn_batch = ttk.Button(left, text="Сгенерировать батч", command=self._batch)
        self.btn_batch.pack(fill="x", pady=4)
        self.progress = ttk.Progressbar(left, mode="determinate")
        self.progress.pack(fill="x")
        ttk.Button(left, text="Открыть папку с результатами", command=self._open_out).pack(fill="x", pady=(6, 0))

        # --- превью
        self.canvas = tk.Label(right, bg="#222", width=80, height=26)
        self.canvas.pack(fill="both", expand=True)
        self.status = tk.StringVar(value="Готово")
        ttk.Label(right, textvariable=self.status).pack(anchor="w", pady=(6, 0))

        # --- автосмена обоев
        box = ttk.LabelFrame(right, text="Обои рабочего стола (по картинке на каждый монитор)", padding=6)
        box.pack(fill="x", pady=(10, 0))
        self.interval_var = tk.StringVar(value=str(wallpaper.load_config()["interval_min"]))
        ttk.Label(box, text="Менять каждые, мин:").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(box, from_=1, to=1440, textvariable=self.interval_var, width=6).grid(row=0, column=1, padx=4)
        self.autostart_var = tk.BooleanVar(value=wallpaper.autostart_enabled())
        ttk.Checkbutton(box, text="Запускать при входе в Windows", variable=self.autostart_var
                        ).grid(row=0, column=2, padx=12)
        ttk.Button(box, text="Применить и запустить", command=self._wp_apply).grid(row=1, column=0, columnspan=2,
                                                                                  sticky="ew", pady=(6, 0))
        ttk.Button(box, text="Сменить сейчас", command=self._wp_now).grid(row=1, column=2, sticky="w",
                                                                         padx=12, pady=(6, 0))
        ttk.Button(box, text="Остановить", command=self._wp_stop).grid(row=1, column=3, pady=(6, 0))
        self.wp_status = tk.StringVar()
        ttk.Label(box, textvariable=self.wp_status).grid(row=2, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self._wp_refresh()

    # --- helpers
    def _on_size(self):
        custom = self.size_var.get() == "custom"
        state = "normal" if custom else "disabled"
        self.w_entry.configure(state=state)
        self.h_entry.configure(state=state)
        if self.size_var.get() in canvas_size.PRESETS:
            w, h = canvas_size.PRESETS[self.size_var.get()]
            for var, val in ((self.w_var, w), (self.h_var, h)):
                var.set(str(val))

    def _pick_color(self):
        c = colorchooser.askcolor(color=self.color_var.get(), parent=self)[1]
        if c:
            self.color_var.set(c)
            self.swatch.configure(bg=c)
            self.mode.set("color")

    def _pick_dir(self):
        d = filedialog.askdirectory(parent=self)
        if d:
            self.out_var.set(d)

    # --- обои
    def _wp_refresh(self):
        run = "работает" if wallpaper.is_running() else "остановлена"
        self.wp_status.set(f"Автосмена: {run}. Настройки берутся из палитры, эффектов и числа фигур слева.")

    def _wp_apply(self):
        try:
            spec = self._spec()
            interval = int(self.interval_var.get())
            if interval < 1:
                raise ValueError("интервал должен быть не меньше 1 минуты")
        except ValueError as e:
            return messagebox.showerror("Ошибка", str(e), parent=self)
        use_color = spec.color is not None
        wallpaper.save_config({
            "interval_min": interval, "palette": spec.palette or "random", "color": spec.color,
            "scheme": spec.scheme, "dominance": spec.dominance, "bg": spec.bg, "shapes": list(spec.shapes),
            "effects": spec.effects, "variations": spec.variations,
        })
        autostart = self.autostart_var.get()
        self.wp_status.set("Применяю настройки…")

        def work():
            wallpaper.set_autostart(autostart)
            wallpaper.stop_background()
            wallpaper.start_background()

        self._run_bg(work, lambda res, err: (self.wp_status.set(f"Ошибка: {err}") if err else self._wp_refresh()))

    def _wp_now(self):
        if not wallpaper.is_running():
            self._wp_apply_config_only()
        wallpaper.change_now()
        self.wp_status.set("Обои меняются (на 4K это может занять до минуты)…")

    def _wp_apply_config_only(self):
        """Для разовой смены без фонового процесса используем текущие настройки окна."""
        try:
            spec = self._spec()
        except ValueError:
            return
        cfg = wallpaper.load_config()
        cfg.update({"palette": spec.palette or "random", "color": spec.color, "scheme": spec.scheme,
                    "dominance": spec.dominance, "bg": spec.bg, "shapes": list(spec.shapes),
                    "effects": spec.effects, "variations": spec.variations})
        wallpaper.save_config(cfg)

    def _wp_stop(self):
        self.wp_status.set("Останавливаю…")
        self._run_bg(wallpaper.stop_background, lambda res, err: self._wp_refresh())

    def _open_out(self):
        path = Path(self.out_var.get()).resolve()
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(path)  # Windows: открыть в Проводнике

    def _spec(self) -> BatchSpec:
        size = f"{self.w_var.get()}x{self.h_var.get()}" if self.size_var.get() == "custom" else self.size_var.get()
        names = [n for n, v in self.fx_vars.items() if v.get()]
        parts = self.shapes_var.get().replace("..", "-").split("-")
        shapes = (int(parts[0]), int(parts[-1]))
        use_color = self.mode.get() == "color"
        return BatchSpec(
            size=size, palette=None if use_color else self.palette_var.get(),
            color=self.color_var.get() if use_color else None, scheme=self.scheme_var.get(),
            dominance=round(self.dom_var.get(), 2), bg=self.bg_var.get(), shapes=shapes,
            effects=",".join(names) if names else "none", variations=self.var_var.get(),
        )

    def _set_busy(self, busy: bool, text: str = ""):
        self._busy = busy
        for b in (self.btn_prev, self.btn_batch):
            b.configure(state="disabled" if busy else "normal")
        if text:
            self.status.set(text)

    def _run_bg(self, work, done):
        def target():
            try:
                self._q.put(lambda res=work(): done(res, None))
            except Exception as e:  # noqa: BLE001 — показываем пользователю любую ошибку
                self._q.put(lambda e=e: done(None, e))
        threading.Thread(target=target, daemon=True).start()

    def _poll(self):
        """Выполняет в главном потоке колбэки, поставленные рабочими потоками (tkinter не потокобезопасен)."""
        try:
            while True:
                self._q.get_nowait()()
        except queue.Empty:
            pass
        self.after(80, self._poll)

    # --- actions
    def _preview(self):
        try:
            spec, seed = self._spec(), int(self.seed_var.get())
            cfg = build_config(spec, seed)
        except ValueError as e:
            return messagebox.showerror("Ошибка", str(e), parent=self)
        w, h = cfg.size
        warn = canvas_size.size_warning(w, h)
        self._set_busy(True, f"Предпросмотр {w}x{h}…" + (f" {warn}" if warn else ""))

        def work():
            img, meta = generate(cfg, seed)
            img.thumbnail(PREVIEW_MAX, Image.Resampling.LANCZOS)
            return img, meta

        def done(res, err):
            self._set_busy(False)
            if err:
                return self.status.set(f"Ошибка: {err}")
            img, meta = res
            self._photo = ImageTk.PhotoImage(img)
            self.canvas.configure(image=self._photo, width=img.width, height=img.height)
            self.status.set(f"seed={meta['seed']}  {meta['size'][0]}x{meta['size'][1]}  палитра: {meta['palette']['name']}")
        self._run_bg(work, done)

    def _batch(self):
        try:
            spec, seed, count = self._spec(), int(self.seed_var.get()), int(self.count_var.get())
            build_config(spec, seed)
        except ValueError as e:
            return messagebox.showerror("Ошибка", str(e), parent=self)
        self.progress.configure(maximum=count, value=0)
        self._set_busy(True, f"Генерация 0/{count}…")

        def on_progress(done_n, total, meta):
            self._q.put(lambda: (self.progress.configure(value=done_n),
                                 self.status.set(f"Генерация {done_n}/{total}: {meta['file']}")))

        def done(res, err):
            self._set_busy(False)
            self.status.set(f"Ошибка: {err}" if err else f"Готово: {count} файл(ов) в «{self.out_var.get()}»")
            if not err and count > AUTO_OPEN_OVER:
                self._open_out()

        out_dir = self.out_var.get()  # читаем Tk-переменную здесь: из рабочего потока к Tk обращаться нельзя
        self._run_bg(lambda: run_batch(spec, count, seed, out_dir, workers=1, on_progress=on_progress), done)


if __name__ == "__main__":
    App().mainloop()

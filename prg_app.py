"""Единая точка входа для exe (и для запуска из исходников).

  PRG.exe                      — графический интерфейс
  PRG.exe wallpaper <команда>  — фоновая смена обоев (run|once|start|stop|autostart|status)
"""
import multiprocessing
import sys


def main() -> int:
    multiprocessing.freeze_support()  # нужен для батча в нескольких процессах внутри exe
    if len(sys.argv) > 1 and sys.argv[1] == "wallpaper":
        import wallpaper
        return wallpaper.main(sys.argv[2:])
    import gui
    gui.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())

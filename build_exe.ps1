# Build PRG.exe (single file, no console). Run: powershell -File build_exe.ps1
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$py = '.\.venv\Scripts\python.exe'
& $py -m pip install -q pyinstaller
& $py -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name PRG --icon assets\prg.ico `
    --collect-submodules shapes --collect-submodules effects `
    --hidden-import comtypes --hidden-import tkinter.colorchooser `
    --exclude-module pytest --exclude-module matplotlib `
    prg_app.py
Write-Host "Done: dist\PRG.exe"

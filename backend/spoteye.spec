# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Spoteye (Windows, onedir). Built by ..\build.ps1:
#   python -m PyInstaller backend\spoteye.spec --noconfirm --clean --distpath dist --workpath build\pyi
#
# Layout of the result (dist\Spoteye\):
#   Spoteye.exe            console app; no arguments = `serve`
#   _internal\             Python runtime + packages; sys._MEIPASS points here
#   _internal\ui\          the built React app (config.FRONTEND_DIST when frozen)
#   _internal\defaults.json  optional baked-in Spotify Client ID (build.ps1 -ClientId)
#   bin\                   ffmpeg.exe, deno.exe, yt-dlp.exe (copied in by build.ps1, not by this spec)

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

BACKEND = Path(SPECPATH)  # noqa: F821  (SPECPATH is defined by PyInstaller)
ROOT = BACKEND.parent
UI_DIST = ROOT / "frontend" / "dist"
DEFAULTS = ROOT / "build" / "defaults.json"
ICON = ROOT / "assets" / "spoteye.ico"

if not (UI_DIST / "index.html").is_file():
    raise SystemExit(f"Frontend not built: {UI_DIST}\\index.html is missing (npm --prefix frontend run build)")

datas = [(str(UI_DIST), "ui")]
datas += collect_data_files("ytmusicapi")  # locale files used by ytmusicapi at runtime
if DEFAULTS.is_file():
    datas.append((str(DEFAULTS), "."))

hiddenimports = []
hiddenimports += collect_submodules("app")      # commands/routers are imported by name in places
hiddenimports += collect_submodules("uvicorn")  # protocol/loop implementations are picked at runtime
hiddenimports += collect_submodules("mutagen")  # mutagen.File imports format modules lazily
hiddenimports += collect_submodules("rich")     # rich loads some tables lazily
hiddenimports += ["sqlalchemy.dialects.sqlite"]
# yt_dlp ships its own PyInstaller hook; the library is only the fallback when bin\yt-dlp.exe is missing.

a = Analysis(
    [str(BACKEND / "spoteye_main.py")],
    pathex=[str(BACKEND)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "_pytest", "tests", "PyInstaller", "IPython", "matplotlib", "numpy"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Spoteye",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX-packed exes trigger far more antivirus false positives
    console=True,  # the console window is the "server is running" indicator; closing it quits
    disable_windowed_traceback=False,
    icon=str(ICON) if ICON.is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Spoteye",
)

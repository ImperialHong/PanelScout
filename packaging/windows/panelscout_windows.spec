# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

project_root = Path(SPECPATH).parents[1]
launcher = project_root / "src" / "panelscout" / "windows_launcher.py"

playwright_datas, playwright_binaries, playwright_hiddenimports = collect_all("playwright")

a = Analysis(
    [str(launcher)],
    pathex=[str(project_root / "src"), str(project_root)],
    binaries=playwright_binaries,
    datas=playwright_datas,
    hiddenimports=playwright_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PanelScout",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PanelScout",
)

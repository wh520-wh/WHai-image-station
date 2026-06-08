# -*- mode: python ; coding: utf-8 -*-

import os

src_dir = os.path.dirname(os.path.abspath(SPEC))
src_path = os.path.join(src_dir, 'src')

a = Analysis(
    [os.path.join(src_path, 'main.py')],
    pathex=[],
    binaries=[],
    datas=[(src_path, 'src')],
    hiddenimports=['PySide6', 'httpx', 'PIL', 'cryptography', 'aiosqlite'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['setuptools', 'pkg_resources', 'pygame', 'yt_dlp'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='WHai-image-station',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
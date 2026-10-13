# -*- mode: python ; coding: utf-8 -*-

import os

src_dir = os.path.dirname(os.path.abspath(SPEC))
src_path = os.path.join(src_dir, 'src')
console_build = os.environ.get('WHAI_CONSOLE_BUILD') == '1'
application_name = 'WHai-image-station-debug' if console_build else 'WHai-image-station'

a = Analysis(
    [os.path.join(src_path, 'main.py')],
    pathex=[src_dir],
    binaries=[],
    datas=[(os.path.join(src_path, 'ui'), 'src/ui')],
    hiddenimports=['PySide6.QtSvg'],
    hookspath=[os.path.join(src_dir, 'tools', 'pyinstaller_hooks')],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['setuptools', 'pkg_resources', 'pygame', 'yt_dlp'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
if os.name == 'nt':
    # Qt uses the Windows ICU ABI; a different ICU on PATH breaks QtCore loading.
    a.binaries = [entry for entry in a.binaries if not os.path.basename(entry[0]).lower().startswith(('icuuc', 'icuin', 'icudt'))]

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=application_name,
    icon=os.path.join(src_path, 'ui', 'assets', 'app.ico'),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=console_build,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
collect = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=application_name)

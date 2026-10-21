# -*- mode: python ; coding: utf-8 -*-


import json
import os
from pathlib import Path
import sys
from PyInstaller.config import CONF

sys.path.insert(0, str(Path(SPECPATH)))
from utils.provider_config import public_build_configuration

# Bundle public identity only, never the environment or user settings/cache.
provider_config_path = Path(CONF['workpath']) / 'provider_config.json'
provider_config = public_build_configuration(os.environ)
provider_config_path.parent.mkdir(parents=True, exist_ok=True)
provider_config_path.write_text(json.dumps(provider_config), encoding='utf-8')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('VERSION', '.'), (str(provider_config_path), '.')],
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name='TraceSync',
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
    icon=['assets\\icons\\tracesync.png'],
)

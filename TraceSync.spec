# -*- mode: python ; coding: utf-8 -*-

import json
import os
from pathlib import Path


google_client_id = os.environ.get("TRACESYNC_GOOGLE_CLIENT_ID", "").strip()
if not google_client_id:
    raise SystemExit(
        "Set TRACESYNC_GOOGLE_CLIENT_ID to the public desktop OAuth client ID "
        "before packaging the Google Drive build."
    )

provider_config_path = Path(SPECPATH) / "build" / "provider_config.json"
provider_config_path.parent.mkdir(parents=True, exist_ok=True)
provider_config_path.write_text(
    json.dumps({"google_drive_client_id": google_client_id}),
    encoding="utf-8",
)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('VERSION', '.'), (str(provider_config_path), '.')],
    # Keyring selects the Windows Credential Manager backend through package
    # entry points, which PyInstaller cannot discover from the lazy imports in
    # GoogleTokenStore. Bundle the backend and let its imports pull in
    # pywin32-ctypes dependencies.
    hiddenimports=['keyring.backends.Windows'],
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

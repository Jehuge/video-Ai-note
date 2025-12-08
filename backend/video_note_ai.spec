# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all, copy_metadata

datas = [
    ('../frontend/dist', 'dist'),
]

# 检查 .env 是否存在
if os.path.exists('.env'):
    datas.append(('.env', '.'))

# 收集依赖的元数据和文件
binaries = []
hiddenimports = [
    'uvicorn.loops.auto',
    'uvicorn.loops.asyncio',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11',
    'uvicorn.lifespan.on',
    'uvicorn.logging',
    'app.routers.note',
    'app.routers.model',
    'faster_whisper',
    'engineio.async_drivers.asgi',
    'python-multipart', 
]

# Collect libraries
for lib in ['faster_whisper', 'ctranslate2', 'imageio_ffmpeg', 'google.generativeai', 'openai', 'pywebview']:
    try:
        tmp_ret = collect_all(lib)
        datas += tmp_ret[0]
        binaries += tmp_ret[1]
        hiddenimports += tmp_ret[2]
    except Exception as e:
        print(f"Warning: Could not collect {lib}: {e}")

# Copy metadata for some packages that might need it
def safe_copy_metadata(package_name):
    try:
        return copy_metadata(package_name)
    except Exception as e:
        print(f"Warning: Could not copy metadata for {package_name}: {e}")
        return []

datas += safe_copy_metadata('tqdm')
# datas += safe_copy_metadata('regex') # regex might not be installed
datas += safe_copy_metadata('requests')
datas += safe_copy_metadata('packaging')
datas += safe_copy_metadata('filelock')
datas += safe_copy_metadata('numpy')
datas += safe_copy_metadata('tokenizers')
datas += safe_copy_metadata('huggingface-hub')
datas += safe_copy_metadata('google-generativeai')
datas += safe_copy_metadata('openai')

a = Analysis(
    ['app_entry.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='VideoNoteAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False, 
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
    name='VideoNoteAI',
)
app = BUNDLE(
    coll,
    name='VideoNoteAI.app',
    icon=None,
    bundle_identifier='com.jackjia.videonoteai',
)

# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata

is_macos = sys.platform == 'darwin'
entitlements_file = 'entitlements.mac.plist' if is_macos and os.path.exists('entitlements.mac.plist') else None

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
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.lifespan.on',
    'uvicorn.logging',
    'app.routers.note',
    'app.routers.model',
    'app.routers.extension',
    'app.services.note',
    'app.services.web_video',
    'app.services.extension_bridge',
    'app.services.model_provider',
    'app.services.model_settings',
    'app.services.openai_client',
    'app.transcriber.transcriber_provider',
    'app.transcriber.fast_whisper',
    'faster_whisper',
    'yt_dlp',
    'python_multipart',
]

def safe_collect_data(package_name):
    try:
        return collect_data_files(package_name)
    except Exception as e:
        print(f"Warning: Could not collect data for {package_name}: {e}")
        return []


def safe_collect_binaries(package_name):
    try:
        return collect_dynamic_libs(package_name)
    except Exception as e:
        print(f"Warning: Could not collect binaries for {package_name}: {e}")
        return []


for lib in ['faster_whisper', 'ctranslate2', 'imageio_ffmpeg', 'google.generativeai', 'openai', 'yt_dlp', 'playwright']:
    datas += safe_collect_data(lib)
    binaries += safe_collect_binaries(lib)

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
datas += safe_copy_metadata('yt-dlp')
datas += safe_copy_metadata('playwright')

a = Analysis(
    ['app_entry.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch',
        'torchvision',
        'torchaudio',
        'tensorflow',
        'transformers',
        'pandas',
        'sklearn',
        'scipy',
        'matplotlib',
        'pyarrow',
        'IPython',
        'notebook',
        'jupyter',
    ],
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
    upx=not is_macos,
    console=False, 
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=os.getenv('CODESIGN_IDENTITY') if is_macos else None,
    entitlements_file=entitlements_file,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=not is_macos,
    upx_exclude=[],
    name='VideoNoteAI',
)
app = BUNDLE(
    coll,
    name='VideoNoteAI.app',
    icon='icon.icns',
    bundle_identifier='com.jackjia.videonoteai',
    info_plist={
        'CFBundleName': 'VideoNoteAI',
        'CFBundleDisplayName': 'Video Note AI',
        'CFBundleShortVersionString': '1.1.0',
        'CFBundleVersion': '1.1.0',
        'LSMinimumSystemVersion': '12.0',
        'NSHighResolutionCapable': True,
    },
)

# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\HyperX_DV\\Desktop\\PythonProject\\Mic_Effect_Tester\\Main.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\HyperX_DV\\Desktop\\PythonProject\\Mic_Effect_Tester\\resources\\AINR_Test.wav', 'resources'), ('C:\\Users\\HyperX_DV\\Desktop\\PythonProject\\Mic_Effect_Tester\\resources\\Limiter_Test.wav', 'resources'), ('C:\\Users\\HyperX_DV\\Desktop\\PythonProject\\Mic_Effect_Tester\\resources\\Compressor_Test.wav', 'resources')],
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
    name='Mic_Effect_Tester_1.0.3',
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

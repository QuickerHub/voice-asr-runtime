# PyInstaller spec — quicker-voice-runtime (Windows x64, onedir)
# Run: uv run pyinstaller quicker-voice-runtime.spec

from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH)
ENTRY = ROOT / "packaging" / "runtime_entry.py"

sherpa_datas, sherpa_binaries, sherpa_hiddenimports = collect_all("sherpa_onnx")

a = Analysis(
    [str(ENTRY)],
    pathex=[str(ROOT / "src")],
    binaries=sherpa_binaries,
    datas=sherpa_datas,
    hiddenimports=[
        *sherpa_hiddenimports,
        "aiohttp",
        "aiohttp.web",
        "multidict",
        "yarl",
        "frozenlist",
        "aiosignal",
        "async_timeout",
        "charset_normalizer",
        "idna",
        "numpy",
        "quicker_voice_runtime",
        "quicker_voice_runtime.__main__",
        "quicker_voice_runtime.server",
        "quicker_voice_runtime.session",
        "quicker_voice_runtime.protocol",
        "quicker_voice_runtime.config",
        "quicker_voice_runtime.paths",
        "quicker_voice_runtime.download_model",
        "quicker_voice_runtime.recognizer",
        "quicker_voice_runtime.recognizer.stub",
        "quicker_voice_runtime.recognizer.sherpa_onnx",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "pygments"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="quicker-voice-runtime",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
    upx=False,
    upx_exclude=[],
    name="quicker-voice-runtime",
)

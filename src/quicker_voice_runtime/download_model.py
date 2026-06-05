"""Download offline ASR model for sherpa-onnx."""

from __future__ import annotations

import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from quicker_voice_runtime.paths import plugin_data_root

MODEL_PRESETS: dict[str, dict[str, str]] = {
    "sensevoice": {
        "url": (
            "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
            "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17-int8.tar.bz2"
        ),
        "dir": "sensevoice",
        "label": "SenseVoice int8 (~160MB, zh/en/ja/ko/yue + ITN/punctuation)",
    },
    "paraformer": {
        "url": (
            "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
            "sherpa-onnx-paraformer-zh-small-2024-03-09.tar.bz2"
        ),
        "dir": "paraformer-zh",
        "label": "Paraformer zh-small (~76MB)",
    },
}
DEFAULT_PRESET = "sensevoice"
REQUIRED_FILES = ("tokens.txt",)
MODEL_FILE_CANDIDATES = ("model.int8.onnx", "model.onnx")
OPTIONAL_FILES = ("am.mvn", "config.yaml")


def package_root() -> Path:
    return plugin_data_root()


def resolve_preset(name: str | None = None) -> str:
    raw = (name or os.environ.get("QUICKER_VOICE_ASR_MODEL") or DEFAULT_PRESET).strip().lower()
    if raw in MODEL_PRESETS:
        return raw
    if raw in {"sensevoice", "sense-voice", "sense_voice"}:
        return "sensevoice"
    if raw in {"paraformer", "paraformer-zh"}:
        return "paraformer"
    return DEFAULT_PRESET


def target_dir(root: Path | None = None, preset: str | None = None) -> Path:
    base = root or package_root()
    key = resolve_preset(preset)
    return base / "models" / MODEL_PRESETS[key]["dir"]


def _model_file(dest: Path) -> Path | None:
    for name in MODEL_FILE_CANDIDATES:
        path = dest / name
        if path.is_file():
            return path
    return None


def is_model_ready(dest: Path | None = None) -> bool:
    path = dest or target_dir()
    if not all((path / name).is_file() for name in REQUIRED_FILES):
        return False
    return _model_file(path) is not None


def download_archive(url: str, dest: Path) -> None:
    print(f"Downloading {url}")
    print(f"  -> {dest}")
    with urllib.request.urlopen(url, timeout=120) as response:
        total = int(response.headers.get("Content-Length") or 0)
        downloaded = 0
        block = 1024 * 1024
        with dest.open("wb") as out:
            while True:
                chunk = response.read(block)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded * 100 // total
                    print(f"\r  {pct}% ({downloaded // (1024 * 1024)} MB)", end="", flush=True)
    print()


def extract_model(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, mode="r:bz2") as tar:
        members = tar.getmembers()
        top_dirs = {
            m.name.split("/", maxsplit=1)[0]
            for m in members
            if "/" in m.name
        }
        if len(top_dirs) != 1:
            raise RuntimeError(f"Unexpected archive layout: {top_dirs}")
        prefix = f"{next(iter(top_dirs))}/"
        names_to_copy = [*REQUIRED_FILES, *MODEL_FILE_CANDIDATES, *OPTIONAL_FILES]
        for name in names_to_copy:
            member_name = prefix + name
            try:
                member = tar.getmember(member_name)
            except KeyError:
                continue
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            out_path = dest / name
            with out_path.open("wb") as out:
                shutil.copyfileobj(extracted, out)
            print(f"  wrote {out_path}")


def ensure_asr_model(root: Path | None = None, preset: str | None = None) -> Path:
    key = resolve_preset(preset)
    preset_info = MODEL_PRESETS[key]
    dest = target_dir(root, key)
    if is_model_ready(dest):
        return dest

    print(f"Fetching {preset_info['label']}")
    archive_name = preset_info["url"].rsplit("/", maxsplit=1)[-1]
    with tempfile.TemporaryDirectory(prefix="quicker-voice-model-") as tmp:
        archive = Path(tmp) / archive_name
        download_archive(preset_info["url"], archive)
        extract_model(archive, dest)

    if not is_model_ready(dest):
        raise RuntimeError(f"Model files missing after extract: {dest}")
    return dest


ensure_sensevoice_model = ensure_asr_model


def ensure_paraformer_model(root: Path | None = None) -> Path:
    return ensure_asr_model(root, preset="paraformer")


def main() -> None:
    preset = resolve_preset()
    try:
        path = ensure_asr_model(preset=preset)
    except Exception as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    model_file = _model_file(path)
    print(f"ASR model ready at {path} ({model_file.name if model_file else '?'})")


if __name__ == "__main__":
    main()

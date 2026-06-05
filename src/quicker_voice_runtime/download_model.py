"""Download offline ASR model for sherpa-onnx."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

from quicker_voice_runtime.paths import plugin_data_root

_IDENTITY_PATH = Path(__file__).resolve().parents[2] / "models" / "sensevoice-model-identity.json"

SENSEVOICE_ARCHIVE_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17.tar.bz2"
)
SENSEVOICE_MODELSCOPE_RESOLVE = (
    "https://www.modelscope.cn/models/pengzhendong/sherpa-onnx-sense-voice-zh-en-ja-ko-yue/resolve/master"
)

MODEL_PRESETS: dict[str, dict[str, str]] = {
    "sensevoice": {
        "url": SENSEVOICE_ARCHIVE_URL,
        "dir": "sensevoice",
        "label": "SenseVoice int8 (~228MB, zh/en/ja/ko/yue + ITN/punctuation)",
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


def load_sensevoice_identity() -> dict[str, Any]:
    if not _IDENTITY_PATH.is_file():
        raise RuntimeError(f"Missing model identity file: {_IDENTITY_PATH}")
    return json.loads(_IDENTITY_PATH.read_text(encoding="utf-8"))


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


def sha256_hex_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sensevoice_files(dest: Path) -> None:
    identity = load_sensevoice_identity()
    expected_files: dict[str, Any] = identity["files"]
    for name, spec in expected_files.items():
        path = dest / name
        if not path.is_file():
            raise RuntimeError(f"Missing expected model file: {name}")
        actual_size = path.stat().st_size
        expected_size = int(spec["size"])
        if actual_size != expected_size:
            raise RuntimeError(
                f"{name} size mismatch: got {actual_size}, expected {expected_size} "
                f"({identity['id']})"
            )
        actual_hash = sha256_hex_file(path)
        expected_hash = str(spec["sha256"]).lower()
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"{name} sha256 mismatch for {identity['id']}: got {actual_hash}, expected {expected_hash}"
            )


def is_model_ready(dest: Path | None = None, *, preset: str | None = None) -> bool:
    path = dest or target_dir(preset=preset)
    if resolve_preset(preset) == "sensevoice":
        try:
            verify_sensevoice_files(path)
            return True
        except RuntimeError:
            return False
    if not all((path / name).is_file() for name in REQUIRED_FILES):
        return False
    return _model_file(path) is not None


def expand_download_urls(url: str) -> list[str]:
    """Prefer domestic-friendly mirrors, then the canonical GitHub URL."""
    canonical = url.strip()
    if not canonical:
        return []

    mirrors: list[str] = []
    if canonical.startswith("https://github.com/"):
        mirrors.extend(
            [
                f"https://ghfast.top/{canonical}",
                f"https://gh-proxy.com/{canonical}",
            ]
        )
    mirrors.append(canonical)

    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in mirrors:
        if candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)
    return ordered


def download_file(url: str, dest: Path) -> None:
    last_error: Exception | None = None
    for candidate in expand_download_urls(url):
        try:
            _download_file_once(candidate, dest)
            return
        except Exception as exc:  # noqa: BLE001 — try next mirror
            last_error = exc
            dest.unlink(missing_ok=True)
            print(f"  mirror failed: {exc}", file=sys.stderr)
    if last_error is None:
        raise RuntimeError(f"No download URL resolved for {url}")
    raise RuntimeError(f"All download mirrors failed for {url}: {last_error}") from last_error


def download_archive(url: str, dest: Path) -> None:
    download_file(url, dest)


def _download_file_once(url: str, dest: Path) -> None:
    print(f"Downloading {url}")
    print(f"  -> {dest}")
    with urllib.request.urlopen(url, timeout=300) as response:
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


def download_sensevoice_from_modelscope(dest: Path) -> None:
    identity = load_sensevoice_identity()
    modelscope_base = (
        identity.get("modelscopeResolveBase")
        or identity.get("modelscope")
        or SENSEVOICE_MODELSCOPE_RESOLVE
    )
    if not str(modelscope_base).endswith("/resolve/master"):
        modelscope_base = f"{str(modelscope_base).rstrip('/')}/resolve/master"
    dest.mkdir(parents=True, exist_ok=True)
    print(f"Fetching {identity['label']} from ModelScope ({identity['id']})")
    for name in identity["files"]:
        out_path = dest / name
        url = f"{modelscope_base}/{name}"
        download_file(url, out_path)
    verify_sensevoice_files(dest)


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


def download_sensevoice_from_archive(dest: Path) -> None:
    identity = load_sensevoice_identity()
    archive_url = str(identity.get("upstream") or SENSEVOICE_ARCHIVE_URL)
    print(f"Fetching {identity['label']} from k2-fsa archive ({identity['id']})")
    archive_name = archive_url.rsplit("/", maxsplit=1)[-1]
    with tempfile.TemporaryDirectory(prefix="quicker-voice-model-") as tmp:
        archive = Path(tmp) / archive_name
        download_archive(archive_url, archive)
        extract_model(archive, dest)
    verify_sensevoice_files(dest)


def ensure_sensevoice_model(root: Path | None = None) -> Path:
    dest = target_dir(root, "sensevoice")
    if is_model_ready(dest, preset="sensevoice"):
        return dest

    errors: list[str] = []
    for fetch in (download_sensevoice_from_modelscope, download_sensevoice_from_archive):
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        try:
            fetch(dest)
            return dest
        except Exception as exc:  # noqa: BLE001 — try next source
            errors.append(f"{fetch.__name__}: {exc}")
            print(f"  source failed: {exc}", file=sys.stderr)

    raise RuntimeError(
        f"SenseVoice download failed ({load_sensevoice_identity()['id']}): {' | '.join(errors)}"
    )


def ensure_asr_model(root: Path | None = None, preset: str | None = None) -> Path:
    key = resolve_preset(preset)
    if key == "sensevoice":
        return ensure_sensevoice_model(root)

    preset_info = MODEL_PRESETS[key]
    dest = target_dir(root, key)
    if is_model_ready(dest, preset=key):
        return dest

    print(f"Fetching {preset_info['label']}")
    archive_name = preset_info["url"].rsplit("/", maxsplit=1)[-1]
    with tempfile.TemporaryDirectory(prefix="quicker-voice-model-") as tmp:
        archive = Path(tmp) / archive_name
        download_archive(preset_info["url"], archive)
        extract_model(archive, dest)

    if not is_model_ready(dest, preset=key):
        raise RuntimeError(f"Model files missing after extract: {dest}")
    return dest


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
    if preset == "sensevoice" or resolve_preset(preset) == "sensevoice":
        identity = load_sensevoice_identity()
        print(f"Verified {identity['id']}")
    print(f"ASR model ready at {path} ({model_file.name if model_file else '?'})")


if __name__ == "__main__":
    main()

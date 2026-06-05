from __future__ import annotations

import logging
import struct
from pathlib import Path

import sherpa_onnx

from quicker_voice_runtime.recognizer.base import Recognizer

logger = logging.getLogger(__name__)


def _pcm_s16le_to_float32(pcm: bytes) -> list[float]:
    count = len(pcm) // 2
    if count == 0:
        return []
    samples = struct.unpack(f"<{count}h", pcm[: count * 2])
    return [s / 32768.0 for s in samples]


def _find_onnx(model_dir: Path) -> Path | None:
    preferred = (
        model_dir / "model.int8.onnx",
        model_dir / "model.onnx",
        model_dir / "encoder.int8.onnx",
        model_dir / "encoder.onnx",
    )
    for path in preferred:
        if path.is_file():
            return path
    matches = sorted(model_dir.glob("*.onnx"))
    return matches[0] if matches else None


def _detect_model_type(model_dir: Path, explicit: str | None) -> str | None:
    if explicit:
        return explicit
    name = model_dir.name.lower()
    if "sensevoice" in name or "sense_voice" in name or "sense-voice" in name:
        return "sensevoice"
    if "paraformer" in name:
        return "paraformer"
    if "whisper" in name:
        return "whisper"
    if (model_dir / "model.int8.onnx").is_file() or (model_dir / "model.onnx").is_file():
        if "paraformer" in name:
            return "paraformer"
        if "sensevoice" in name or "sense_voice" in name or "sense-voice" in name:
            return "sensevoice"
        return "paraformer"
    if (model_dir / "encoder.onnx").is_file() or (
        model_dir / "encoder.int8.onnx"
    ).is_file():
        return "paraformer"
    return None


def _map_language(language: str) -> str:
    normalized = language.strip().lower().replace("_", "-")
    if not normalized or normalized in {"auto", "default"}:
        return "auto"
    if normalized.startswith("zh"):
        return "zh"
    if normalized.startswith("en"):
        return "en"
    if normalized.startswith("ja"):
        return "ja"
    if normalized.startswith("ko"):
        return "ko"
    if normalized in {"yue", "cantonese"}:
        return "yue"
    return "auto"


def try_create_sherpa_recognizer(
    model_dir: Path,
    model_type: str | None,
) -> Recognizer | None:
    if not model_dir.is_dir():
        return None

    tokens = model_dir / "tokens.txt"
    if not tokens.is_file():
        logger.warning("Missing tokens.txt in %s", model_dir)
        return None

    onnx_path = _find_onnx(model_dir)
    if onnx_path is None:
        logger.warning("No .onnx model in %s", model_dir)
        return None

    kind = _detect_model_type(model_dir, model_type)
    if kind is None:
        logger.warning("Could not detect model type in %s", model_dir)
        return None

    try:
        if kind == "sensevoice":
            recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=str(onnx_path),
                tokens=str(tokens),
                num_threads=2,
                debug=False,
                provider="cpu",
                language="auto",
                use_itn=True,
            )
            model_id = "sensevoice"
        elif kind == "paraformer":
            recognizer = sherpa_onnx.OfflineRecognizer.from_paraformer(
                paraformer=str(onnx_path),
                tokens=str(tokens),
                num_threads=2,
                debug=False,
                provider="cpu",
            )
            model_id = "paraformer"
        elif kind == "whisper":
            decoder = model_dir / "decoder.onnx"
            if not decoder.is_file():
                decoder = model_dir / "decoder.int8.onnx"
            if not decoder.is_file():
                logger.warning("Missing whisper decoder in %s", model_dir)
                return None
            recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
                encoder=str(onnx_path),
                decoder=str(decoder),
                tokens=str(tokens),
                num_threads=2,
                debug=False,
                provider="cpu",
            )
            model_id = "whisper"
        else:
            return None
    except Exception:
        logger.exception("Failed to create sherpa-onnx recognizer from %s", model_dir)
        return None

    return _SherpaOnnxRecognizer(recognizer=recognizer, model_id=model_id)


class _SherpaOnnxRecognizer:
    def __init__(self, recognizer: sherpa_onnx.OfflineRecognizer, model_id: str) -> None:
        self._recognizer = recognizer
        self.model_id = model_id
        self.ready = True

    def transcribe(self, pcm_s16le: bytes, *, sample_rate: int, language: str) -> str:
        del language  # SenseVoice auto-detects; per-request override not needed in v1
        samples = _pcm_s16le_to_float32(pcm_s16le)
        if not samples:
            return ""
        import numpy as np

        stream = self._recognizer.create_stream()
        stream.accept_waveform(sample_rate, np.array(samples, dtype=np.float32))
        self._recognizer.decode_stream(stream)
        return (stream.result.text or "").strip()

from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from quicker_voice_runtime.paths import default_models_dir


@dataclass(frozen=True)
class RuntimeConfig:
    host: str
    port: int
    model_dir: Path | None
    model_type: str | None
    log_level: str

    @property
    def runtime_version(self) -> str:
        from quicker_voice_runtime import __version__

        return __version__


def _default_model_dir() -> Path:
    return default_models_dir()


def load_config(argv: list[str] | None = None) -> RuntimeConfig:
    parser = argparse.ArgumentParser(
        prog="quicker-voice-runtime",
        description="QuickerAgent local ASR server (quicker-voice-v1)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("QUICKER_VOICE_HOST", "127.0.0.1"),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("QUICKER_VOICE_PORT", "6016")),
    )
    parser.add_argument(
        "--model-dir",
        default=os.environ.get("QUICKER_VOICE_MODEL_DIR"),
        help="Directory with sherpa-onnx model files (optional)",
    )
    parser.add_argument(
        "--model-type",
        default=os.environ.get("QUICKER_VOICE_MODEL_TYPE"),
        help="sherpa model family: sensevoice | paraformer | whisper",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("QUICKER_VOICE_LOG_LEVEL", "INFO"),
    )
    args = parser.parse_args(argv)

    model_dir: Path | None = None
    if args.model_dir:
        model_dir = Path(args.model_dir).expanduser().resolve()
    else:
        candidate = _default_model_dir()
        sensevoice = candidate / "sensevoice"
        paraformer = candidate / "paraformer-zh"
        if (sensevoice / "tokens.txt").is_file() and (
            (sensevoice / "model.int8.onnx").is_file() or (sensevoice / "model.onnx").is_file()
        ):
            model_dir = sensevoice.resolve()
        elif (paraformer / "tokens.txt").is_file() and (
            (paraformer / "model.int8.onnx").is_file() or (paraformer / "model.onnx").is_file()
        ):
            model_dir = paraformer.resolve()
        elif candidate.is_dir():
            entries = [
                p
                for p in candidate.iterdir()
                if p.name not in {".gitkeep", "README.md"}
            ]
            subs = [p for p in entries if p.is_dir()]
            if len(subs) == 1:
                model_dir = subs[0].resolve()
            elif (candidate / "tokens.txt").is_file() or list(candidate.glob("*.onnx")):
                model_dir = candidate.resolve()

    return RuntimeConfig(
        host=str(args.host),
        port=int(args.port),
        model_dir=model_dir,
        model_type=str(args.model_type) if args.model_type else None,
        log_level=str(args.log_level).upper(),
    )


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

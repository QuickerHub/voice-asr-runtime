from __future__ import annotations

import asyncio
import logging
import os

from quicker_voice_runtime.config import RuntimeConfig, configure_logging, load_config
from quicker_voice_runtime.recognizer import create_recognizer
from quicker_voice_runtime.server import run_server


def _config_with_model(config: RuntimeConfig) -> RuntimeConfig:
    if config.model_dir is not None:
        return config
    if os.environ.get("QUICKER_VOICE_AUTO_DOWNLOAD_MODEL", "1") == "0":
        return config

    logger = logging.getLogger(__name__)
    try:
        from quicker_voice_runtime.download_model import (
            ensure_sensevoice_model,
            is_model_ready,
            target_dir,
        )

        if not is_model_ready():
            logger.info("Downloading SenseVoice model (~160MB, one-time)...")
            ensure_sensevoice_model()
        if is_model_ready():
            return RuntimeConfig(
                host=config.host,
                port=config.port,
                model_dir=target_dir(),
                model_type=config.model_type or "sensevoice",
                log_level=config.log_level,
            )
    except Exception as exc:
        logger.warning("ASR model download failed, using stub: %s", exc)
    return config


def main(argv: list[str] | None = None) -> None:
    config = _config_with_model(load_config(argv))
    configure_logging(config.log_level)
    logging.getLogger(__name__).info(
        "Starting quicker-voice-runtime (model_dir=%s)",
        config.model_dir,
    )
    recognizer = create_recognizer(config.model_dir, config.model_type)
    try:
        asyncio.run(run_server(config, recognizer))
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Shutting down")

if __name__ == "__main__":
    main()

"""Resolve install / dev / PyInstaller paths."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def plugin_data_root() -> Path:
    """Writable plugin root (models/, logs/, settings.json)."""
    env_root = os.environ.get("QUICKER_VOICE_PLUGIN_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    if is_frozen():
        exe = Path(sys.executable).resolve()
        if exe.parent.name == "runtime":
            return exe.parent.parent
        return exe.parent
    return Path(__file__).resolve().parents[2]


def default_models_dir() -> Path:
    return plugin_data_root() / "models"

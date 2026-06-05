"""Resolve install / dev / PyInstaller paths."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def plugin_data_root() -> Path:
    """Writable plugin root (models/, logs/, settings.json)."""
    if is_frozen():
        exe = Path(sys.executable).resolve()
        if exe.parent.name == "runtime":
            return exe.parent.parent
        return exe.parent
    return Path(__file__).resolve().parents[2]


def default_models_dir() -> Path:
    return plugin_data_root() / "models"

from __future__ import annotations

from pathlib import Path

from quicker_voice_runtime.download_model import (
    describe_model_status,
    remove_model_dir,
    target_dir,
)


def test_describe_model_status_missing_dir(tmp_path: Path) -> None:
    dest = target_dir(tmp_path, "sensevoice")
    ready, err = describe_model_status(dest, preset="sensevoice")
    assert ready is False
    assert err is not None


def test_describe_model_status_partial_onnx(tmp_path: Path) -> None:
    dest = target_dir(tmp_path, "paraformer")
    dest.mkdir(parents=True)
    (dest / "tokens.txt").write_text("a", encoding="utf-8")
    (dest / "model.onnx").write_bytes(b"x" * 512)
    ready, err = describe_model_status(dest, preset="paraformer")
    assert ready is False
    assert err is not None
    assert err is not None
    assert "不完整" in err or "过小" in err


def test_remove_model_dir_clears_partial(tmp_path: Path) -> None:
    dest = target_dir(tmp_path, "paraformer")
    dest.mkdir(parents=True)
    (dest / "tokens.txt").write_text("a", encoding="utf-8")
    remove_model_dir(dest)
    assert not dest.exists()

# Models directory

Place offline ASR model files here. The runtime reads `QUICKER_VOICE_MODEL_DIR` (defaults to auto-detect under this folder).

## Default model (SenseVoice int8)

Download (~160 MB, includes ITN / punctuation):

```powershell
cd voice-asr-runtime
uv run download-asr-model
# or from agent-gui:
pnpm voice:download-model
```

Expected layout:

```text
models/sensevoice/
  model.int8.onnx
  tokens.txt
```

Set `QUICKER_VOICE_ASR_MODEL=paraformer` before download to fetch the smaller Paraformer zh-small model instead.

## Sherpa-ONNX dependency

PyPI's `sherpa-onnx` wheel bundles an older ONNX Runtime that cannot load current models.
This project pins wheels from [k2-fsa CPU index](https://k2-fsa.github.io/sherpa/onnx/cpu.html) via `uv sync`.

## Fallback

If SenseVoice is missing, `models/paraformer-zh/` is used automatically when present.

Without any model, the runtime uses a **stub** recognizer (protocol / UI testing only).

# quicker-voice-runtime — local ASR server for QuickerAgent

Fork-friendly Python runtime implementing the **quicker-voice-v1** protocol ([`docs/voice-input-plugin.md`](../docs/voice-input-plugin.md)).

Inspired by [CapsWriter-Offline](https://github.com/HaujetZhao/CapsWriter-Offline) (C/S + offline ASR), but uses a simpler JSON+binary PCM WebSocket contract for QuickerAgent Composer integration.

## Quick start

```powershell
cd voice-asr-runtime
uv sync
uv run download-asr-model   # first time: ~160 MB SenseVoice int8 (ITN/punctuation)
uv run quicker-voice-runtime
```

- HTTP health: `http://127.0.0.1:6016/health`
- WebSocket: `ws://127.0.0.1:6016` (subprotocol `quicker-voice-v1`)

From `agent-gui`:

```powershell
pnpm voice:dev-server
```

Then in QuickerAgent settings → disable **mock**, hold the Composer microphone.

## Backends

| Backend | When | Output |
|---------|------|--------|
| **stub** | No model files | `[stub] 收到约 Xs 音频` — protocol/UI testing |
| **sherpa-onnx** | `models/sensevoice/` + `uv sync` | Real offline ASR (SenseVoice, ITN/punctuation) |
| **sherpa-onnx (fallback)** | `models/paraformer-zh/` | Paraformer zh-small, no auto punctuation |

See [`models/README.md`](models/README.md) for model layout.

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `QUICKER_VOICE_HOST` | `127.0.0.1` | Bind address |
| `QUICKER_VOICE_PORT` | `6016` | HTTP + WS port |
| `QUICKER_VOICE_MODEL_DIR` | auto | Sherpa model directory |
| `QUICKER_VOICE_MODEL_TYPE` | auto | `sensevoice` / `paraformer` / `whisper` |
| `QUICKER_VOICE_LOG_LEVEL` | `INFO` | Logging |

## Packaging (Windows)

```powershell
cd voice-asr-runtime
pwsh -NoProfile -File ./scripts/build-win.ps1
pwsh -NoProfile -File ./scripts/package-release.ps1
# -> publish/voice-asr-runtime-0.1.0-win-x64.zip  (~80 MB)
# -> publish/voice-asr-model-sensevoice-0.1.0-win-x64.zip  (~160 MB)
```

Upload both zips to [QuickerHub/voice-asr-runtime Releases](https://github.com/QuickerHub/voice-asr-runtime/releases); URLs go in `agent-gui/src-tauri/resources/voice-plugin-channel.json`.

```powershell
pwsh -NoProfile -File ./publish/Publish-VoiceAsrRelease.ps1
# or reuse existing zips:
pwsh -NoProfile -File ./publish/Publish-VoiceAsrRelease.ps1 -SkipBuild
```

**User install (Tauri)**：设置 → 本地语音输入 → **一键安装**。应用自动依次下载 Runtime、模型、写入配置并启动（用户只点一次；**不是**单个合并包，但安装过程全自动）。完成后离线可用。

Dev without network: Tauri install copies from `voice-asr-runtime/dist/` + `models/sensevoice/` when present.

Installed layout:

```text
Documents/QuickerAgent/plugins/voice-asr/
  manifest.json
  settings.json
  runtime/quicker-voice-runtime.exe
  runtime/_internal/...
  models/sensevoice/tokens.txt
  models/sensevoice/model.int8.onnx
```

## Fork as standalone repo

This directory is designed to be split out:

```powershell
cd voice-asr-runtime
git init
git add .
git commit -m "chore: initial quicker-voice-runtime fork"
```

QuickerAgent consumes it via:

- dev: `pnpm voice:dev-server` → `uv run quicker-voice-runtime`
- release (planned): Tauri copies/spawns packaged `quicker-voice-runtime.exe` under `Documents/QuickerAgent/plugins/voice-asr/`

## Protocol

Host ↔ Runtime messages are documented in [`docs/voice-input-plugin.md`](../docs/voice-input-plugin.md#websocket-协议-v1).

Client reference: `agent-gui/lib/voice-input/voice-input-ws-client.ts`.

## License

MIT — see [LICENSE](LICENSE).

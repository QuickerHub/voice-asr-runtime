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

## Release automation

| Trigger | What runs |
|---------|-----------|
| **Git tag `v*.*.*` push** | [`.github/workflows/release.yml`](.github/workflows/release.yml) — build, zip, GitHub Release + `voice-plugin-channel.generated.json` |
| **Local one-shot** | `publish/Publish-VoiceAsrRelease.ps1` — same assets + optional Bitiful + optional monorepo channel sync |

```powershell
# CI: push tag (builds on GitHub Actions)
git tag v0.1.0 && git push origin v0.1.0

# Local full pipeline (monorepo root)
pwsh ./publish/Publish-VoiceAsrRelease.ps1 -SkipBuild -UploadBitiful -UpdateChannelJson

# voice-asr-runtime repo only
pwsh -NoProfile -File ./publish/Publish-VoiceAsrRelease.ps1 -SkipBuild -UploadBitiful

# Bitiful only (after GitHub release exists)
pwsh -NoProfile -File ./publish/Upload-VoiceAsrToBitiful.ps1 -Version 0.1.0 -UseLocalVoiceRoot
```

Bitiful upload uses `publish/.env` (see `publish/.env.example`). CI Bitiful is **off** by default; set repo variable `BITIFUL_UPLOAD_IN_CI=true` to enable (same as quicker-rpc).

**Domestic mirror (Bitiful)** — same bucket layout as QuickerAgent:

| Asset | URL pattern |
|-------|-------------|
| Runtime zip | `https://s3.bitiful.net/quicker-pkgs/quicker-rpc/voice-asr/voice-asr-runtime-<ver>-win-x64.zip` |
| Model zip | `https://s3.bitiful.net/quicker-pkgs/quicker-rpc/voice-asr/voice-asr-model-sensevoice-<ver>-win-x64.zip` |
| version.txt | `https://s3.bitiful.net/quicker-pkgs/quicker-rpc/voice-asr/version.txt` |

Tauri **一键安装** tries `*MirrorUrl` first (Bitiful), then GitHub release; verifies `*Sha256` when set in `voice-plugin-channel.json`.

## Packaging (Windows)

```powershell
pwsh -NoProfile -File ./scripts/build-win.ps1
pwsh -NoProfile -File ./scripts/package-release.ps1
# -> publish/voice-asr-runtime-<ver>-win-x64.zip
# -> publish/voice-asr-model-sensevoice-<ver>-win-x64.zip
```

**User install (Tauri)**：设置 → 本地语音输入 → **一键安装**。

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

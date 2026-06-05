from __future__ import annotations

import logging
import time
from typing import Any

from aiohttp import web

from quicker_voice_runtime.config import RuntimeConfig
from quicker_voice_runtime.protocol import PROTOCOL_VERSION, WS_SUBPROTOCOL, dumps, loads
from quicker_voice_runtime.recognizer.base import Recognizer
from quicker_voice_runtime.session import VoiceSession

logger = logging.getLogger(__name__)


class VoiceRuntimeApp:
    def __init__(self, config: RuntimeConfig, recognizer: Recognizer) -> None:
        self._config = config
        self._recognizer = recognizer

    def health_payload(self) -> dict[str, Any]:
        return {
            "ok": True,
            "protocolVersion": PROTOCOL_VERSION,
            "runtimeVersion": self._config.runtime_version,
            "modelId": self._recognizer.model_id,
            "modelLoaded": self._recognizer.model_id != "stub",
            "ready": self._recognizer.ready,
        }

    async def health_handler(self, request: web.Request) -> web.Response:
        response = web.json_response(self.health_payload())
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    async def options_handler(self, request: web.Request) -> web.Response:
        response = web.Response(status=204)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    async def websocket_handler(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(protocols=(WS_SUBPROTOCOL,))
        await ws.prepare(request)

        if ws.ws_protocol != WS_SUBPROTOCOL:
            logger.warning(
                "Client connected without %s subprotocol (got %r)",
                WS_SUBPROTOCOL,
                ws.ws_protocol,
            )
            await ws.close()
            return ws

        active: VoiceSession | None = None

        async def maybe_send_partial(ws: web.WebSocketResponse, session: VoiceSession) -> None:
            if not session.should_emit_partial():
                return
            try:
                text = self._recognizer.transcribe(
                    session.pcm,
                    sample_rate=session.sample_rate,
                    language=session.language,
                )
            except Exception:
                return
            if not text or text == session.last_partial_text:
                return
            session.last_partial_text = text
            session.last_partial_at = time.monotonic()
            await ws.send_str(
                dumps(
                    {
                        "type": "partial",
                        "sessionId": session.session_id,
                        "text": text,
                    }
                )
            )

        async for msg in ws:
            if msg.type == web.WSMsgType.BINARY:
                if active is not None:
                    active.append_pcm(msg.data)
                    if active.streaming:
                        await maybe_send_partial(ws, active)
                continue

            if msg.type != web.WSMsgType.TEXT:
                if msg.type in (web.WSMsgType.CLOSE, web.WSMsgType.ERROR):
                    break
                continue

            payload = loads(msg.data)
            if payload is None:
                continue

            msg_type = payload.get("type")
            if msg_type == "ping":
                await ws.send_str(
                    dumps(
                        {
                            "type": "pong",
                            "id": payload.get("id"),
                            "protocolVersion": PROTOCOL_VERSION,
                        }
                    )
                )
                continue

            if msg_type == "session.start":
                if active is not None:
                    await ws.send_str(
                        dumps(
                            {
                                "type": "error",
                                "sessionId": payload.get("sessionId"),
                                "code": "busy",
                                "message": "Session already active",
                            }
                        )
                    )
                    continue

                if not self._recognizer.ready:
                    await ws.send_str(
                        dumps(
                            {
                                "type": "error",
                                "sessionId": payload.get("sessionId"),
                                "code": "not_ready",
                                "message": "Model is not ready",
                            }
                        )
                    )
                    continue

                session_id = str(payload.get("sessionId") or "")
                if not session_id:
                    await ws.send_str(
                        dumps(
                            {
                                "type": "error",
                                "code": "invalid_session",
                                "message": "sessionId required",
                            }
                        )
                    )
                    continue

                active = VoiceSession(
                    session_id=session_id,
                    language=str(payload.get("language") or "zh-CN"),
                    streaming=bool(payload.get("streaming")),
                    sample_rate=int(payload.get("sampleRate") or 16_000),
                )
                await ws.send_str(
                    dumps({"type": "session.started", "sessionId": session_id})
                )
                continue

            if msg_type == "session.end":
                session_id = str(payload.get("sessionId") or "")
                if active is None or active.session_id != session_id:
                    await ws.send_str(
                        dumps(
                            {
                                "type": "error",
                                "sessionId": session_id,
                                "code": "invalid_session",
                                "message": "No matching active session",
                            }
                        )
                    )
                    continue

                try:
                    text = self._recognizer.transcribe(
                        active.pcm,
                        sample_rate=active.sample_rate,
                        language=active.language,
                    )
                    confidence = 0.9 if text else 0.0
                except Exception as exc:
                    logger.exception("Recognition failed")
                    await ws.send_str(
                        dumps(
                            {
                                "type": "error",
                                "sessionId": session_id,
                                "code": "recognition_failed",
                                "message": str(exc),
                            }
                        )
                    )
                    active = None
                    continue

                await ws.send_str(
                    dumps(
                        {
                            "type": "final",
                            "sessionId": session_id,
                            "text": text,
                            "confidence": confidence,
                        }
                    )
                )
                await ws.send_str(
                    dumps({"type": "session.ended", "sessionId": session_id})
                )
                active = None
                continue

            if msg_type == "session.cancel":
                session_id = str(payload.get("sessionId") or "")
                if active is not None and active.session_id == session_id:
                    active = None
                await ws.send_str(
                    dumps({"type": "session.ended", "sessionId": session_id})
                )
                continue

        if active is not None:
            active = None
        return ws

    def create_web_app(self) -> web.Application:
        app = web.Application()
        app.router.add_route("OPTIONS", "/health", self.options_handler)
        app.router.add_get("/health", self.health_handler)
        app.router.add_get("/", self.websocket_handler)
        return app


async def run_server(config: RuntimeConfig, recognizer: Recognizer) -> None:
    runtime = VoiceRuntimeApp(config, recognizer)
    app = runtime.create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config.host, config.port)
    await site.start()
    logger.info(
        "quicker-voice-runtime %s listening on http://%s:%s/health (ws on /)",
        config.runtime_version,
        config.host,
        config.port,
    )
    try:
        import asyncio

        await asyncio.Event().wait()
    finally:
        await runner.cleanup()

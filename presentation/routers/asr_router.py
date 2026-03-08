"""
ASR（语音识别）路由

提供两个接口：
1. POST /api/asr/transcribe  —— 浏览器 PTT，上传 WAV 文件，返回识别文本
2. WS   /ws/asr              —— 外部系统，WebSocket 实时流式音频，返回识别结果事件
"""

import io
import json
import logging
import wave
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect

from infrastructure.api.asr_client import DashScopeASRClient
from presentation.schemas.asr_schemas import (
    ASRErrorCode,
    ASRErrorResponse,
    ASRTranscribeResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["asr"])

# 最短有效音频时长对应的 PCM 字节数（0.5s @ 16kHz, 16-bit, mono）
MIN_PCM_BYTES = 16000  # 0.5s * 16000 samples/s * 2 bytes/sample


def _extract_pcm_from_wav(wav_bytes: bytes) -> bytes:
    """
    从 WAV 文件字节中提取原始 PCM 数据。
    使用 Python 内置 wave 模块，零额外依赖。

    Returns:
        原始 PCM 字节（int16 小端序）

    Raises:
        ValueError: 文件格式不是有效 WAV
    """
    try:
        with wave.open(io.BytesIO(wav_bytes)) as wf:
            logger.debug(
                f"[ASR] WAV 信息: channels={wf.getnchannels()}, "
                f"sampwidth={wf.getsampwidth()}, "
                f"framerate={wf.getframerate()}, "
                f"nframes={wf.getnframes()}"
            )
            return wf.readframes(wf.getnframes())
    except wave.Error as e:
        raise ValueError(f"WAV 格式解析失败: {e}") from e


# ── HTTP POST: 浏览器 PTT 接口 ─────────────────────────────────────────────

@router.post(
    "/api/asr/transcribe",
    response_model=ASRTranscribeResponse,
    summary="语音转文字（文件上传）",
    description=(
        "接收 WAV 格式音频文件（16kHz, 单声道, 16-bit），"
        "调用 DashScope ASR 返回识别文本。供浏览器 PTT 使用。"
    ),
)
async def transcribe_audio(audio: UploadFile = File(..., description="WAV 格式音频文件")):
    """浏览器 Push-to-Talk 接口：上传 WAV → 返回识别文本"""
    # 1. 读取上传文件
    wav_bytes = await audio.read()
    if not wav_bytes:
        raise HTTPException(
            status_code=400,
            detail=ASRErrorResponse(
                error_code=ASRErrorCode.INVALID_FORMAT,
                message="上传的音频文件为空"
            ).model_dump()
        )

    # 2. 提取 PCM
    try:
        pcm_data = _extract_pcm_from_wav(wav_bytes)
    except ValueError as e:
        logger.warning(f"[ASR] WAV 解析失败: {e}")
        raise HTTPException(
            status_code=400,
            detail=ASRErrorResponse(
                error_code=ASRErrorCode.INVALID_FORMAT,
                message=f"音频格式不支持，请上传 WAV 格式文件"
            ).model_dump()
        )

    # 3. 校验时长（< 0.5s 的录音通常无有效语音）
    if len(pcm_data) < MIN_PCM_BYTES:
        raise HTTPException(
            status_code=400,
            detail=ASRErrorResponse(
                error_code=ASRErrorCode.AUDIO_TOO_SHORT,
                message="录音时长过短，请按住按钮后再说话"
            ).model_dump()
        )

    # 4. 调用 DashScope ASR
    try:
        client = DashScopeASRClient(language="zh")
        text = await client.transcribe(pcm_data)
    except ValueError as e:
        # API Key 未配置
        logger.error(f"[ASR] 配置错误: {e}")
        raise HTTPException(
            status_code=500,
            detail=ASRErrorResponse(
                error_code=ASRErrorCode.INTERNAL_ERROR,
                message="ASR 服务配置错误，请联系管理员"
            ).model_dump()
        )
    except RuntimeError as e:
        logger.error(f"[ASR] DashScope 错误: {e}")
        raise HTTPException(
            status_code=502,
            detail=ASRErrorResponse(
                error_code=ASRErrorCode.ASR_API_ERROR,
                message=f"DashScope ASR 服务异常，请稍后重试"
            ).model_dump()
        )
    except Exception as e:
        logger.exception(f"[ASR] 未知错误: {e}")
        raise HTTPException(
            status_code=500,
            detail=ASRErrorResponse(
                error_code=ASRErrorCode.INTERNAL_ERROR,
                message="语音识别服务内部错误，请重试"
            ).model_dump()
        )

    # 5. 空结果处理
    if not text or not text.strip():
        raise HTTPException(
            status_code=400,
            detail=ASRErrorResponse(
                error_code=ASRErrorCode.NO_SPEECH_DETECTED,
                message="未检测到语音，请说话后再松开按钮"
            ).model_dump()
        )

    logger.info(f"[ASR] HTTP 识别成功: '{text[:50]}{'...' if len(text) > 50 else ''}'")
    return ASRTranscribeResponse(text=text.strip())


# ── WebSocket: 外部系统实时流式接口 ────────────────────────────────────────

@router.websocket("/ws/asr")
async def asr_websocket(websocket: WebSocket):
    """
    外部系统 WebSocket 语音识别接口。

    协议：
      客户端先发 JSON {"event":"start","request_id":"...","language":"zh"}
      然后持续发送 binary PCM 帧（int16, 16kHz, mono）
      最后发 JSON {"event":"stop"}

    服务端响应：
      {"event":"started","request_id":"..."}
      {"event":"result","request_id":"...","text":"...","is_final":false/true}
      {"event":"done","request_id":"...","text":"..."}
      {"event":"error","request_id":"...","error_code":"...","message":"..."}
    """
    await websocket.accept()

    request_id: Optional[str] = None
    language: str = "zh"
    audio_buffer = bytearray()
    started = False

    logger.info("[ASR-WS] 新连接建立")

    try:
        while True:
            data = await websocket.receive()

            # ── 处理文本控制消息 ────────────────────────────────────────
            if "text" in data:
                try:
                    msg = json.loads(data["text"])
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "event": "error",
                        "request_id": request_id,
                        "error_code": ASRErrorCode.INVALID_FORMAT,
                        "message": "无效的 JSON 格式"
                    })
                    continue

                event = msg.get("event", "")

                if event == "start":
                    request_id = msg.get("request_id")
                    language = msg.get("language", "zh")
                    audio_buffer.clear()
                    started = True
                    logger.info(f"[ASR-WS] 任务开始，request_id={request_id}，language={language}")
                    await websocket.send_json({
                        "event": "started",
                        "request_id": request_id
                    })

                elif event == "stop":
                    if not started:
                        await websocket.send_json({
                            "event": "error",
                            "request_id": request_id,
                            "error_code": ASRErrorCode.INVALID_FORMAT,
                            "message": "请先发送 start 消息"
                        })
                        continue

                    logger.info(
                        f"[ASR-WS] 收到 stop，PCM 大小={len(audio_buffer)} bytes，"
                        f"request_id={request_id}"
                    )

                    # 校验时长
                    if len(audio_buffer) < MIN_PCM_BYTES:
                        await websocket.send_json({
                            "event": "error",
                            "request_id": request_id,
                            "error_code": ASRErrorCode.AUDIO_TOO_SHORT,
                            "message": "录音时长过短"
                        })
                        audio_buffer.clear()
                        started = False
                        continue

                    # 调用 DashScope ASR
                    try:
                        client = DashScopeASRClient(language=language)
                        text = await client.transcribe(bytes(audio_buffer))
                    except Exception as e:
                        logger.exception(f"[ASR-WS] ASR 识别失败: {e}")
                        await websocket.send_json({
                            "event": "error",
                            "request_id": request_id,
                            "error_code": ASRErrorCode.ASR_API_ERROR,
                            "message": "ASR 服务异常，请稍后重试"
                        })
                        audio_buffer.clear()
                        started = False
                        continue

                    text = (text or "").strip()

                    if not text:
                        await websocket.send_json({
                            "event": "error",
                            "request_id": request_id,
                            "error_code": ASRErrorCode.NO_SPEECH_DETECTED,
                            "message": "未检测到语音"
                        })
                    else:
                        # 发送最终结果
                        await websocket.send_json({
                            "event": "result",
                            "request_id": request_id,
                            "text": text,
                            "is_final": True
                        })
                        # 发送完成事件
                        await websocket.send_json({
                            "event": "done",
                            "request_id": request_id,
                            "text": text
                        })
                        logger.info(f"[ASR-WS] 识别完成: '{text[:50]}{'...' if len(text) > 50 else ''}'，request_id={request_id}")

                    audio_buffer.clear()
                    started = False

            # ── 处理二进制音频数据 ──────────────────────────────────────
            elif "bytes" in data:
                if not started:
                    # 忽略未 start 时的音频数据
                    continue
                chunk = data["bytes"]
                if chunk:
                    audio_buffer.extend(chunk)

    except WebSocketDisconnect:
        logger.info(f"[ASR-WS] 连接断开，request_id={request_id}")
    except Exception as e:
        logger.exception(f"[ASR-WS] 未处理异常: {e}")
        try:
            await websocket.send_json({
                "event": "error",
                "request_id": request_id,
                "error_code": ASRErrorCode.INTERNAL_ERROR,
                "message": "服务端内部错误"
            })
        except Exception:
            pass

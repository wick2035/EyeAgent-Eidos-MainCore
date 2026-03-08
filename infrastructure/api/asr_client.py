"""
DashScope 实时语音识别客户端
模型：qwen3-asr-flash-realtime-2026-02-10

该模型使用 OpenAI Realtime API 兼容协议，不是 DashScope 传统 NLS 协议。

协议流程：
  连接 → 收到 session.created
  → 发送 input_audio_buffer.append（base64 PCM 音频）
  → 发送 input_audio_buffer.commit
  → 收到 conversation.item.input_audio_transcription.completed
  → 返回 transcript 文本
"""

import asyncio
import base64
import json
import logging
import os

import aiohttp

logger = logging.getLogger(__name__)

# 每帧 base64 前 PCM 大小：6400 bytes = 200ms @ 16kHz 16-bit mono
CHUNK_SIZE = 6400
# 等待 session.created 的超时（秒）
SESSION_TIMEOUT = 10.0
# 等待转写结果的超时（秒）
TRANSCRIPTION_TIMEOUT = 30.0


class DashScopeASRClient:
    """
    阿里云 DashScope 实时语音识别客户端（OpenAI Realtime API 兼容格式）。

    用法：
        client = DashScopeASRClient(language="zh")
        text = await client.transcribe(pcm_bytes)
    """

    MODEL = "qwen3-asr-flash-realtime-2026-02-10"
    WS_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"

    def __init__(self, language: str = "zh"):
        self.language = language
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY 未配置，请检查 .env 文件")

    async def transcribe(self, pcm_data: bytes) -> str:
        """
        将 PCM 音频发送到 DashScope ASR，返回识别文字。

        Args:
            pcm_data: 原始 PCM 字节（int16 小端序，单声道，16000 Hz）

        Returns:
            识别文字，无结果时返回空字符串

        Raises:
            RuntimeError: DashScope 返回错误或连接失败
        """
        if not pcm_data:
            logger.warning("[ASR] 收到空的 PCM 数据")
            return ""

        url = f"{self.WS_URL}?model={self.MODEL}"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        duration_s = len(pcm_data) / 32000  # 16000Hz * 2bytes
        logger.info(
            f"[ASR] 开始识别 PCM={len(pcm_data)}bytes({duration_s:.1f}s) lang={self.language}"
        )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(url, headers=headers) as ws:
                    # ── 第一步：等待 session.created ─────────────────────────
                    session_ok = await self._wait_for_session_created(ws)
                    if not session_ok:
                        raise RuntimeError("DashScope 未返回 session.created")

                    # ── 第二步（可选）：更新 session 配置 ────────────────────
                    # 如需覆盖 VAD 或语言设置，在此发送 session.update
                    # 默认 session 已配置 pcm + 16000Hz，通常无需修改

                    # ── 第三步：分块发送 PCM 音频（base64 编码）────────────
                    total_chunks = 0
                    for i in range(0, len(pcm_data), CHUNK_SIZE):
                        chunk = pcm_data[i : i + CHUNK_SIZE]
                        audio_b64 = base64.b64encode(chunk).decode("utf-8")
                        await ws.send_json({
                            "type": "input_audio_buffer.append",
                            "audio": audio_b64,
                        })
                        total_chunks += 1

                    logger.info(f"[ASR] 已发送 {total_chunks} 帧音频")

                    # ── 第四步：提交音频缓冲区（触发转写）──────────────────
                    await ws.send_json({"type": "input_audio_buffer.commit"})
                    logger.info("[ASR] input_audio_buffer.commit 已发送")

                    # ── 第五步：等待转写结果 ─────────────────────────────────
                    text = await self._collect_transcription(ws)
                    logger.info(f"[ASR] 识别完成 text='{text}'")
                    return text

        except aiohttp.WSServerHandshakeError as e:
            logger.error(f"[ASR] WebSocket 握手失败（API Key 或模型名可能有误）: {e}")
            raise RuntimeError(f"DashScope 连接失败: {e}") from e
        except aiohttp.ClientError as e:
            logger.error(f"[ASR] 网络连接失败: {e}")
            raise RuntimeError(f"网络连接失败: {e}") from e
        except asyncio.TimeoutError:
            logger.error("[ASR] 整体请求超时")
            raise RuntimeError("ASR 识别超时，请重试")

    async def _wait_for_session_created(self, ws) -> bool:
        """等待 session.created 事件，打印所有收到的消息便于调试。"""
        try:
            async with asyncio.timeout(SESSION_TIMEOUT):
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        logger.info(f"[ASR][DashScope←] {msg.data}")
                        try:
                            data = json.loads(msg.data)
                        except json.JSONDecodeError:
                            logger.warning(f"[ASR] 非 JSON 消息: {msg.data[:200]}")
                            continue

                        event_type = data.get("type", "")

                        if event_type == "session.created":
                            logger.info(
                                f"[ASR] session.created model={data.get('session', {}).get('model')}"
                            )
                            return True

                        if event_type == "error":
                            err = data.get("error", {})
                            logger.error(f"[ASR] DashScope 错误: {err}")
                            raise RuntimeError(
                                f"DashScope 错误: {err.get('message', str(err))}"
                            )

                        logger.info(f"[ASR] 等待 session.created 期间收到: type={event_type}")

                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error(f"[ASR] WebSocket 错误: {msg.data}")
                        return False
                    elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING):
                        logger.error(f"[ASR] 连接被关闭 code={ws.close_code}")
                        return False

        except TimeoutError:
            logger.error(f"[ASR] 等待 session.created 超时（>{SESSION_TIMEOUT}s）")
            return False

        return False

    async def _collect_transcription(self, ws) -> str:
        """
        收集转写结果。

        关注的事件（OpenAI Realtime API 格式）：
          - conversation.item.input_audio_transcription.completed → 返回 transcript
          - conversation.item.input_audio_transcription.failed   → 抛出异常
          - error                                                 → 抛出异常

        其他事件（speech_started、committed 等）记录后继续等待。
        """
        transcript_parts: list[str] = []

        try:
            async with asyncio.timeout(TRANSCRIPTION_TIMEOUT):
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        logger.info(f"[ASR][DashScope←] {msg.data}")
                        try:
                            data = json.loads(msg.data)
                        except json.JSONDecodeError:
                            continue

                        event_type = data.get("type", "")

                        # ── 转写完成 ──────────────────────────────────────
                        if event_type == "conversation.item.input_audio_transcription.completed":
                            transcript = data.get("transcript", "").strip()
                            logger.info(f"[ASR] 转写结果: '{transcript}'")
                            if transcript:
                                transcript_parts.append(transcript)
                            # 有了完整结果就可以提前退出
                            break

                        # ── 转写失败 ──────────────────────────────────────
                        if event_type == "conversation.item.input_audio_transcription.failed":
                            err = data.get("error", {})
                            logger.error(f"[ASR] 转写失败: {err}")
                            raise RuntimeError(
                                f"DashScope 转写失败: {err.get('message', str(err))}"
                            )

                        # ── DashScope 错误 ────────────────────────────────
                        if event_type == "error":
                            err = data.get("error", {})
                            logger.error(f"[ASR] DashScope 错误: {err}")
                            raise RuntimeError(
                                f"DashScope 错误: {err.get('message', str(err))}"
                            )

                        # 其他事件：VAD 检测、committed 等，继续等待
                        logger.info(f"[ASR] 收到中间事件: type={event_type}")

                    elif msg.type == aiohttp.WSMsgType.BINARY:
                        logger.info(f"[ASR][DashScope←] 二进制帧 {len(msg.data)}bytes")

                    elif msg.type in (
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSING,
                        aiohttp.WSMsgType.ERROR,
                    ):
                        logger.warning(f"[ASR] WebSocket 关闭 type={msg.type}")
                        break

        except TimeoutError:
            logger.warning(
                f"[ASR] 等待转写结果超时（>{TRANSCRIPTION_TIMEOUT}s），"
                f"当前已收到: {transcript_parts}"
            )

        return " ".join(transcript_parts)

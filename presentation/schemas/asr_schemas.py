"""
ASR（语音识别）接口的 Pydantic 模型和错误码定义
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ASRErrorCode(str, Enum):
    """ASR 接口错误码"""
    NO_SPEECH_DETECTED = "NO_SPEECH_DETECTED"   # 音频中未检测到语音
    AUDIO_TOO_SHORT = "AUDIO_TOO_SHORT"          # 音频时长不足（< 0.5s）
    INVALID_FORMAT = "INVALID_FORMAT"            # 音频格式不支持或损坏
    ASR_API_ERROR = "ASR_API_ERROR"              # DashScope WebSocket 连接或识别失败
    INTERNAL_ERROR = "INTERNAL_ERROR"            # 服务端内部错误


# ── HTTP POST /api/asr/transcribe ──────────────────────────────────────────

class ASRTranscribeResponse(BaseModel):
    """HTTP POST 转写成功响应"""
    text: str


class ASRErrorResponse(BaseModel):
    """HTTP POST 转写失败响应（配合 HTTPException detail 使用）"""
    error_code: ASRErrorCode
    message: str


# ── WebSocket /ws/asr 消息模型 ─────────────────────────────────────────────

class WSStartMessage(BaseModel):
    """客户端 → 服务端：开始任务"""
    event: str = "start"
    request_id: Optional[str] = None   # 调用方自定义追踪ID，原样回传
    language: str = "zh"               # 识别语言，默认中文


class WSStopMessage(BaseModel):
    """客户端 → 服务端：结束任务（停止发送音频）"""
    event: str = "stop"


class WSStartedMessage(BaseModel):
    """服务端 → 客户端：任务已启动，可开始发送音频"""
    event: str = "started"
    request_id: Optional[str] = None


class WSResultMessage(BaseModel):
    """服务端 → 客户端：识别结果（中间或最终）"""
    event: str = "result"
    request_id: Optional[str] = None
    text: str
    is_final: bool


class WSDoneMessage(BaseModel):
    """服务端 → 客户端：任务完成，text 为最终识别文本"""
    event: str = "done"
    request_id: Optional[str] = None
    text: str


class WSErrorMessage(BaseModel):
    """服务端 → 客户端：错误"""
    event: str = "error"
    request_id: Optional[str] = None
    error_code: ASRErrorCode
    message: str

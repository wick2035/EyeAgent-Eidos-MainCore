"""
合规审查Agent路由 - 独立API接口
支持SSE流式响应，仅医生可用

基于 LangGraph GraphManager 实现
"""
import uuid
import json
import logging
import re
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from presentation.schemas.compliance_schemas import (
    ComplianceChatRequest,
    ComplianceChatResponse,
)
from agents.graph_manager import get_graph_manager
from application.services.chat_persistence_service import get_chat_persistence_service

logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/api/compliance", tags=["compliance"])

# GraphManager 单例
graph_manager = get_graph_manager()

# UUID格式验证
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$',
    re.IGNORECASE
)


def verify_doctor_role(doctor_id: str) -> bool:
    """
    验证医生身份

    TODO: 实现实际的医生身份验证逻辑
    目前仅验证UUID格式
    """
    return bool(UUID_PATTERN.match(doctor_id))


@router.post("/chat", response_model=ComplianceChatResponse)
async def compliance_chat(request: ComplianceChatRequest) -> ComplianceChatResponse:
    """
    合规审查对话接口（非流式）

    仅医生用户可调用，对患者的诊断/处方/病历进行合规性审查。

    Args:
        request: 合规审查对话请求

    Returns:
        ComplianceChatResponse: 对话响应
    """
    try:
        logger.info(
            f"[ComplianceRouter] 收到请求: doctor={request.doctor_id}, "
            f"patient={request.patient_id}"
        )

        # 验证医生身份
        if not verify_doctor_role(request.doctor_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="仅医生用户可访问合规审查Agent，请提供有效的doctor_id"
            )

        # 生成session_id
        session_id = request.session_id or f"compliance_{uuid.uuid4().hex[:16]}"

        # 获取持久化服务
        persistence_service = get_chat_persistence_service()
        conversation_id = request.conversation_id

        # 如果没有conversation_id，创建新会话
        if not conversation_id:
            conversation_id = persistence_service.create_conversation(
                host_id=request.doctor_id,
                user_type="doctor",
                title="合规审查"
            )
            logger.info(f"[ComplianceRouter] 创建新会话: {conversation_id}")

        # 使用 GraphManager 处理对话
        result = graph_manager.chat(
            patient_id=request.patient_id,
            session_id=session_id,
            message=request.message,
            role="doctor",
            doctor_id=request.doctor_id,
            conversation_id=conversation_id,
            agent_type="compliance",
        )

        return ComplianceChatResponse(
            response=result["response"],
            session_id=session_id,
            conversation_id=conversation_id,
            is_completed=result["is_completed"],
            stage=result["stage"],
            agent_type="compliance",
            metadata={
                "doctor_id": request.doctor_id,
                "patient_id": request.patient_id,
                "thread_id": result.get("thread_id", ""),
            }
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"[ComplianceRouter] 参数错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"[ComplianceRouter] 处理失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理请求失败: {str(e)}"
        )


@router.post("/chat/stream")
async def compliance_chat_stream(request: ComplianceChatRequest):
    """
    合规审查对话接口（SSE流式）

    返回Server-Sent Events流式响应

    SSE事件类型:
    - start: 开始处理
    - chunk: 响应内容块
    - tool_call: 工具调用通知
    - done: 完成，包含完整响应和元数据
    - error: 错误信息

    Args:
        request: 合规审查对话请求

    Returns:
        StreamingResponse: SSE流式响应
    """
    async def generate_sse() -> AsyncGenerator[str, None]:
        """生成 SSE 事件流"""
        try:
            # 验证医生身份
            if not verify_doctor_role(request.doctor_id):
                yield f"data: {json.dumps({'event': 'error', 'message': '仅医生用户可访问合规审查Agent'})}\n\n"
                return

            # 生成session_id
            session_id = request.session_id or f"compliance_{uuid.uuid4().hex[:16]}"

            # 获取持久化服务
            persistence_service = get_chat_persistence_service()
            conversation_id = request.conversation_id

            # 如果没有conversation_id，创建新会话
            if not conversation_id:
                conversation_id = persistence_service.create_conversation(
                    host_id=request.doctor_id,
                    user_type="doctor",
                    title="合规审查"
                )

            # 获取 thread_id
            from agents.graph.id_mapping import get_thread_config
            thread_config = get_thread_config(session_id, conversation_id)
            thread_id = thread_config["configurable"]["thread_id"]

            # 发送开始事件
            yield f"data: {json.dumps({'event': 'start', 'session_id': session_id, 'conversation_id': conversation_id, 'thread_id': thread_id})}\n\n"

            # 调用异步流式对话
            full_response = ""
            current_stage = "greeting"

            async for chunk in graph_manager.chat_stream_async(
                patient_id=request.patient_id,
                session_id=session_id,
                message=request.message,
                role="doctor",
                doctor_id=request.doctor_id,
                conversation_id=conversation_id,
                agent_type="compliance",
            ):
                event_type = chunk.get("type", "")
                content = chunk.get("content", "")
                metadata = chunk.get("metadata", {})

                if event_type == "token":
                    full_response += content
                    yield f"data: {json.dumps({'event': 'chunk', 'content': content})}\n\n"

                elif event_type == "node_end":
                    if metadata.get("stage"):
                        current_stage = metadata["stage"]

                elif event_type == "tool_start":
                    yield f"data: {json.dumps({'event': 'tool_call', 'tool': metadata.get('tool', 'unknown'), 'status': 'start', 'input': metadata.get('input', {})})}\n\n"

                elif event_type == "tool_end":
                    yield f"data: {json.dumps({'event': 'tool_call', 'tool': metadata.get('tool', 'unknown'), 'status': 'end', 'output': metadata.get('output', '')})}\n\n"

                elif event_type == "done":
                    full_response = content
                    current_stage = metadata.get("stage", current_stage)

                elif event_type == "error":
                    yield f"data: {json.dumps({'event': 'error', 'message': content})}\n\n"

            # 发送完成事件
            yield f"data: {json.dumps({'event': 'done', 'response': full_response, 'session_id': session_id, 'conversation_id': conversation_id, 'stage': current_stage, 'agent_type': 'compliance', 'metadata': {'doctor_id': request.doctor_id, 'patient_id': request.patient_id}})}\n\n"

        except Exception as e:
            logger.error(f"[ComplianceRouter] SSE生成错误: {e}", exc_info=True)
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

    try:
        logger.info(
            f"[ComplianceRouter] 收到SSE请求: doctor={request.doctor_id}, "
            f"patient={request.patient_id}"
        )

        return StreamingResponse(
            generate_sse(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*"
            }
        )

    except Exception as e:
        logger.error(f"[ComplianceRouter] SSE处理失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理请求失败: {str(e)}"
        )


@router.get("/health")
async def compliance_health_check():
    """
    合规审查Agent健康检查

    Returns:
        健康状态和功能可用性
    """
    # 检查Search1API是否可用（合规审查依赖联网搜索）
    search_available = False
    try:
        from infrastructure.api.search1api_client import get_search1api_client
        client = get_search1api_client()
        search_available = client.is_available()
    except Exception:
        pass

    return {
        "status": "healthy",
        "agent_type": "compliance",
        "version": "1.0.0",
        "architecture": "langgraph",
        "access_control": "doctor_only",
        "features": {
            "prescription_review": True,
            "diagnosis_review": True,
            "medical_record_review": True,
            "examination_review": True,
            "web_search": search_available,
            "sse_streaming": True,
            "save_review": True,
            "export_pdf": True,
        },
        "endpoints": [
            "POST /api/compliance/chat",
            "POST /api/compliance/chat/stream",
            "GET /api/compliance/health",
        ]
    }

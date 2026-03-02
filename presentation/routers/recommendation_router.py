"""
产品推荐Agent路由 - 独立API接口
支持SSE流式响应，医生和患者均可使用

基于 LangGraph GraphManager 实现
"""
import uuid
import json
import logging
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from presentation.schemas.recommendation_schemas import (
    RecommendationChatRequest,
    RecommendationChatResponse,
)
from agents.graph_manager import get_graph_manager
from application.services.chat_persistence_service import get_chat_persistence_service
from utils.ui_element_parser import parse_ui_elements

logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/api/recommendation", tags=["recommendation"])

# GraphManager 单例
graph_manager = get_graph_manager()


@router.post("/chat", response_model=RecommendationChatResponse)
async def recommendation_chat(request: RecommendationChatRequest) -> RecommendationChatResponse:
    """
    产品推荐对话接口（非流式）

    医生和患者均可调用，根据role字段区分推荐模式。

    Args:
        request: 产品推荐对话请求

    Returns:
        RecommendationChatResponse: 对话响应（含UI元素）
    """
    try:
        role = request.role or "patient"
        logger.info(
            f"[RecommendationRouter] 收到请求: role={role}, "
            f"patient={request.patient_id}, doctor={request.doctor_id}"
        )

        # 医生模式需要doctor_id
        if role == "doctor" and not request.doctor_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="医生模式需要提供 doctor_id"
            )

        # 生成session_id
        session_id = request.session_id or f"rec_{uuid.uuid4().hex[:16]}"

        # 获取持久化服务
        persistence_service = get_chat_persistence_service()
        conversation_id = request.conversation_id

        # 如果没有conversation_id，创建新会话
        if not conversation_id:
            host_id = request.doctor_id if role == "doctor" else request.patient_id
            conversation_id = persistence_service.create_conversation(
                host_id=host_id,
                user_type=role,
                title="产品推荐"
            )
            logger.info(f"[RecommendationRouter] 创建新会话: {conversation_id}")

        # 使用 GraphManager 处理对话
        result = graph_manager.chat(
            patient_id=request.patient_id,
            session_id=session_id,
            message=request.message,
            role=role,
            doctor_id=request.doctor_id,
            conversation_id=conversation_id,
            agent_type="recommendation",
        )

        # 解析UI元素
        raw_response = result["response"]
        clean_text, ui_elements = parse_ui_elements(raw_response)

        return RecommendationChatResponse(
            response=clean_text,
            session_id=session_id,
            conversation_id=conversation_id,
            is_completed=result["is_completed"],
            stage=result["stage"],
            agent_type="recommendation",
            ui_elements=ui_elements,
            metadata={
                "patient_id": request.patient_id,
                "doctor_id": request.doctor_id,
                "role": role,
                "thread_id": result.get("thread_id", ""),
            }
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"[RecommendationRouter] 参数错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"[RecommendationRouter] 处理失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理请求失败: {str(e)}"
        )


@router.post("/chat/stream")
async def recommendation_chat_stream(request: RecommendationChatRequest):
    """
    产品推荐对话接口（SSE流式）

    返回Server-Sent Events流式响应

    SSE事件类型:
    - start: 开始处理
    - chunk: 响应内容块
    - tool_call: 工具调用通知
    - ui_elements: UI元素数据（产品卡片/选项）
    - done: 完成，包含完整响应和元数据
    - error: 错误信息

    Args:
        request: 产品推荐对话请求

    Returns:
        StreamingResponse: SSE流式响应
    """
    async def generate_sse() -> AsyncGenerator[str, None]:
        """生成 SSE 事件流"""
        try:
            role = request.role or "patient"

            # 医生模式需要doctor_id
            if role == "doctor" and not request.doctor_id:
                yield f"data: {json.dumps({'event': 'error', 'message': '医生模式需要提供doctor_id'})}\n\n"
                return

            # 生成session_id
            session_id = request.session_id or f"rec_{uuid.uuid4().hex[:16]}"

            # 获取持久化服务
            persistence_service = get_chat_persistence_service()
            conversation_id = request.conversation_id

            # 如果没有conversation_id，创建新会话
            if not conversation_id:
                host_id = request.doctor_id if role == "doctor" else request.patient_id
                conversation_id = persistence_service.create_conversation(
                    host_id=host_id,
                    user_type=role,
                    title="产品推荐"
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
                role=role,
                doctor_id=request.doctor_id,
                conversation_id=conversation_id,
                agent_type="recommendation",
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

            # 解析UI元素
            clean_text, ui_elements = parse_ui_elements(full_response)

            # 发送UI元素事件（如果有）
            if ui_elements:
                ui_data = ui_elements.model_dump(exclude_none=True)
                yield f"data: {json.dumps({'event': 'ui_elements', **ui_data})}\n\n"

            # 发送完成事件
            yield f"data: {json.dumps({'event': 'done', 'response': clean_text, 'session_id': session_id, 'conversation_id': conversation_id, 'stage': current_stage, 'agent_type': 'recommendation', 'metadata': {'patient_id': request.patient_id, 'doctor_id': request.doctor_id, 'role': role}})}\n\n"

        except Exception as e:
            logger.error(f"[RecommendationRouter] SSE生成错误: {e}", exc_info=True)
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

    try:
        role = request.role or "patient"
        logger.info(
            f"[RecommendationRouter] 收到SSE请求: role={role}, "
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
        logger.error(f"[RecommendationRouter] SSE处理失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理请求失败: {str(e)}"
        )


@router.get("/health")
async def recommendation_health_check():
    """
    产品推荐Agent健康检查

    Returns:
        健康状态和功能可用性
    """
    return {
        "status": "healthy",
        "agent_type": "recommendation",
        "version": "1.0.0",
        "architecture": "langgraph",
        "access_control": "all_roles",
        "features": {
            "doctor_prescription": True,
            "patient_purchase": True,
            "product_search": True,
            "product_cards": True,
            "interactive_options": True,
            "sse_streaming": True,
        },
        "endpoints": [
            "POST /api/recommendation/chat",
            "POST /api/recommendation/chat/stream",
            "GET /api/recommendation/health",
        ]
    }

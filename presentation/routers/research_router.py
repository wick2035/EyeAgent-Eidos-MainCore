"""
科研Agent路由 - 独立API接口
支持SSE流式响应

基于 LangGraph GraphManager 实现
"""
import uuid
import json
import logging
import asyncio
import re
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from presentation.schemas.research_schemas import (
    ResearchChatRequest,
    ResearchChatResponse,
    ResearchConversationListResponse,
    ConversationSummary
)
from agents.graph_manager import get_graph_manager
from application.services.chat_persistence_service import get_chat_persistence_service

logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/api/research", tags=["research"])

# GraphManager 单例
graph_manager = get_graph_manager()

# UUID格式验证
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$',
    re.IGNORECASE
)


def verify_doctor_role(doctor_id: str, patient_id: str = "") -> bool:
    """
    验证医生身份

    使用集中角色校验模块，校验 doctor_id 有效性。
    """
    if not doctor_id:
        return False
    from utils.role_verification import verify_role
    verified_role, _ = verify_role("doctor", patient_id, doctor_id)
    return verified_role == "doctor"


@router.post("/chat", response_model=ResearchChatResponse)
async def research_chat(request: ResearchChatRequest) -> ResearchChatResponse:
    """
    科研对话接口（非流式）

    Args:
        request: 科研对话请求

    Returns:
        ResearchChatResponse: 对话响应
    """
    try:
        logger.info(
            f"[ResearchRouter] 收到请求: doctor={request.doctor_id}, "
            f"patient={request.patient_id}, institution_data={request.enable_institution_data}, "
            f"web_search={request.enable_web_search}, search_types={request.web_search_types}"
        )

        # 验证医生身份
        if not verify_doctor_role(request.doctor_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="仅医生用户可访问科研Agent，请提供有效的doctor_id"
            )

        # 生成session_id
        session_id = request.session_id or f"research_{uuid.uuid4().hex[:16]}"

        # 获取持久化服务
        persistence_service = get_chat_persistence_service()
        conversation_id = request.conversation_id

        # 如果没有conversation_id，创建新会话
        if not conversation_id:
            conversation_id = persistence_service.create_conversation(
                host_id=request.doctor_id,
                user_type="doctor",
                title="科研对话"
            )
            logger.info(f"[ResearchRouter] 创建新会话: {conversation_id}")

        # 使用 GraphManager 处理对话
        result = graph_manager.chat(
            patient_id=request.patient_id or request.doctor_id,
            session_id=session_id,
            message=request.message,
            role="doctor",
            doctor_id=request.doctor_id,
            conversation_id=conversation_id,
            agent_type="research",
            parent_anchor_id=request.parent_anchor_id,
            dual_answer=request.dual_answer,
            request_id=request.request_id,
            client_message_id=request.client_message_id,
            dual_answer_group_id=request.dual_answer_group_id,
            dual_answer_index=request.dual_answer_index,
            enable_institution_data=request.enable_institution_data,
            enable_web_search=request.enable_web_search,
            web_search_types=request.web_search_types,
        )

        return ResearchChatResponse(
            response=result["response"],
            session_id=session_id,
            conversation_id=conversation_id,
            is_completed=result["is_completed"],
            stage=result["stage"],
            agent_type="research",
            metadata={
                "doctor_id": request.doctor_id,
                "patient_id": request.patient_id,
                "enable_institution_data": request.enable_institution_data,
                "enable_web_search": request.enable_web_search,
                "web_search_types": request.web_search_types,
                "thread_id": result.get("thread_id", ""),
                "citations": result.get("citations", []),
            }
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"[ResearchRouter] 参数错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"[ResearchRouter] 处理失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理请求失败: {str(e)}"
        )


@router.post("/chat/stream")
async def research_chat_stream(request: ResearchChatRequest):
    """
    科研对话接口（SSE流式）

    返回Server-Sent Events流式响应

    SSE事件类型:
    - start: 开始处理
    - token: 响应内容块
    - tool_call: 工具调用通知
    - done: 完成，包含完整响应和元数据
    - error: 错误信息

    Args:
        request: 科研对话请求

    Returns:
        StreamingResponse: SSE流式响应
    """
    async def generate_sse() -> AsyncGenerator[str, None]:
        """生成 SSE 事件流"""
        try:
            # 验证医生身份
            if not verify_doctor_role(request.doctor_id):
                yield f"data: {json.dumps({'event': 'error', 'message': '仅医生用户可访问科研Agent'})}\n\n"
                return

            # 生成session_id
            session_id = request.session_id or f"research_{uuid.uuid4().hex[:16]}"

            # 获取持久化服务
            persistence_service = get_chat_persistence_service()
            conversation_id = request.conversation_id

            # 如果没有conversation_id，创建新会话
            if not conversation_id:
                conversation_id = persistence_service.create_conversation(
                    host_id=request.doctor_id,
                    user_type="doctor",
                    title="科研对话"
                )

            # 获取 thread_id
            from agents.graph.id_mapping import get_thread_config
            thread_config = get_thread_config(session_id, conversation_id)
            thread_id = thread_config["configurable"]["thread_id"]

            # 发送开始事件
            yield f"data: {json.dumps({'event': 'start', 'session_id': session_id, 'conversation_id': conversation_id, 'thread_id': thread_id})}\n\n"

            # 调用异步流式对话（Token 级别）
            full_response = ""
            current_stage = "greeting"
            citations = []

            async for chunk in graph_manager.chat_stream_async(
                patient_id=request.patient_id or request.doctor_id,
                session_id=session_id,
                message=request.message,
                role="doctor",
                doctor_id=request.doctor_id,
                conversation_id=conversation_id,
                agent_type="research",
                parent_anchor_id=request.parent_anchor_id,
                dual_answer=request.dual_answer,
                request_id=request.request_id,
                client_message_id=request.client_message_id,
                dual_answer_group_id=request.dual_answer_group_id,
                dual_answer_index=request.dual_answer_index,
                enable_institution_data=request.enable_institution_data,
                enable_web_search=request.enable_web_search,
                web_search_types=request.web_search_types,
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
                    citations = chunk.get("citations") or metadata.get("citations") or []

                elif event_type == "error":
                    yield f"data: {json.dumps({'event': 'error', 'message': content})}\n\n"

            # 发送完成事件
            done_data = {
                'event': 'done',
                'response': full_response,
                'session_id': session_id,
                'conversation_id': conversation_id,
                'stage': current_stage,
                'agent_type': 'research',
                'citations': citations,
                'metadata': {
                    'doctor_id': request.doctor_id,
                    'patient_id': request.patient_id,
                    'enable_institution_data': request.enable_institution_data,
                    'enable_web_search': request.enable_web_search,
                    'citations': citations,
                },
            }
            yield f"data: {json.dumps(done_data)}\n\n"

        except GeneratorExit:
            logger.info("[ResearchRouter] SSE 生成器关闭，取消科研流式对话")
            raise

        except asyncio.CancelledError:
            logger.info("[ResearchRouter] SSE 客户端断开，取消科研流式对话")
            raise

        except Exception as e:
            logger.error(f"[ResearchRouter] SSE生成错误: {e}", exc_info=True)
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

    try:
        logger.info(
            f"[ResearchRouter] 收到SSE请求: doctor={request.doctor_id}, "
            f"patient={request.patient_id}, web_search={request.enable_web_search}"
        )

        # 返回SSE流式响应
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
        logger.error(f"[ResearchRouter] SSE处理失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理请求失败: {str(e)}"
        )


@router.get("/conversations")
async def list_research_conversations(
    doctor_id: str,
    limit: int = 20,
    offset: int = 0
) -> ResearchConversationListResponse:
    """
    获取科研会话列表

    Args:
        doctor_id: 医生UUID
        limit: 返回数量（1-100）
        offset: 偏移量

    Returns:
        ResearchConversationListResponse: 会话列表
    """
    try:
        # 验证医生身份
        if not verify_doctor_role(doctor_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="仅医生用户可访问"
            )

        # 限制参数范围
        limit = max(1, min(limit, 100))
        offset = max(0, offset)

        persistence_service = get_chat_persistence_service()
        conversations, total, has_more = persistence_service.list_conversations(
            host_id=doctor_id,
            user_type="doctor",
            limit=limit,
            offset=offset
        )

        return ResearchConversationListResponse(
            conversations=[
                ConversationSummary(
                    id=conv.id,
                    title=conv.title,
                    summary=conv.summary,
                    total_messages=conv.total_messages,
                    create_time=conv.create_time,
                    update_time=conv.update_time
                )
                for conv in conversations
            ],
            total=total,
            has_more=has_more
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ResearchRouter] 获取会话列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取会话列表失败: {str(e)}"
        )


@router.get("/conversations/{conversation_id}")
async def get_research_conversation(conversation_id: str, doctor_id: str):
    """
    获取科研会话详情

    Args:
        conversation_id: 会话ID
        doctor_id: 医生UUID（用于权限验证）

    Returns:
        会话详情和消息列表
    """
    try:
        # 验证医生身份
        if not verify_doctor_role(doctor_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="仅医生用户可访问"
            )

        persistence_service = get_chat_persistence_service()
        conversation, messages = persistence_service.load_conversation(conversation_id)

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会话不存在: {conversation_id}"
            )

        # 验证会话所属
        if conversation.host_id != doctor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此会话"
            )

        return {
            "conversation": {
                "id": conversation.id,
                "title": conversation.title,
                "summary": conversation.summary,
                "total_messages": conversation.total_messages,
                "create_time": conversation.create_time.isoformat() if conversation.create_time else None,
                "update_time": conversation.update_time.isoformat() if conversation.update_time else None
            },
            "messages": [
                {
                    "id": msg.id,
                    "message_order": msg.message_order,
                    "message_content": msg.message_content,
                    "message_type": msg.message_type,
                    "create_time": msg.create_time.isoformat() if msg.create_time else None
                }
                for msg in messages
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ResearchRouter] 获取会话详情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取会话详情失败: {str(e)}"
        )


@router.delete("/conversations/{conversation_id}")
async def delete_research_conversation(conversation_id: str, doctor_id: str):
    """
    删除科研会话

    Args:
        conversation_id: 会话ID
        doctor_id: 医生UUID（用于权限验证）

    Returns:
        删除结果
    """
    try:
        # 验证医生身份
        if not verify_doctor_role(doctor_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="仅医生用户可访问"
            )

        persistence_service = get_chat_persistence_service()

        # 先检查会话是否存在及权限
        conversation = persistence_service.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会话不存在: {conversation_id}"
            )

        if conversation.host_id != doctor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权删除此会话"
            )

        # 删除会话
        success = persistence_service.delete_conversation(conversation_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除会话失败"
            )

        return {"message": "会话已删除", "conversation_id": conversation_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ResearchRouter] 删除会话失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除会话失败: {str(e)}"
        )


@router.get("/health")
async def research_health_check():
    """
    科研Agent健康检查

    Returns:
        健康状态和功能可用性
    """
    # 检查Search1API是否可用
    search_available = False
    try:
        from infrastructure.api.search1api_client import get_search1api_client
        client = get_search1api_client()
        search_available = client.is_available()
    except Exception:
        pass

    # 检查Minio是否可用
    minio_available = False
    try:
        from infrastructure.storage.minio_client import get_minio_client
        minio_client = get_minio_client()
        minio_available = minio_client.is_available()
    except Exception:
        pass

    # 检查统计分析库是否可用
    stats_available = False
    try:
        import pandas
        import numpy
        import scipy
        stats_available = True
    except ImportError:
        pass

    # 检查可视化库是否可用
    viz_available = False
    try:
        import matplotlib
        viz_available = True
    except ImportError:
        pass

    return {
        "status": "healthy",
        "agent_type": "research",
        "version": "3.0.0",
        "architecture": "langgraph",
        "features": {
            "institution_data": True,
            "web_search": search_available,
            "sse_streaming": True,
            "statistical_analysis": stats_available,
            "data_visualization": viz_available,
            "visualization_storage": minio_available,
            "literature_review": True,
            "research_design": True,
        },
        "dependencies": {
            "search1api": search_available,
            "minio": minio_available,
            "pandas": stats_available,
            "scipy": stats_available,
            "matplotlib": viz_available
        },
        "endpoints": [
            "POST /api/research/chat",
            "POST /api/research/chat/stream",
            "GET /api/research/conversations",
            "GET /api/research/conversations/{id}",
            "DELETE /api/research/conversations/{id}",
            "GET /api/research/health"
        ]
    }

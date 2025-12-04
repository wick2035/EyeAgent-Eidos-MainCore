"""
科研Agent路由 - 独立API接口
支持SSE流式响应

Created: 2025-12-03
"""
import uuid
import json
import asyncio
import logging
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
from agents.research.research_agent import ResearchAgent
from application.services.chat_persistence_service import get_chat_persistence_service

logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/api/research", tags=["research"])

# UUID格式验证
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$',
    re.IGNORECASE
)


def verify_doctor_role(doctor_id: str) -> bool:
    """
    验证医生身份

    TODO: 实现实际的医生身份验证逻辑
    - 检查doctor_id是否存在于系统中
    - 验证用户角色是否为doctor
    - 检查机构数据库访问权限

    目前仅验证UUID格式
    """
    return bool(UUID_PATTERN.match(doctor_id))


async def generate_sse_response(
    agent: ResearchAgent,
    message: str,
    conversation_id: str
) -> AsyncGenerator[str, None]:
    """
    生成SSE流式响应

    SSE消息格式:
    - start: 开始处理
    - chunk: 内容块
    - tool_call: 工具调用通知
    - done: 完成，包含摘要信息
    - error: 错误信息

    Args:
        agent: ResearchAgent实例
        message: 用户消息
        conversation_id: 会话ID

    Yields:
        SSE格式的消息
    """
    try:
        # 发送开始事件
        start_data = {
            "event": "start",
            "session_id": agent.session_id,
            "conversation_id": conversation_id,
            "message": "开始处理..."
        }
        yield f"data: {json.dumps(start_data, ensure_ascii=False)}\n\n"

        # 调用agent处理消息（在线程池中运行以避免阻塞）
        loop = asyncio.get_event_loop()
        response_text = await loop.run_in_executor(None, agent.chat, message)

        # 流式输出响应（分块发送）
        # 按句子或段落分割，模拟流式效果
        chunks = split_response_into_chunks(response_text)

        for i, chunk in enumerate(chunks):
            chunk_data = {
                "event": "chunk",
                "index": i,
                "content": chunk,
                "is_last": i == len(chunks) - 1
            }
            yield f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.03)  # 短暂延迟，模拟打字效果

        # 获取对话摘要
        summary = agent.get_conversation_summary()

        # 发送完成事件
        done_data = {
            "event": "done",
            "response": response_text,  # 完整响应
            "session_id": agent.session_id,
            "conversation_id": conversation_id,
            "is_completed": summary["is_completed"],
            "stage": summary["stage"],
            "agent_type": "research",
            "metadata": {
                "doctor_id": agent.doctor_id,
                "patient_id": agent.target_patient_id,
                "message_count": summary["message_count"],
                "enable_institution_data": agent.enable_institution_data,
                "enable_web_search": agent.enable_web_search
            }
        }
        yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"

    except Exception as e:
        logger.error(f"[ResearchRouter] SSE生成错误: {e}", exc_info=True)
        error_data = {
            "event": "error",
            "message": str(e)
        }
        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"


def split_response_into_chunks(text: str, chunk_size: int = 50) -> list:
    """
    将响应文本分割成块

    优先按句子分割，如果句子太长则按字符数分割
    """
    if not text:
        return []

    # 按句子分割（中文和英文标点）
    sentences = re.split(r'([。！？\n])', text)

    chunks = []
    current_chunk = ""

    for i in range(0, len(sentences), 2):
        sentence = sentences[i]
        # 添加标点（如果有）
        if i + 1 < len(sentences):
            sentence += sentences[i + 1]

        if len(current_chunk) + len(sentence) <= chunk_size:
            current_chunk += sentence
        else:
            if current_chunk:
                chunks.append(current_chunk)
            # 如果单个句子太长，按字符分割
            if len(sentence) > chunk_size:
                for j in range(0, len(sentence), chunk_size):
                    chunks.append(sentence[j:j + chunk_size])
                current_chunk = ""
            else:
                current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk)

    return chunks if chunks else [text]


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

        # 创建ResearchAgent
        agent = ResearchAgent(
            doctor_id=request.doctor_id,
            session_id=session_id,
            patient_id=request.patient_id,
            enable_institution_data=request.enable_institution_data,
            enable_web_search=request.enable_web_search,
            web_search_types=request.web_search_types,
            conversation_id=conversation_id,
            persistence_service=persistence_service
        )

        # 处理消息
        response_text = agent.chat(request.message)

        # 获取摘要
        summary = agent.get_conversation_summary()

        return ResearchChatResponse(
            response=response_text,
            session_id=session_id,
            conversation_id=conversation_id,
            is_completed=summary["is_completed"],
            stage=summary["stage"],
            agent_type="research",
            metadata={
                "doctor_id": request.doctor_id,
                "patient_id": request.patient_id,
                "message_count": summary["message_count"],
                "enable_institution_data": request.enable_institution_data,
                "enable_web_search": request.enable_web_search,
                "web_search_types": request.web_search_types
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
    - chunk: 响应内容块
    - done: 完成，包含完整响应和元数据
    - error: 错误信息

    Args:
        request: 科研对话请求

    Returns:
        StreamingResponse: SSE流式响应
    """
    try:
        logger.info(
            f"[ResearchRouter] 收到SSE请求: doctor={request.doctor_id}, "
            f"patient={request.patient_id}, web_search={request.enable_web_search}"
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
            logger.info(f"[ResearchRouter] SSE创建新会话: {conversation_id}")

        # 创建ResearchAgent
        agent = ResearchAgent(
            doctor_id=request.doctor_id,
            session_id=session_id,
            patient_id=request.patient_id,
            enable_institution_data=request.enable_institution_data,
            enable_web_search=request.enable_web_search,
            web_search_types=request.web_search_types,
            conversation_id=conversation_id,
            persistence_service=persistence_service
        )

        # 返回SSE流式响应
        return StreamingResponse(
            generate_sse_response(agent, request.message, conversation_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # 禁用Nginx缓冲
                "Access-Control-Allow-Origin": "*"
            }
        )

    except HTTPException:
        raise
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
        "version": "2.0.0",  # 阶段二版本
        "features": {
            # 阶段一功能
            "institution_data": True,  # 功能已实现，但需要后端接口
            "web_search": search_available,
            "sse_streaming": True,
            # 阶段二功能
            "statistical_analysis": stats_available,
            "data_visualization": viz_available,
            "visualization_storage": minio_available,
            "literature_review": True,  # 已实现
            "research_design": True,  # 已实现
            # 阶段三功能（待实现）
            "paper_writing": False,
            "clinical_guidelines": False,
            "drug_interactions": False,
            "case_matching": False,
            "ethics_review": False,
            "data_export": False
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
        ],
        "tools": {
            "phase1": ["get_institution_research_data", "web_search_medical"],
            "phase2": ["statistical_analysis", "summarize_medical_literature", "generate_research_visualization", "design_research_protocol"],
            "inherited": 11
        }
    }

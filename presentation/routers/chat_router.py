"""
聊天路由 - 处理与Agent的对话交互
基于 LangGraph GraphManager 实现
"""
import uuid
import json
import logging
import asyncio
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from presentation.schemas.chat_schemas import (
    ChatRequest,
    ChatResponse,
    EditResendRequest,
    RegenerateRequest,
)
from agents.graph_manager import get_graph_manager
from application.services.chat_persistence_service import (
    LegacyBranchForbiddenError,
    LegacyBranchSourceInvalidError,
    get_chat_persistence_service,
)
from utils.ui_element_parser import parse_options_only
from utils.attachment_analyzer import analyze_attachments
from presentation.dependencies.security import (
    LegacyRouteError,
    require_legacy_platform_doctor,
)

logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/api/chat", tags=["chat"])

# GraphManager 单例
graph_manager = get_graph_manager()

# 患者模式下支持OPTIONS选择框的Agent类型
_AGENTS_WITH_OPTIONS = {"health", "reminder", "report"}
_CHAT_ERROR_MESSAGE = "对话暂时不可用，请稍后再试。"


def _reject_research_on_generic_route(request) -> None:
    if request.agent_type == "research":
        raise HTTPException(
            status_code=403,
            detail={"error_code": "PLATFORM_RESEARCH_ROUTE_REQUIRED"},
        )


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    与Agent进行对话 (基于 LangGraph)

    使用 LangGraph 框架实现，支持：
    - 更好的状态管理
    - MySQL Checkpoint 持久化
    - 自动路由和 Agent 切换

    Args:
        request: 聊天请求

    Returns:
        ChatResponse: 聊天响应
    """
    _reject_research_on_generic_route(request)
    try:
        logger.info(
            f"[ChatRouter] 收到聊天请求: patient={request.patient_id}, "
            f"doctor={request.doctor_id}, role={request.role}, "
            f"agent={request.agent_type}, conversation_id={request.conversation_id}"
        )

        # 生成session_id（如果没有提供）
        session_id = request.session_id or f"sess_{uuid.uuid4().hex[:16]}"

        # 获取持久化服务（用于创建 conversation_id）
        persistence_service = get_chat_persistence_service()
        conversation_id = request.conversation_id

        # 根据角色决定 host_id
        if request.role == "doctor":
            if not request.doctor_id:
                raise ValueError("医生端请求必须提供 doctor_id")
            host_id = request.doctor_id
        else:
            host_id = request.patient_id

        # 如果没有 conversation_id，创建新的数据库会话
        if not conversation_id:
            conversation_id = persistence_service.create_conversation(
                host_id=host_id,
                user_type=request.role or "patient",
                title="新对话"
            )
            logger.info(f"[ChatRouter] 创建新会话: {conversation_id}")

        # 附件预分析（如有附件，同步调用视觉/文档模型，得到分析文本）
        attachments_raw = []
        attachment_analysis = ""
        if request.attachments:
            attachments_raw = [a.model_dump() for a in request.attachments]
            logger.info(f"[ChatRouter] 开始预分析附件，数量={len(attachments_raw)}")
            attachment_analysis = analyze_attachments(attachments_raw, request.message)
            logger.info(f"[ChatRouter] 附件预分析完成，分析长度={len(attachment_analysis)}")

        # 使用 GraphManager 处理对话
        result = graph_manager.chat(
            patient_id=request.patient_id,
            session_id=session_id,
            message=request.message,
            role=request.role or "patient",
            doctor_id=request.doctor_id,
            conversation_id=conversation_id,
            agent_type=request.agent_type or "health",
            attachments=attachments_raw,
            attachment_analysis=attachment_analysis,
        )

        # 解析UI元素（仅患者模式的特定Agent）
        raw_response = result["response"]
        ui_elements = None
        role = request.role or "patient"
        agent = result["agent_type"]

        if role == "patient" and agent in _AGENTS_WITH_OPTIONS:
            raw_response, ui_elements = parse_options_only(raw_response)

        # 构建响应
        return ChatResponse(
            response=raw_response,
            session_id=session_id,
            conversation_id=conversation_id,
            is_completed=result["is_completed"],
            stage=result["stage"],
            agent_type=agent,
            ui_elements=ui_elements,
            metadata={
                "patient_id": request.patient_id,
                "role": role,
                "thread_id": result.get("thread_id", ""),
                "version": "langgraph",
                "citations": result.get("citations", []),
            }
        )

    except ValueError as e:
        logger.error(f"[ChatRouter] 参数错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except Exception as e:
        logger.error(f"[ChatRouter] 处理失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理请求失败: {str(e)}"
        )


@router.delete("/{session_id}")
async def delete_session(session_id: str, conversation_id: str = None):
    """
    删除会话

    Args:
        session_id: 会话ID
        conversation_id: 数据库会话ID（可选）

    Returns:
        删除结果
    """
    try:
        success = graph_manager.reset_conversation(
            session_id=session_id,
            conversation_id=conversation_id,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会话不存在: {session_id}"
            )

        return {"message": "会话已删除", "session_id": session_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ChatRouter] 删除会话失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除会话失败: {str(e)}"
        )


@router.get("/{session_id}/state")
async def get_session_state(session_id: str, conversation_id: str = None):
    """
    获取会话状态

    Args:
        session_id: 会话ID
        conversation_id: 数据库会话ID（可选）

    Returns:
        会话状态
    """
    try:
        state = graph_manager.get_conversation_state(
            session_id=session_id,
            conversation_id=conversation_id,
        )

        if state is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会话不存在: {session_id}"
            )

        # 提取关键状态信息
        return {
            "session_id": session_id,
            "conversation_id": conversation_id,
            "current_agent": state.get("current_agent", "health"),
            "stage": state.get("stage", "greeting"),
            "is_completed": state.get("is_completed", False),
            "message_count": len(state.get("messages", [])),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ChatRouter] 获取状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取状态失败: {str(e)}"
        )


@router.get("/{session_id}/agent-history")
async def get_agent_history(session_id: str, conversation_id: str = None):
    """
    获取 Agent 切换历史

    用于调试和监控对话过程中 Agent 的切换情况。

    Args:
        session_id: 会话ID
        conversation_id: 数据库会话ID（可选）

    Returns:
        Agent 切换历史列表
    """
    try:
        from agents.graph.id_mapping import get_thread_config
        thread_config = get_thread_config(session_id, conversation_id)
        thread_id = thread_config["configurable"]["thread_id"]

        history = graph_manager.get_agent_history(
            session_id=session_id,
            conversation_id=conversation_id,
        )

        # 格式化时间戳
        formatted_history = []
        for item in history:
            formatted_item = {
                "agent_type": item.get("agent_type"),
                "checkpoint_id": item.get("checkpoint_id"),
                "started_at": item["started_at"].isoformat() if item.get("started_at") else None,
                "ended_at": item["ended_at"].isoformat() if item.get("ended_at") else None,
            }
            formatted_history.append(formatted_item)

        return {
            "session_id": session_id,
            "conversation_id": conversation_id,
            "thread_id": thread_id,
            "history": formatted_history,
        }

    except Exception as e:
        logger.error(f"[ChatRouter] 获取 Agent 历史失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取 Agent 历史失败: {str(e)}"
        )


@router.get("/{session_id}/checkpoints")
async def get_checkpoints(session_id: str, conversation_id: str = None, limit: int = 10):
    """
    获取检查点列表

    用于调试和回溯对话状态。

    Args:
        session_id: 会话ID
        conversation_id: 数据库会话ID（可选）
        limit: 返回数量限制，默认 10

    Returns:
        检查点列表
    """
    try:
        from agents.graph.id_mapping import get_thread_config
        thread_config = get_thread_config(session_id, conversation_id)
        thread_id = thread_config["configurable"]["thread_id"]

        checkpoints = graph_manager.get_checkpoints(
            session_id=session_id,
            conversation_id=conversation_id,
            limit=limit,
        )

        return {
            "session_id": session_id,
            "conversation_id": conversation_id,
            "thread_id": thread_id,
            "count": len(checkpoints),
            "checkpoints": checkpoints,
        }

    except Exception as e:
        logger.error(f"[ChatRouter] 获取检查点列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取检查点列表失败: {str(e)}"
        )


@router.get("/{session_id}/messages")
async def get_messages(session_id: str, conversation_id: str = None):
    """
    获取消息历史

    用于调试查看完整的对话消息链。

    Args:
        session_id: 会话ID
        conversation_id: 数据库会话ID（可选）

    Returns:
        消息历史
    """
    try:
        from agents.graph.id_mapping import get_thread_config
        thread_config = get_thread_config(session_id, conversation_id)
        thread_id = thread_config["configurable"]["thread_id"]

        result = graph_manager.get_messages(
            session_id=session_id,
            conversation_id=conversation_id,
        )

        return {
            "session_id": session_id,
            "conversation_id": conversation_id,
            "thread_id": thread_id,
            "message_count": result["message_count"],
            "messages": result["messages"],
        }

    except Exception as e:
        logger.error(f"[ChatRouter] 获取消息历史失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取消息历史失败: {str(e)}"
        )


def _streaming_response_for_request(
    request,
    branch_mode: str = "normal",
    source_message_id: Optional[str] = None,
) -> StreamingResponse:
    async def generate_sse() -> AsyncGenerator[str, None]:
        """生成 SSE 事件流"""
        try:
            # 生成 session_id
            session_id = request.session_id or f"sess_{uuid.uuid4().hex[:16]}"
            message = getattr(request, "message", "")

            # 获取持久化服务
            persistence_service = get_chat_persistence_service()
            conversation_id = request.conversation_id

            # 根据角色决定 host_id
            if request.role == "doctor":
                if not request.doctor_id:
                    yield f"data: {json.dumps({'event': 'error', 'message': '医生端请求必须提供 doctor_id'})}\n\n"
                    return
                host_id = request.doctor_id
            else:
                host_id = request.patient_id

            # 创建新会话
            if not conversation_id:
                conversation_id = persistence_service.create_conversation(
                    host_id=host_id,
                    user_type=request.role or "patient",
                    title="新对话"
                )

            # 获取 thread_id
            from agents.graph.id_mapping import get_thread_config
            thread_config = get_thread_config(session_id, conversation_id)
            thread_id = thread_config["configurable"]["thread_id"]

            # 附件预分析（在第一个 SSE token 之前完成）
            attachments_raw = []
            attachment_analysis = ""
            attachments = getattr(request, "attachments", None)
            if attachments:
                attachments_raw = [a.model_dump() for a in attachments]
                logger.info(f"[ChatRouter/Stream] 开始预分析附件，数量={len(attachments_raw)}")
                attachment_analysis = analyze_attachments(attachments_raw, message)
                logger.info(f"[ChatRouter/Stream] 附件预分析完成，分析长度={len(attachment_analysis)}")

            # 获取当前 Agent（用于检测切换）
            previous_agent = graph_manager.checkpointer.get_current_agent(thread_id)

            # 调用异步流式对话（Token 级别）
            full_response = ""
            current_agent = request.agent_type or "health"
            current_stage = "greeting"
            citations = []

            async for chunk in graph_manager.chat_stream_async(
                patient_id=request.patient_id,
                session_id=session_id,
                message=message,
                role=request.role or "patient",
                doctor_id=request.doctor_id,
                conversation_id=conversation_id,
                agent_type=request.agent_type or "health",
                source_message_id=source_message_id,
                branch_mode=branch_mode,
                attachments=attachments_raw,
                attachment_analysis=attachment_analysis,
            ):
                event_type = chunk.get("type", "")
                content = chunk.get("content", "")
                metadata = chunk.get("metadata", {})

                if event_type == "start":
                    payload = {"event": "start", "session_id": session_id, **metadata}
                    yield f"data: {json.dumps(payload)}\n\n"
                    continue

                if event_type == "token":
                    full_response += content
                    yield f"data: {json.dumps({'event': 'token', 'content': content})}\n\n"

                elif event_type == "node_start":
                    # Agent 切换检测
                    node = metadata.get("node", "")
                    if node and node != current_agent:
                        yield f"data: {json.dumps({'event': 'agent_switch', 'from': current_agent, 'to': node})}\n\n"
                        current_agent = node

                elif event_type == "node_end":
                    if metadata.get("stage"):
                        current_stage = metadata["stage"]

                elif event_type == "tool_start":
                    yield f"data: {json.dumps({'event': 'tool_call', 'tool': metadata.get('tool', 'unknown'), 'status': 'start', 'input': metadata.get('input', {})})}\n\n"

                elif event_type == "tool_end":
                    yield f"data: {json.dumps({'event': 'tool_call', 'tool': metadata.get('tool', 'unknown'), 'status': 'end', 'output': metadata.get('output', '')})}\n\n"

                elif event_type == "done":
                    full_response = content
                    current_agent = metadata.get("agent_type", current_agent)
                    current_stage = metadata.get("stage", current_stage)
                    citations = chunk.get("citations") or metadata.get("citations") or []

                elif event_type == "error":
                    error_code = metadata.get("error_code")
                    if error_code not in {
                        "CHAT_EXECUTION_FAILED",
                        "CHAT_PERSISTENCE_FAILED",
                        "CHAT_SOURCE_INVALID",
                    }:
                        error_code = "CHAT_STREAM_FAILED"
                    yield f"data: {json.dumps({'event': 'error', 'code': error_code, 'message': _CHAT_ERROR_MESSAGE})}\n\n"
                    return

            # 解析UI元素（仅患者模式的特定Agent）
            role = request.role or "patient"
            ui_elements_data = None
            if role == "patient" and current_agent in _AGENTS_WITH_OPTIONS:
                full_response, ui_elements = parse_options_only(full_response)
                if ui_elements:
                    ui_elements_data = ui_elements.model_dump(exclude_none=True)
                    yield f"data: {json.dumps({'event': 'ui_elements', **ui_elements_data})}\n\n"

            # 发送完成事件
            done_data = {
                'event': 'done',
                'response': full_response,
                'agent_type': current_agent,
                'stage': current_stage,
                'session_id': session_id,
                'conversation_id': conversation_id,
                'citations': citations,
                'metadata': {
                    'citations': citations,
                },
            }
            if ui_elements_data:
                done_data['ui_elements'] = ui_elements_data
            yield f"data: {json.dumps(done_data)}\n\n"

        except GeneratorExit:
            logger.info("[ChatRouter] SSE 生成器关闭，取消流式对话")
            raise

        except asyncio.CancelledError:
            logger.info("[ChatRouter] SSE 客户端断开，取消流式对话")
            raise

        except Exception as error:
            logger.error(
                "chat_stream_failed operation=generate exception_class=%s",
                type(error).__name__,
                exc_info=None,
            )
            yield f"data: {json.dumps({'event': 'error', 'code': 'CHAT_STREAM_FAILED', 'message': _CHAT_ERROR_MESSAGE})}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    流式对话 (SSE)

    使用 Server-Sent Events 实现流式响应，支持：
    - 实时 token 输出
    - Agent 切换通知
    - 工具调用状态

    Args:
        request: 聊天请求

    Returns:
        StreamingResponse: SSE 流式响应
    """
    _reject_research_on_generic_route(request)
    return _streaming_response_for_request(request)


@router.post("/edit-resend/stream")
async def chat_edit_resend_stream(
    request: EditResendRequest,
    http_request: Request,
):
    require_legacy_platform_doctor(
        http_request,
        request.doctor_id or "",
        request.agent_type,
    )
    _assert_legacy_branch_authority(request, "edit")
    return _streaming_response_for_request(
        request,
        branch_mode="edit",
        source_message_id=request.source_message_id,
    )


@router.post("/regenerate/stream")
async def chat_regenerate_stream(
    request: RegenerateRequest,
    http_request: Request,
):
    require_legacy_platform_doctor(
        http_request,
        request.doctor_id or "",
        request.agent_type,
    )
    _assert_legacy_branch_authority(request, "regenerate")
    return _streaming_response_for_request(
        request,
        branch_mode="regenerate",
        source_message_id=request.source_message_id,
    )


def _assert_legacy_branch_authority(request, branch_mode: str) -> None:
    try:
        get_chat_persistence_service().assert_legacy_branch_authority(
            chat_id=request.conversation_id,
            source_message_id=request.source_message_id,
            branch_mode=branch_mode,
            doctor_id=request.doctor_id or "",
            agent_type=request.agent_type or "health",
            patient_id=request.patient_id,
        )
    except LegacyBranchForbiddenError:
        raise LegacyRouteError(403, "PLATFORM_DOCTOR_FORBIDDEN") from None
    except LegacyBranchSourceInvalidError:
        raise LegacyRouteError(409, "LEGACY_BRANCH_SOURCE_INVALID") from None

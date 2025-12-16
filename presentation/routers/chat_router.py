"""
聊天路由 - 处理与Agent的对话交互
支持对话历史持久化
"""
import uuid
import logging
from fastapi import APIRouter, HTTPException, status

from presentation.schemas.chat_schemas import ChatRequest, ChatResponse
from agents.agent_manager import AgentManager
from application.services.chat_persistence_service import get_chat_persistence_service
from utils.hybrid_intent_router import get_hybrid_router

logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/api/chat", tags=["chat"])

# 全局AgentManager实例
agent_manager = AgentManager()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    与Agent进行对话

    支持两种模式：
    1. 新建对话：conversation_id 为空，创建新的数据库会话
    2. 继续对话：conversation_id 有值，加载历史对话继续

    Args:
        request: 聊天请求

    Returns:
        ChatResponse: 聊天响应（包含 conversation_id 供后续使用）

    Raises:
        HTTPException: 当出现错误时
    """
    try:
        logger.info(
            f"[ChatRouter] 收到聊天请求: patient={request.patient_id}, "
            f"doctor={request.doctor_id}, role={request.role}, "
            f"agent={request.agent_type}, conversation_id={request.conversation_id}"
        )

        # 生成session_id（如果没有提供）
        session_id = request.session_id or f"sess_{uuid.uuid4().hex[:16]}"

        # 获取持久化服务
        persistence_service = get_chat_persistence_service()
        conversation_id = request.conversation_id

        # 根据角色决定 host_id
        # 患者端：host_id = patient_id
        # 医生端：host_id = doctor_id（医生自己的UUID）
        if request.role == "doctor":
            if not request.doctor_id:
                raise ValueError("医生端请求必须提供 doctor_id")
            host_id = request.doctor_id
            logger.info(f"[ChatRouter] 医生端请求: host_id={host_id}, 目标患者={request.patient_id}")
        else:
            host_id = request.patient_id

        # 如果没有 conversation_id，创建新的数据库会话
        if not conversation_id:
            conversation_id = persistence_service.create_conversation(
                host_id=host_id,
                user_type=request.role or "patient",
                title="新对话"
            )
            logger.info(f"[ChatRouter] 创建新会话: {conversation_id}, host_id={host_id}")

        # === 意图检测与自动路由 ===
        # 如果请求没有明确指定agent_type，或使用默认值，则进行意图检测
        effective_agent_type = request.agent_type or "health"
        need_switch = False  # 是否需要切换Agent

        # 患者端和医生端都启用意图自动路由
        # 根据消息内容自动判断使用 health/report/reminder agent
        try:
            hybrid_router = get_hybrid_router()

            intent_result = hybrid_router.route(
                message=request.message,
                role=request.role or "patient",
                current_agent=effective_agent_type
            )

            # 如果检测到不同的意图且置信度足够高，使用检测到的agent类型
            if hybrid_router.should_switch_agent(
                current_agent=effective_agent_type,
                detected_intent=intent_result,
                threshold=0.7
            ):
                detected_type = intent_result.get('agent_type')
                logger.info(
                    f"[ChatRouter] 意图检测: '{request.message}' -> {detected_type} "
                    f"(置信度: {intent_result.get('confidence', 0):.2f})"
                )
                effective_agent_type = detected_type
                need_switch = True  # 标记需要切换Agent
        except Exception as e:
            logger.warning(f"[ChatRouter] 意图检测失败，使用默认agent_type: {e}")

        # 根据是否需要切换选择不同的方法
        if need_switch:
            # 切换到新的Agent类型（删除旧Agent，创建新Agent）
            agent = agent_manager.switch_agent_type(
                session_id=session_id,
                new_agent_type=effective_agent_type,
                patient_id=request.patient_id,
                role=request.role,
                doctor_id=request.doctor_id,
                conversation_id=conversation_id,
                persistence_service=persistence_service
            )
        else:
            # 获取或创建agent（带持久化支持）
            agent = agent_manager.get_or_create_agent(
                session_id=session_id,
                patient_id=request.patient_id,
                agent_type=effective_agent_type,
                role=request.role,
                doctor_id=request.doctor_id,
                conversation_id=conversation_id,
                persistence_service=persistence_service
            )

        # 调用agent处理消息
        response_text = agent.chat(request.message)

        # 获取对话摘要
        summary = agent.get_conversation_summary()

        # 构建响应
        return ChatResponse(
            response=response_text,
            session_id=session_id,
            conversation_id=summary.get("conversation_id") or conversation_id,
            is_completed=summary["is_completed"],
            stage=summary["stage"],
            agent_type=summary["agent_type"],
            metadata={
                "patient_id": summary["patient_id"],
                "message_count": summary["message_count"],
                "role": summary["role"],
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
async def delete_session(session_id: str):
    """
    删除会话

    Args:
        session_id: 会话ID

    Returns:
        删除结果
    """
    try:
        success = agent_manager.remove_agent(session_id)

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


@router.get("/sessions")
async def get_all_sessions():
    """
    获取所有活动会话（调试用）

    Returns:
        活动会话列表
    """
    try:
        from infrastructure.session.session_manager import get_session_manager
        session_manager = get_session_manager()
        sessions = session_manager.get_all_sessions()

        return {
            "total_count": len(sessions),
            "sessions": sessions
        }

    except Exception as e:
        logger.error(f"[ChatRouter] 获取会话列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取会话列表失败: {str(e)}"
        )


@router.post("/{session_id}/reset")
async def reset_session(session_id: str):
    """
    重置会话

    Args:
        session_id: 会话ID

    Returns:
        重置结果
    """
    try:
        # 先检查会话是否存在
        from infrastructure.session.session_manager import get_session_manager
        session_manager = get_session_manager()
        session = session_manager.get_session(session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会话不存在或已过期: {session_id}. 请创建新会话"
            )

        # 重置agent
        success = agent_manager.reset_agent(session_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会话不存在: {session_id}"
            )

        return {"message": "会话已重置", "session_id": session_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ChatRouter] 重置会话失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重置会话失败: {str(e)}"
        )

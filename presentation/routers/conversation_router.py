"""
会话管理路由 - 处理对话历史的查询和管理
"""
import logging
from fastapi import APIRouter, HTTPException, status, Query

from presentation.schemas.conversation_schemas import (
    ConversationListResponse,
    ConversationSummary,
    ConversationDetailResponse,
    MessageResponse,
    MessageSiblingResponse,
    DeleteConversationResponse,
    ActiveBranchRequest,
)
from application.services.chat_persistence_service import get_chat_persistence_service

logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    host_id: str = Query(..., description="用户ID（患者/医生UUID）"),
    user_type: str = Query("patient", description="用户类型 (patient/doctor)"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量")
) -> ConversationListResponse:
    """
    获取用户的历史会话列表

    Args:
        host_id: 用户ID（患者/医生UUID）
        user_type: 用户类型 (patient/doctor)
        limit: 返回数量（默认20，最大100）
        offset: 偏移量

    Returns:
        ConversationListResponse: 会话列表响应
    """
    try:
        logger.info(f"[ConversationRouter] 获取会话列表: host_id={host_id}, user_type={user_type}")

        persistence_service = get_chat_persistence_service()
        conversations, total, has_more = persistence_service.list_conversations(
            host_id=host_id,
            user_type=user_type,
            limit=limit,
            offset=offset
        )

        # 转换为响应模型
        conversation_summaries = [
            ConversationSummary(
                id=conv.id,
                title=conv.title,
                summary=conv.summary,
                total_messages=conv.total_messages,
                create_time=conv.create_time,
                update_time=conv.update_time
            )
            for conv in conversations
        ]

        return ConversationListResponse(
            conversations=conversation_summaries,
            total=total,
            has_more=has_more
        )

    except Exception as e:
        logger.error(f"[ConversationRouter] 获取会话列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取会话列表失败: {str(e)}"
        )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation_detail(conversation_id: str) -> ConversationDetailResponse:
    """
    获取会话详情和所有消息

    Args:
        conversation_id: 会话UUID

    Returns:
        ConversationDetailResponse: 会话详情响应
    """
    try:
        logger.info(f"[ConversationRouter] 获取会话详情: {conversation_id}")

        persistence_service = get_chat_persistence_service()
        conversation = persistence_service.get_conversation(conversation_id)

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会话不存在: {conversation_id}"
            )
        conversation, messages, sibling_map = persistence_service.load_active_path(conversation_id)

        # 转换消息为响应模型
        message_responses = []
        for msg in messages:
            siblings = sibling_map.get(msg.id, [])
            context_list = None
            if msg.context:
                try:
                    context_list = msg.get_context_dict()
                except Exception:
                    context_list = None

            message_responses.append(MessageResponse(
                id=msg.id,
                message_order=msg.message_order,
                message_content=msg.message_content,
                message_type=msg.message_type,
                create_time=msg.create_time,
                context=context_list,
                parent_id=msg.parent_id,
                siblings_group_id=msg.siblings_group_id,
                status=msg.status,
                feedback=getattr(msg, "feedback", None),
                siblings=[
                    MessageSiblingResponse(
                        id=s.id,
                        message_type=s.message_type,
                        text_preview=s.message_content[:80],
                        active=s.id == msg.id,
                    )
                    for s in siblings
                ],
            ))

        return ConversationDetailResponse(
            id=conversation.id,
            user_type=conversation.user_type,
            host_id=conversation.host_id,
            title=conversation.title,
            summary=conversation.summary,
            total_messages=conversation.total_messages,
            create_time=conversation.create_time,
            update_time=conversation.update_time,
            messages=message_responses
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ConversationRouter] 获取会话详情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取会话详情失败: {str(e)}"
        )


@router.put("/{conversation_id}/active-branch")
async def switch_active_branch(conversation_id: str, request: ActiveBranchRequest):
    try:
        persistence_service = get_chat_persistence_service()
        success = persistence_service.switch_active_branch(conversation_id, request.through_message_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="切换分支失败")
        conversation = persistence_service.get_conversation(conversation_id)
        active_node_id = conversation.active_node_id if conversation else request.through_message_id
        return {"success": True, "conversation_id": conversation_id, "active_node_id": active_node_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ConversationRouter] 切换分支失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="切换分支失败"
        )


@router.delete("/{conversation_id}", response_model=DeleteConversationResponse)
async def delete_conversation(conversation_id: str) -> DeleteConversationResponse:
    """
    软删除会话

    Args:
        conversation_id: 会话UUID

    Returns:
        DeleteConversationResponse: 删除响应
    """
    try:
        logger.info(f"[ConversationRouter] 删除会话: {conversation_id}")

        persistence_service = get_chat_persistence_service()

        # 检查会话是否存在
        conversation = persistence_service.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会话不存在: {conversation_id}"
            )

        # 执行软删除
        success = persistence_service.delete_conversation(conversation_id)

        if success:
            return DeleteConversationResponse(
                success=True,
                message="会话已删除",
                conversation_id=conversation_id
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除会话失败"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ConversationRouter] 删除会话失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除会话失败: {str(e)}"
        )

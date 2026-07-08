"""
MySQL 持久化适配器

实现 PersistenceAdapter 接口，将消息持久化到 MySQL 数据库
"""
import logging
from contextvars import ContextVar
from typing import Optional, Dict, Any, List

from agents.graph.persistence_adapter import PersistenceAdapter
from domain.models.chat_entity import MessageContext

logger = logging.getLogger(__name__)


class MySQLPersistenceAdapter(PersistenceAdapter):
    """
    MySQL 持久化适配器

    通过 ChatPersistenceService 实现消息持久化
    """

    def __init__(self, persistence_service):
        """
        初始化适配器

        Args:
            persistence_service: ChatPersistenceService 实例
        """
        self.service = persistence_service
        self._pending_assistant_ids: ContextVar[Dict[str, List[str]]] = ContextVar(
            f"mysql_pending_assistant_ids_{id(self)}",
            default={},
        )
        logger.info("[MySQLPersistenceAdapter] 初始化完成")

    def _push_pending_assistant_id(self, chat_id: str, assistant_message_id: str) -> None:
        pending = {key: value.copy() for key, value in self._pending_assistant_ids.get().items()}
        pending.setdefault(chat_id, []).append(assistant_message_id)
        self._pending_assistant_ids.set(pending)

    def _pop_pending_assistant_id(self, chat_id: str) -> Optional[str]:
        pending = {key: value.copy() for key, value in self._pending_assistant_ids.get().items()}
        ids = pending.get(chat_id)
        if not ids:
            return None
        assistant_message_id = ids.pop(0)
        if ids:
            pending[chat_id] = ids
        else:
            pending.pop(chat_id, None)
        self._pending_assistant_ids.set(pending)
        return assistant_message_id

    def save_user_message(
        self,
        chat_id: str,
        content: str,
        sender_id: str,
        context: Optional[Dict[str, Any]] = None,
        is_first_message: bool = False,
    ) -> str:
        """保存用户消息"""
        try:
            ids = self.prepare_normal_turn(
                chat_id=chat_id,
                content=content,
                sender_id=sender_id,
                context=context,
                is_first_message=is_first_message,
            )
            self._push_pending_assistant_id(chat_id, ids["assistant_message_id"])

            logger.debug(
                f"[MySQLPersistenceAdapter] 保存用户消息: chat_id={chat_id}, "
                f"message_id={ids['user_message_id']}, is_first={is_first_message}"
            )
            return ids["user_message_id"]

        except Exception as e:
            logger.error(f"[MySQLPersistenceAdapter] 保存用户消息失败: {e}", exc_info=True)
            raise

    def create_assistant_placeholder(
        self,
        chat_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建 AI 回复占位"""
        try:
            pending_id = self._pop_pending_assistant_id(chat_id)
            if pending_id:
                logger.debug(
                    f"[MySQLPersistenceAdapter] 复用 AI 占位: chat_id={chat_id}, "
                    f"message_id={pending_id}"
                )
                return pending_id

            msg_context = self._build_assistant_context(context)
            conversation = self.service._must_get_conversation(chat_id)
            if not conversation.active_node_id:
                raise ValueError("会话缺少 active_node_id")
            message = self.service.create_assistant_regeneration(
                chat_id=chat_id,
                source_assistant_id=conversation.active_node_id,
                context=msg_context,
            )

            logger.debug(
                f"[MySQLPersistenceAdapter] 创建 AI 占位: chat_id={chat_id}, "
                f"message_id={message.id}"
            )
            return message.id

        except Exception as e:
            logger.error(f"[MySQLPersistenceAdapter] 创建 AI 占位失败: {e}", exc_info=True)
            raise

    def prepare_normal_turn(
        self,
        chat_id: str,
        content: str,
        sender_id: str,
        context: Optional[Dict[str, Any]] = None,
        is_first_message: bool = False,
    ) -> Dict[str, str]:
        msg_context = self._build_user_context(context, is_first_message)
        user, assistant = self.service.create_turn(chat_id, content, sender_id, msg_context)
        if is_first_message:
            self.update_conversation_title(chat_id, content)
        return {"user_message_id": user.id, "assistant_message_id": assistant.id}

    def prepare_edit_resend_turn(
        self,
        chat_id: str,
        source_message_id: str,
        content: str,
        sender_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        msg_context = self._build_user_context(context, False)
        user, assistant = self.service.create_turn(
            chat_id,
            content,
            sender_id,
            msg_context,
            source_message_id=source_message_id,
            mode="edit",
        )
        return {"user_message_id": user.id, "assistant_message_id": assistant.id}

    def prepare_regenerate_turn(
        self,
        chat_id: str,
        source_assistant_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        msg_context = self._build_assistant_context(context)
        assistant = self.service.create_assistant_regeneration(
            chat_id,
            source_assistant_id,
            msg_context,
        )
        return {"assistant_message_id": assistant.id}

    def update_assistant_success(
        self,
        message_id: str,
        content: str,
        token_used: Optional[int] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """更新 AI 回复为成功，tool_results/citations 由 GraphManager 统一归一化。"""
        try:
            # 构建更新的上下文
            updated_context = None
            if context or tool_results or citations:
                updated_context = MessageContext(
                    patient_info=None,
                    conversation_stage=context.get("stage") if context else None,
                    tool_results=tool_results if tool_results else None,
                    citations=citations if citations else None,
                    metadata={
                        "agent_type": context.get("agent_type") if context else None,
                    } if context else None,
                )

            update_kwargs = {
                "message_id": message_id,
                "content": content,
                "status": "success",
                "context": updated_context,
            }
            # provider 未返回 usage 时保持 token_used 不更新，避免用 None 覆盖已有值。
            if token_used is not None:
                update_kwargs["token_used"] = token_used

            success = self.service.update_message(**update_kwargs)

            logger.debug(
                f"[MySQLPersistenceAdapter] 更新 AI 成功: message_id={message_id}, "
                f"token_used={token_used}"
            )
            return success

        except Exception as e:
            logger.error(f"[MySQLPersistenceAdapter] 更新 AI 成功失败: {e}", exc_info=True)
            return False

    def update_assistant_failed(
        self,
        message_id: str,
        error_message: str,
    ) -> bool:
        """更新 AI 回复为失败"""
        try:
            success = self.service.update_message(
                message_id=message_id,
                status="failed",
                error_message=error_message,
            )

            logger.warning(
                f"[MySQLPersistenceAdapter] 更新 AI 失败: message_id={message_id}, "
                f"error={error_message}"
            )
            return success

        except Exception as e:
            logger.error(f"[MySQLPersistenceAdapter] 更新 AI 失败状态失败: {e}", exc_info=True)
            return False

    def update_assistant_final_status(
        self,
        message_id: str,
        status: str,
        content: str,
        error_message: Optional[str] = None,
        token_used: Optional[int] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """更新 AI 回复为最终状态，tool_results/citations 由 GraphManager 统一归一化。"""
        try:
            updated_context = None
            if context or tool_results or citations:
                updated_context = MessageContext(
                    patient_info=None,
                    conversation_stage=context.get("stage") if context else None,
                    tool_results=tool_results if tool_results else None,
                    citations=citations if citations else None,
                    metadata={
                        "agent_type": context.get("agent_type") if context else None,
                    } if context else None,
                )

            update_kwargs = {
                "message_id": message_id,
                "content": content,
                "status": status,
                "context": updated_context,
                "error_message": error_message,
            }
            # provider 未返回 usage 时保持 token_used 不更新，避免用 None 覆盖已有值。
            if token_used is not None:
                update_kwargs["token_used"] = token_used

            success = self.service.update_message(**update_kwargs)

            logger.info(
                f"[MySQLPersistenceAdapter] 更新 AI 最终状态: message_id={message_id}, status={status}"
            )
            return success

        except Exception as e:
            logger.error(f"[MySQLPersistenceAdapter] 更新 AI 最终状态失败: {e}", exc_info=True)
            return False

    def update_conversation_title(
        self,
        chat_id: str,
        first_message: str,
    ) -> bool:
        """更新会话标题"""
        try:
            success = self.service.update_conversation_title(chat_id, first_message)
            logger.debug(f"[MySQLPersistenceAdapter] 更新标题: chat_id={chat_id}")
            return success
        except Exception as e:
            logger.error(f"[MySQLPersistenceAdapter] 更新标题失败: {e}", exc_info=True)
            return False

    def is_first_message(self, chat_id: str) -> bool:
        """判断是否为首条消息"""
        try:
            return self.service.is_first_message(chat_id)
        except Exception as e:
            logger.error(f"[MySQLPersistenceAdapter] 判断首条消息失败: {e}", exc_info=True)
            return False

    def _build_user_context(
        self,
        context: Optional[Dict[str, Any]],
        is_first_message: bool,
    ) -> Optional[MessageContext]:
        """
        构建用户消息的上下文

        Args:
            context: 原始上下文 {patient_info, stage, agent_type}
            is_first_message: 是否为首条消息

        Returns:
            MessageContext 或 None
        """
        if not context:
            return None

        return MessageContext(
            # patient_info 仅首条消息保存
            patient_info=context.get("patient_info") if is_first_message else None,
            conversation_stage=context.get("stage"),
            tool_results=None,  # 用户消息无 tool_results
            citations=None,  # 用户消息无 citations
            metadata={
                "agent_type": context.get("agent_type"),
            } if context.get("agent_type") else None,
        )

    def _build_assistant_context(
        self,
        context: Optional[Dict[str, Any]],
    ) -> Optional[MessageContext]:
        """
        构建 AI 消息的上下文（占位时）

        Args:
            context: 原始上下文

        Returns:
            MessageContext 或 None
        """
        if not context:
            return None

        return MessageContext(
            patient_info=None,  # AI 消息不保存 patient_info
            conversation_stage=context.get("stage"),
            tool_results=None,  # 占位时无结果，成功后更新
            citations=None,  # 占位时无引用来源，成功后更新
            metadata={
                "agent_type": context.get("agent_type"),
            } if context.get("agent_type") else None,
        )


# 工厂函数
def get_mysql_persistence_adapter():
    """
    获取 MySQL 持久化适配器实例

    Returns:
        MySQLPersistenceAdapter 实例
    """
    from application.services.chat_persistence_service import get_chat_persistence_service
    return MySQLPersistenceAdapter(get_chat_persistence_service())

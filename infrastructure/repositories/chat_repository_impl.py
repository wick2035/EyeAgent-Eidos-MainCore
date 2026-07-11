"""
对话持久化仓储 MySQL 实现
实现 chat_conversation 和 chat_message 表的 CRUD 操作
"""
import uuid
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from application.repositories.chat_repository import (
    IChatConversationRepository,
    IChatMessageRepository
)
from domain.models.chat_entity import ChatConversationEntity, ChatMessageEntity
from infrastructure.database.mysql_connection import get_db_connection, DatabaseError

logger = logging.getLogger(__name__)


class ChatConversationRepositoryImpl(IChatConversationRepository):
    """
    对话会话仓储 MySQL 实现
    """

    def __init__(self):
        """初始化仓储"""
        self.db = get_db_connection()
        logger.info("[ChatConversationRepository] 初始化完成")

    def create(self, conversation: ChatConversationEntity) -> ChatConversationEntity:
        """创建新会话"""
        try:
            sql = """
                INSERT INTO chat_conversation
                (id, user_type, host_id, title, summary, total_messages, active_node_id,
                 create_time, create_by, update_time, update_by, deleted, version)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                conversation.id,
                conversation.user_type,
                conversation.host_id,
                conversation.title,
                conversation.summary,
                conversation.total_messages,
                conversation.active_node_id,
                conversation.create_time,
                conversation.create_by,
                conversation.update_time,
                conversation.update_by,
                1 if conversation.deleted else 0,
                conversation.version
            )
            self.db.execute(sql, params)
            logger.info(f"[ChatConversationRepository] 创建会话成功: {conversation.id}")
            return conversation
        except DatabaseError as e:
            logger.error(f"[ChatConversationRepository] 创建会话失败: {e}")
            raise

    def get_by_id(self, conversation_id: str) -> Optional[ChatConversationEntity]:
        """根据ID获取会话"""
        try:
            sql = """
                SELECT id, user_type, host_id, title, summary, total_messages, active_node_id,
                       create_time, create_by, update_time, update_by, deleted, version
                FROM chat_conversation
                WHERE id = %s AND deleted = 0
            """
            result = self.db.fetch_one(sql, (conversation_id,))
            if not result:
                return None
            return self._row_to_entity(result)
        except DatabaseError as e:
            logger.error(f"[ChatConversationRepository] 获取会话失败: {e}")
            return None

    def lock_by_id(self, conversation_id: str) -> Optional[ChatConversationEntity]:
        """在当前事务中读取并锁定会话行。"""
        sql = """
            SELECT id, user_type, host_id, title, summary, total_messages, active_node_id,
                   create_time, create_by, update_time, update_by, deleted, version
            FROM chat_conversation
            WHERE id = %s AND deleted = 0
            FOR UPDATE
        """
        result = self.db.fetch_one(sql, (conversation_id,))
        return self._row_to_entity(result) if result else None

    def list_by_host(
        self,
        host_id: str,
        user_type: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[ChatConversationEntity]:
        """获取用户的会话列表"""
        try:
            sql = """
                SELECT id, user_type, host_id, title, summary, total_messages, active_node_id,
                       create_time, create_by, update_time, update_by, deleted, version
                FROM chat_conversation
                WHERE host_id = %s AND user_type = %s AND deleted = 0
                ORDER BY update_time DESC
                LIMIT %s OFFSET %s
            """
            results = self.db.fetch_all(sql, (host_id, user_type, limit, offset))
            return [self._row_to_entity(row) for row in results]
        except DatabaseError as e:
            logger.error(f"[ChatConversationRepository] 获取会话列表失败: {e}")
            return []

    def count_by_host(self, host_id: str, user_type: str) -> int:
        """获取用户的会话总数"""
        try:
            sql = """
                SELECT COUNT(*) as count
                FROM chat_conversation
                WHERE host_id = %s AND user_type = %s AND deleted = 0
            """
            return self.db.fetch_count(sql, (host_id, user_type))
        except DatabaseError as e:
            logger.error(f"[ChatConversationRepository] 获取会话数量失败: {e}")
            return 0

    def update_title(self, conversation_id: str, title: str) -> bool:
        """更新会话标题"""
        try:
            sql = """
                UPDATE chat_conversation
                SET title = %s, update_time = %s, version = version + 1
                WHERE id = %s AND deleted = 0
            """
            affected = self.db.execute(sql, (title, datetime.now(), conversation_id))
            return affected > 0
        except DatabaseError as e:
            logger.error(f"[ChatConversationRepository] 更新标题失败: {e}")
            return False

    def update_summary_and_count(
        self,
        conversation_id: str,
        summary: Optional[str],
        total_messages: int
    ) -> bool:
        """更新会话摘要和消息数量"""
        try:
            sql = """
                UPDATE chat_conversation
                SET summary = %s, total_messages = %s, update_time = %s, version = version + 1
                WHERE id = %s AND deleted = 0
            """
            affected = self.db.execute(
                sql,
                (summary, total_messages, datetime.now(), conversation_id)
            )
            return affected > 0
        except DatabaseError as e:
            logger.error(f"[ChatConversationRepository] 更新摘要失败: {e}")
            return False

    def update_active_node(self, conversation_id: str, active_node_id: str) -> bool:
        """更新会话当前活跃叶子节点"""
        try:
            sql = """
                UPDATE chat_conversation
                SET active_node_id = %s, update_time = %s, version = version + 1
                WHERE id = %s AND deleted = 0
            """
            affected = self.db.execute(sql, (active_node_id, datetime.now(), conversation_id))
            return affected > 0
        except DatabaseError as e:
            logger.error(f"[ChatConversationRepository] 更新 active_node_id 失败: {e}")
            return False

    def compare_and_set_active_node(
        self,
        conversation_id: str,
        expected_node_id: str,
        active_node_id: Optional[str],
    ) -> bool:
        """只恢复仍指向旧附件占位的活跃节点，避免旧 abort 覆盖新分支。"""
        sql = """
            UPDATE chat_conversation
            SET active_node_id = %s, update_time = %s, version = version + 1
            WHERE id = %s AND active_node_id = %s AND deleted = 0
        """
        affected = self.db.execute(
            sql,
            (active_node_id, datetime.now(), conversation_id, expected_node_id),
        )
        return affected > 0

    def soft_delete(self, conversation_id: str) -> bool:
        """软删除会话"""
        try:
            sql = """
                UPDATE chat_conversation
                SET deleted = 1, update_time = %s, version = version + 1
                WHERE id = %s AND deleted = 0
            """
            affected = self.db.execute(sql, (datetime.now(), conversation_id))
            if affected > 0:
                logger.info(f"[ChatConversationRepository] 软删除会话: {conversation_id}")
            return affected > 0
        except DatabaseError as e:
            logger.error(f"[ChatConversationRepository] 删除会话失败: {e}")
            return False

    def _row_to_entity(self, row: dict) -> ChatConversationEntity:
        """将数据库行转换为实体"""
        return ChatConversationEntity(
            id=row["id"],
            user_type=row["user_type"] or "patient",
            host_id=row["host_id"] or "",
            title=row["title"] or "Untitled",
            summary=row.get("summary"),
            total_messages=row.get("total_messages") or 0,
            active_node_id=row.get("active_node_id"),
            create_time=row.get("create_time") or datetime.now(),
            create_by=row.get("create_by"),
            update_time=row.get("update_time") or datetime.now(),
            update_by=row.get("update_by"),
            deleted=bool(row.get("deleted")),
            version=row.get("version") or 1
        )


class ChatMessageRepositoryImpl(IChatMessageRepository):
    """
    对话消息仓储 MySQL 实现
    """

    def __init__(self):
        """初始化仓储"""
        self.db = get_db_connection()
        logger.info("[ChatMessageRepository] 初始化完成")

    def create(self, message: ChatMessageEntity) -> ChatMessageEntity:
        """创建新消息"""
        try:
            sql = """
                INSERT INTO chat_message
                (id, chat_id, parent_id, siblings_group_id, message_order, message_content, message_type,
                 sender_id, context, token_used, status, error_message,
                 create_time, create_by, update_time, update_by, deleted, version)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                message.id,
                message.chat_id,
                message.parent_id,
                message.siblings_group_id,
                message.message_order,
                message.message_content,
                message.message_type,
                message.sender_id,
                message.context,
                message.token_used,
                message.status,
                message.error_message,
                message.create_time,
                message.create_by,
                message.update_time,
                message.update_by,
                1 if message.deleted else 0,
                message.version
            )
            self.db.execute(sql, params)
            logger.debug(f"[ChatMessageRepository] 创建消息成功: {message.id}, status={message.status}")
            return message
        except DatabaseError as e:
            logger.error(f"[ChatMessageRepository] 创建消息失败: {e}")
            raise

    def get_by_id(self, message_id: str) -> Optional[ChatMessageEntity]:
        """根据ID获取消息"""
        try:
            sql = """
                SELECT id, chat_id, parent_id, siblings_group_id, message_order, message_content, message_type,
                       sender_id, context, token_used, status, error_message,
                       create_time, create_by, update_time, update_by, deleted, version
                FROM chat_message
                WHERE id = %s AND deleted = 0
            """
            result = self.db.fetch_one(sql, (message_id,))
            if not result:
                return None
            return self._row_to_entity(result)
        except DatabaseError as e:
            logger.error(f"[ChatMessageRepository] 获取消息失败: {e}")
            return None

    def get_by_ids(self, chat_id: str, ids: List[str]) -> List[ChatMessageEntity]:
        """按ID列表获取同一会话内的消息"""
        if not ids:
            return []

        try:
            placeholders = ", ".join(["%s"] * len(ids))
            sql = f"""
                SELECT id, chat_id, parent_id, siblings_group_id, message_order, message_content,
                       message_type, sender_id, context, token_used, status, error_message,
                       create_time, create_by, update_time, update_by, deleted, version
                FROM chat_message
                WHERE chat_id = %s AND id IN ({placeholders}) AND deleted = 0
            """
            rows = self.db.fetch_all(sql, tuple([chat_id, *ids]))
            by_id = {row["id"]: self._row_to_entity(row) for row in rows}
            return [by_id[message_id] for message_id in ids if message_id in by_id]
        except DatabaseError as e:
            logger.error(f"[ChatMessageRepository] 批量获取消息失败: {e}")
            return []

    def update(self, message_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新消息字段

        Args:
            message_id: 消息ID
            updates: 要更新的字段字典

        Returns:
            bool: 是否更新成功
        """
        if not updates:
            return False

        try:
            # 动态构建 SET 子句
            set_clauses = []
            params = []

            for field, value in updates.items():
                set_clauses.append(f"{field} = %s")
                params.append(value)

            # 添加 update_time 和 version
            set_clauses.append("update_time = %s")
            params.append(datetime.now())
            set_clauses.append("version = version + 1")

            # 添加 WHERE 条件参数
            params.append(message_id)

            sql = f"""
                UPDATE chat_message
                SET {', '.join(set_clauses)}
                WHERE id = %s AND deleted = 0
            """

            affected = self.db.execute(sql, tuple(params))
            if affected > 0:
                logger.debug(f"[ChatMessageRepository] 更新消息成功: {message_id}")
            return affected > 0

        except DatabaseError as e:
            logger.error(f"[ChatMessageRepository] 更新消息失败: {e}")
            return False

    def get_by_chat_id(
        self,
        chat_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[ChatMessageEntity]:
        """获取会话的所有消息"""
        try:
            sql = """
                SELECT id, chat_id, parent_id, siblings_group_id, message_order, message_content, message_type,
                       sender_id, context, token_used, status, error_message,
                       create_time, create_by, update_time, update_by, deleted, version
                FROM chat_message
                WHERE chat_id = %s AND deleted = 0
                ORDER BY message_order ASC
                LIMIT %s OFFSET %s
            """
            results = self.db.fetch_all(sql, (chat_id, limit, offset))
            return [self._row_to_entity(row) for row in results]
        except DatabaseError as e:
            logger.error(f"[ChatMessageRepository] 获取消息列表失败: {e}")
            return []

    def get_children(self, chat_id: str, parent_id: str) -> List[ChatMessageEntity]:
        """获取某父节点下的直接子消息"""
        try:
            sql = """
                SELECT id, chat_id, parent_id, siblings_group_id, message_order, message_content,
                       message_type, sender_id, context, token_used, status, error_message,
                       create_time, create_by, update_time, update_by, deleted, version
                FROM chat_message
                WHERE chat_id = %s AND parent_id = %s AND deleted = 0
                ORDER BY message_order ASC, create_time ASC
            """
            rows = self.db.fetch_all(sql, (chat_id, parent_id))
            return [self._row_to_entity(row) for row in rows]
        except DatabaseError as e:
            logger.error(f"[ChatMessageRepository] 获取子消息失败: {e}")
            return []

    def get_active_assistant_for_conversation(
        self,
        conversation_id: str,
    ) -> Optional[ChatMessageEntity]:
        """查询仍在生成的最新助手消息；会话锁由上层统一持有。"""
        sql = """
            SELECT id, chat_id, parent_id, siblings_group_id, message_order, message_content,
                   message_type, sender_id, context, token_used, status, error_message,
                   create_time, create_by, update_time, update_by, deleted, version
            FROM chat_message
            WHERE chat_id = %s
              AND message_type = 'assistant'
              AND status IN ('running', 'streaming')
              AND deleted = 0
            ORDER BY message_order DESC, create_time DESC
            LIMIT 1
        """
        row = self.db.fetch_one(sql, (conversation_id,))
        return self._row_to_entity(row) if row else None

    def get_latest_sibling_order(self, chat_id: str, parent_id: str, message_type: str) -> int:
        """获取同父同角色消息的最大 message_order"""
        try:
            sql = """
                SELECT MAX(message_order) as max_order
                FROM chat_message
                WHERE chat_id = %s AND parent_id = %s AND message_type = %s AND deleted = 0
            """
            row = self.db.fetch_one(sql, (chat_id, parent_id, message_type))
            return int(row["max_order"]) if row and row.get("max_order") is not None else 0
        except DatabaseError as e:
            logger.error(f"[ChatMessageRepository] 获取兄弟消息最大序号失败: {e}")
            return 0

    def get_latest_order(self, chat_id: str) -> int:
        """获取会话中最新的消息序号"""
        try:
            sql = """
                SELECT MAX(message_order) as max_order
                FROM chat_message
                WHERE chat_id = %s AND deleted = 0
            """
            result = self.db.fetch_one(sql, (chat_id,))
            if result and result.get("max_order") is not None:
                return result["max_order"]
            return 0
        except DatabaseError as e:
            logger.error(f"[ChatMessageRepository] 获取最新序号失败: {e}")
            return 0

    def count_by_chat_id(self, chat_id: str) -> int:
        """获取会话的消息总数"""
        try:
            sql = """
                SELECT COUNT(*) as count
                FROM chat_message
                WHERE chat_id = %s AND deleted = 0
            """
            return self.db.fetch_count(sql, (chat_id,))
        except DatabaseError as e:
            logger.error(f"[ChatMessageRepository] 获取消息数量失败: {e}")
            return 0

    def batch_create(self, messages: List[ChatMessageEntity]) -> List[ChatMessageEntity]:
        """批量创建消息"""
        if not messages:
            return []
        try:
            sql = """
                INSERT INTO chat_message
                (id, chat_id, parent_id, siblings_group_id, message_order, message_content, message_type,
                 sender_id, context, token_used, create_time, create_by,
                 update_time, update_by, deleted, version)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params_list = [
                (
                    msg.id,
                    msg.chat_id,
                    msg.parent_id,
                    msg.siblings_group_id,
                    msg.message_order,
                    msg.message_content,
                    msg.message_type,
                    msg.sender_id,
                    msg.context,
                    msg.token_used,
                    msg.create_time,
                    msg.create_by,
                    msg.update_time,
                    msg.update_by,
                    1 if msg.deleted else 0,
                    msg.version
                )
                for msg in messages
            ]
            self.db.execute_many(sql, params_list)
            logger.info(f"[ChatMessageRepository] 批量创建消息成功: {len(messages)}条")
            return messages
        except DatabaseError as e:
            logger.error(f"[ChatMessageRepository] 批量创建消息失败: {e}")
            raise

    def soft_delete_by_chat_id(self, chat_id: str) -> int:
        """软删除会话的所有消息"""
        try:
            sql = """
                UPDATE chat_message
                SET deleted = 1, update_time = %s, version = version + 1
                WHERE chat_id = %s AND deleted = 0
            """
            affected = self.db.execute(sql, (datetime.now(), chat_id))
            if affected > 0:
                logger.info(f"[ChatMessageRepository] 软删除消息: {affected}条")
            return affected
        except DatabaseError as e:
            logger.error(f"[ChatMessageRepository] 删除消息失败: {e}")
            return 0

    def _row_to_entity(self, row: dict) -> ChatMessageEntity:
        """将数据库行转换为实体"""
        return ChatMessageEntity(
            id=row["id"],
            chat_id=row["chat_id"],
            parent_id=row.get("parent_id"),
            siblings_group_id=row.get("siblings_group_id"),
            message_order=row["message_order"] or 0,
            message_content=row["message_content"] or "",
            message_type=row["message_type"] or "user",
            sender_id=row.get("sender_id"),
            context=row.get("context"),
            token_used=row.get("token_used"),
            status=row.get("status") or "success",
            error_message=row.get("error_message"),
            create_time=row.get("create_time") or datetime.now(),
            create_by=row.get("create_by"),
            update_time=row.get("update_time") or datetime.now(),
            update_by=row.get("update_by"),
            deleted=bool(row.get("deleted")),
            version=row.get("version") or 1
        )


# 单例实例
_conversation_repo: Optional[ChatConversationRepositoryImpl] = None
_message_repo: Optional[ChatMessageRepositoryImpl] = None


def get_conversation_repository() -> ChatConversationRepositoryImpl:
    """获取会话仓储单例"""
    global _conversation_repo
    if _conversation_repo is None:
        _conversation_repo = ChatConversationRepositoryImpl()
    return _conversation_repo


def get_message_repository() -> ChatMessageRepositoryImpl:
    """获取消息仓储单例"""
    global _message_repo
    if _message_repo is None:
        _message_repo = ChatMessageRepositoryImpl()
    return _message_repo

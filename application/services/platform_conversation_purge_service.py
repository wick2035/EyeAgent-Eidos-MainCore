"""MainCore 侧的平台会话彻底清理协调器。"""

from dataclasses import dataclass

from infrastructure.database.mysql_connection import get_db_connection


class PlatformConversationPurgeNotFoundError(LookupError):
    code = "PLATFORM_CONVERSATION_NOT_FOUND"


class PlatformConversationPurgeForbiddenError(PermissionError):
    code = "PLATFORM_CONVERSATION_FORBIDDEN"


class PlatformConversationPurgeBusyError(RuntimeError):
    code = "PLATFORM_CONVERSATION_BUSY"


@dataclass(frozen=True, slots=True)
class PlatformConversationPurgeResult:
    conversation_id: str
    already_deleted: bool


class PlatformConversationPurgeService:
    """在一个 MySQL 事务中清理会话数据及其全部 LangGraph 线程。"""

    def __init__(self, db=None) -> None:
        self.db = db or get_db_connection()

    def purge(
        self,
        conversation_id: str,
        doctor_id: str,
    ) -> PlatformConversationPurgeResult:
        with self.db.transaction():
            conversation = self.db.fetch_one(
                """
                    SELECT id, user_type, host_id, deleted
                    FROM chat_conversation
                    WHERE id = %s
                    FOR UPDATE
                """,
                (conversation_id,),
            )
            if conversation is None:
                raise PlatformConversationPurgeNotFoundError()
            if (
                conversation.get("user_type") != "doctor"
                or conversation.get("host_id") != doctor_id
            ):
                raise PlatformConversationPurgeForbiddenError()

            canonical_id = str(conversation["id"])
            active_turn = self.db.fetch_one(
                """
                    SELECT request_id
                    FROM chat_turn_request
                    WHERE conversation_id = %s
                      AND status IN ('prepared', 'streaming')
                    ORDER BY create_time ASC, request_id ASC
                    LIMIT 1
                    FOR UPDATE
                """,
                (canonical_id,),
            )
            if active_turn is not None:
                raise PlatformConversationPurgeBusyError()

            active_legacy_assistant = self.db.fetch_one(
                """
                    SELECT id
                    FROM chat_message
                    WHERE chat_id = %s
                      AND message_type = 'assistant'
                      AND status IN ('running', 'streaming')
                    ORDER BY message_order DESC, create_time DESC
                    LIMIT 1
                    FOR UPDATE
                """,
                (canonical_id,),
            )
            if active_legacy_assistant is not None:
                raise PlatformConversationPurgeBusyError()

            already_deleted = bool(conversation.get("deleted"))
            self.db.execute(
                """
                    UPDATE chat_message
                    SET deleted = 1,
                        update_time = CURRENT_TIMESTAMP(6),
                        version = version + 1
                    WHERE chat_id = %s
                      AND deleted = 0
                """,
                (canonical_id,),
            )
            self.db.execute(
                """
                    UPDATE chat_conversation
                    SET deleted = 1,
                        update_time = CURRENT_TIMESTAMP(6),
                        version = version + 1
                    WHERE id = %s
                      AND deleted = 0
                """,
                (canonical_id,),
            )
            self.db.execute(
                """
                    DELETE FROM chat_turn_request
                    WHERE conversation_id = %s
                """,
                (canonical_id,),
            )

            base_thread_id = f"conv_{canonical_id}"
            branch_prefix = f"{base_thread_id}_branch_"
            thread_params = (
                base_thread_id,
                branch_prefix,
                branch_prefix,
            )
            thread_predicate = """
                (
                    thread_id = %s
                    OR LEFT(thread_id, CHAR_LENGTH(%s)) = %s
                )
            """

            self.db.execute(
                f"""
                    UPDATE langgraph_checkpoint_writes
                    SET is_deleted = 1,
                        deleted_at = CURRENT_TIMESTAMP,
                        version = version + 1
                    WHERE {thread_predicate}
                      AND is_deleted = 0
                """,
                thread_params,
            )
            self.db.execute(
                f"""
                    UPDATE langgraph_checkpoint
                    SET is_deleted = 1,
                        deleted_at = CURRENT_TIMESTAMP,
                        version = version + 1
                    WHERE {thread_predicate}
                      AND is_deleted = 0
                """,
                thread_params,
            )
            self.db.execute(
                f"""
                    UPDATE langgraph_thread_agent_history
                    SET is_deleted = 1,
                        deleted_at = CURRENT_TIMESTAMP,
                        ended_at = COALESCE(ended_at, CURRENT_TIMESTAMP),
                        version = version + 1
                    WHERE {thread_predicate}
                      AND is_deleted = 0
                """,
                thread_params,
            )
            self.db.execute(
                f"""
                    UPDATE langgraph_thread_mapping
                    SET is_deleted = 1,
                        deleted_at = CURRENT_TIMESTAMP,
                        status = 'deleted',
                        version = version + 1
                    WHERE {thread_predicate}
                      AND is_deleted = 0
                """,
                thread_params,
            )

            return PlatformConversationPurgeResult(
                conversation_id=canonical_id,
                already_deleted=already_deleted,
            )


def get_platform_conversation_purge_service() -> PlatformConversationPurgeService:
    return PlatformConversationPurgeService()

import json
from datetime import datetime, timedelta
from typing import Optional, Sequence

from application.repositories.chat_turn_request_repository import (
    ChatTurnRequestRepository,
)
from domain.models.chat_turn_request import ChatTurnRequestEntity
from infrastructure.database.mysql_connection import get_db_connection


class DuplicateChatTurnRequestError(RuntimeError):
    """幂等主键或 assistant_message_id 唯一约束冲突。"""

    def __init__(self, doctor_id: str, request_id: str):
        super().__init__(f"重复附件回合: {doctor_id}/{request_id}")
        self.doctor_id = doctor_id
        self.request_id = request_id


class ChatTurnRequestRepositoryImpl(ChatTurnRequestRepository):
    _SELECT_COLUMNS = """
        doctor_id, request_id, request_fingerprint, operation,
        protocol_version, agent_type, attachment_scope, research_options_json,
        ingestion_ids_json,
        conversation_id, session_id, patient_id, source_message_id,
        implicit_prompt_id, attachment_ids_json, user_message_id,
        assistant_message_id, previous_active_node_id, status, error_code,
        execute_started_at, deadline_at, create_time, update_time
    """

    def __init__(self, db=None):
        self.db = db or get_db_connection()

    def get(
        self,
        doctor_id: str,
        request_id: str,
    ) -> Optional[ChatTurnRequestEntity]:
        row = self.db.fetch_one(
            f"""
                SELECT {self._SELECT_COLUMNS}
                FROM chat_turn_request
                WHERE doctor_id = %s AND request_id = %s
            """,
            (doctor_id, request_id),
        )
        return self._row_to_entity(row) if row else None

    def get_for_update(
        self,
        doctor_id: str,
        request_id: str,
    ) -> Optional[ChatTurnRequestEntity]:
        row = self.db.fetch_one(
            f"""
                SELECT {self._SELECT_COLUMNS}
                FROM chat_turn_request
                WHERE doctor_id = %s AND request_id = %s
                FOR UPDATE
            """,
            (doctor_id, request_id),
        )
        return self._row_to_entity(row) if row else None

    def insert(self, entity: ChatTurnRequestEntity) -> ChatTurnRequestEntity:
        sql = """
            INSERT INTO chat_turn_request (
                doctor_id, request_id, request_fingerprint, operation,
                protocol_version, agent_type, attachment_scope,
                research_options_json, ingestion_ids_json,
                conversation_id, session_id, patient_id, source_message_id,
                implicit_prompt_id, attachment_ids_json, user_message_id,
                assistant_message_id, previous_active_node_id, status, error_code,
                execute_started_at, deadline_at, create_time, update_time
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
        """
        params = (
            entity.doctor_id,
            entity.request_id,
            entity.request_fingerprint,
            entity.operation,
            entity.protocol_version,
            entity.agent_type,
            entity.attachment_scope,
            entity.research_options_json,
            entity.ingestion_ids_json,
            entity.conversation_id,
            entity.session_id,
            entity.patient_id,
            entity.source_message_id,
            entity.implicit_prompt_id,
            entity.attachment_ids_json,
            entity.user_message_id,
            entity.assistant_message_id,
            entity.previous_active_node_id,
            entity.status,
            entity.error_code,
            entity.execute_started_at,
            entity.deadline_at,
            entity.create_time,
            entity.update_time,
        )
        try:
            self.db.execute(sql, params)
        except Exception as error:
            if self._is_duplicate_error(error):
                raise DuplicateChatTurnRequestError(
                    entity.doctor_id,
                    entity.request_id,
                ) from error
            raise
        return entity

    def compare_and_set_status(
        self,
        doctor_id: str,
        request_id: str,
        expected_status: str | Sequence[str],
        new_status: str,
        error_code: Optional[str] = None,
        execute_started_at: Optional[datetime] = None,
        deadline_at: Optional[datetime] = None,
    ) -> bool:
        expected = (
            [expected_status]
            if isinstance(expected_status, str)
            else list(expected_status)
        )
        if not expected:
            raise ValueError("expected_status 不能为空")

        set_clauses = ["status = %s", "error_code = %s"]
        params = [new_status, error_code]
        if execute_started_at is not None:
            set_clauses.append("execute_started_at = %s")
            params.append(execute_started_at)
        if deadline_at is not None:
            set_clauses.append("deadline_at = %s")
            params.append(deadline_at)
        set_clauses.append("update_time = %s")
        params.append(datetime.now())

        placeholders = ", ".join(["%s"] * len(expected))
        params.extend([doctor_id, request_id, *expected])
        affected = self.db.execute(
            f"""
                UPDATE chat_turn_request
                SET {', '.join(set_clauses)}
                WHERE doctor_id = %s
                  AND request_id = %s
                  AND status IN ({placeholders})
            """,
            tuple(params),
        )
        return affected > 0

    def get_active_for_conversation(
        self,
        conversation_id: str,
        ignore_request_id: Optional[str] = None,
    ) -> Optional[ChatTurnRequestEntity]:
        ignore_clause = ""
        params = [conversation_id]
        if ignore_request_id is not None:
            ignore_clause = "AND request_id <> %s"
            params.append(ignore_request_id)
        row = self.db.fetch_one(
            f"""
                SELECT {self._SELECT_COLUMNS}
                FROM chat_turn_request
                WHERE conversation_id = %s
                  AND status IN ('prepared', 'streaming')
                  {ignore_clause}
                ORDER BY create_time DESC
                LIMIT 1
                FOR UPDATE
            """,
            tuple(params),
        )
        return self._row_to_entity(row) if row else None

    def list_stale(
        self,
        now: Optional[datetime] = None,
    ) -> list[ChatTurnRequestEntity]:
        now = now or datetime.now()
        prepared_before = now - timedelta(minutes=10)
        rows = self.db.fetch_all(
            f"""
                SELECT {self._SELECT_COLUMNS}
                FROM chat_turn_request
                WHERE (
                    status = 'prepared'
                    AND create_time <= %s
                ) OR (
                    status = 'streaming'
                    AND deadline_at IS NOT NULL
                    AND deadline_at <= %s
                )
                ORDER BY CASE
                    WHEN status = 'prepared' THEN create_time
                    ELSE deadline_at
                END ASC
            """,
            (prepared_before, now),
        )
        return [self._row_to_entity(row) for row in rows]

    @staticmethod
    def _is_duplicate_error(error: Exception) -> bool:
        current = error
        while current is not None:
            args = getattr(current, "args", ())
            if args and args[0] == 1062:
                return True
            if "1062" in str(current) or "duplicate entry" in str(current).lower():
                return True
            current = current.__cause__ or current.__context__
        return False

    @staticmethod
    def _row_to_entity(row: dict) -> ChatTurnRequestEntity:
        attachment_ids_json = row["attachment_ids_json"]
        if not isinstance(attachment_ids_json, str):
            attachment_ids_json = json.dumps(
                attachment_ids_json,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        return ChatTurnRequestEntity(
            doctor_id=row["doctor_id"],
            request_id=row["request_id"],
            request_fingerprint=row["request_fingerprint"],
            protocol_version=row.get("protocol_version", 1),
            agent_type=row.get("agent_type", "health"),
            attachment_scope=row.get("attachment_scope", "patient"),
            research_options_json=row.get("research_options_json"),
            ingestion_ids_json=(
                row.get("ingestion_ids_json")
                if isinstance(row.get("ingestion_ids_json"), str)
                or row.get("ingestion_ids_json") is None
                else json.dumps(
                    row["ingestion_ids_json"],
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            ),
            operation=row["operation"],
            conversation_id=row["conversation_id"],
            session_id=row["session_id"],
            patient_id=row["patient_id"],
            source_message_id=row.get("source_message_id"),
            implicit_prompt_id=row.get("implicit_prompt_id"),
            attachment_ids_json=attachment_ids_json,
            user_message_id=row["user_message_id"],
            assistant_message_id=row["assistant_message_id"],
            previous_active_node_id=row.get("previous_active_node_id"),
            status=row["status"],
            error_code=row.get("error_code"),
            execute_started_at=row.get("execute_started_at"),
            deadline_at=row.get("deadline_at"),
            create_time=row.get("create_time") or datetime.now(),
            update_time=row.get("update_time") or datetime.now(),
        )


_turn_repository: Optional[ChatTurnRequestRepositoryImpl] = None


def get_chat_turn_request_repository() -> ChatTurnRequestRepositoryImpl:
    global _turn_repository
    if _turn_repository is None:
        _turn_repository = ChatTurnRequestRepositoryImpl()
    return _turn_repository

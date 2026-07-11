import re
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import pymysql

from domain.models.research_document import (
    IngestionIdentity,
    ResearchDocumentSegmentEntity,
)
from infrastructure.repositories.chat_turn_request_repository_impl import (
    ChatTurnRequestRepositoryImpl,
)
from infrastructure.repositories.research_document_repository_impl import (
    ResearchDocumentRepositoryImpl,
)


class ScriptedDB:
    def __init__(
        self,
        *,
        fetch_one_results=None,
        fetch_all_results=None,
        execute_results=None,
        execute_many_results=None,
    ):
        self.fetch_one_results = list(fetch_one_results or [])
        self.fetch_all_results = list(fetch_all_results or [])
        self.execute_results = list(execute_results or [])
        self.execute_many_results = list(execute_many_results or [])
        self.operations = []
        self.transaction_depth = 0
        self.transaction_events = []

    @contextmanager
    def transaction(self):
        self.transaction_events.append("begin")
        self.transaction_depth += 1
        try:
            yield
        except Exception:
            self.transaction_events.append("rollback")
            raise
        else:
            self.transaction_events.append("commit")
        finally:
            self.transaction_depth -= 1

    def fetch_one(self, sql, params=None):
        self.operations.append(("fetch_one", sql, params, self.transaction_depth))
        return self._next(self.fetch_one_results, None)

    def fetch_all(self, sql, params=None):
        self.operations.append(("fetch_all", sql, params, self.transaction_depth))
        return self._next(self.fetch_all_results, [])

    def execute(self, sql, params=None):
        self.operations.append(("execute", sql, params, self.transaction_depth))
        return self._next(self.execute_results, 1)

    def execute_many(self, sql, params_list):
        self.operations.append(
            ("execute_many", sql, list(params_list), self.transaction_depth)
        )
        return self._next(self.execute_many_results, len(params_list))

    @staticmethod
    def _next(values, default):
        value = values.pop(0) if values else default
        if isinstance(value, BaseException):
            raise value
        return value


def _identity() -> IngestionIdentity:
    return IngestionIdentity(
        doctor_id="doctor-1",
        attachment_id="attachment-1",
        document_version=3,
        content_sha256="a" * 64,
        processor_type="pdf_hybrid_v1",
        extractor_version="pymupdf_v1",
        segment_schema_version="segment_v1",
    )


def _ingestion_row(
    *,
    status="processing",
    attempt_count=1,
    lease_expires_at=None,
):
    now = datetime(2026, 7, 11, 9, 0, 0)
    return {
        "id": "11111111-1111-5111-8111-111111111111",
        "doctor_id": "doctor-1",
        "attachment_id": "attachment-1",
        "document_version": 3,
        "content_sha256": "a" * 64,
        "processor_type": "pdf_hybrid_v1",
        "extractor_version": "pymupdf_v1",
        "segment_schema_version": "segment_v1",
        "status": status,
        "attempt_count": attempt_count,
        "lease_expires_at": lease_expires_at,
        "page_count": 2,
        "error_code": None,
        "started_at": now,
        "completed_at": now if status == "ready" else None,
        "create_time": now,
        "update_time": now,
    }


def _segment(ordinal=0, content="第一段科研材料"):
    return ResearchDocumentSegmentEntity(
        ingestion_id="11111111-1111-5111-8111-111111111111",
        ordinal=ordinal,
        content=content,
        page_start=ordinal + 1,
        page_end=ordinal + 1,
        token_count=8,
        metadata={"extraction_mode": "text"},
    )


def _segment_row(metadata_json='{"extraction_mode":"text"}'):
    segment = _segment()
    return {
        "id": segment.id,
        "ingestion_id": segment.ingestion_id,
        "ordinal": segment.ordinal,
        "content": segment.content,
        "content_sha256": segment.content_sha256,
        "page_start": segment.page_start,
        "page_end": segment.page_end,
        "sheet_name": None,
        "row_start": None,
        "row_end": None,
        "token_count": segment.token_count,
        "metadata_json": metadata_json,
    }


class ResearchDocumentSchemaTest(unittest.TestCase):
    def test_identity_rejects_post_parse_extraction_mode_as_processor_type(self):
        with self.assertRaisesRegex(ValueError, "processor_type"):
            IngestionIdentity(
                doctor_id="doctor-1",
                attachment_id="attachment-1",
                document_version=3,
                content_sha256="a" * 64,
                processor_type="pdf_mixed",
                extractor_version="pymupdf_v1",
                segment_schema_version="segment_v1",
            )

    def test_schema_uses_full_seven_part_identity_and_cascade(self):
        sql = (
            Path(__file__).parents[1]
            / "scripts"
            / "create_research_document_tables.sql"
        ).read_text(encoding="utf-8")
        normalized = re.sub(r"\s+", " ", sql.lower())

        self.assertRegex(
            normalized,
            re.compile(
                r"unique(?: key)? [^(]*\(\s*doctor_id\s*,\s*attachment_id\s*,"
                r"\s*document_version\s*,\s*content_sha256\s*,\s*processor_type\s*,"
                r"\s*extractor_version\s*,\s*segment_schema_version\s*\)"
            ),
        )
        self.assertIn("foreign key (ingestion_id)", normalized)
        self.assertIn("on delete cascade", normalized)
        self.assertIn("unique", normalized)
        self.assertIn("(ingestion_id, ordinal)", normalized)

    def test_chat_turn_schema_and_replayable_upgrade_include_ingestion_ids(self):
        scripts = Path(__file__).parents[1] / "scripts"
        create_sql = (scripts / "create_chat_turn_request_table.sql").read_text(
            encoding="utf-8"
        )
        upgrade_sql = (scripts / "upgrade_chat_turn_request_v2_research.sql").read_text(
            encoding="utf-8"
        )

        self.assertRegex(
            create_sql.lower(),
            r"ingestion_ids_json\s+json\s+null",
        )
        self.assertRegex(
            upgrade_sql.lower(),
            r"information_schema\.columns",
        )
        self.assertRegex(
            upgrade_sql.lower(),
            r"ingestion_ids_json",
        )


class ResearchDocumentRepositoryTest(unittest.TestCase):
    def test_duplicate_insert_claim_returns_existing_active_owner(self):
        lease_until = datetime(2026, 7, 11, 9, 5, 0)
        existing = _ingestion_row(lease_expires_at=lease_until)
        db = ScriptedDB(
            fetch_one_results=[existing],
            execute_results=[pymysql.err.IntegrityError(1062, "duplicate entry")],
        )
        repository = ResearchDocumentRepositoryImpl(db=db)

        claimed = repository.claim(
            _identity(),
            now=datetime(2026, 7, 11, 9, 1, 0),
            lease_until=datetime(2026, 7, 11, 9, 6, 0),
        )

        self.assertEqual(claimed.id, existing["id"])
        self.assertEqual(claimed.attempt_count, 1)
        self.assertEqual(claimed.lease_expires_at, lease_until)
        self.assertEqual(db.transaction_events, ["begin", "commit"])
        self.assertEqual(db.operations[0][0], "execute")
        insert = next(op for op in db.operations if "INSERT INTO" in op[1])
        self.assertEqual(insert[2][1:8], (
            "doctor-1",
            "attachment-1",
            3,
            "a" * 64,
            "pdf_hybrid_v1",
            "pymupdf_v1",
            "segment_v1",
        ))

    def test_claim_retries_entire_transaction_for_1205_and_1213(self):
        for error_code in (1205, 1213):
            with self.subTest(error_code=error_code):
                db = ScriptedDB(
                    execute_results=[
                        pymysql.err.OperationalError(error_code, "retryable"),
                        1,
                    ]
                )

                claimed = ResearchDocumentRepositoryImpl(db=db).claim(
                    _identity(),
                    now=datetime(2026, 7, 11, 9, 0, 0),
                    lease_until=datetime(2026, 7, 11, 9, 5, 0),
                )

                self.assertEqual(claimed.attempt_count, 1)
                self.assertEqual(
                    db.transaction_events,
                    ["begin", "rollback", "begin", "commit"],
                )

    def test_claim_retry_exhaustion_stops_after_three_transactions(self):
        for error_code in (1205, 1213):
            with self.subTest(error_code=error_code):
                db = ScriptedDB(
                    execute_results=[
                        pymysql.err.OperationalError(error_code, "retryable")
                        for _ in range(3)
                    ]
                )

                with self.assertRaises(pymysql.err.OperationalError) as raised:
                    ResearchDocumentRepositoryImpl(db=db).claim(
                        _identity(),
                        now=datetime(2026, 7, 11, 9, 0, 0),
                        lease_until=datetime(2026, 7, 11, 9, 5, 0),
                    )

                self.assertEqual(raised.exception.args[0], error_code)
                self.assertEqual(
                    db.transaction_events,
                    ["begin", "rollback"] * 3,
                )

    def test_expired_lease_takeover_increments_attempt_fencing_token(self):
        now = datetime(2026, 7, 11, 9, 10, 0)
        db = ScriptedDB(
            fetch_one_results=[
                _ingestion_row(
                    attempt_count=4,
                    lease_expires_at=now - timedelta(microseconds=1),
                )
            ],
            execute_results=[
                pymysql.err.IntegrityError(1062, "duplicate entry"),
                1,
            ],
        )
        repository = ResearchDocumentRepositoryImpl(db=db)

        claimed = repository.claim(
            _identity(),
            now=now,
            lease_until=now + timedelta(minutes=5),
        )

        self.assertEqual(claimed.status, "processing")
        self.assertEqual(claimed.attempt_count, 5)
        update = next(
            op
            for op in db.operations
            if op[1].lstrip().upper().startswith("UPDATE")
        )
        normalized = " ".join(update[1].split()).lower()
        self.assertIn("attempt_count = %s", normalized)
        self.assertIn("status <> 'ready'", normalized)

    def test_old_attempt_cannot_complete_or_renew_new_attempt(self):
        row = _ingestion_row(attempt_count=2)
        complete_db = ScriptedDB(fetch_one_results=[row])
        repository = ResearchDocumentRepositoryImpl(db=complete_db)

        self.assertFalse(repository.complete(row["id"], 1, [_segment()]))
        self.assertFalse(any(op[0] == "execute_many" for op in complete_db.operations))

        renew_db = ScriptedDB(execute_results=[0])
        repository = ResearchDocumentRepositoryImpl(db=renew_db)
        self.assertFalse(
            repository.renew_lease(
                row["id"],
                1,
                datetime(2026, 7, 11, 9, 20, 0),
            )
        )
        renew_sql = " ".join(renew_db.operations[0][1].split()).lower()
        self.assertIn("status = 'processing'", renew_sql)
        self.assertIn("attempt_count = %s", renew_sql)

    def test_renew_lease_only_accepts_future_extension_by_database_time(self):
        lease_until = datetime(2026, 7, 11, 9, 30, 0)
        db = ScriptedDB(execute_results=[0])

        renewed = ResearchDocumentRepositoryImpl(db=db).renew_lease(
            "11111111-1111-5111-8111-111111111111",
            2,
            lease_until,
        )

        self.assertFalse(renewed)
        sql = " ".join(db.operations[0][1].split()).lower()
        self.assertIn("%s > current_timestamp(6)", sql)
        self.assertIn("%s > lease_expires_at", sql)
        self.assertEqual(db.operations[0][2].count(lease_until), 3)

    def test_ready_ingestion_never_returns_to_processing_or_failed(self):
        ready = _ingestion_row(status="ready", attempt_count=3)
        claim_db = ScriptedDB(
            fetch_one_results=[ready],
            execute_results=[pymysql.err.IntegrityError(1062, "duplicate entry")],
        )
        repository = ResearchDocumentRepositoryImpl(db=claim_db)

        claimed = repository.claim(
            _identity(),
            now=datetime(2026, 7, 11, 10, 0, 0),
            lease_until=datetime(2026, 7, 11, 10, 5, 0),
        )

        self.assertEqual(claimed.status, "ready")
        self.assertFalse(
            any(
                op[0] == "execute"
                and op[1].lstrip().upper().startswith("UPDATE")
                for op in claim_db.operations
            )
        )

        fail_db = ScriptedDB(execute_results=[0])
        self.assertFalse(
            ResearchDocumentRepositoryImpl(db=fail_db).fail(
                ready["id"], ready["attempt_count"], "PARSER_FAILED"
            )
        )
        fail_sql = " ".join(fail_db.operations[0][1].split()).lower()
        self.assertIn("status = 'processing'", fail_sql)

    def test_complete_replaces_segments_and_ready_state_in_one_transaction(self):
        processing = _ingestion_row(attempt_count=2)
        db = ScriptedDB(
            fetch_one_results=[processing],
            execute_results=[1, 1],
            execute_many_results=[2],
        )
        repository = ResearchDocumentRepositoryImpl(db=db)
        segments = [_segment(0, "第一段"), _segment(1, "第二段")]

        self.assertTrue(repository.complete(processing["id"], 2, segments))

        writes = [op for op in db.operations if op[0] in {"execute", "execute_many"}]
        self.assertTrue(all(op[3] == 1 for op in writes))
        self.assertIn("delete from research_document_segment", writes[0][1].lower())
        self.assertEqual(writes[1][0], "execute_many")
        self.assertIn("status = 'ready'", writes[2][1].lower())
        self.assertEqual(db.transaction_events, ["begin", "commit"])
        self.assertEqual(segments[0].id, _segment(0, "第一段").id)
        self.assertNotEqual(segments[0].id, segments[1].id)
        lock_sql = " ".join(db.operations[0][1].split()).lower()
        self.assertIn("status = 'processing'", lock_sql)
        self.assertIn("attempt_count = %s", lock_sql)
        self.assertIn("lease_expires_at > current_timestamp(6)", lock_sql)
        final_where = " ".join(writes[2][1].split()).lower().split("where", 1)[1]
        self.assertNotIn("current_timestamp(6)", final_where)

    def test_segment_failure_rolls_back_without_publishing_ready(self):
        processing = _ingestion_row(attempt_count=2)
        db = ScriptedDB(
            fetch_one_results=[processing],
            execute_results=[1],
            execute_many_results=[RuntimeError("segment write failed")],
        )

        with self.assertRaisesRegex(RuntimeError, "segment write failed"):
            ResearchDocumentRepositoryImpl(db=db).complete(
                processing["id"], 2, [_segment()]
            )

        self.assertEqual(db.transaction_events, ["begin", "rollback"])
        self.assertFalse(
            any(
                op[0] == "execute" and "status = 'ready'" in op[1].lower()
                for op in db.operations
            )
        )

    def test_complete_cas_loss_rolls_back_replaced_segments(self):
        processing = _ingestion_row(attempt_count=2)
        db = ScriptedDB(
            fetch_one_results=[processing],
            execute_results=[1, 0],
            execute_many_results=[1],
        )

        with self.assertRaises(RuntimeError):
            ResearchDocumentRepositoryImpl(db=db).complete(
                processing["id"], 2, [_segment()]
            )
        self.assertEqual(db.transaction_events, ["begin", "rollback"])

    def test_complete_revalidates_mutated_segments_before_any_database_write(self):
        for mutation in ("content", "id", "hash", "metadata"):
            with self.subTest(mutation=mutation):
                segment = _segment()
                if mutation == "content":
                    segment.content = "构造后被替换的正文"
                elif mutation == "id":
                    segment.id = "22222222-2222-5222-8222-222222222222"
                elif mutation == "hash":
                    segment.content_sha256 = "b" * 64
                else:
                    segment.metadata["url"] = "https://forbidden.example"
                db = ScriptedDB(fetch_one_results=[_ingestion_row(attempt_count=2)])

                with self.assertRaises(ValueError):
                    ResearchDocumentRepositoryImpl(db=db).complete(
                        segment.ingestion_id,
                        2,
                        [segment],
                    )

                self.assertEqual(db.operations, [])

    def test_segment_metadata_validates_each_whitelisted_value_type(self):
        valid_metadata = {
            "block_index": 0,
            "extraction_method": "digital_text",
            "extraction_mode": "text",
            "heading": "研究结论",
            "ocr_applied": False,
            "ocr_page_count": 0,
            "source_page_numbers": [1, 2],
        }
        self.assertEqual(
            ResearchDocumentSegmentEntity(
                ingestion_id="11111111-1111-5111-8111-111111111111",
                ordinal=0,
                content="正文",
                token_count=2,
                metadata=valid_metadata,
            ).metadata,
            valid_metadata,
        )

        invalid_values = {
            "block_index": "0",
            "extraction_method": 1,
            "extraction_mode": [],
            "heading": 3,
            "ocr_applied": 1,
            "ocr_page_count": True,
            "source_page_numbers": [0],
        }
        for key, value in invalid_values.items():
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    ResearchDocumentSegmentEntity(
                        ingestion_id="11111111-1111-5111-8111-111111111111",
                        ordinal=0,
                        content="正文",
                        token_count=2,
                        metadata={key: value},
                    )

    def test_list_segments_uses_requested_ingestion_ids_and_decodes_metadata(self):
        segment = _segment()
        db = ScriptedDB(fetch_all_results=[[_segment_row()]])

        loaded = ResearchDocumentRepositoryImpl(db=db).list_segments(
            [segment.ingestion_id, "22222222-2222-5222-8222-222222222222"]
        )

        self.assertEqual(loaded, [segment])
        self.assertEqual(
            db.operations[0][2],
            (
                segment.ingestion_id,
                "22222222-2222-5222-8222-222222222222",
            ),
        )

    def test_list_segments_rejects_non_object_metadata_json(self):
        for metadata_json in ("[]", "null", [], None):
            with self.subTest(metadata_json=metadata_json):
                db = ScriptedDB(
                    fetch_all_results=[[_segment_row(metadata_json)]]
                )

                with self.assertRaises(ValueError):
                    ResearchDocumentRepositoryImpl(db=db).list_segments(
                        ["11111111-1111-5111-8111-111111111111"]
                    )

    def test_purge_is_scoped_by_doctor_and_attachment(self):
        db = ScriptedDB(execute_results=[1])

        ResearchDocumentRepositoryImpl(db=db).purge("doctor-1", "attachment-1")

        operation = db.operations[0]
        normalized = " ".join(operation[1].split()).lower()
        self.assertIn("delete from research_document_ingestion", normalized)
        self.assertIn("doctor_id = %s", normalized)
        self.assertIn("attachment_id = %s", normalized)
        self.assertEqual(operation[2], ("doctor-1", "attachment-1"))


class ChatTurnIngestionReferencesTest(unittest.TestCase):
    def test_entity_and_repository_round_trip_ingestion_ids(self):
        row = {
            "doctor_id": "doctor-1",
            "request_id": "request-1",
            "request_fingerprint": "b" * 64,
            "protocol_version": 2,
            "agent_type": "research",
            "attachment_scope": "research",
            "research_options_json": "{}",
            "ingestion_ids_json": '["ingestion-1","ingestion-2"]',
            "operation": "send",
            "conversation_id": "conversation-1",
            "session_id": "session-1",
            "patient_id": None,
            "source_message_id": None,
            "implicit_prompt_id": None,
            "attachment_ids_json": '["attachment-1"]',
            "user_message_id": "user-1",
            "assistant_message_id": "assistant-1",
            "previous_active_node_id": None,
            "status": "prepared",
            "error_code": None,
            "execute_started_at": None,
            "deadline_at": None,
            "create_time": datetime(2026, 7, 11, 9, 0, 0),
            "update_time": datetime(2026, 7, 11, 9, 0, 0),
        }
        entity = ChatTurnRequestRepositoryImpl._row_to_entity(row)

        self.assertEqual(entity.ingestion_ids, ["ingestion-1", "ingestion-2"])

        db = ScriptedDB(execute_results=[1])
        ChatTurnRequestRepositoryImpl(db=db).insert(entity)
        insert = db.operations[0]
        self.assertIn("ingestion_ids_json", insert[1])
        self.assertIn(row["ingestion_ids_json"], insert[2])
        self.assertEqual(insert[1].count("%s"), len(insert[2]))


if __name__ == "__main__":
    unittest.main()

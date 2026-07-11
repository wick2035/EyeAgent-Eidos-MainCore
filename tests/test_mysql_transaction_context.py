import unittest
from datetime import datetime, timedelta

import pymysql

from domain.models.research_document import (
    IngestionIdentity,
    ResearchDocumentSegmentEntity,
)
from infrastructure.database.mysql_connection import MySQLConnectionPool
from infrastructure.repositories.research_document_repository_impl import (
    ResearchDocumentClaimTransactionBoundaryError,
    ResearchDocumentRepositoryImpl,
)


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.closed = False

    def execute(self, sql, params=None):
        self.connection.statements.append((sql, params))
        if sql == "FAIL":
            raise RuntimeError("second write failed")
        if sql == "DEADLOCK":
            raise pymysql.err.OperationalError(1213, "deadlock found")
        return 1

    def executemany(self, sql, params_list):
        params = list(params_list)
        self.connection.statements.append((sql, params))
        if sql == "FAIL_MANY":
            raise RuntimeError("segment batch failed")
        return len(params)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.statements = []
        self.cursor_calls = 0
        self.commit_calls = 0
        self.rollback_calls = 0
        self.close_calls = 0
        self.cursor_instance = None

    def cursor(self):
        self.cursor_calls += 1
        self.cursor_instance = FakeCursor(self)
        return self.cursor_instance

    def commit(self):
        self.commit_calls += 1

    def rollback(self):
        self.rollback_calls += 1

    def close(self):
        self.close_calls += 1


class CompleteCasLossCursor(FakeCursor):
    def execute(self, sql, params=None):
        self.connection.statements.append((sql, params))
        if "set status = 'ready'" in " ".join(sql.split()).lower():
            return 0
        return 1

    def fetchone(self):
        return self.connection.locked_ingestion


class CompleteCasLossConnection(FakeConnection):
    def __init__(self):
        super().__init__()
        now = datetime.now()
        self.locked_ingestion = {
            "id": "11111111-1111-5111-8111-111111111111",
            "doctor_id": "doctor-1",
            "attachment_id": "attachment-1",
            "document_version": 1,
            "content_sha256": "a" * 64,
            "processor_type": "pdf_hybrid_v1",
            "extractor_version": "pymupdf_v1",
            "segment_schema_version": "segment_v1",
            "status": "processing",
            "attempt_count": 2,
            "lease_expires_at": now + timedelta(minutes=5),
            "page_count": None,
            "error_code": None,
            "started_at": now,
            "completed_at": None,
            "create_time": now,
            "update_time": now,
        }

    def cursor(self):
        self.cursor_calls += 1
        self.cursor_instance = CompleteCasLossCursor(self)
        return self.cursor_instance


class ClaimCursor(FakeCursor):
    def execute(self, sql, params=None):
        self.connection.statements.append((sql, params))
        if self.connection.error_code is not None:
            raise pymysql.err.OperationalError(
                self.connection.error_code,
                "claim transaction retryable failure",
            )
        return 1


class ClaimConnection(FakeConnection):
    def __init__(self, error_code=None):
        super().__init__()
        self.error_code = error_code

    def cursor(self):
        self.cursor_calls += 1
        self.cursor_instance = ClaimCursor(self)
        return self.cursor_instance


class FakePooledDB:
    def close(self):
        pass


class FakeMySQLConnectionPool(MySQLConnectionPool):
    def __init__(self, connection):
        self.fake_connection = connection
        self.connection_calls = 0
        super().__init__()

    def _init_pool(self):
        self._pool = FakePooledDB()

    def _get_connection(self):
        self.connection_calls += 1
        return self.fake_connection


class SequencedFakeMySQLConnectionPool(MySQLConnectionPool):
    def __init__(self, connections):
        self.connections = list(connections)
        self.connection_calls = 0
        super().__init__()

    def _init_pool(self):
        self._pool = FakePooledDB()

    def _get_connection(self):
        connection = self.connections[self.connection_calls]
        self.connection_calls += 1
        return connection


class TinyRepository:
    def __init__(self, db):
        self.db = db

    def insert(self, value):
        self.db.execute("INSERT", (value,))


def _claim_identity():
    return IngestionIdentity(
        doctor_id="doctor-1",
        attachment_id="attachment-1",
        document_version=1,
        content_sha256="a" * 64,
        processor_type="pdf_hybrid_v1",
        extractor_version="pymupdf_v1",
        segment_schema_version="segment_v1",
    )


class MySQLTransactionContextTest(unittest.TestCase):
    def test_in_transaction_probe_tracks_outermost_scope(self):
        connection = FakeConnection()
        db = FakeMySQLConnectionPool(connection)

        self.assertFalse(getattr(db, "in_transaction", False))
        with db.transaction():
            self.assertTrue(getattr(db, "in_transaction", False))
        self.assertFalse(getattr(db, "in_transaction", False))

    def test_top_level_claim_retry_uses_new_connection_and_full_rollback(self):
        for error_code in (1205, 1213):
            with self.subTest(error_code=error_code):
                failed = ClaimConnection(error_code)
                succeeded = ClaimConnection()
                db = SequencedFakeMySQLConnectionPool([failed, succeeded])

                claimed = ResearchDocumentRepositoryImpl(db=db).claim(
                    _claim_identity(),
                    now=datetime(2026, 7, 11, 9, 0, 0),
                    lease_until=datetime(2026, 7, 11, 9, 5, 0),
                )

                self.assertEqual(claimed.attempt_count, 1)
                self.assertEqual(db.connection_calls, 2)
                self.assertEqual(failed.commit_calls, 0)
                self.assertEqual(failed.rollback_calls, 1)
                self.assertEqual(failed.close_calls, 1)
                self.assertEqual(succeeded.commit_calls, 1)
                self.assertEqual(succeeded.rollback_calls, 0)
                self.assertEqual(succeeded.close_calls, 1)

    def test_top_level_claim_retry_exhaustion_rolls_back_three_connections(self):
        for error_code in (1205, 1213):
            with self.subTest(error_code=error_code):
                connections = [ClaimConnection(error_code) for _ in range(3)]
                db = SequencedFakeMySQLConnectionPool(connections)

                with self.assertRaises(pymysql.err.OperationalError) as raised:
                    ResearchDocumentRepositoryImpl(db=db).claim(
                        _claim_identity(),
                        now=datetime(2026, 7, 11, 9, 0, 0),
                        lease_until=datetime(2026, 7, 11, 9, 5, 0),
                    )

                self.assertEqual(raised.exception.args[0], error_code)
                self.assertEqual(db.connection_calls, 3)
                self.assertTrue(
                    all(connection.commit_calls == 0 for connection in connections)
                )
                self.assertTrue(
                    all(connection.rollback_calls == 1 for connection in connections)
                )
                self.assertTrue(
                    all(connection.close_calls == 1 for connection in connections)
                )

    def test_claim_inside_outer_transaction_fails_before_any_sql(self):
        connection = ClaimConnection()
        db = SequencedFakeMySQLConnectionPool([connection])
        repository = ResearchDocumentRepositoryImpl(db=db)

        with self.assertRaises(ResearchDocumentClaimTransactionBoundaryError):
            with db.transaction():
                repository.claim(
                    _claim_identity(),
                    now=datetime(2026, 7, 11, 9, 0, 0),
                    lease_until=datetime(2026, 7, 11, 9, 5, 0),
                )
        self.assertEqual(connection.statements, [])
        self.assertEqual(connection.commit_calls, 0)
        self.assertEqual(connection.rollback_calls, 1)

    def test_nested_repository_calls_reuse_one_connection(self):
        connection = FakeConnection()
        db = FakeMySQLConnectionPool(connection)
        repository = TinyRepository(db)

        with db.transaction():
            repository.insert("first")
            with db.transaction():
                repository.insert("second")

        self.assertEqual(db.connection_calls, 1)
        self.assertEqual(connection.cursor_calls, 1)
        self.assertEqual(connection.commit_calls, 1)
        self.assertEqual(connection.rollback_calls, 0)
        self.assertEqual(connection.close_calls, 1)
        self.assertTrue(connection.cursor_instance.closed)

    def test_second_write_failure_rolls_back_both_writes(self):
        connection = FakeConnection()
        db = FakeMySQLConnectionPool(connection)

        with self.assertRaisesRegex(RuntimeError, "second write failed"):
            with db.transaction():
                db.execute("INSERT", ("first",))
                db.execute("FAIL", ("second",))

        self.assertEqual(connection.statements, [
            ("INSERT", ("first",)),
            ("FAIL", ("second",)),
        ])
        self.assertEqual(connection.commit_calls, 0)
        self.assertEqual(connection.rollback_calls, 1)
        self.assertEqual(connection.close_calls, 1)

    def test_outermost_success_commits_once(self):
        connection = FakeConnection()
        db = FakeMySQLConnectionPool(connection)

        with db.transaction():
            db.execute("INSERT", ("only",))

        self.assertEqual(connection.commit_calls, 1)
        self.assertEqual(connection.rollback_calls, 0)

    def test_deadlock_inside_transaction_is_not_retried_per_statement(self):
        connection = FakeConnection()
        db = FakeMySQLConnectionPool(connection)

        with self.assertRaises(pymysql.err.OperationalError) as raised:
            with db.transaction():
                db.execute("INSERT", ("first",))
                db.execute("DEADLOCK", ("second",))

        self.assertEqual(raised.exception.args[0], 1213)
        self.assertEqual(connection.statements, [
            ("INSERT", ("first",)),
            ("DEADLOCK", ("second",)),
        ])
        self.assertEqual(connection.commit_calls, 0)
        self.assertEqual(connection.rollback_calls, 1)

    def test_batch_write_reuses_transaction_and_commits_with_state_update(self):
        connection = FakeConnection()
        db = FakeMySQLConnectionPool(connection)

        with db.transaction():
            db.execute_many("INSERT_SEGMENTS", [("segment-1",), ("segment-2",)])
            db.execute("MARK_READY", ("ingestion-1", 2))

        self.assertEqual(connection.statements, [
            ("INSERT_SEGMENTS", [("segment-1",), ("segment-2",)]),
            ("MARK_READY", ("ingestion-1", 2)),
        ])
        self.assertEqual(db.connection_calls, 1)
        self.assertEqual(connection.commit_calls, 1)
        self.assertEqual(connection.rollback_calls, 0)

    def test_nested_complete_cas_loss_rolls_back_segment_writes(self):
        connection = CompleteCasLossConnection()
        db = FakeMySQLConnectionPool(connection)
        repository = ResearchDocumentRepositoryImpl(db=db)
        segment = ResearchDocumentSegmentEntity(
            ingestion_id=connection.locked_ingestion["id"],
            ordinal=0,
            content="科研文档分段",
            page_start=1,
            page_end=1,
            token_count=6,
            metadata={"extraction_mode": "text"},
        )

        raised = None
        try:
            with db.transaction():
                repository.complete(
                    connection.locked_ingestion["id"],
                    2,
                    [segment],
                )
        except RuntimeError as error:
            raised = error

        self.assertIsNotNone(raised, "最终 ready CAS 丢失必须穿透外层事务")
        self.assertEqual(connection.commit_calls, 0)
        self.assertEqual(connection.rollback_calls, 1)
        self.assertTrue(
            any(
                "insert into research_document_segment" in sql.lower()
                for sql, _ in connection.statements
            )
        )


if __name__ == "__main__":
    unittest.main()

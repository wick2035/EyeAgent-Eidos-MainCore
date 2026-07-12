import os
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from domain.models.research_document import IngestionIdentity
from infrastructure.database.mysql_connection import MySQLConnectionPool
from infrastructure.repositories.research_document_repository_impl import (
    ResearchDocumentRepositoryImpl,
)


_RUN_MYSQL_INTEGRATION = (
    os.getenv("RUN_RESEARCH_DOCUMENT_MYSQL_INTEGRATION") == "1"
)


@unittest.skipUnless(
    _RUN_MYSQL_INTEGRATION,
    "设置 RUN_RESEARCH_DOCUMENT_MYSQL_INTEGRATION=1 后运行真实 MySQL 集成测试",
)
class ResearchDocumentRepositoryMySQLIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = MySQLConnectionPool()
        cls.repository = ResearchDocumentRepositoryImpl(db=cls.db)
        for table_name in (
            "research_document_ingestion",
            "research_document_segment",
        ):
            row = cls.db.fetch_one(f"SHOW TABLE STATUS LIKE '{table_name}'")
            if row is None:
                raise AssertionError(f"缺少真实 MySQL 表: {table_name}")
            if row["Engine"].lower() != "innodb":
                raise AssertionError(f"{table_name} 必须使用 InnoDB")

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        suffix = uuid.uuid4().hex[:12]
        self.doctor_id = f"task9-doctor-{suffix}"

    def tearDown(self):
        self.db.execute(
            "DELETE FROM research_document_ingestion WHERE doctor_id = %s",
            (self.doctor_id,),
        )

    def _identity(self, attachment_suffix: str) -> IngestionIdentity:
        return IngestionIdentity(
            doctor_id=self.doctor_id,
            attachment_id=f"task9-{attachment_suffix}",
            document_version=9,
            content_sha256=("a" if attachment_suffix == "empty" else "b")
            * 64,
            processor_type="plain_text_v1",
            extractor_version="plain_text_v1",
            segment_schema_version="segment_v1",
        )

    def _concurrent_claims(self, identity, now, lease_until):
        barrier = threading.Barrier(3)

        def claim():
            barrier.wait(timeout=10)
            return ResearchDocumentRepositoryImpl(db=self.db).claim(
                identity,
                now,
                lease_until,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(claim) for _ in range(2)]
            barrier.wait(timeout=10)
            return [future.result(timeout=20) for future in futures]

    def _assert_single_owner_observer(self, results, expected_attempt):
        owners = [result for result in results if result.acquired]
        observers = [result for result in results if not result.acquired]
        self.assertEqual(len(owners), 1)
        self.assertEqual(len(observers), 1)
        self.assertEqual(owners[0].entity.id, observers[0].entity.id)
        self.assertEqual(owners[0].entity.attempt_count, expected_attempt)
        self.assertEqual(observers[0].entity.attempt_count, expected_attempt)

    def _identity_row_summary(self, identity):
        return self.db.fetch_one(
            """
                SELECT COUNT(*) AS row_count,
                       MIN(attempt_count) AS min_attempt,
                       MAX(attempt_count) AS max_attempt
                FROM research_document_ingestion
                WHERE doctor_id = %s AND attachment_id = %s
            """,
            (identity.doctor_id, identity.attachment_id),
        )

    def test_empty_table_same_identity_has_one_owner_and_one_observer(self):
        identity = self._identity("empty")
        now = datetime(2026, 7, 12, 20, 0, 0)

        results = self._concurrent_claims(
            identity,
            now,
            now + timedelta(minutes=5),
        )

        self._assert_single_owner_observer(results, expected_attempt=1)
        summary = self._identity_row_summary(identity)
        self.assertEqual(summary["row_count"], 1)
        self.assertEqual(summary["min_attempt"], 1)
        self.assertEqual(summary["max_attempt"], 1)

    def test_expired_takeover_has_one_owner_and_single_attempt_increment(self):
        identity = self._identity("expired")
        initial_now = datetime(2026, 7, 12, 20, 0, 0)
        initial = self.repository.claim(
            identity,
            initial_now,
            initial_now + timedelta(minutes=1),
        )
        self.assertTrue(initial.acquired)
        self.assertEqual(initial.entity.attempt_count, 1)

        takeover_now = initial_now + timedelta(minutes=2)
        results = self._concurrent_claims(
            identity,
            takeover_now,
            takeover_now + timedelta(minutes=5),
        )

        self._assert_single_owner_observer(results, expected_attempt=2)
        summary = self._identity_row_summary(identity)
        self.assertEqual(summary["row_count"], 1)
        self.assertEqual(summary["min_attempt"], 2)
        self.assertEqual(summary["max_attempt"], 2)

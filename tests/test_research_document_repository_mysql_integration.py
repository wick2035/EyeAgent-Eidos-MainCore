import os
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from application.services.research_document_segmenter import estimate_tokens_v1
from domain.models.research_dataset import (
    ExtractedCsvChunk,
    ExtractedCsvRow,
    ExtractedResearchCsv,
    ExtractedResearchXlsx,
    ExtractedXlsxChunk,
    ExtractedXlsxRow,
    ExtractedXlsxSheet,
    build_research_csv_chunk_payload_sha256,
    build_research_csv_descriptor_sha256,
    build_research_dataset_id,
    build_research_dataset_materialization,
    build_research_xlsx_chunk_payload_sha256,
    build_research_xlsx_descriptor_sha256,
    build_research_xlsx_sheet_descriptor_sha256,
)
from domain.models.research_dataset_query import ResearchDatasetAccessScope
from domain.models.research_document import (
    IngestionIdentity,
    ResearchDocumentSegmentEntity,
)
from infrastructure.database.mysql_connection import MySQLConnectionPool
from infrastructure.repositories.research_document_repository_impl import (
    ResearchDocumentRepositoryImpl,
)
from infrastructure.repositories.research_dataset_query_repository_impl import (
    ResearchDatasetQueryRepositoryImpl,
)


def _mysql_integration_enabled() -> bool:
    return os.getenv("RUN_MYSQL_INTEGRATION") == "1"


_RUN_MYSQL_INTEGRATION = _mysql_integration_enabled()


@unittest.skipUnless(
    _RUN_MYSQL_INTEGRATION,
    "设置 RUN_MYSQL_INTEGRATION=1 后运行真实 MySQL 集成测试",
)
class ResearchDocumentRepositoryMySQLIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = MySQLConnectionPool()
        cls.repository = ResearchDocumentRepositoryImpl(db=cls.db)
        cls.query_repository = ResearchDatasetQueryRepositoryImpl(db=cls.db)
        for table_name in (
            "chat_turn_request",
            "research_document_ingestion",
            "research_document_segment",
            "research_dataset",
            "research_dataset_sheet",
            "research_dataset_row_chunk",
        ):
            row = cls.db.fetch_one(f"SHOW TABLE STATUS LIKE '{table_name}'")
            if row is None:
                raise AssertionError(f"缺少真实 MySQL 表: {table_name}")
            if row["Engine"].lower() != "innodb":
                raise AssertionError(f"{table_name} 必须使用 InnoDB")
        expected_columns = {
            "research_dataset": {
                "date_system",
                "workbook_sheet_count",
                "empty_sheet_count",
                "total_record_count",
                "total_formula_cell_count",
                "total_merged_range_count",
            },
            "research_dataset_sheet": {
                "visibility",
                "formula_cell_count",
                "merged_range_count",
            },
            "research_dataset_row_chunk": {"formula_cell_count"},
        }
        for table_name, column_names in expected_columns.items():
            rows = cls.db.fetch_all(
                """
                    SELECT COLUMN_NAME AS column_name
                    FROM information_schema.columns
                    WHERE table_schema = DATABASE() AND table_name = %s
                """,
                (table_name,),
            )
            actual = {row["column_name"] for row in rows}
            missing = column_names - actual
            if missing:
                raise AssertionError(
                    f"{table_name} 缺少 C3-2 列: {sorted(missing)}"
                )
        name_column = cls.db.fetch_one(
            """
                SELECT COLLATION_NAME AS collation_name
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                  AND table_name = 'research_dataset_sheet'
                  AND column_name = 'name'
            """
        )
        if name_column["collation_name"] != "utf8mb4_bin":
            raise AssertionError("research_dataset_sheet.name 必须使用 utf8mb4_bin")

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

    def _csv_identity(self) -> IngestionIdentity:
        return IngestionIdentity(
            doctor_id=self.doctor_id,
            attachment_id="task9-csv",
            document_version=1,
            content_sha256="c" * 64,
            processor_type="csv_dataset_v1",
            extractor_version="research_csv_v1",
            segment_schema_version="segment_v1",
        )

    def _xlsx_identity(self) -> IngestionIdentity:
        return IngestionIdentity(
            doctor_id=self.doctor_id,
            attachment_id="task9-xlsx",
            document_version=1,
            content_sha256="d" * 64,
            processor_type="xlsx_dataset_v1",
            extractor_version="research_xlsx_v1",
            segment_schema_version="segment_v1",
        )

    @staticmethod
    def _csv_materialization(ingestion_id: str):
        rows = (
            ExtractedCsvRow(
                logical_row_number=1,
                physical_row_start=2,
                physical_row_end=2,
                values=("Alice", "1"),
            ),
        )
        chunk_fields = {
            "ordinal": 1,
            "logical_row_start": 1,
            "logical_row_end": 1,
            "physical_row_start": 2,
            "physical_row_end": 2,
            "row_count": 1,
            "non_empty_cell_count": 2,
            "formula_like_cell_count": 0,
            "rows": rows,
        }
        chunk = ExtractedCsvChunk(
            **chunk_fields,
            payload_sha256=build_research_csv_chunk_payload_sha256(
                **chunk_fields
            ),
        )
        descriptor_fields = {
            "sheet_name": "CSV",
            "headers": ("name", "value"),
            "header_row_start": 1,
            "header_row_end": 1,
            "physical_line_count": 2,
            "record_count": 2,
            "data_row_count": 1,
            "column_count": 2,
            "non_empty_cell_count": 4,
            "formula_like_cell_count": 0,
            "missing_value_counts": (0, 0),
        }
        extracted = ExtractedResearchCsv(
            **descriptor_fields,
            chunks=(chunk,),
            descriptor_sha256=build_research_csv_descriptor_sha256(
                **descriptor_fields
            ),
        )
        return build_research_dataset_materialization(
            ingestion_id,
            extracted,
        )

    @staticmethod
    def _xlsx_materialization(ingestion_id: str):
        def make_sheet(ordinal, name, visibility, value, formula, merged):
            row = ExtractedXlsxRow(
                logical_row_number=1,
                physical_row_start=2,
                physical_row_end=2,
                values=(value, formula),
                formula_cell_indexes=(1,) if formula.startswith("=") else (),
            )
            chunk_fields = {
                "sheet_ordinal": ordinal,
                "ordinal": 1,
                "logical_row_start": 1,
                "logical_row_end": 1,
                "physical_row_start": 2,
                "physical_row_end": 2,
                "row_count": 1,
                "non_empty_cell_count": sum(cell != "" for cell in row.values),
                "formula_like_cell_count": sum(
                    cell.lstrip().startswith(("=", "+", "-", "@"))
                    for cell in row.values
                ),
                "formula_cell_count": len(row.formula_cell_indexes),
                "rows": (row,),
            }
            chunk = ExtractedXlsxChunk(
                **chunk_fields,
                payload_sha256=build_research_xlsx_chunk_payload_sha256(
                    **chunk_fields
                ),
            )
            sheet_fields = {
                "ordinal": ordinal,
                "name": name,
                "visibility": visibility,
                "headers": ("name", "value"),
                "header_row_start": 1,
                "header_row_end": 1,
                "physical_line_count": 2,
                "record_count": 2,
                "data_row_count": 1,
                "column_count": 2,
                "non_empty_cell_count": 2 + chunk.non_empty_cell_count,
                "formula_like_cell_count": chunk.formula_like_cell_count,
                "formula_cell_count": chunk.formula_cell_count,
                "merged_range_count": merged,
                "missing_value_counts": tuple(
                    int(row.values[column] == "") for column in range(2)
                ),
            }
            return ExtractedXlsxSheet(
                **sheet_fields,
                chunks=(chunk,),
                descriptor_sha256=build_research_xlsx_sheet_descriptor_sha256(
                    **sheet_fields
                ),
            )

        sheets = (
            make_sheet(0, "Visible", "visible", "Alice", "=1+1", 1),
            make_sheet(1, "Hidden", "veryHidden", "Bob", "", 0),
        )
        workbook_fields = {
            "date_system": "1900",
            "workbook_sheet_count": 2,
            "empty_sheet_count": 0,
            "sheets": sheets,
            "total_record_count": 4,
            "total_data_row_count": 2,
            "total_non_empty_cell_count": 7,
            "total_formula_like_cell_count": 1,
            "total_formula_cell_count": 1,
            "total_merged_range_count": 1,
        }
        extracted = ExtractedResearchXlsx(
            **workbook_fields,
            descriptor_sha256=build_research_xlsx_descriptor_sha256(
                **workbook_fields
            ),
        )
        return build_research_dataset_materialization(ingestion_id, extracted)

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

    def test_csv_complete_is_atomic_and_purge_cascades_dataset_graph(self):
        identity = self._csv_identity()
        now = datetime.now()
        claim = self.repository.claim(
            identity,
            now,
            now + timedelta(minutes=5),
        )
        content = "CSV 结构摘要；本摘要不包含原始数据行"
        segment = ResearchDocumentSegmentEntity(
            ingestion_id=claim.entity.id,
            ordinal=0,
            content=content,
            sheet_name="CSV",
            row_start=1,
            row_end=2,
            token_count=estimate_tokens_v1(content),
            metadata={
                "block_index": 0,
                "extraction_method": "csv_structured",
                "extraction_mode": "structured_summary",
            },
        )

        materialization = self._csv_materialization(claim.entity.id)
        completed = self.repository.complete(
            claim.entity.id,
            claim.entity.attempt_count,
            [segment],
            materialization,
        )

        self.assertTrue(completed)
        dataset_id = build_research_dataset_id(claim.entity.id)
        queries = (
            (
                "SELECT COUNT(*) AS row_count FROM research_dataset "
                "WHERE ingestion_id = %s",
                claim.entity.id,
            ),
            (
                "SELECT COUNT(*) AS row_count FROM research_dataset_sheet "
                "WHERE dataset_id = %s",
                dataset_id,
            ),
            (
                """
                    SELECT COUNT(*) AS row_count
                    FROM research_dataset_row_chunk chunk
                    JOIN research_dataset_sheet sheet
                      ON sheet.id = chunk.sheet_id
                    WHERE sheet.dataset_id = %s
                """,
                dataset_id,
            ),
            (
                "SELECT COUNT(*) AS row_count FROM research_document_segment "
                "WHERE ingestion_id = %s",
                claim.entity.id,
            ),
        )
        for sql, value in queries:
            row = self.db.fetch_one(sql, (value,))
            self.assertEqual(row["row_count"], 1)
        csv_defaults = self.db.fetch_one(
            """
                SELECT date_system, workbook_sheet_count, empty_sheet_count,
                       total_record_count, total_formula_cell_count,
                       total_merged_range_count
                FROM research_dataset
                WHERE ingestion_id = %s
            """,
            (claim.entity.id,),
        )
        self.assertEqual(csv_defaults["total_formula_cell_count"], 0)
        self.assertEqual(csv_defaults["total_merged_range_count"], 0)
        self.assertIsNone(csv_defaults["date_system"])
        self.assertIsNone(csv_defaults["workbook_sheet_count"])
        self.assertIsNone(csv_defaults["empty_sheet_count"])
        self.assertIsNone(csv_defaults["total_record_count"])

        scope = ResearchDatasetAccessScope(
            doctor_id=self.doctor_id,
            ingestion_id=claim.entity.id,
            attachment_id=identity.attachment_id,
            document_version=identity.document_version,
            processor_type="csv_dataset_v1",
        )
        self.assertEqual(
            self.query_repository.load_authorized(scope),
            materialization,
        )
        self.assertIsNone(
            self.query_repository.load_authorized(
                scope.model_copy(update={"doctor_id": "other-doctor"})
            )
        )
        self.db.execute(
            """
                UPDATE research_dataset_row_chunk
                SET payload_sha256 = %s
                WHERE sheet_id = %s
            """,
            ("0" * 64, materialization.sheets[0].id),
        )
        with self.assertRaises(ValueError):
            self.query_repository.load_authorized(scope)

        self.assertEqual(
            self.repository.purge(self.doctor_id, identity.attachment_id),
            1,
        )
        dataset_row = self.db.fetch_one(
            "SELECT COUNT(*) AS row_count FROM research_dataset "
            "WHERE ingestion_id = %s",
            (claim.entity.id,),
        )
        self.assertEqual(dataset_row["row_count"], 0)

    def test_xlsx_complete_persists_multisheet_and_purge_cascades_all_levels(self):
        identity = self._xlsx_identity()
        now = datetime.now()
        claim = self.repository.claim(
            identity,
            now,
            now + timedelta(minutes=5),
        )
        content = "XLSX 结构摘要；本摘要不包含原始数据行"
        segment = ResearchDocumentSegmentEntity(
            ingestion_id=claim.entity.id,
            ordinal=0,
            content=content,
            sheet_name="Visible",
            row_start=1,
            row_end=2,
            token_count=estimate_tokens_v1(content),
            metadata={"extraction_mode": "structured_summary"},
        )
        materialization = self._xlsx_materialization(claim.entity.id)

        completed = self.repository.complete(
            claim.entity.id,
            claim.entity.attempt_count,
            [segment],
            materialization,
        )

        self.assertTrue(completed)
        dataset_row = self.db.fetch_one(
            """
                SELECT file_type, date_system, workbook_sheet_count,
                       empty_sheet_count, total_record_count, sheet_count,
                       total_formula_cell_count, total_merged_range_count
                FROM research_dataset
                WHERE ingestion_id = %s
            """,
            (claim.entity.id,),
        )
        self.assertEqual(
            dataset_row,
            {
                "file_type": "xlsx",
                "date_system": "1900",
                "workbook_sheet_count": 2,
                "empty_sheet_count": 0,
                "total_record_count": 4,
                "sheet_count": 2,
                "total_formula_cell_count": 1,
                "total_merged_range_count": 1,
            },
        )
        sheet_rows = self.db.fetch_all(
            """
                SELECT id, ordinal, name, visibility, formula_cell_count,
                       merged_range_count
                FROM research_dataset_sheet
                WHERE dataset_id = %s
                ORDER BY ordinal
            """,
            (materialization.dataset.id,),
        )
        self.assertEqual(len(sheet_rows), 2)
        self.assertEqual(
            [(row["name"], row["visibility"]) for row in sheet_rows],
            [("Visible", "visible"), ("Hidden", "veryHidden")],
        )
        chunk_count = self.db.fetch_one(
            """
                SELECT COUNT(*) AS row_count,
                       SUM(formula_cell_count) AS formula_cell_count
                FROM research_dataset_row_chunk
                WHERE sheet_id IN (%s, %s)
            """,
            (sheet_rows[0]["id"], sheet_rows[1]["id"]),
        )
        self.assertEqual(chunk_count["row_count"], 2)
        self.assertEqual(chunk_count["formula_cell_count"], 1)
        self.assertEqual(
            self.query_repository.load_authorized(
                ResearchDatasetAccessScope(
                    doctor_id=self.doctor_id,
                    ingestion_id=claim.entity.id,
                    attachment_id=identity.attachment_id,
                    document_version=identity.document_version,
                    processor_type="xlsx_dataset_v1",
                )
            ),
            materialization,
        )

        self.assertEqual(
            self.repository.purge(self.doctor_id, identity.attachment_id),
            1,
        )
        for table_name, column_name, values in (
            ("research_dataset", "id", (materialization.dataset.id,)),
            (
                "research_dataset_sheet",
                "id",
                (sheet_rows[0]["id"], sheet_rows[1]["id"]),
            ),
            (
                "research_dataset_row_chunk",
                "sheet_id",
                (sheet_rows[0]["id"], sheet_rows[1]["id"]),
            ),
        ):
            placeholders = ", ".join(["%s"] * len(values))
            row = self.db.fetch_one(
                f"SELECT COUNT(*) AS row_count FROM {table_name} "
                f"WHERE {column_name} IN ({placeholders})",
                values,
            )
            self.assertEqual(row["row_count"], 0)

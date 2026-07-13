import copy
import json
from datetime import datetime
from typing import Optional

from application.repositories.research_document_repository import (
    ResearchDocumentRepository,
)
from domain.models.research_dataset import (
    ResearchDatasetMaterialization,
    ResearchDatasetRowChunkEntity,
    ResearchDatasetSheetEntity,
)
from domain.models.research_document import (
    IngestionIdentity,
    ResearchDocumentClaimResult,
    ResearchDocumentIngestionEntity,
    ResearchDocumentSegmentEntity,
    build_research_document_ingestion_id,
)
from infrastructure.database.mysql_connection import get_db_connection


class ResearchDocumentFencingError(RuntimeError):
    """锁定后发布 ready 失败；调用方必须回滚整个事务。"""


class ResearchDocumentClaimTransactionBoundaryError(RuntimeError):
    """claim 必须拥有顶层事务，才能安全重启完整工作单元。"""


class ResearchDocumentRepositoryImpl(ResearchDocumentRepository):
    _CLAIM_MAX_TRANSACTION_ATTEMPTS = 3

    _INGESTION_COLUMNS = """
        id, doctor_id, attachment_id, document_version, content_sha256,
        processor_type, extractor_version, segment_schema_version, status,
        attempt_count, lease_expires_at, page_count, error_code, started_at,
        completed_at, create_time, update_time
    """

    _SEGMENT_COLUMNS = """
        id, ingestion_id, ordinal, content, content_sha256, page_start,
        page_end, sheet_name, row_start, row_end, token_count, metadata_json
    """

    def __init__(self, db=None):
        self.db = db or get_db_connection()

    def get_ready(
        self,
        identity: IngestionIdentity,
    ) -> Optional[ResearchDocumentIngestionEntity]:
        row = self.db.fetch_one(
            f"""
                SELECT {self._INGESTION_COLUMNS}
                FROM research_document_ingestion
                WHERE doctor_id = %s
                  AND attachment_id = %s
                  AND document_version = %s
                  AND content_sha256 = %s
                  AND processor_type = %s
                  AND extractor_version = %s
                  AND segment_schema_version = %s
                  AND status = 'ready'
            """,
            self._identity_params(identity),
        )
        return self._row_to_ingestion(row) if row else None

    def claim(
        self,
        identity: IngestionIdentity,
        now: datetime,
        lease_until: datetime,
    ) -> ResearchDocumentClaimResult:
        if getattr(self.db, "in_transaction", False):
            raise ResearchDocumentClaimTransactionBoundaryError(
                "claim 不能在已有数据库事务中执行"
            )
        if lease_until <= now:
            raise ValueError("lease_until 必须晚于 now")

        for transaction_attempt in range(self._CLAIM_MAX_TRANSACTION_ATTEMPTS):
            try:
                return self._claim_once(identity, now, lease_until)
            except Exception as error:
                if (
                    not self._is_retryable_claim_transaction_error(error)
                    or transaction_attempt
                    == self._CLAIM_MAX_TRANSACTION_ATTEMPTS - 1
                ):
                    raise
        raise RuntimeError("claim transaction retry 状态不可达")

    def _claim_once(
        self,
        identity: IngestionIdentity,
        now: datetime,
        lease_until: datetime,
    ) -> ResearchDocumentClaimResult:
        with self.db.transaction():
            try:
                entity = self._insert_claim(identity, now, lease_until)
                return ResearchDocumentClaimResult(entity=entity, acquired=True)
            except Exception as error:
                if not self._is_duplicate_error(error):
                    raise
                row = self._select_identity_for_update(identity)
                if row is None:
                    raise RuntimeError("duplicate claim 后摄取记录不可见") from error
            return self._claim_existing(row, now, lease_until)

    def renew_lease(
        self,
        ingestion_id: str,
        attempt_count: int,
        lease_until: datetime,
    ) -> bool:
        affected = self.db.execute(
            """
                UPDATE research_document_ingestion
                SET lease_expires_at = %s,
                    update_time = CURRENT_TIMESTAMP(6)
                WHERE id = %s
                  AND status = 'processing'
                  AND attempt_count = %s
                  AND lease_expires_at > CURRENT_TIMESTAMP(6)
                  AND %s > CURRENT_TIMESTAMP(6)
                  AND %s > lease_expires_at
            """,
            (
                lease_until,
                ingestion_id,
                attempt_count,
                lease_until,
                lease_until,
            ),
        )
        return affected == 1

    def complete(
        self,
        ingestion_id: str,
        attempt_count: int,
        segments: list[ResearchDocumentSegmentEntity],
        dataset: Optional[ResearchDatasetMaterialization] = None,
    ) -> bool:
        segments = self._validate_completion_segments(ingestion_id, segments)
        dataset = self._validate_completion_dataset(ingestion_id, dataset)
        with self.db.transaction():
            row = self._select_active_attempt_for_update(
                ingestion_id,
                attempt_count,
            )
            if (
                row is None
                or row["status"] != "processing"
                or row["attempt_count"] != attempt_count
            ):
                return False
            is_csv_ingestion = row["processor_type"] == "csv_dataset_v1"
            if is_csv_ingestion != (dataset is not None):
                raise ValueError("dataset 必须与 ingestion processor_type 匹配")
            if dataset is not None and dataset.dataset.file_type != "csv":
                raise ValueError("CSV ingestion 只能发布 CSV dataset")

            self.db.execute(
                """
                    DELETE FROM research_document_segment
                    WHERE ingestion_id = %s
                """,
                (ingestion_id,),
            )
            if dataset is not None:
                self.db.execute(
                    """
                        DELETE FROM research_dataset
                        WHERE ingestion_id = %s
                    """,
                    (ingestion_id,),
                )
                self.db.execute(
                    """
                        INSERT INTO research_dataset (
                            id, ingestion_id, file_type, sheet_count,
                            total_data_row_count, total_column_count,
                            total_non_empty_cell_count,
                            total_formula_like_cell_count, descriptor_sha256
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """,
                    self._dataset_params(dataset),
                )
                self.db.execute_many(
                    """
                        INSERT INTO research_dataset_sheet (
                            id, dataset_id, ordinal, name, header_json,
                            header_row_start, header_row_end,
                            physical_line_count, record_count, data_row_count,
                            column_count, missing_value_counts_json,
                            non_empty_cell_count, formula_like_cell_count,
                            descriptor_sha256
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s
                        )
                    """,
                    [self._dataset_sheet_params(sheet) for sheet in dataset.sheets],
                )
                if dataset.row_chunks:
                    self.db.execute_many(
                        """
                            INSERT INTO research_dataset_row_chunk (
                                id, sheet_id, ordinal, physical_row_start,
                                physical_row_end, logical_row_start,
                                logical_row_end, row_count,
                                non_empty_cell_count, formula_like_cell_count,
                                rows_json, payload_sha256
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s
                            )
                        """,
                        [
                            self._dataset_row_chunk_params(chunk)
                            for chunk in dataset.row_chunks
                        ],
                    )
            self.db.execute_many(
                """
                    INSERT INTO research_document_segment (
                        id, ingestion_id, ordinal, content, content_sha256,
                        page_start, page_end, sheet_name, row_start, row_end,
                        token_count, metadata_json
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s
                    )
                """,
                [self._segment_params(segment) for segment in segments],
            )
            page_count = max(
                (
                    segment.page_end or segment.page_start or 0
                    for segment in segments
                ),
                default=0,
            )
            affected = self.db.execute(
                """
                    UPDATE research_document_ingestion
                    SET status = 'ready',
                        lease_expires_at = NULL,
                        page_count = %s,
                        error_code = NULL,
                        completed_at = CURRENT_TIMESTAMP(6),
                        update_time = CURRENT_TIMESTAMP(6)
                    WHERE id = %s
                      AND status = 'processing'
                      AND attempt_count = %s
                """,
                (page_count, ingestion_id, attempt_count),
            )
            if affected != 1:
                raise ResearchDocumentFencingError(
                    "锁定后的 ready CAS 未命中"
                )
        return True

    def fail(
        self,
        ingestion_id: str,
        attempt_count: int,
        error_code: str,
    ) -> bool:
        affected = self.db.execute(
            """
                UPDATE research_document_ingestion
                SET status = 'failed',
                    lease_expires_at = NULL,
                    error_code = %s,
                    update_time = CURRENT_TIMESTAMP(6)
                WHERE id = %s
                  AND status = 'processing'
                  AND attempt_count = %s
                  AND lease_expires_at > CURRENT_TIMESTAMP(6)
            """,
            (error_code, ingestion_id, attempt_count),
        )
        return affected == 1

    def list_segments(
        self,
        ingestion_ids: list[str],
    ) -> list[ResearchDocumentSegmentEntity]:
        if not ingestion_ids:
            return []
        placeholders = ", ".join(["%s"] * len(ingestion_ids))
        rows = self.db.fetch_all(
            f"""
                SELECT {self._SEGMENT_COLUMNS}
                FROM research_document_segment
                WHERE ingestion_id IN ({placeholders})
                ORDER BY ingestion_id ASC, ordinal ASC
            """,
            tuple(ingestion_ids),
        )
        return [self._row_to_segment(row) for row in rows]

    def purge(self, doctor_id: str, attachment_id: str) -> int:
        return self.db.execute(
            """
                DELETE FROM research_document_ingestion
                WHERE doctor_id = %s AND attachment_id = %s
            """,
            (doctor_id, attachment_id),
        )

    def _select_identity_for_update(self, identity: IngestionIdentity):
        return self.db.fetch_one(
            f"""
                SELECT {self._INGESTION_COLUMNS}
                FROM research_document_ingestion
                WHERE doctor_id = %s
                  AND attachment_id = %s
                  AND document_version = %s
                  AND content_sha256 = %s
                  AND processor_type = %s
                  AND extractor_version = %s
                  AND segment_schema_version = %s
                FOR UPDATE
            """,
            self._identity_params(identity),
        )

    def _select_active_attempt_for_update(
        self,
        ingestion_id: str,
        attempt_count: int,
    ):
        return self.db.fetch_one(
            f"""
                SELECT {self._INGESTION_COLUMNS}
                FROM research_document_ingestion
                WHERE id = %s
                  AND status = 'processing'
                  AND attempt_count = %s
                  AND lease_expires_at > CURRENT_TIMESTAMP(6)
                FOR UPDATE
            """,
            (ingestion_id, attempt_count),
        )

    def _insert_claim(
        self,
        identity: IngestionIdentity,
        now: datetime,
        lease_until: datetime,
    ) -> ResearchDocumentIngestionEntity:
        entity = ResearchDocumentIngestionEntity(
            id=build_research_document_ingestion_id(identity),
            **identity.model_dump(),
            status="processing",
            attempt_count=1,
            lease_expires_at=lease_until,
            started_at=now,
            create_time=now,
            update_time=now,
        )
        self.db.execute(
            """
                INSERT INTO research_document_ingestion (
                    id, doctor_id, attachment_id, document_version,
                    content_sha256, processor_type, extractor_version,
                    segment_schema_version, status, attempt_count,
                    lease_expires_at, page_count, error_code, started_at,
                    completed_at, create_time, update_time
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
            """,
            (
                entity.id,
                entity.doctor_id,
                entity.attachment_id,
                entity.document_version,
                entity.content_sha256,
                entity.processor_type,
                entity.extractor_version,
                entity.segment_schema_version,
                entity.status,
                entity.attempt_count,
                entity.lease_expires_at,
                entity.page_count,
                entity.error_code,
                entity.started_at,
                entity.completed_at,
                entity.create_time,
                entity.update_time,
            ),
        )
        return entity

    def _claim_existing(
        self,
        row: dict,
        now: datetime,
        lease_until: datetime,
    ) -> ResearchDocumentClaimResult:
        entity = self._row_to_ingestion(row)
        if entity.status == "ready":
            return ResearchDocumentClaimResult(entity=entity, acquired=False)
        if (
            entity.status == "processing"
            and entity.lease_expires_at is not None
            and entity.lease_expires_at > now
        ):
            return ResearchDocumentClaimResult(entity=entity, acquired=False)

        next_attempt = entity.attempt_count + 1
        affected = self.db.execute(
            """
                UPDATE research_document_ingestion
                SET status = 'processing',
                    attempt_count = %s,
                    lease_expires_at = %s,
                    page_count = NULL,
                    error_code = NULL,
                    started_at = %s,
                    completed_at = NULL,
                    update_time = %s
                WHERE id = %s
                  AND attempt_count = %s
                  AND status <> 'ready'
                  AND (
                      status <> 'processing'
                      OR lease_expires_at IS NULL
                      OR lease_expires_at <= %s
                  )
            """,
            (
                next_attempt,
                lease_until,
                now,
                now,
                entity.id,
                entity.attempt_count,
                now,
            ),
        )
        if affected != 1:
            latest = self._select_identity_for_update(entity.identity)
            if latest is None:
                raise RuntimeError("claim CAS 后摄取记录不存在")
            return ResearchDocumentClaimResult(
                entity=self._row_to_ingestion(latest),
                acquired=False,
            )
        claimed = entity.model_copy(
            update={
                "status": "processing",
                "attempt_count": next_attempt,
                "lease_expires_at": lease_until,
                "page_count": None,
                "error_code": None,
                "started_at": now,
                "completed_at": None,
                "update_time": now,
            }
        )
        return ResearchDocumentClaimResult(entity=claimed, acquired=True)

    @staticmethod
    def _identity_params(identity: IngestionIdentity) -> tuple:
        return (
            identity.doctor_id,
            identity.attachment_id,
            identity.document_version,
            identity.content_sha256,
            identity.processor_type,
            identity.extractor_version,
            identity.segment_schema_version,
        )

    @staticmethod
    def _validate_completion_segments(
        ingestion_id: str,
        segments: list[ResearchDocumentSegmentEntity],
    ) -> list[ResearchDocumentSegmentEntity]:
        if not segments:
            raise ValueError("segments 不能为空")
        validated_segments = [
            ResearchDocumentSegmentEntity.model_validate(
                copy.deepcopy(segment.model_dump(mode="python"))
            )
            for segment in segments
        ]
        if any(
            segment.ingestion_id != ingestion_id
            for segment in validated_segments
        ):
            raise ValueError("segment 不属于目标 ingestion")
        ordinals = [segment.ordinal for segment in validated_segments]
        if len(ordinals) != len(set(ordinals)):
            raise ValueError("segment ordinal 不能重复")
        return validated_segments

    @staticmethod
    def _validate_completion_dataset(
        ingestion_id: str,
        dataset: Optional[ResearchDatasetMaterialization],
    ) -> Optional[ResearchDatasetMaterialization]:
        if dataset is None:
            return None
        validated_dataset = ResearchDatasetMaterialization.model_validate(
            copy.deepcopy(dataset.model_dump(mode="python"))
        )
        if validated_dataset.dataset.ingestion_id != ingestion_id:
            raise ValueError("dataset 不属于目标 ingestion")
        return validated_dataset

    @staticmethod
    def _dataset_params(dataset: ResearchDatasetMaterialization) -> tuple:
        entity = dataset.dataset
        return (
            entity.id,
            entity.ingestion_id,
            entity.file_type,
            entity.sheet_count,
            entity.total_data_row_count,
            entity.total_column_count,
            entity.total_non_empty_cell_count,
            entity.total_formula_like_cell_count,
            entity.descriptor_sha256,
        )

    @classmethod
    def _dataset_sheet_params(cls, sheet: ResearchDatasetSheetEntity) -> tuple:
        return (
            sheet.id,
            sheet.dataset_id,
            sheet.ordinal,
            sheet.name,
            cls._canonical_json(sheet.headers),
            sheet.header_row_start,
            sheet.header_row_end,
            sheet.physical_line_count,
            sheet.record_count,
            sheet.data_row_count,
            sheet.column_count,
            cls._canonical_json(sheet.missing_value_counts),
            sheet.non_empty_cell_count,
            sheet.formula_like_cell_count,
            sheet.descriptor_sha256,
        )

    @classmethod
    def _dataset_row_chunk_params(
        cls,
        chunk: ResearchDatasetRowChunkEntity,
    ) -> tuple:
        return (
            chunk.id,
            chunk.sheet_id,
            chunk.ordinal,
            chunk.physical_row_start,
            chunk.physical_row_end,
            chunk.logical_row_start,
            chunk.logical_row_end,
            chunk.row_count,
            chunk.non_empty_cell_count,
            chunk.formula_like_cell_count,
            cls._canonical_json(
                [row.model_dump(mode="json") for row in chunk.rows]
            ),
            chunk.payload_sha256,
        )

    @staticmethod
    def _canonical_json(value: object) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _segment_params(segment: ResearchDocumentSegmentEntity) -> tuple:
        return (
            segment.id,
            segment.ingestion_id,
            segment.ordinal,
            segment.content,
            segment.content_sha256,
            segment.page_start,
            segment.page_end,
            segment.sheet_name,
            segment.row_start,
            segment.row_end,
            segment.token_count,
            json.dumps(
                segment.metadata,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )

    @staticmethod
    def _row_to_ingestion(row: dict) -> ResearchDocumentIngestionEntity:
        return ResearchDocumentIngestionEntity.model_validate(row)

    @staticmethod
    def _row_to_segment(row: dict) -> ResearchDocumentSegmentEntity:
        metadata = row.get("metadata_json")
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        if not isinstance(metadata, dict):
            raise ValueError("metadata_json 必须是 JSON 对象")
        return ResearchDocumentSegmentEntity(
            id=row["id"],
            ingestion_id=row["ingestion_id"],
            ordinal=row["ordinal"],
            content=row["content"],
            content_sha256=row["content_sha256"],
            page_start=row.get("page_start"),
            page_end=row.get("page_end"),
            sheet_name=row.get("sheet_name"),
            row_start=row.get("row_start"),
            row_end=row.get("row_end"),
            token_count=row["token_count"],
            metadata=metadata,
        )

    @staticmethod
    def _is_duplicate_error(error: Exception) -> bool:
        current = error
        while current is not None:
            args = getattr(current, "args", ())
            if args and args[0] == 1062:
                return True
            if "duplicate entry" in str(current).lower():
                return True
            current = current.__cause__ or current.__context__
        return False

    @staticmethod
    def _is_retryable_claim_transaction_error(error: Exception) -> bool:
        current = error
        while current is not None:
            args = getattr(current, "args", ())
            if args and args[0] in {1205, 1213}:
                return True
            current = current.__cause__ or current.__context__
        return False


_research_document_repository: Optional[ResearchDocumentRepositoryImpl] = None


def get_research_document_repository() -> ResearchDocumentRepositoryImpl:
    global _research_document_repository
    if _research_document_repository is None:
        _research_document_repository = ResearchDocumentRepositoryImpl()
    return _research_document_repository

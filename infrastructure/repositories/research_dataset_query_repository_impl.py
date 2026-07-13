import json
import math
from threading import Lock
from typing import Any

from application.repositories.research_dataset_query_repository import (
    ResearchDatasetQueryRepository,
)
from domain.models.research_dataset import (
    ResearchDatasetEntity,
    ResearchDatasetMaterialization,
    ResearchDatasetRowChunkEntity,
    ResearchDatasetSheetEntity,
    ResearchXlsxMaterializationMetadata,
)
from domain.models.research_dataset_query import ResearchDatasetAccessScope
from infrastructure.database.mysql_connection import get_db_connection


class ResearchDatasetQueryRepositoryImpl(ResearchDatasetQueryRepository):
    """只读加载通过完整摄取身份授权的科研数据集。"""

    _FILE_TYPE_BY_PROCESSOR = {
        "csv_dataset_v1": "csv",
        "xlsx_dataset_v1": "xlsx",
    }

    _LOAD_AUTHORIZED_SQL = """
        SELECT
            i.id AS ingestion_id,
            i.doctor_id AS ingestion_doctor_id,
            i.attachment_id AS ingestion_attachment_id,
            i.document_version AS ingestion_document_version,
            i.status AS ingestion_status,
            i.processor_type AS ingestion_processor_type,
            i.page_count AS ingestion_page_count,
            d.id AS dataset_id,
            d.ingestion_id AS dataset_ingestion_id,
            d.file_type AS dataset_file_type,
            d.date_system AS dataset_date_system,
            d.workbook_sheet_count AS dataset_workbook_sheet_count,
            d.empty_sheet_count AS dataset_empty_sheet_count,
            d.total_record_count AS dataset_total_record_count,
            d.sheet_count AS dataset_sheet_count,
            d.total_data_row_count AS dataset_total_data_row_count,
            d.total_column_count AS dataset_total_column_count,
            d.total_non_empty_cell_count
                AS dataset_total_non_empty_cell_count,
            d.total_formula_like_cell_count
                AS dataset_total_formula_like_cell_count,
            d.total_formula_cell_count AS dataset_total_formula_cell_count,
            d.total_merged_range_count AS dataset_total_merged_range_count,
            d.descriptor_sha256 AS dataset_descriptor_sha256,
            s.id AS sheet_id,
            s.dataset_id AS sheet_dataset_id,
            s.ordinal AS sheet_ordinal,
            s.name AS sheet_name,
            s.visibility AS sheet_visibility,
            s.header_json AS sheet_header_json,
            s.header_row_start AS sheet_header_row_start,
            s.header_row_end AS sheet_header_row_end,
            s.physical_line_count AS sheet_physical_line_count,
            s.record_count AS sheet_record_count,
            s.data_row_count AS sheet_data_row_count,
            s.column_count AS sheet_column_count,
            s.missing_value_counts_json AS sheet_missing_value_counts_json,
            s.non_empty_cell_count AS sheet_non_empty_cell_count,
            s.formula_like_cell_count AS sheet_formula_like_cell_count,
            s.formula_cell_count AS sheet_formula_cell_count,
            s.merged_range_count AS sheet_merged_range_count,
            s.descriptor_sha256 AS sheet_descriptor_sha256,
            c.id AS chunk_id,
            c.sheet_id AS chunk_sheet_id,
            c.ordinal AS chunk_ordinal,
            c.physical_row_start AS chunk_physical_row_start,
            c.physical_row_end AS chunk_physical_row_end,
            c.logical_row_start AS chunk_logical_row_start,
            c.logical_row_end AS chunk_logical_row_end,
            c.row_count AS chunk_row_count,
            c.non_empty_cell_count AS chunk_non_empty_cell_count,
            c.formula_like_cell_count AS chunk_formula_like_cell_count,
            c.formula_cell_count AS chunk_formula_cell_count,
            c.rows_json AS chunk_rows_json,
            c.payload_sha256 AS chunk_payload_sha256
        FROM research_document_ingestion AS i
        JOIN research_dataset AS d
          ON d.ingestion_id = i.id
        JOIN research_dataset_sheet AS s
          ON s.dataset_id = d.id
        LEFT JOIN research_dataset_row_chunk AS c
          ON c.sheet_id = s.id
        WHERE i.id = %s
          AND i.doctor_id = %s
          AND i.attachment_id = %s
          AND i.document_version = %s
          AND i.status = 'ready'
          AND i.processor_type = %s
        ORDER BY s.ordinal ASC, c.ordinal ASC
    """

    _CHUNK_COLUMNS = (
        "chunk_id",
        "chunk_sheet_id",
        "chunk_ordinal",
        "chunk_physical_row_start",
        "chunk_physical_row_end",
        "chunk_logical_row_start",
        "chunk_logical_row_end",
        "chunk_row_count",
        "chunk_non_empty_cell_count",
        "chunk_formula_like_cell_count",
        "chunk_formula_cell_count",
        "chunk_rows_json",
        "chunk_payload_sha256",
    )

    _CSV_ROW_FIELDS = frozenset(
        {
            "logical_row_number",
            "physical_row_start",
            "physical_row_end",
            "values",
        }
    )
    _XLSX_ROW_FIELDS = _CSV_ROW_FIELDS | {"formula_cell_indexes"}

    def __init__(self, db=None):
        self.db = db or get_db_connection()

    def load_authorized(
        self,
        scope: ResearchDatasetAccessScope,
    ) -> ResearchDatasetMaterialization | None:
        scope = ResearchDatasetAccessScope.model_validate(
            scope.model_dump(mode="python")
        )
        rows = self.db.fetch_all(
            self._LOAD_AUTHORIZED_SQL,
            (
                scope.ingestion_id,
                scope.doctor_id,
                scope.attachment_id,
                scope.document_version,
                scope.processor_type,
            ),
        )
        if not rows:
            return None

        expected_file_type = self._FILE_TYPE_BY_PROCESSOR[scope.processor_type]
        dataset: ResearchDatasetEntity | None = None
        xlsx_metadata: ResearchXlsxMaterializationMetadata | None = None
        sheets: list[ResearchDatasetSheetEntity] = []
        sheets_by_id: dict[str, ResearchDatasetSheetEntity] = {}
        chunks: list[ResearchDatasetRowChunkEntity] = []

        for row in rows:
            self._validate_authorization_row(row, scope, expected_file_type)

            current_dataset = self._row_to_dataset(row)
            current_metadata = self._row_to_xlsx_metadata(row, expected_file_type)
            if dataset is None:
                dataset = current_dataset
                xlsx_metadata = current_metadata
            elif dataset != current_dataset or xlsx_metadata != current_metadata:
                raise ValueError("dataset join rows 元数据不一致")

            sheet = self._row_to_sheet(row)
            existing_sheet = sheets_by_id.get(sheet.id)
            if existing_sheet is None:
                sheets_by_id[sheet.id] = sheet
                sheets.append(sheet)
            elif existing_sheet != sheet:
                raise ValueError("sheet join rows 元数据不一致")

            chunk = self._row_to_chunk(row, expected_file_type, sheet.ordinal)
            if chunk is not None:
                chunks.append(chunk)

        if dataset is None:
            raise ValueError("dataset 查询结果不可达")

        return ResearchDatasetMaterialization.model_validate(
            {
                "dataset": dataset.model_dump(mode="python"),
                "sheets": [sheet.model_dump(mode="python") for sheet in sheets],
                "row_chunks": [chunk.model_dump(mode="python") for chunk in chunks],
                "xlsx_metadata": (
                    xlsx_metadata.model_dump(mode="python")
                    if xlsx_metadata is not None
                    else None
                ),
            }
        )

    @staticmethod
    def _validate_authorization_row(
        row: dict[str, Any],
        scope: ResearchDatasetAccessScope,
        expected_file_type: str,
    ) -> None:
        expected = {
            "ingestion_id": scope.ingestion_id,
            "ingestion_doctor_id": scope.doctor_id,
            "ingestion_attachment_id": scope.attachment_id,
            "ingestion_document_version": scope.document_version,
            "ingestion_status": "ready",
            "ingestion_processor_type": scope.processor_type,
            "ingestion_page_count": 0,
            "dataset_ingestion_id": scope.ingestion_id,
            "dataset_file_type": expected_file_type,
        }
        if any(row[field] != value for field, value in expected.items()):
            raise ValueError("dataset 查询结果超出授权 scope 或类型不匹配")

    @staticmethod
    def _row_to_dataset(row: dict[str, Any]) -> ResearchDatasetEntity:
        return ResearchDatasetEntity.model_validate(
            {
                "id": row["dataset_id"],
                "ingestion_id": row["dataset_ingestion_id"],
                "file_type": row["dataset_file_type"],
                "sheet_count": row["dataset_sheet_count"],
                "total_data_row_count": row["dataset_total_data_row_count"],
                "total_column_count": row["dataset_total_column_count"],
                "total_non_empty_cell_count": row[
                    "dataset_total_non_empty_cell_count"
                ],
                "total_formula_like_cell_count": row[
                    "dataset_total_formula_like_cell_count"
                ],
                "total_formula_cell_count": row[
                    "dataset_total_formula_cell_count"
                ],
                "total_merged_range_count": row[
                    "dataset_total_merged_range_count"
                ],
                "descriptor_sha256": row["dataset_descriptor_sha256"],
            }
        )

    @staticmethod
    def _row_to_xlsx_metadata(
        row: dict[str, Any],
        file_type: str,
    ) -> ResearchXlsxMaterializationMetadata | None:
        raw_metadata = {
            "date_system": row["dataset_date_system"],
            "workbook_sheet_count": row["dataset_workbook_sheet_count"],
            "empty_sheet_count": row["dataset_empty_sheet_count"],
            "total_record_count": row["dataset_total_record_count"],
        }
        if file_type == "csv":
            if any(value is not None for value in raw_metadata.values()):
                raise ValueError("CSV dataset 的 XLSX metadata 必须全部为 NULL")
            return None
        if any(value is None for value in raw_metadata.values()):
            raise ValueError("XLSX dataset metadata 不得缺失")
        return ResearchXlsxMaterializationMetadata.model_validate(raw_metadata)

    @classmethod
    def _row_to_sheet(cls, row: dict[str, Any]) -> ResearchDatasetSheetEntity:
        return ResearchDatasetSheetEntity.model_validate(
            {
                "id": row["sheet_id"],
                "dataset_id": row["sheet_dataset_id"],
                "ordinal": row["sheet_ordinal"],
                "name": row["sheet_name"],
                "visibility": row["sheet_visibility"],
                "headers": cls._decode_json_list(row["sheet_header_json"]),
                "header_row_start": row["sheet_header_row_start"],
                "header_row_end": row["sheet_header_row_end"],
                "physical_line_count": row["sheet_physical_line_count"],
                "record_count": row["sheet_record_count"],
                "data_row_count": row["sheet_data_row_count"],
                "column_count": row["sheet_column_count"],
                "missing_value_counts": cls._decode_json_list(
                    row["sheet_missing_value_counts_json"]
                ),
                "non_empty_cell_count": row["sheet_non_empty_cell_count"],
                "formula_like_cell_count": row[
                    "sheet_formula_like_cell_count"
                ],
                "formula_cell_count": row["sheet_formula_cell_count"],
                "merged_range_count": row["sheet_merged_range_count"],
                "descriptor_sha256": row["sheet_descriptor_sha256"],
            }
        )

    @classmethod
    def _row_to_chunk(
        cls,
        row: dict[str, Any],
        file_type: str,
        sheet_ordinal: int,
    ) -> ResearchDatasetRowChunkEntity | None:
        values = [row[column] for column in cls._CHUNK_COLUMNS]
        if all(value is None for value in values):
            return None
        if any(value is None for value in values):
            raise ValueError("LEFT JOIN chunk 必须为完整记录或全部 NULL")

        decoded_rows = cls._decode_json_list(row["chunk_rows_json"])
        expected_row_fields = (
            cls._CSV_ROW_FIELDS if file_type == "csv" else cls._XLSX_ROW_FIELDS
        )
        for decoded_row in decoded_rows:
            if not isinstance(decoded_row, dict):
                raise ValueError("rows_json 每一项必须为 object")
            if frozenset(decoded_row) != expected_row_fields:
                raise ValueError("rows_json row 字段不完整或包含额外字段")

        return ResearchDatasetRowChunkEntity.model_validate(
            {
                "id": row["chunk_id"],
                "sheet_id": row["chunk_sheet_id"],
                "schema_version": (
                    "research_csv_chunk_v1"
                    if file_type == "csv"
                    else "research_xlsx_chunk_v1"
                ),
                "sheet_ordinal": None if file_type == "csv" else sheet_ordinal,
                "ordinal": row["chunk_ordinal"],
                "physical_row_start": row["chunk_physical_row_start"],
                "physical_row_end": row["chunk_physical_row_end"],
                "logical_row_start": row["chunk_logical_row_start"],
                "logical_row_end": row["chunk_logical_row_end"],
                "row_count": row["chunk_row_count"],
                "non_empty_cell_count": row["chunk_non_empty_cell_count"],
                "formula_like_cell_count": row[
                    "chunk_formula_like_cell_count"
                ],
                "formula_cell_count": row["chunk_formula_cell_count"],
                "rows": decoded_rows,
                "payload_sha256": row["chunk_payload_sha256"],
            }
        )

    @classmethod
    def _decode_json_list(cls, value: object) -> list[object]:
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="strict")
        if isinstance(value, str):
            value = json.loads(
                value,
                object_pairs_hook=cls._unique_object,
                parse_constant=cls._reject_json_constant,
            )
        if not isinstance(value, list):
            raise ValueError("MySQL JSON 顶层必须为 list")
        cls._validate_decoded_json(value)
        return value

    @staticmethod
    def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("MySQL JSON object 不得包含 duplicate key")
            result[key] = value
        return result

    @staticmethod
    def _reject_json_constant(value: str) -> None:
        raise ValueError(f"MySQL JSON 不得包含 {value}")

    @classmethod
    def _validate_decoded_json(cls, value: object) -> None:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("MySQL JSON 不得包含 NaN 或 Infinity")
        if isinstance(value, list):
            for item in value:
                cls._validate_decoded_json(item)
        elif isinstance(value, dict):
            if any(not isinstance(key, str) for key in value):
                raise ValueError("MySQL JSON object key 必须为 string")
            for item in value.values():
                cls._validate_decoded_json(item)


_research_dataset_query_repository: ResearchDatasetQueryRepositoryImpl | None = None
_research_dataset_query_repository_lock = Lock()


def get_research_dataset_query_repository() -> ResearchDatasetQueryRepositoryImpl:
    global _research_dataset_query_repository
    if _research_dataset_query_repository is None:
        with _research_dataset_query_repository_lock:
            if _research_dataset_query_repository is None:
                _research_dataset_query_repository = (
                    ResearchDatasetQueryRepositoryImpl()
                )
    return _research_dataset_query_repository

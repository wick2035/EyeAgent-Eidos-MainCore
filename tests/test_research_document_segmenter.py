import hashlib
import math
import unicodedata
import unittest

from application.services.research_document_segmenter import (
    GLOBAL_CONTEXT_BUDGET,
    MAX_SEGMENT_TOKENS,
    SEGMENT_SCHEMA_VERSION,
    ResearchDocumentSegmenter,
    estimate_tokens_v1,
)
from domain.models.research_document import (
    ExtractedResearchPage,
    ExtractedResearchText,
    build_research_document_segment_id,
)
from domain.models.research_dataset import (
    ExtractedCsvChunk,
    ExtractedCsvRow,
    ExtractedResearchCsv,
    ExtractedResearchXlsx,
    ExtractedXlsxChunk,
    ExtractedXlsxRow,
    ExtractedXlsxSheet,
    build_research_xlsx_chunk_payload_sha256,
    build_research_xlsx_descriptor_sha256,
    build_research_xlsx_sheet_descriptor_sha256,
)
from infrastructure.attachments.research_csv_contract import (
    parse_research_csv_bytes,
)


def _page(number, text, method="digital_text"):
    return ExtractedResearchPage(
        page_number=number,
        text=text,
        extraction_method=method,
    )


def _csv_extracted(raw: bytes) -> ExtractedResearchCsv:
    normalized = parse_research_csv_bytes(raw)
    descriptor = normalized.descriptor
    return ExtractedResearchCsv(
        schema_version=descriptor.schema_version,
        sheet_name=descriptor.sheet_name,
        headers=descriptor.headers,
        header_row_start=descriptor.header_row_start,
        header_row_end=descriptor.header_row_end,
        physical_line_count=descriptor.physical_line_count,
        record_count=descriptor.record_count,
        data_row_count=descriptor.data_row_count,
        column_count=descriptor.column_count,
        non_empty_cell_count=descriptor.non_empty_cell_count,
        formula_like_cell_count=descriptor.formula_like_cell_count,
        missing_value_counts=descriptor.missing_value_counts,
        descriptor_sha256=descriptor.sha256,
        chunks=tuple(
            ExtractedCsvChunk(
                schema_version=chunk.schema_version,
                ordinal=chunk.ordinal,
                logical_row_start=chunk.logical_row_start,
                logical_row_end=chunk.logical_row_end,
                physical_row_start=chunk.physical_row_start,
                physical_row_end=chunk.physical_row_end,
                row_count=chunk.row_count,
                non_empty_cell_count=chunk.non_empty_cell_count,
                formula_like_cell_count=chunk.formula_like_cell_count,
                rows=tuple(
                    ExtractedCsvRow(
                        logical_row_number=row.logical_row_number,
                        physical_row_start=row.physical_row_start,
                        physical_row_end=row.physical_row_end,
                        values=row.values,
                    )
                    for row in chunk.rows
                ),
                payload_sha256=chunk.sha256,
            )
            for chunk in normalized.chunks
        ),
    )


def _xlsx_extracted() -> ExtractedResearchXlsx:
    row = ExtractedXlsxRow(
        logical_row_number=1,
        physical_row_start=3,
        physical_row_end=3,
        values=("PRIVATE_XLSX_ROW_SENTINEL", "=1+1"),
        formula_cell_indexes=(1,),
    )
    chunk_fields = {
        "sheet_ordinal": 1,
        "ordinal": 1,
        "logical_row_start": 1,
        "logical_row_end": 1,
        "physical_row_start": 3,
        "physical_row_end": 3,
        "row_count": 1,
        "non_empty_cell_count": 2,
        "formula_like_cell_count": 1,
        "formula_cell_count": 1,
        "rows": (row,),
    }
    chunk = ExtractedXlsxChunk(
        **chunk_fields,
        payload_sha256=build_research_xlsx_chunk_payload_sha256(
            **chunk_fields
        ),
    )
    sheet_fields = {
        "ordinal": 1,
        "name": "隐藏表",
        "visibility": "hidden",
        "headers": ("患者", "结果"),
        "header_row_start": 2,
        "header_row_end": 2,
        "physical_line_count": 3,
        "record_count": 2,
        "data_row_count": 1,
        "column_count": 2,
        "non_empty_cell_count": 4,
        "formula_like_cell_count": 1,
        "formula_cell_count": 1,
        "merged_range_count": 1,
        "missing_value_counts": (0, 0),
    }
    sheet = ExtractedXlsxSheet(
        **sheet_fields,
        chunks=(chunk,),
        descriptor_sha256=build_research_xlsx_sheet_descriptor_sha256(
            **sheet_fields
        ),
    )
    workbook_fields = {
        "date_system": "1900",
        "workbook_sheet_count": 2,
        "empty_sheet_count": 1,
        "sheets": (sheet,),
        "total_record_count": 2,
        "total_data_row_count": 1,
        "total_non_empty_cell_count": 4,
        "total_formula_like_cell_count": 1,
        "total_formula_cell_count": 1,
        "total_merged_range_count": 1,
    }
    return ExtractedResearchXlsx(
        **workbook_fields,
        descriptor_sha256=build_research_xlsx_descriptor_sha256(
            **workbook_fields
        ),
    )


class ResearchDocumentSegmenterTest(unittest.TestCase):
    def setUp(self):
        self.segmenter = ResearchDocumentSegmenter()
        self.ingestion_id = "11111111-1111-5111-8111-111111111111"

    def test_constants_and_estimator_are_versioned_and_conservative(self):
        self.assertEqual(SEGMENT_SCHEMA_VERSION, "segment_v1")
        self.assertEqual(MAX_SEGMENT_TOKENS, 2500)
        self.assertEqual(GLOBAL_CONTEXT_BUDGET, 12000)
        for text in ("", "abc", "abcd", "中文", "e\u0301"):
            normalized = unicodedata.normalize("NFC", text)
            expected = max(1, math.ceil(len(normalized.encode("utf-8")) / 3))
            self.assertEqual(estimate_tokens_v1(text), expected)

    def test_exact_2500_boundary_and_hard_cut_have_no_character_loss(self):
        text = "a" * 15001
        segments = self.segmenter.segment_pdf(
            self.ingestion_id,
            [_page(1, text)],
        )

        self.assertEqual("".join(segment.content for segment in segments), text)
        self.assertEqual(segments[0].token_count, 2500)
        self.assertTrue(
            all(segment.token_count <= MAX_SEGMENT_TOKENS for segment in segments)
        )

    def test_split_prefers_paragraph_then_sentence_then_whitespace(self):
        paragraph = "甲" * 2400 + "\n\n" + "乙" * 2400
        sentence = "甲" * 2400 + "。" + "乙" * 2400
        whitespace = "a" * 7400 + " " + "b" * 7400

        paragraph_segments = self.segmenter.segment_pdf(
            self.ingestion_id, [_page(1, paragraph)]
        )
        sentence_segments = self.segmenter.segment_pdf(
            self.ingestion_id, [_page(1, sentence)]
        )
        whitespace_segments = self.segmenter.segment_pdf(
            self.ingestion_id, [_page(1, whitespace)]
        )

        self.assertTrue(paragraph_segments[0].content.endswith("\n\n"))
        self.assertTrue(sentence_segments[0].content.endswith("。"))
        self.assertTrue(whitespace_segments[0].content.endswith(" "))
        self.assertEqual("".join(item.content for item in paragraph_segments), paragraph)
        self.assertEqual("".join(item.content for item in sentence_segments), sentence)
        self.assertEqual("".join(item.content for item in whitespace_segments), whitespace)

    def test_cross_page_packing_tracks_page_range_methods_and_ocr_count(self):
        pages = [
            _page(1, "数字第一页。"),
            _page(2, "OCR 第二页。", "ocr"),
            _page(3, "数字第三页。"),
        ]

        segments = self.segmenter.segment_pdf(self.ingestion_id, pages)

        self.assertEqual(len(segments), 1)
        segment = segments[0]
        self.assertEqual(segment.content, "\n\n".join(page.text for page in pages))
        self.assertEqual((segment.page_start, segment.page_end), (1, 3))
        self.assertEqual(segment.metadata["source_page_numbers"], [1, 2, 3])
        self.assertEqual(segment.metadata["extraction_method"], "mixed")
        self.assertEqual(segment.metadata["extraction_mode"], "mixed")
        self.assertTrue(segment.metadata["ocr_applied"])
        self.assertEqual(segment.metadata["ocr_page_count"], 1)

    def test_image_is_exactly_one_segment_with_null_page_range(self):
        segment = self.segmenter.segment_image(
            self.ingestion_id,
            _page(1, "科研图像结果", "vision"),
        )[0]

        self.assertIsNone(segment.page_start)
        self.assertIsNone(segment.page_end)
        self.assertEqual(segment.metadata["extraction_method"], "vision")
        self.assertEqual(segment.metadata["extraction_mode"], "vision")
        self.assertNotIn("source_page_numbers", segment.metadata)
        with self.assertRaises(ValueError):
            self.segmenter.segment_image(
                self.ingestion_id,
                _page(1, "a" * 7501, "vision"),
            )

    def test_csv_generates_only_deterministic_structure_summary(self):
        sentinel = "PRIVATE_ROW_SENTINEL_DO_NOT_LEAK"
        extracted = _csv_extracted(
            (
                "name,value\r\n"
                f"Alice,{sentinel}\r\n"
                "Bob,=formula-like"
            ).encode("utf-8")
        )

        [segment] = self.segmenter.segment(
            self.ingestion_id,
            extracted,
            processor_type="csv_dataset_v1",
        )

        self.assertNotIn(sentinel, segment.content)
        self.assertNotIn("Alice", segment.content)
        self.assertNotIn("Bob", segment.content)
        self.assertIn("name", segment.content)
        self.assertIn("本摘要不包含原始数据行", segment.content)
        self.assertEqual(segment.sheet_name, "CSV")
        self.assertEqual((segment.row_start, segment.row_end), (1, 3))
        self.assertIsNone(segment.page_start)
        self.assertIsNone(segment.page_end)
        self.assertEqual(
            segment.metadata,
            {
                "block_index": 0,
                "extraction_method": "csv_structured",
                "extraction_mode": "structured_summary",
            },
        )
        self.assertLessEqual(segment.token_count, MAX_SEGMENT_TOKENS)

    def test_xlsx_hidden_sheet_generates_summary_without_private_rows(self):
        [segment] = self.segmenter.segment(
            self.ingestion_id,
            _xlsx_extracted(),
            processor_type="xlsx_dataset_v1",
        )

        self.assertNotIn("PRIVATE_XLSX_ROW_SENTINEL", segment.content)
        self.assertNotIn("=1+1", segment.content)
        self.assertIn('"visibility":"hidden"', segment.content)
        self.assertIn('"formula_cell_count":1', segment.content)
        self.assertEqual(segment.sheet_name, "隐藏表")
        self.assertEqual((segment.row_start, segment.row_end), (2, 3))
        self.assertIsNone(segment.page_start)
        self.assertIsNone(segment.page_end)
        self.assertEqual(
            segment.metadata,
            {
                "block_index": 0,
                "extraction_method": "xlsx_structured",
                "extraction_mode": "structured_summary",
            },
        )

    def test_text_segments_have_stable_ids_no_locators_and_exact_metadata(self):
        extracted = ExtractedResearchText(
            text="e\u0301\r\n" + "a" * 16000,
            text_sha256=hashlib.sha256(
                ("e\u0301\r\n" + "a" * 16000).encode("utf-8")
            ).hexdigest(),
            character_count=16004,
        )

        direct = self.segmenter.segment_text(self.ingestion_id, extracted)
        dispatched = self.segmenter.segment(
            self.ingestion_id,
            extracted,
            processor_type="plain_text_v1",
        )

        self.assertEqual(direct, dispatched)
        self.assertEqual("".join(item.content for item in direct), "\u00e9\n" + "a" * 16000)
        self.assertEqual([item.ordinal for item in direct], list(range(len(direct))))
        for segment in direct:
            self.assertIsNone(segment.page_start)
            self.assertIsNone(segment.page_end)
            self.assertIsNone(segment.sheet_name)
            self.assertIsNone(segment.row_start)
            self.assertIsNone(segment.row_end)
            self.assertEqual(
                segment.metadata,
                {
                    "block_index": segment.ordinal,
                    "extraction_method": "plain_text",
                    "extraction_mode": "text",
                },
            )
            digest = hashlib.sha256(segment.content.encode("utf-8")).hexdigest()
            self.assertEqual(segment.content_sha256, digest)
            self.assertEqual(
                segment.id,
                build_research_document_segment_id(
                    self.ingestion_id,
                    segment.ordinal,
                    digest,
                ),
            )
            self.assertEqual(segment.token_count, estimate_tokens_v1(segment.content))
            self.assertLessEqual(segment.token_count, MAX_SEGMENT_TOKENS)

    def test_text_filters_whitespace_only_chunks_and_reindexes_stably(self):
        cases = (
            (" " * 7500 + "evidence", 1),
            ("a" * 7500 + " " * 7500 + "evidence", 2),
        )
        for text, expected_count in cases:
            with self.subTest(expected_count=expected_count):
                extracted = ExtractedResearchText(
                    text=text,
                    text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    character_count=len(text),
                )

                first = self.segmenter.segment_text(self.ingestion_id, extracted)
                second = self.segmenter.segment_text(self.ingestion_id, extracted)

                self.assertEqual(first, second)
                self.assertEqual(len(first), expected_count)
                self.assertTrue(all(segment.content.strip() for segment in first))
                self.assertEqual(
                    [segment.ordinal for segment in first],
                    list(range(expected_count)),
                )
                for segment in first:
                    digest = hashlib.sha256(
                        segment.content.encode("utf-8")
                    ).hexdigest()
                    self.assertEqual(
                        segment.id,
                        build_research_document_segment_id(
                            self.ingestion_id,
                            segment.ordinal,
                            digest,
                        ),
                    )

    def test_output_is_stable_continuous_and_uses_entity_hash_uuid(self):
        pages = [_page(1, "a" * 8000), _page(2, "结尾", "ocr")]

        first = self.segmenter.segment_pdf(self.ingestion_id, pages)
        second = self.segmenter.segment_pdf(self.ingestion_id, pages)

        self.assertEqual(first, second)
        self.assertEqual([segment.ordinal for segment in first], list(range(len(first))))
        for segment in first:
            digest = hashlib.sha256(segment.content.encode("utf-8")).hexdigest()
            self.assertEqual(segment.content_sha256, digest)
            self.assertEqual(
                segment.id,
                build_research_document_segment_id(
                    self.ingestion_id, segment.ordinal, digest
                ),
            )
            self.assertEqual(segment.metadata["block_index"], segment.ordinal)
            self.assertLessEqual(segment.token_count, MAX_SEGMENT_TOKENS)

    def test_normalizes_unicode_and_newlines_without_losing_normalized_content(self):
        pages = [_page(1, "e\u0301\r\n第一行\r第二行\n")]
        segments = self.segmenter.segment_pdf(self.ingestion_id, pages)
        expected = "é\n第一行\n第二行\n"
        self.assertEqual("".join(segment.content for segment in segments), expected)

    def test_cross_page_packing_inserts_stable_page_boundary(self):
        segments = self.segmenter.segment_pdf(
            self.ingestion_id,
            [_page(1, "abc"), _page(2, "def")],
        )

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].content, "abc\n\ndef")
        self.assertNotIn("abcdef", segments[0].content)

    def test_pdf_requires_continuous_page_numbers_and_known_methods(self):
        with self.assertRaises(ValueError):
            self.segmenter.segment_pdf(self.ingestion_id, [_page(2, "正文")])
        with self.assertRaises(ValueError):
            self.segmenter.segment_pdf(
                self.ingestion_id,
                [ExtractedResearchPage.model_construct(page_number=1, text="正文", extraction_method="vision")],
            )


if __name__ == "__main__":
    unittest.main()

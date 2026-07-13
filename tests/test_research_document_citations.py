import hashlib
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from agents.graph.attachment_citations import (
    CITATION_TOOL_NAME,
    AttachmentCitationSelection,
    build_attachment_citation_fallback,
    build_attachment_citation_tool,
    build_attachment_citations,
)
from agents.graph.citation_extractor import merge_citations
from agents.graph_manager import GraphManager, PreparedGraphTerminal
from application.services.research_document_context_selector import (
    ResearchCitationCandidate,
    ResearchContextBlock,
    ResearchDocumentContextSelection,
)
from application.services.research_document_segmenter import (
    ResearchDocumentSegmenter,
)
from domain.models.chat_entity import AttachmentSheetRowsLocator, MessageContext
from domain.models.research_document import (
    ExtractedResearchText,
    SelectedResearchSegment,
)
from utils.transient_attachment_context import (
    TransientResearchDocumentContext,
    bind_research_document_context,
    reset_research_document_context,
)


def _candidate(
    segment_id: str,
    *,
    attachment_id: str = "attachment-1",
    document_version: int = 3,
    page_start: int | None = 1,
    page_end: int | None = 1,
    sheet_name: str | None = None,
    row_start: int | None = None,
    row_end: int | None = None,
    content: str = "  第一段\n\t科研   证据  ",
) -> ResearchCitationCandidate:
    return ResearchCitationCandidate(
        segment_id=segment_id,
        ingestion_id=f"ingestion-{segment_id}",
        attachment_id=attachment_id,
        document_version=document_version,
        page_start=page_start,
        page_end=page_end,
        sheet_name=sheet_name,
        row_start=row_start,
        row_end=row_end,
        content=content,
        token_count=12,
        score=0.9,
    )


class AttachmentCitationBuilderTest(unittest.TestCase):
    def test_sheet_rows_locator_accepts_row_50000(self):
        locator = AttachmentSheetRowsLocator(
            type="sheet_rows",
            sheet_name="CSV",
            row_start=50_000,
            row_end=50_000,
        )

        self.assertEqual(locator.row_start, 50_000)
        self.assertEqual(locator.row_end, 50_000)

    def test_sheet_rows_locator_rejects_row_50001(self):
        for row_start, row_end in ((50_001, 50_001), (1, 50_001)):
            with self.subTest(row_start=row_start, row_end=row_end):
                with self.assertRaises(ValidationError):
                    AttachmentSheetRowsLocator(
                        type="sheet_rows",
                        sheet_name="CSV",
                        row_start=row_start,
                        row_end=row_end,
                    )

    def test_dataset_candidate_above_row_limit_fails_final_citation_validation(self):
        candidate = _candidate(
            "segment-over-row-limit",
            page_start=None,
            page_end=None,
            sheet_name="CSV",
            row_start=1,
            row_end=50_001,
        )

        with self.assertRaises(ValidationError):
            build_attachment_citations(
                [candidate.segment_id],
                (candidate,),
            )

    def test_selected_segment_preserves_sheet_row_source_fields(self):
        selected = SelectedResearchSegment(
            segment_id="segment-selected",
            ingestion_id="ingestion-selected",
            attachment_id="attachment-selected",
            document_version=1,
            content="数据行",
            page_start=None,
            page_end=None,
            sheet_name="Sheet 1",
            row_start=3,
            row_end=5,
            token_count=2,
        )

        dumped = selected.model_dump()
        self.assertEqual(
            {
                key: dumped[key]
                for key in ("sheet_name", "row_start", "row_end")
            },
            {"sheet_name": "Sheet 1", "row_start": 3, "row_end": 5},
        )

    def test_plain_text_whitespace_chunks_do_not_break_fallback(self):
        text = " " * 7500 + "evidence"
        extracted = ExtractedResearchText(
            text=text,
            text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            character_count=len(text),
        )
        segments = ResearchDocumentSegmenter().segment_text(
            "11111111-1111-5111-8111-111111111111",
            extracted,
        )
        candidates = tuple(
            _candidate(
                segment.id,
                attachment_id="attachment-text",
                page_start=None,
                page_end=None,
                content=segment.content,
            )
            for segment in segments
        )

        citations = build_attachment_citation_fallback(candidates)

        self.assertEqual(
            [citation["excerpt"] for citation in citations],
            ["evidence"],
        )

    def test_plain_text_candidate_uses_file_locator_without_page_fields(self):
        [citation] = build_attachment_citations(
            ["segment-text"],
            (
                _candidate(
                    "segment-text",
                    attachment_id="attachment-text",
                    document_version=9,
                    page_start=None,
                    page_end=None,
                    content="TXT 科研正文",
                ),
            ),
        )

        self.assertEqual(citation["locator"], {"type": "file"})
        self.assertNotIn("page_start", citation["locator"])
        self.assertNotIn("page_end", citation["locator"])

    def test_dataset_candidate_uses_exact_sheet_rows_locator(self):
        [citation] = build_attachment_citations(
            ["segment-dataset"],
            (
                _candidate(
                    "segment-dataset",
                    attachment_id="attachment-csv",
                    page_start=None,
                    page_end=None,
                    sheet_name="CSV",
                    row_start=2,
                    row_end=10,
                    content="结构化数据行",
                ),
            ),
        )

        self.assertEqual(
            citation["locator"],
            {
                "type": "sheet_rows",
                "sheet_name": "CSV",
                "row_start": 2,
                "row_end": 10,
            },
        )

        [boundary] = build_attachment_citations(
            ["segment-boundary"],
            (
                _candidate(
                    "segment-boundary",
                    page_start=None,
                    page_end=None,
                    sheet_name="表" * 128,
                    row_start=1,
                    row_end=50_000,
                ),
            ),
        )
        self.assertEqual(len(boundary["locator"]["sheet_name"]), 128)
        self.assertEqual(boundary["locator"]["row_end"], 50_000)

    def test_sheet_rows_rejects_partial_mixed_reversed_and_unsafe_fields(self):
        invalid_candidates = (
            _candidate(
                "partial",
                page_start=None,
                page_end=None,
                sheet_name="CSV",
                row_start=1,
                row_end=None,
            ),
            _candidate(
                "mixed",
                page_start=1,
                page_end=1,
                sheet_name="CSV",
                row_start=1,
                row_end=2,
            ),
            _candidate(
                "reversed",
                page_start=None,
                page_end=None,
                sheet_name="CSV",
                row_start=3,
                row_end=2,
            ),
            _candidate(
                "blank-sheet",
                page_start=None,
                page_end=None,
                sheet_name="   ",
                row_start=1,
                row_end=1,
            ),
            _candidate(
                "control-sheet",
                page_start=None,
                page_end=None,
                sheet_name="Sheet\n1",
                row_start=1,
                row_end=1,
            ),
            _candidate(
                "long-sheet",
                page_start=None,
                page_end=None,
                sheet_name="S" * 129,
                row_start=1,
                row_end=1,
            ),
            _candidate(
                "boolean-row",
                page_start=None,
                page_end=None,
                sheet_name="CSV",
                row_start=True,
                row_end=2,
            ),
        )
        for candidate in invalid_candidates:
            with self.subTest(segment_id=candidate.segment_id):
                with self.assertRaises((ValidationError, ValueError)):
                    build_attachment_citations(
                        [candidate.segment_id],
                        (candidate,),
                    )

    def test_page_file_mapping_excerpt_cap_and_stable_selected_order(self):
        long_content = "  " + "证 据\n" * 100 + "尾部"
        candidates = (
            _candidate("segment-page", content=long_content),
            _candidate(
                "segment-file",
                attachment_id="attachment-2",
                document_version=7,
                page_start=None,
                page_end=None,
                content="  图片   视觉结论  ",
            ),
        )

        citations = build_attachment_citations(
            ["segment-file", "segment-page"],
            candidates,
        )

        self.assertEqual(
            [item["segment_id"] for item in citations],
            ["segment-file", "segment-page"],
        )
        self.assertEqual(citations[0]["locator"], {"type": "file"})
        self.assertEqual(
            citations[1]["locator"],
            {"type": "page", "page_start": 1, "page_end": 1},
        )
        self.assertEqual(citations[0]["excerpt"], "图片 视觉结论")
        self.assertEqual(len(citations[1]["excerpt"]), 300)
        self.assertEqual(
            set(citations[0]),
            {
                "source_type",
                "attachment_id",
                "document_version",
                "segment_id",
                "locator",
                "excerpt",
            },
        )
        serialized = json.dumps(citations, ensure_ascii=False)
        for forbidden in (
            "ingestion-",
            "token_count",
            "score",
            "filename",
            "url",
        ):
            self.assertNotIn(forbidden, serialized.lower())

    def test_selection_rejects_unknown_duplicate_non_string_bool_and_over_ten(self):
        candidates = tuple(_candidate(f"segment-{index}") for index in range(11))
        invalid = (
            ["unknown"],
            ["segment-1", "segment-1"],
            [1],
            [True],
            [f"segment-{index}" for index in range(11)],
        )

        for segment_ids in invalid:
            with self.subTest(segment_ids=segment_ids):
                with self.assertRaises((ValidationError, ValueError)):
                    build_attachment_citations(segment_ids, candidates)

    def test_excerpt_must_remain_non_empty_after_whitespace_normalization(self):
        for content in ("", "   \n\t  "):
            with self.subTest(content=content):
                with self.assertRaises(ValidationError):
                    build_attachment_citations(
                        ["segment-empty"],
                        (_candidate("segment-empty", content=content),),
                    )

    def test_tool_accepts_only_segment_ids_and_rejects_forged_fields(self):
        candidates = (_candidate("segment-1"),)
        tool = build_attachment_citation_tool(candidates)

        self.assertEqual(tool.name, CITATION_TOOL_NAME)
        self.assertEqual(
            set(tool.args_schema.model_json_schema()["properties"]),
            {"segment_ids"},
        )
        self.assertEqual(
            tool.invoke({"segment_ids": ["segment-1"]}),
            {"segment_ids": ["segment-1"]},
        )
        forged = (
            {"segment_ids": ["segment-1"], "locator": {"type": "page"}},
            {"segment_ids": ["segment-1"], "url": "https://secret"},
            {"segment_ids": ["segment-1"], "filename": "secret.pdf"},
        )
        for payload in forged:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    tool.invoke(payload)

    def test_selection_model_is_strict_extra_forbid_and_unique(self):
        valid = AttachmentCitationSelection(segment_ids=["segment-1"])
        self.assertEqual(valid.segment_ids, ["segment-1"])
        for payload in (
            {"segment_ids": ("segment-1",)},
            {"segment_ids": [False]},
            {"segment_ids": ["segment-1"], "url": "https://secret"},
            {"segment_ids": ["segment-1", "segment-1"]},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    AttachmentCitationSelection.model_validate(payload)


class CitationMergeAndHistoryTest(unittest.TestCase):
    def test_web_and_attachment_dedupe_independently_then_merge(self):
        web = [
            {
                "id": f"old-{index}",
                "title": f"来源 {index}",
                "sourceType": "web",
                "url": f"https://example.com/{index}",
            }
            for index in range(11)
        ]
        web.insert(1, dict(web[0]))
        attachment = [
            build_attachment_citations(
                [f"segment-{index}"],
                (
                    _candidate(
                        f"segment-{index}",
                        attachment_id=f"attachment-{index}",
                    ),
                ),
            )[0]
            for index in range(11)
        ]
        attachment.insert(1, dict(attachment[0]))

        merged = merge_citations(web, attachment)

        self.assertEqual(len(merged), 20)
        self.assertTrue(all("sourceType" in item for item in merged[:10]))
        self.assertTrue(
            all(item.get("source_type") == "attachment" for item in merged[10:])
        )
        self.assertEqual(merged[10]["segment_id"], "segment-0")

    def test_attachment_history_round_trip_keeps_exact_shape(self):
        citation = build_attachment_citations(
            ["segment-1"],
            (_candidate("segment-1"),),
        )[0]

        encoded = MessageContext(citations=[citation]).to_context_list()
        restored = MessageContext.from_context_list(encoded)

        self.assertEqual(encoded, [{"citations": [citation]}])
        self.assertEqual(restored.citations, [citation])

    def test_sheet_rows_history_round_trip_keeps_exact_shape(self):
        citation = build_attachment_citations(
            ["segment-sheet"],
            (
                _candidate(
                    "segment-sheet",
                    page_start=None,
                    page_end=None,
                    sheet_name="数据表",
                    row_start=4,
                    row_end=8,
                ),
            ),
        )[0]

        encoded = MessageContext(citations=[citation]).to_context_list()
        restored = MessageContext.from_context_list(encoded)

        self.assertEqual(encoded, [{"citations": [citation]}])
        self.assertEqual(restored.citations, [citation])

        forged = dict(citation)
        forged["locator"] = {**citation["locator"], "url": "https://secret"}
        with self.assertRaises(ValidationError):
            MessageContext(citations=[forged])

    def test_legacy_web_history_keeps_optional_source_type_compatible(self):
        citation = {
            "id": "legacy-1",
            "title": "既有网页来源",
            "url": "https://example.com/source",
        }

        encoded = MessageContext(citations=[citation]).to_context_list()
        restored = MessageContext.from_context_list(encoded)

        self.assertEqual(encoded, [{"citations": [citation]}])
        self.assertEqual(restored.citations, [citation])


class GraphManagerAttachmentCitationTest(unittest.IsolatedAsyncioTestCase):
    async def _stream_prepared(
        self,
        candidates,
        stream_events,
        *,
        safe_attachment_refs,
    ):
        candidate_ids = tuple(candidate.segment_id for candidate in candidates)
        context = TransientResearchDocumentContext(
            implicit_prompt_id=None,
            selection=ResearchDocumentContextSelection(
                context_blocks=(
                    ResearchContextBlock(
                        content="受控科研上下文",
                        supporting_segment_ids=candidate_ids,
                        estimated_tokens=10,
                    ),
                ),
                citation_candidates=tuple(candidates),
                mode="focused",
                estimated_tokens=10,
            ),
        )

        class Checkpointer:
            @staticmethod
            def save_thread_mapping(**_kwargs):
                return True

        class StreamingGraph:
            async def astream_events(self, _state, config, version):
                for event in stream_events:
                    yield event

            @staticmethod
            def get_state(_config):
                return SimpleNamespace(values={})

        manager = object.__new__(GraphManager)
        manager.checkpointer = Checkpointer()
        manager._build_branch_history_messages = lambda **_kwargs: []
        manager._get_state_message_count = lambda *_args: 0
        config = {"configurable": {}}
        binding = bind_research_document_context(context, config)
        try:
            with patch(
                "agents.graph.graph_builder.get_streaming_medical_graph",
                return_value=StreamingGraph(),
            ):
                return [
                    event
                    async for event in manager.chat_stream_prepared_async(
                        patient_id=None,
                        doctor_id="11111111-1111-4111-8111-111111111111",
                        session_id="session-1",
                        conversation_id="conversation-1",
                        message="请分析",
                        user_message_id="user-1",
                        assistant_message_id="assistant-1",
                        safe_attachment_refs=safe_attachment_refs,
                        agent_type="research",
                        research_options={
                            "enable_institution_data": False,
                            "enable_web_search": True,
                            "types": ["general"],
                        },
                        health_handle=None,
                        research_handle=binding.handle,
                        runnable_config=config,
                    )
                ]
        finally:
            reset_research_document_context(binding, config)

    async def test_only_exact_tool_maps_current_transient_candidates(self):
        page = _candidate("segment-page")
        file = _candidate(
            "segment-file",
            page_start=None,
            page_end=None,
        )
        context = TransientResearchDocumentContext(
            implicit_prompt_id=None,
            selection=ResearchDocumentContextSelection(
                context_blocks=(
                    ResearchContextBlock(
                        content="PRIVATE_RESEARCH_CONTEXT",
                        supporting_segment_ids=("segment-page", "segment-file"),
                        estimated_tokens=10,
                    ),
                ),
                citation_candidates=(page, file),
                mode="focused",
                estimated_tokens=10,
            ),
        )

        class Checkpointer:
            @staticmethod
            def save_thread_mapping(**_kwargs):
                return True

        class StreamingGraph:
            async def astream_events(self, _state, config, version):
                yield {
                    "event": "on_tool_end",
                    "name": "similar_but_untrusted_tool",
                    "data": {"output": {"segment_ids": ["segment-file"]}},
                }
                yield {
                    "event": "on_tool_end",
                    "name": CITATION_TOOL_NAME,
                    "data": {"output": {"segment_ids": ["segment-page"]}},
                }
                yield {
                    "event": "on_chat_model_stream",
                    "data": {"chunk": SimpleNamespace(content="安全回答")},
                }

            @staticmethod
            def get_state(_config):
                return SimpleNamespace(values={})

        manager = object.__new__(GraphManager)
        manager.checkpointer = Checkpointer()
        manager._build_branch_history_messages = lambda **_kwargs: []
        manager._get_state_message_count = lambda *_args: 0
        config = {"configurable": {}}
        binding = bind_research_document_context(context, config)
        try:
            with patch(
                "agents.graph.graph_builder.get_streaming_medical_graph",
                return_value=StreamingGraph(),
            ):
                events = [
                    event
                    async for event in manager.chat_stream_prepared_async(
                        patient_id=None,
                        doctor_id="11111111-1111-4111-8111-111111111111",
                        session_id="session-1",
                        conversation_id="conversation-1",
                        message="请分析",
                        user_message_id="user-1",
                        assistant_message_id="assistant-1",
                        safe_attachment_refs=[
                            {
                                "attachment_id": "attachment-1",
                                "document_version": 3,
                                "content_sha256": "a" * 64,
                                "page_count": 1,
                            }
                        ],
                        agent_type="research",
                        research_options={
                            "enable_institution_data": False,
                            "enable_web_search": False,
                            "types": [],
                        },
                        health_handle=None,
                        research_handle=binding.handle,
                        runnable_config=config,
                    )
                ]
        finally:
            reset_research_document_context(binding, config)

        terminal = events[-1]
        self.assertIsInstance(terminal, PreparedGraphTerminal)
        self.assertEqual(
            [item["segment_id"] for item in terminal.citations],
            ["segment-page"],
        )
        self.assertNotIn("segment-file", json.dumps(terminal.citations))

    async def test_invalid_exact_tool_does_not_silently_trigger_fallback(self):
        candidates = (
            _candidate("segment-a"),
            _candidate("segment-b"),
        )

        events = await self._stream_prepared(
            candidates,
            (
                {
                    "event": "on_tool_end",
                    "name": CITATION_TOOL_NAME,
                    "data": {"output": {"segment_ids": ["unknown"]}},
                },
                {
                    "event": "on_chat_model_stream",
                    "data": {"chunk": SimpleNamespace(content="安全回答")},
                },
            ),
            safe_attachment_refs=[
                {
                    "attachment_id": "attachment-1",
                    "document_version": 3,
                    "content_sha256": "a" * 64,
                    "page_count": 1,
                }
            ],
        )

        terminal = events[-1]
        self.assertIsInstance(terminal, PreparedGraphTerminal)
        self.assertEqual(terminal.citations, [])

    async def test_no_tool_uses_stable_server_fallback_and_keeps_web_merge(self):
        private_tail = "PRIVATE_DOCUMENT_BODY_URL_HANDLE"
        first_attachment = tuple(
            _candidate(
                f"segment-page-{index}",
                attachment_id="attachment-pdf",
                page_start=index + 1,
                page_end=index + 1,
                content=(
                    "受控 PDF 摘录 " + "证" * 310 + private_tail
                    if index == 0
                    else f"PDF 证据 {index}"
                ),
            )
            for index in range(6)
        )
        second_attachment = tuple(
            _candidate(
                f"segment-image-{index}",
                attachment_id="attachment-image",
                page_start=None,
                page_end=None,
                content=f"图片证据 {index}",
            )
            for index in range(6)
        )
        candidates = (*first_attachment, *second_attachment)
        events = await self._stream_prepared(
            candidates,
            (
                {
                    "event": "on_tool_end",
                    "name": "web_search_medical",
                    "data": {
                        "output": {
                            "results": [
                                {
                                    "title": "公开网页",
                                    "url": "https://example.com/evidence",
                                    "snippet": "网页证据",
                                }
                            ]
                        }
                    },
                },
                {
                    "event": "on_chat_model_stream",
                    "data": {
                        "chunk": SimpleNamespace(
                            content=(
                                "模型自由文本伪造 segment-forged、page 999、"
                                "https://private.invalid/handle"
                            )
                        )
                    },
                },
            ),
            safe_attachment_refs=[
                {
                    "attachment_id": "attachment-pdf",
                    "document_version": 3,
                    "content_sha256": "a" * 64,
                    "page_count": 6,
                },
                {
                    "attachment_id": "attachment-image",
                    "document_version": 3,
                    "content_sha256": "b" * 64,
                    "page_count": 0,
                },
            ],
        )

        terminal = events[-1]
        self.assertIsInstance(terminal, PreparedGraphTerminal)
        self.assertEqual(terminal.citations[0]["title"], "公开网页")
        attachment = [
            item
            for item in terminal.citations
            if item.get("source_type") == "attachment"
        ]
        self.assertEqual(len(attachment), 10)
        self.assertEqual(
            [item["segment_id"] for item in attachment[:4]],
            [
                "segment-page-0",
                "segment-image-0",
                "segment-page-1",
                "segment-page-2",
            ],
        )
        self.assertEqual(
            attachment[0]["locator"],
            {"type": "page", "page_start": 1, "page_end": 1},
        )
        self.assertEqual(attachment[1]["locator"], {"type": "file"})
        serialized = json.dumps(attachment, ensure_ascii=False)
        self.assertNotIn("segment-forged", serialized)
        self.assertNotIn("page 999", serialized)
        self.assertNotIn("private.invalid", serialized)
        self.assertNotIn(private_tail, serialized)

    async def test_fallback_rejects_too_many_attachments_and_invalid_candidate(self):
        stream_events = (
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": SimpleNamespace(content="安全回答")},
            },
        )
        too_many = tuple(
            _candidate(
                f"segment-{index}",
                attachment_id=f"attachment-{index}",
            )
            for index in range(11)
        )
        invalid = (
            _candidate(
                "segment-invalid",
                attachment_id="attachment-invalid",
                page_start=3,
                page_end=2,
            ),
        )
        cases = (
            (
                too_many,
                [
                    {
                        "attachment_id": f"attachment-{index}",
                        "document_version": 3,
                        "content_sha256": f"{index % 10}" * 64,
                        "page_count": 1,
                    }
                    for index in range(11)
                ],
            ),
            (
                invalid,
                [
                    {
                        "attachment_id": "attachment-invalid",
                        "document_version": 3,
                        "content_sha256": "c" * 64,
                        "page_count": 3,
                    }
                ],
            ),
        )
        for candidates, safe_refs in cases:
            with self.subTest(candidate_count=len(candidates)):
                with self.assertRaises(ValueError):
                    await self._stream_prepared(
                        candidates,
                        stream_events,
                        safe_attachment_refs=safe_refs,
                    )


if __name__ == "__main__":
    unittest.main()

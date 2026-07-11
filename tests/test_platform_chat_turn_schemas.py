import json
import inspect
import unittest
from pathlib import Path

from pydantic import ValidationError

from application.services.chat_turn_fingerprint import (
    canonical_turn_json,
    fingerprint_turn,
)
import presentation.schemas.platform_chat_turn_schemas as turn_schemas
from presentation.schemas.platform_chat_turn_schemas import (
    AbortPlatformChatTurnRequest,
    AbortPlatformChatTurnResponse,
    ExecutePlatformChatTurnRequest,
    InternalAttachmentDescriptor,
    PlatformAttachmentStatusEvent,
    PlatformChatTurnDoneEvent,
    PlatformChatTurnErrorEvent,
    PlatformChatTurnExecutionStartedEvent,
    PlatformChatTurnStatusResponse,
    PreparePlatformChatTurnRequest,
    PreparePlatformChatTurnResponse,
)


_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
_TEN_MIB = 10 * 1024 * 1024
_THIRTY_MIB = 30 * 1024 * 1024


def load_fixture(name: str):
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def valid_descriptor(**overrides):
    payload = {
        "attachment_id": "att-1",
        "file_type": "image",
        "filename": "fundus.png",
        "mime_type": "image/png",
        "size_bytes": 1024,
        "page_count": None,
        "content_sha256": "1" * 64,
        "document_version": 1,
        "analysis_attempt_id": "attempt-1",
        "download_url": "https://storage.example/short-lived/token",
    }
    payload.update(overrides)
    return payload


def valid_prepare(**overrides):
    payload = {
        "version": 1,
        "request_id": "turn-request-1",
        "operation": "normal",
        "conversation_id": "conversation-1",
        "session_id": "session-1",
        "patient_id": "patient-1",
        "doctor_id": "doctor:42",
        "message": "检查",
        "source_message_id": None,
        "implicit_prompt_id": None,
        "attachment_ids": ["att-1"],
    }
    payload.update(overrides)
    payload["request_fingerprint"] = fingerprint_turn(
        version=payload["version"],
        operation=payload["operation"],
        conversation_id=payload["conversation_id"],
        session_id=payload["session_id"],
        patient_id=payload["patient_id"],
        message=payload["message"],
        source_message_id=payload["source_message_id"],
        implicit_prompt_id=payload["implicit_prompt_id"],
        attachment_ids=payload["attachment_ids"],
        agent_type=payload.get("agent_type"),
        attachment_scope=payload.get("attachment_scope"),
        research_options=payload.get("research_options"),
    )
    return payload


def valid_execute(**overrides):
    payload = {
        "request_id": "turn-request-1",
        "request_fingerprint": "1" * 64,
        "conversation_id": "conversation-1",
        "session_id": "session-1",
        "patient_id": "patient-1",
        "doctor_id": "doctor:42",
        "user_message_id": "message-user-1",
        "assistant_message_id": "message-assistant-1",
        "attachments": [valid_descriptor()],
    }
    payload.update(overrides)
    return payload


class PlatformChatTurnSchemaTest(unittest.TestCase):
    def test_fingerprint_matches_v2_health_and_research_fixtures(self):
        self.assertIn(
            "agent_type",
            inspect.signature(canonical_turn_json).parameters,
        )
        fixture = load_fixture("attachment_turn_fingerprint_v2.json")

        for name, vector in fixture.items():
            with self.subTest(name=name):
                self.assertEqual(
                    canonical_turn_json(**vector["input"]),
                    vector["canonical_json"],
                )
                self.assertEqual(
                    fingerprint_turn(**vector["input"]),
                    vector["sha256"],
                )

    def test_research_options_normalize_types_and_disable_clears_them(self):
        options_type = getattr(turn_schemas, "ResearchOptionsV2", None)
        self.assertIsNotNone(options_type)
        enabled = options_type(
            enable_web_search=True,
            types=["scholar", "general", "pubmed", "general"],
        )
        disabled = options_type(
            enable_web_search=False,
            types=["pubmed"],
        )

        self.assertEqual(enabled.types, ["general", "pubmed", "scholar"])
        self.assertEqual(disabled.types, [])

    def test_v2_prepare_requires_and_validates_agent_contract(self):
        self.assertIn(
            "agent_type",
            inspect.signature(fingerprint_turn).parameters,
        )
        base = valid_prepare(
            version=2,
            patient_id="patient-1",
            message="",
            implicit_prompt_id="attachment-analysis-v1",
            agent_type="health",
            attachment_scope="patient",
            research_options=None,
        )

        health = PreparePlatformChatTurnRequest(**base)
        self.assertEqual(health.agent_type, "health")
        for field in (
            "patient_id",
            "doctor_id",
            "agent_type",
            "attachment_scope",
            "research_options",
        ):
            with self.subTest(missing=field):
                payload = dict(base)
                payload.pop(field)
                with self.assertRaises(ValidationError):
                    PreparePlatformChatTurnRequest(**payload)

        invalid = dict(base)
        invalid["agent_type"] = "research"
        with self.assertRaises(ValidationError):
            PreparePlatformChatTurnRequest(**invalid)

    def test_v2_execute_requires_and_validates_agent_contract(self):
        base = valid_execute(
            version=2,
            patient_id=None,
            agent_type="research",
            attachment_scope="research",
            research_options={
                "enable_web_search": True,
                "types": ["scholar", "general", "general"],
            },
        )

        research = ExecutePlatformChatTurnRequest(**base)
        self.assertEqual(research.research_options.types, ["general", "scholar"])
        for field in (
            "patient_id",
            "doctor_id",
            "agent_type",
            "attachment_scope",
            "research_options",
        ):
            with self.subTest(missing=field):
                payload = dict(base)
                payload.pop(field)
                with self.assertRaises(ValidationError):
                    ExecutePlatformChatTurnRequest(**payload)

        invalid = dict(base)
        invalid["attachment_scope"] = "patient"
        with self.assertRaises(ValidationError):
            ExecutePlatformChatTurnRequest(**invalid)
    def test_fingerprint_matches_v1_fixture(self):
        fixture = load_fixture("attachment_turn_fingerprint_v1.json")
        self.assertEqual(
            canonical_turn_json(**fixture["input"]),
            fixture["canonical_json"],
        )
        self.assertEqual(
            fingerprint_turn(**fixture["input"]),
            fixture["sha256"],
        )

    def test_fingerprint_matches_named_edge_whitespace_vectors(self):
        fixture = load_fixture("attachment_turn_fingerprint_v1.json")
        for vector in fixture["boundary_vectors"]:
            with self.subTest(name=vector["name"]):
                self.assertEqual(
                    canonical_turn_json(**vector["input"]),
                    vector["canonical_json"],
                )
                self.assertEqual(
                    fingerprint_turn(**vector["input"]),
                    vector["sha256"],
                )

    def test_prepare_normalizes_message_and_exposes_attachment_only(self):
        request = PreparePlatformChatTurnRequest(
            **valid_prepare(message=" \te\u0301\r\n检查\rX ")
        )

        self.assertEqual(request.message, "é\n检查\rX")
        self.assertFalse(request.attachment_only)

        attachment_only = PreparePlatformChatTurnRequest(
            **valid_prepare(
                message="\t\r\n ",
                implicit_prompt_id="attachment-analysis-v1",
            )
        )
        self.assertEqual(attachment_only.message, "")
        self.assertTrue(attachment_only.attachment_only)

    def test_prepare_requires_text_or_attachment(self):
        with self.assertRaises(ValidationError):
            PreparePlatformChatTurnRequest(
                **valid_prepare(message="", attachment_ids=[])
            )

    def test_prepare_recomputes_implicit_prompt_from_normalized_message(self):
        invalid_payloads = (
            valid_prepare(message="\t\r\n ", implicit_prompt_id=None),
            valid_prepare(
                message="有正文",
                implicit_prompt_id="attachment-analysis-v1",
            ),
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    PreparePlatformChatTurnRequest(**payload)

    def test_prepare_enforces_operation_source_message_contract(self):
        invalid_payloads = (
            valid_prepare(operation="normal", source_message_id="message-1"),
            valid_prepare(operation="edit_resend", source_message_id=None),
            valid_prepare(operation="regenerate", source_message_id=""),
        )

        for payload in invalid_payloads:
            with self.subTest(operation=payload["operation"]):
                with self.assertRaises(ValidationError):
                    PreparePlatformChatTurnRequest(**payload)

    def test_prepare_rejects_conflicting_request_fingerprint(self):
        payload = valid_prepare()
        payload["request_fingerprint"] = "0" * 64

        with self.assertRaisesRegex(
            ValidationError,
            "REQUEST_IDEMPOTENCY_CONFLICT",
        ):
            PreparePlatformChatTurnRequest(**payload)

    def test_internal_descriptor_rejects_legacy_or_unknown_fields(self):
        for legacy_field in ("base64", "page_images", "minio_url", "storage_key"):
            with self.subTest(legacy_field=legacy_field):
                payload = valid_descriptor()
                payload[legacy_field] = "forbidden"
                with self.assertRaises(ValidationError):
                    InternalAttachmentDescriptor(**payload)

    def test_internal_descriptor_enforces_file_type_limits(self):
        invalid_payloads = (
            valid_descriptor(size_bytes=_TEN_MIB + 1),
            valid_descriptor(page_count=1),
            valid_descriptor(file_type="image", mime_type="application/pdf"),
            valid_descriptor(
                file_type="pdf",
                mime_type="application/pdf",
                size_bytes=_THIRTY_MIB + 1,
                page_count=1,
            ),
            valid_descriptor(
                file_type="pdf",
                mime_type="application/pdf",
                page_count=None,
            ),
            valid_descriptor(
                file_type="pdf",
                mime_type="image/png",
                page_count=1,
            ),
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    InternalAttachmentDescriptor(**payload)

    def test_pdf_descriptor_schema_allows_up_to_one_hundred_pages(self):
        descriptor = InternalAttachmentDescriptor(
            **valid_descriptor(
                file_type="pdf",
                mime_type="application/pdf",
                page_count=100,
            )
        )

        self.assertEqual(descriptor.page_count, 100)

    def test_execute_applies_scope_specific_pdf_page_limits(self):
        patient_pdf = valid_descriptor(
            file_type="pdf",
            mime_type="application/pdf",
            page_count=9,
        )
        with self.assertRaises(ValidationError):
            ExecutePlatformChatTurnRequest(
                **valid_execute(attachments=[patient_pdf])
            )

        research_base = {
            "version": 2,
            "patient_id": None,
            "agent_type": "research",
            "attachment_scope": "research",
            "research_options": {
                "enable_web_search": False,
                "types": [],
            },
        }
        accepted = ExecutePlatformChatTurnRequest(
            **valid_execute(
                **research_base,
                attachments=[
                    valid_descriptor(
                        file_type="pdf",
                        mime_type="application/pdf",
                        page_count=100,
                    )
                ],
            )
        )
        self.assertEqual(accepted.attachments[0].page_count, 100)

        with self.assertRaises(ValidationError):
            ExecutePlatformChatTurnRequest(
                **valid_execute(
                    **research_base,
                    attachments=[
                        valid_descriptor(
                            attachment_id="att-1",
                            file_type="pdf",
                            mime_type="application/pdf",
                            page_count=61,
                        ),
                        valid_descriptor(
                            attachment_id="att-2",
                            file_type="pdf",
                            mime_type="application/pdf",
                            page_count=60,
                        ),
                    ],
                )
            )

    def test_execute_rejects_attachment_total_over_forty_mib(self):
        attachments = [
            valid_descriptor(
                attachment_id=f"att-{index}",
                file_type="pdf",
                mime_type="application/pdf",
                size_bytes=_TEN_MIB + 1,
                page_count=1,
            )
            for index in range(4)
        ]

        with self.assertRaises(ValidationError):
            ExecutePlatformChatTurnRequest(
                request_id="turn-request-1",
                request_fingerprint="1" * 64,
                conversation_id="conversation-1",
                session_id="session-1",
                patient_id="patient-1",
                doctor_id="doctor:42",
                user_message_id="message-user-1",
                assistant_message_id="message-assistant-1",
                attachments=attachments,
            )

    def test_complete_internal_wire_fixture_round_trips_without_key_drift(self):
        fixture = load_fixture("platform_chat_turn_internal_wire_v1.json")
        models = {
            "prepare_request": PreparePlatformChatTurnRequest,
            "prepare_response": PreparePlatformChatTurnResponse,
            "execute_request": ExecutePlatformChatTurnRequest,
            "status_response": PlatformChatTurnStatusResponse,
            "abort_request": AbortPlatformChatTurnRequest,
            "abort_response": AbortPlatformChatTurnResponse,
            "execution_started": PlatformChatTurnExecutionStartedEvent,
            "attachment_status": PlatformAttachmentStatusEvent,
            "done": PlatformChatTurnDoneEvent,
            "error": PlatformChatTurnErrorEvent,
        }

        for key, model in models.items():
            with self.subTest(key=key):
                validated = model.model_validate(fixture[key])
                dumped = json.loads(
                    validated.model_dump_json(
                        by_alias=True,
                        exclude_none=False,
                    )
                )
                self.assertEqual(dumped, fixture[key])

    def test_status_response_uses_persisted_lifecycle_vocabulary(self):
        fixture = load_fixture("platform_chat_turn_internal_wire_v1.json")
        payload = fixture["status_response"]

        for status in (
            "prepared",
            "streaming",
            "completed",
            "failed",
            "cancelled",
        ):
            with self.subTest(status=status):
                validated = PlatformChatTurnStatusResponse.model_validate(
                    {**payload, "status": status}
                )
                self.assertEqual(validated.status, status)

        for legacy_status in ("executing", "done", "error", "aborted"):
            with self.subTest(legacy_status=legacy_status):
                with self.assertRaises(ValidationError):
                    PlatformChatTurnStatusResponse.model_validate(
                        {**payload, "status": legacy_status}
                    )

    def test_attachment_status_uses_attempt_sequence_and_safe_statuses(self):
        fixture = load_fixture("platform_chat_turn_internal_wire_v1.json")
        payload = fixture["attachment_status"]

        for status in ("processing", "ready", "failed"):
            with self.subTest(status=status):
                validated = PlatformAttachmentStatusEvent.model_validate(
                    {**payload, "status": status}
                )
                self.assertEqual(validated.status, status)

        for legacy_status in ("pending", "error"):
            with self.subTest(legacy_status=legacy_status):
                with self.assertRaises(ValidationError):
                    PlatformAttachmentStatusEvent.model_validate(
                        {**payload, "status": legacy_status}
                    )

    def test_control_events_reject_uncontrolled_free_form_fields(self):
        fixture = load_fixture("platform_chat_turn_internal_wire_v1.json")
        cases = (
            (PlatformChatTurnDoneEvent, fixture["done"], "response"),
            (PlatformChatTurnErrorEvent, fixture["error"], "message"),
            (PlatformChatTurnErrorEvent, fixture["error"], "retryable"),
        )

        for model, payload, field in cases:
            with self.subTest(event=payload["event"], field=field):
                with self.assertRaises(ValidationError):
                    model.model_validate({**payload, field: "sensitive text"})


if __name__ == "__main__":
    unittest.main()

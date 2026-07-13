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

    def test_research_options_are_exact_strict_and_keep_institution_setting(self):
        options_type = getattr(turn_schemas, "ResearchOptionsV2", None)
        self.assertIsNotNone(options_type)
        enabled = options_type(
            enable_institution_data=True,
            enable_web_search=True,
            types=["scholar", "general", "pubmed", "general"],
        )
        disabled = options_type(
            enable_institution_data=True,
            enable_web_search=False,
            types=["pubmed"],
        )

        self.assertTrue(enabled.enable_institution_data)
        self.assertTrue(disabled.enable_institution_data)
        self.assertEqual(enabled.types, ["general", "pubmed", "scholar"])
        self.assertEqual(disabled.types, [])

        valid = {
            "enable_institution_data": False,
            "enable_web_search": True,
            "types": ["general"],
        }
        for field in valid:
            with self.subTest(missing=field):
                payload = dict(valid)
                payload.pop(field)
                with self.assertRaises(ValidationError):
                    options_type(**payload)
        for field in ("enable_institution_data", "enable_web_search"):
            for invalid_boolean in (0, 1, "true"):
                with self.subTest(field=field, invalid_boolean=invalid_boolean):
                    payload = dict(valid)
                    payload[field] = invalid_boolean
                    with self.assertRaises(ValidationError):
                        options_type(**payload)
        with self.assertRaises(ValidationError):
            options_type(**valid, unknown=True)

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
                "enable_institution_data": True,
                "enable_web_search": True,
                "types": ["scholar", "general", "general"],
            },
        )

        research = ExecutePlatformChatTurnRequest(**base)
        self.assertTrue(research.research_options.enable_institution_data)
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

    def test_v2_research_text_execute_matches_golden_wire(self):
        payload = load_fixture(
            "platform_chat_turn_internal_wire_v2_research_text.json"
        )

        request = ExecutePlatformChatTurnRequest(**payload)

        self.assertEqual(request.attachments[0].file_type, "text")
        self.assertIsNone(request.attachments[0].page_count)
        self.assertEqual(request.model_dump(mode="json"), payload)

    def test_v2_research_docx_execute_matches_golden_wire(self):
        payload = load_fixture(
            "platform_chat_turn_internal_wire_v2_research_docx.json"
        )
        request = ExecutePlatformChatTurnRequest(**payload)
        self.assertEqual(request.attachments[0].file_type, "docx")
        self.assertIsNone(request.attachments[0].page_count)
        self.assertEqual(request.model_dump(mode="json"), payload)

    def test_v2_research_docx_rejects_invalid_contracts(self):
        invalid_payloads = []
        for field, value in (
            ("size_bytes", 10 * 1024 * 1024 + 1),
            ("page_count", 1),
            ("mime_type", "application/zip"),
        ):
            invalid = load_fixture(
                "platform_chat_turn_internal_wire_v2_research_docx.json"
            )
            invalid["attachments"][0][field] = value
            invalid_payloads.append(invalid)

        for mutation in ("missing_page_count", "health", "v1", "extra"):
            invalid = load_fixture(
                "platform_chat_turn_internal_wire_v2_research_docx.json"
            )
            if mutation == "missing_page_count":
                invalid["attachments"][0].pop("page_count")
            elif mutation == "health":
                invalid.update(
                    patient_id="patient-1",
                    agent_type="health",
                    attachment_scope="patient",
                    research_options=None,
                )
            elif mutation == "v1":
                invalid["version"] = 1
                invalid["patient_id"] = "patient-1"
                for field in ("agent_type", "attachment_scope", "research_options"):
                    invalid.pop(field)
            else:
                invalid["attachments"][0]["content"] = "forbidden"
            invalid_payloads.append(invalid)

        for invalid in invalid_payloads:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValidationError):
                    ExecutePlatformChatTurnRequest(**invalid)

    def test_v2_research_text_rejects_invalid_contracts(self):

        invalid_payloads = []
        for field, value in (
            ("size_bytes", 524289),
            ("page_count", 1),
            ("mime_type", "application/pdf"),
        ):
            invalid = load_fixture(
                "platform_chat_turn_internal_wire_v2_research_text.json"
            )
            invalid["attachments"][0][field] = value
            invalid_payloads.append(invalid)

        missing_page_count = load_fixture(
            "platform_chat_turn_internal_wire_v2_research_text.json"
        )
        missing_page_count["attachments"][0].pop("page_count")
        invalid_payloads.append(missing_page_count)

        health_patient = load_fixture(
            "platform_chat_turn_internal_wire_v2_research_text.json"
        )
        health_patient.update(
            patient_id="patient-1",
            agent_type="health",
            attachment_scope="patient",
            research_options=None,
        )
        invalid_payloads.append(health_patient)

        v1 = load_fixture(
            "platform_chat_turn_internal_wire_v2_research_text.json"
        )
        v1["version"] = 1
        v1["patient_id"] = "patient-1"
        for field in ("agent_type", "attachment_scope", "research_options"):
            v1.pop(field)
        invalid_payloads.append(v1)

        extra_field = load_fixture(
            "platform_chat_turn_internal_wire_v2_research_text.json"
        )
        extra_field["attachments"][0]["content"] = "forbidden"
        invalid_payloads.append(extra_field)

        for invalid in invalid_payloads:
            with self.subTest(invalid=invalid):
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

    def test_internal_descriptor_integer_identity_fields_are_strict(self):
        base = valid_descriptor(
            file_type="pdf",
            filename="paper.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            page_count=1,
            document_version=1,
        )
        for field_name in ("size_bytes", "page_count", "document_version"):
            for invalid_value in (True, False, "1", 1.0, 0, -1):
                with self.subTest(
                    field_name=field_name,
                    invalid_value=repr(invalid_value),
                ):
                    payload = dict(base)
                    payload[field_name] = invalid_value
                    with self.assertRaises(ValidationError):
                        InternalAttachmentDescriptor.model_validate_json(
                            json.dumps(payload)
                        )

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
                "enable_institution_data": False,
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

    def test_done_event_accepts_canonical_attachment_citations(self):
        fixture = load_fixture("platform_chat_turn_internal_wire_v1.json")
        citation = {
            "source_type": "attachment",
            "attachment_id": "attachment-1",
            "document_version": 1,
            "segment_id": "segment-1",
            "locator": {"type": "file"},
            "excerpt": "受控引用片段",
        }

        event = PlatformChatTurnDoneEvent.model_validate(
            {**fixture["done"], "citations": [citation]}
        )

        self.assertEqual(event.citations, [citation])


if __name__ == "__main__":
    unittest.main()

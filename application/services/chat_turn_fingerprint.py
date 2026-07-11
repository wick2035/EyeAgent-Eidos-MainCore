import hashlib
import json
import unicodedata
from typing import Any, Protocol


TURN_EDGE_WHITESPACE_V1 = "\u0009\u000a\u000b\u000c\u000d\u0020"


class TurnFingerprintSource(Protocol):
    version: int
    operation: str
    conversation_id: str
    session_id: str
    patient_id: str
    message: str
    source_message_id: str | None
    implicit_prompt_id: str | None
    attachment_ids: list[str]


def normalize_message(message: str) -> str:
    normalized = unicodedata.normalize("NFC", message)
    normalized = normalized.replace("\r\n", "\n")
    return normalized.strip(TURN_EDGE_WHITESPACE_V1)


def canonical_turn_payload(
    version: int,
    operation: str,
    conversation_id: str,
    session_id: str,
    patient_id: str,
    message: str,
    source_message_id: str | None,
    implicit_prompt_id: str | None,
    attachment_ids: list[str],
) -> dict[str, Any]:
    return {
        "version": version,
        "operation": operation,
        "conversation_id": conversation_id,
        "session_id": session_id,
        "patient_id": patient_id,
        "message": normalize_message(message),
        "source_message_id": source_message_id,
        "implicit_prompt_id": implicit_prompt_id,
        "attachment_ids": list(attachment_ids),
    }


def canonical_turn_json(
    version: int,
    operation: str,
    conversation_id: str,
    session_id: str,
    patient_id: str,
    message: str,
    source_message_id: str | None,
    implicit_prompt_id: str | None,
    attachment_ids: list[str],
) -> str:
    payload = canonical_turn_payload(
        version=version,
        operation=operation,
        conversation_id=conversation_id,
        session_id=session_id,
        patient_id=patient_id,
        message=message,
        source_message_id=source_message_id,
        implicit_prompt_id=implicit_prompt_id,
        attachment_ids=attachment_ids,
    )
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def fingerprint_turn(
    version: int,
    operation: str,
    conversation_id: str,
    session_id: str,
    patient_id: str,
    message: str,
    source_message_id: str | None,
    implicit_prompt_id: str | None,
    attachment_ids: list[str],
) -> str:
    canonical = canonical_turn_json(
        version=version,
        operation=operation,
        conversation_id=conversation_id,
        session_id=session_id,
        patient_id=patient_id,
        message=message,
        source_message_id=source_message_id,
        implicit_prompt_id=implicit_prompt_id,
        attachment_ids=attachment_ids,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def fingerprint_turn_from_request(request: TurnFingerprintSource) -> str:
    return fingerprint_turn(
        version=request.version,
        operation=request.operation,
        conversation_id=request.conversation_id,
        session_id=request.session_id,
        patient_id=request.patient_id,
        message=request.message,
        source_message_id=request.source_message_id,
        implicit_prompt_id=request.implicit_prompt_id,
        attachment_ids=request.attachment_ids,
    )

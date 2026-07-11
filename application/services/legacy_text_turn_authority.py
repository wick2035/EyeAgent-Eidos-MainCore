"""Canonical authority for new text-only platform chat turns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence


_RESEARCH_TYPES = ("general", "pubmed", "scholar")


@dataclass(frozen=True)
class LegacyResearchOptions:
    enable_institution_data: bool
    enable_web_search: bool
    types: tuple[str, ...]

    def to_wire(self) -> dict[str, Any]:
        return {
            "enable_institution_data": self.enable_institution_data,
            "enable_web_search": self.enable_web_search,
            "types": list(self.types),
        }


@dataclass(frozen=True)
class LegacyTextTurnAuthority:
    protocol_version: int
    agent_type: str
    attachment_scope: str
    patient_id: Optional[str]
    research_options: Optional[LegacyResearchOptions]

    def to_turn_configuration(self) -> dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "agent_type": self.agent_type,
            "attachment_scope": self.attachment_scope,
            "research_options": (
                self.research_options.to_wire()
                if self.research_options is not None
                else None
            ),
        }

    def to_message_metadata(self) -> dict[str, Any]:
        return {
            "agent_type": self.agent_type,
            "patient_id": self.patient_id,
            "turn_configuration": self.to_turn_configuration(),
            "attachment_ids": [],
        }

    def graph_research_options(self) -> dict[str, Any]:
        if self.research_options is None:
            return {
                "enable_institution_data": False,
                "enable_web_search": False,
                "web_search_types": [],
            }
        return {
            "enable_institution_data": (
                self.research_options.enable_institution_data
            ),
            "enable_web_search": self.research_options.enable_web_search,
            "web_search_types": list(self.research_options.types),
        }


def _canonical_research_options(
    value: Any,
) -> LegacyResearchOptions:
    if not isinstance(value, dict) or set(value) != {
        "enable_institution_data",
        "enable_web_search",
        "types",
    }:
        raise ValueError("LEGACY_TURN_CONFIGURATION_INVALID")
    institution = value["enable_institution_data"]
    web = value["enable_web_search"]
    types = value["types"]
    if (
        type(institution) is not bool
        or type(web) is not bool
        or not isinstance(types, list)
        or not all(isinstance(item, str) for item in types)
        or len(set(types)) != len(types)
        or any(item not in _RESEARCH_TYPES for item in types)
        or tuple(types) != tuple(
            item for item in _RESEARCH_TYPES if item in types
        )
        or web != bool(types)
    ):
        raise ValueError("LEGACY_TURN_CONFIGURATION_INVALID")
    return LegacyResearchOptions(
        enable_institution_data=institution,
        enable_web_search=web,
        types=tuple(types),
    )


def build_legacy_text_turn_authority(
    *,
    agent_type: str,
    patient_id: Optional[str],
    enable_institution_data: bool = False,
    enable_web_search: bool = False,
    web_search_types: Sequence[str] = (),
) -> LegacyTextTurnAuthority:
    if agent_type == "health":
        if not isinstance(patient_id, str) or not patient_id:
            raise ValueError("LEGACY_TURN_CONFIGURATION_INVALID")
        return LegacyTextTurnAuthority(
            protocol_version=1,
            agent_type="health",
            attachment_scope="patient",
            patient_id=patient_id,
            research_options=None,
        )
    if agent_type != "research" or patient_id is not None:
        raise ValueError("LEGACY_TURN_CONFIGURATION_INVALID")
    if not isinstance(web_search_types, (list, tuple)):
        raise ValueError("LEGACY_TURN_CONFIGURATION_INVALID")
    options = _canonical_research_options({
        "enable_institution_data": enable_institution_data,
        "enable_web_search": enable_web_search,
        "types": list(web_search_types),
    })
    return LegacyTextTurnAuthority(
        protocol_version=2,
        agent_type="research",
        attachment_scope="research",
        patient_id=None,
        research_options=options,
    )


def parse_legacy_text_turn_metadata(
    value: Any,
) -> LegacyTextTurnAuthority:
    if not isinstance(value, dict) or set(value) != {
        "agent_type",
        "patient_id",
        "turn_configuration",
        "attachment_ids",
    }:
        raise ValueError("LEGACY_TURN_CONFIGURATION_INVALID")
    if value["attachment_ids"] != []:
        raise ValueError("LEGACY_TURN_CONFIGURATION_INVALID")
    configuration = value["turn_configuration"]
    if not isinstance(configuration, dict) or set(configuration) != {
        "protocol_version",
        "agent_type",
        "attachment_scope",
        "research_options",
    }:
        raise ValueError("LEGACY_TURN_CONFIGURATION_INVALID")
    protocol = configuration["protocol_version"]
    agent_type = configuration["agent_type"]
    scope = configuration["attachment_scope"]
    patient_id = value["patient_id"]
    if (
        type(protocol) is not int
        or protocol not in (1, 2)
        or value["agent_type"] != agent_type
    ):
        raise ValueError("LEGACY_TURN_CONFIGURATION_INVALID")
    if agent_type == "health":
        if (
            scope != "patient"
            or configuration["research_options"] is not None
            or not isinstance(patient_id, str)
            or not patient_id
        ):
            raise ValueError("LEGACY_TURN_CONFIGURATION_INVALID")
        authority = LegacyTextTurnAuthority(
            protocol_version=protocol,
            agent_type="health",
            attachment_scope="patient",
            patient_id=patient_id,
            research_options=None,
        )
    elif agent_type == "research":
        if protocol != 2 or scope != "research" or patient_id is not None:
            raise ValueError("LEGACY_TURN_CONFIGURATION_INVALID")
        authority = LegacyTextTurnAuthority(
            protocol_version=2,
            agent_type="research",
            attachment_scope="research",
            patient_id=None,
            research_options=_canonical_research_options(
                configuration["research_options"],
            ),
        )
    else:
        raise ValueError("LEGACY_TURN_CONFIGURATION_INVALID")
    if authority.to_message_metadata() != value:
        raise ValueError("LEGACY_TURN_CONFIGURATION_INVALID")
    return authority

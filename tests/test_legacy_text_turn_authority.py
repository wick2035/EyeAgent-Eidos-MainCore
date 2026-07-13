import unittest

from application.services.legacy_text_turn_authority import (
    build_legacy_text_turn_authority,
    parse_legacy_text_turn_metadata,
)


class LegacyTextTurnAuthorityTest(unittest.TestCase):
    def test_builds_exact_health_and_research_metadata(self):
        health = build_legacy_text_turn_authority(
            agent_type="health",
            patient_id="patient-1",
        )
        research = build_legacy_text_turn_authority(
            agent_type="research",
            patient_id=None,
            enable_institution_data=True,
            enable_web_search=True,
            web_search_types=["general", "scholar"],
        )

        self.assertEqual(
            health.to_message_metadata(),
            {
                "agent_type": "health",
                "patient_id": "patient-1",
                "turn_configuration": {
                    "protocol_version": 1,
                    "agent_type": "health",
                    "attachment_scope": "patient",
                    "research_options": None,
                },
                "attachment_ids": [],
            },
        )
        self.assertEqual(
            research.graph_research_options(),
            {
                "enable_institution_data": True,
                "enable_web_search": True,
                "web_search_types": ["general", "scholar"],
            },
        )
        self.assertEqual(
            parse_legacy_text_turn_metadata(
                research.to_message_metadata(),
            ),
            research,
        )

    def test_rejects_noncanonical_or_conflicting_metadata(self):
        valid = build_legacy_text_turn_authority(
            agent_type="research",
            patient_id=None,
            enable_web_search=True,
            web_search_types=["general", "pubmed"],
        ).to_message_metadata()
        invalid = []

        extra = {**valid, "extra": True}
        invalid.append(extra)

        attachments = {**valid, "attachment_ids": ["attachment-1"]}
        invalid.append(attachments)

        wrong_agent = {**valid, "agent_type": "health"}
        invalid.append(wrong_agent)

        wrong_patient = {**valid, "patient_id": "patient-1"}
        invalid.append(wrong_patient)

        options = valid["turn_configuration"]["research_options"]
        wrong_order = {
            **valid,
            "turn_configuration": {
                **valid["turn_configuration"],
                "research_options": {
                    **options,
                    "types": ["pubmed", "general"],
                },
            },
        }
        invalid.append(wrong_order)

        disabled_with_types = {
            **valid,
            "turn_configuration": {
                **valid["turn_configuration"],
                "research_options": {
                    **options,
                    "enable_web_search": False,
                },
            },
        }
        invalid.append(disabled_with_types)

        enabled_without_types = {
            **valid,
            "turn_configuration": {
                **valid["turn_configuration"],
                "research_options": {
                    **options,
                    "types": [],
                },
            },
        }
        invalid.append(enabled_without_types)

        for metadata in invalid:
            with self.subTest(metadata=metadata):
                with self.assertRaises(ValueError):
                    parse_legacy_text_turn_metadata(metadata)

    def test_old_two_field_context_cannot_be_promoted(self):
        with self.assertRaises(ValueError):
            parse_legacy_text_turn_metadata({
                "agent_type": "research",
                "patient_id": None,
            })


if __name__ == "__main__":
    unittest.main()

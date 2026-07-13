import json
import logging
from unittest.mock import patch

from agents.tools.research_tools import (
    get_institution_research_data,
    web_search_medical,
)
from agents.tools.research_tools_v3 import (
    assist_paper_writing,
    check_drug_interactions,
    ethics_review_assistant,
    export_research_data,
    search_clinical_guidelines,
)


class _SearchClient:
    def __init__(self, error=None):
        self.error = error

    @staticmethod
    def is_available():
        return True

    def search_sync(self, *_args):
        if self.error is not None:
            raise self.error
        return {}


def test_web_and_institution_logs_do_not_expose_query_or_principal(caplog):
    query = "PRIVATE_WEB_QUERY_SENTINEL"
    doctor = "PRIVATE_DOCTOR_SENTINEL"
    caplog.set_level(logging.INFO)

    with patch(
        "infrastructure.api.search1api_client.get_search1api_client",
        return_value=_SearchClient(),
    ):
        web_search_medical.invoke(
            {
                "query": query,
                "search_types": "pubmed",
                "max_results": 3,
                "crawl_content": False,
            }
        )
    with patch(
        "agents.tools.research_tools.get_api_client",
        return_value=object(),
    ):
        institution_result = get_institution_research_data.invoke(
            {
                "doctor_id": doctor,
                "data_type": "patients",
            }
        )

    assert query not in caplog.text
    assert doctor not in caplog.text
    assert doctor not in institution_result


def test_v3_success_logs_do_not_expose_model_arguments(caplog):
    sentinels = {
        "section": "PRIVATE_SECTION_SENTINEL",
        "template": "PRIVATE_TEMPLATE_SENTINEL",
        "disease": "PRIVATE_DISEASE_SENTINEL",
        "organization": "PRIVATE_ORGANIZATION_SENTINEL",
        "drug": "PRIVATE_DRUG_SENTINEL",
        "condition": "PRIVATE_CONDITION_SENTINEL",
        "study_type": "PRIVATE_STUDY_TYPE_SENTINEL",
        "export_format": "PRIVATE_EXPORT_FORMAT_SENTINEL",
    }
    caplog.set_level(logging.INFO)

    assist_paper_writing.invoke(
        {
            "section": sentinels["section"],
            "research_data": "PRIVATE_DOCUMENT_BODY_SENTINEL",
            "template_type": sentinels["template"],
        }
    )
    search_clinical_guidelines.invoke(
        {
            "disease": sentinels["disease"],
            "organization": sentinels["organization"],
        }
    )
    check_drug_interactions.invoke(
        {
            "drug_list": sentinels["drug"],
            "patient_conditions": sentinels["condition"],
        }
    )
    ethics_review_assistant.invoke(
        {
            "research_protocol": "PRIVATE_PROTOCOL_SENTINEL",
            "study_type": sentinels["study_type"],
        }
    )
    export_research_data.invoke(
        {
            "data_json": json.dumps([{"value": "PRIVATE_EXPORT_FIELD_SENTINEL"}]),
            "export_format": sentinels["export_format"],
        }
    )

    for sentinel in sentinels.values():
        assert sentinel not in caplog.text
    assert "PRIVATE_DOCUMENT_BODY_SENTINEL" not in caplog.text
    assert "PRIVATE_PROTOCOL_SENTINEL" not in caplog.text
    assert "PRIVATE_EXPORT_FIELD_SENTINEL" not in caplog.text


def test_provider_and_v3_exception_messages_are_redacted_from_logs(caplog):
    web_error = "PRIVATE_WEB_PROVIDER_EXCEPTION_SENTINEL"
    v3_error = "PRIVATE_V3_EXCEPTION_SENTINEL"
    caplog.set_level(logging.ERROR)

    with patch(
        "infrastructure.api.search1api_client.get_search1api_client",
        return_value=_SearchClient(RuntimeError(web_error)),
    ):
        web_result = web_search_medical.invoke(
            {"query": "safe", "search_types": "pubmed"}
        )
    with patch(
        "agents.tools.research_tools_v3.json.loads",
        side_effect=RuntimeError(v3_error),
    ):
        v3_result = export_research_data.invoke(
            {"data_json": "[]", "export_format": "json"}
        )

    assert web_error not in caplog.text
    assert v3_error not in caplog.text
    assert web_error not in web_result
    assert v3_error not in v3_result
    assert "error_type=RuntimeError" in caplog.text

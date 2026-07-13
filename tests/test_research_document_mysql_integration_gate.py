import os
import unittest
from unittest.mock import patch

from tests import test_research_document_repository_mysql_integration as integration


class ResearchDocumentMySQLIntegrationGateTest(unittest.TestCase):
    def test_gate_uses_formal_environment_variable_only(self):
        enabled = integration._mysql_integration_enabled

        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(enabled())
        with patch.dict(
            os.environ,
            {"RUN_MYSQL_INTEGRATION": "1"},
            clear=True,
        ):
            self.assertTrue(enabled())
        with patch.dict(
            os.environ,
            {"RUN_RESEARCH_DOCUMENT_MYSQL_INTEGRATION": "1"},
            clear=True,
        ):
            self.assertFalse(enabled())


if __name__ == "__main__":
    unittest.main()

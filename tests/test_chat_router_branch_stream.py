import unittest
from presentation.schemas.chat_schemas import EditResendRequest, RegenerateRequest


class BranchStreamSchemaTest(unittest.TestCase):
    def test_edit_resend_request_accepts_source_message_id(self):
        req = EditResendRequest(
            message="编辑后的问题",
            patient_id="550e8400-e29b-41d4-a716-446655440000",
            doctor_id="660e8400-e29b-41d4-a716-446655440001",
            conversation_id="c1",
            source_message_id="u1",
        )
        self.assertEqual(req.source_message_id, "u1")

    def test_regenerate_request_accepts_source_assistant_id(self):
        req = RegenerateRequest(
            patient_id="550e8400-e29b-41d4-a716-446655440000",
            doctor_id="660e8400-e29b-41d4-a716-446655440001",
            conversation_id="c1",
            source_message_id="a1",
        )
        self.assertEqual(req.source_message_id, "a1")


if __name__ == "__main__":
    unittest.main()

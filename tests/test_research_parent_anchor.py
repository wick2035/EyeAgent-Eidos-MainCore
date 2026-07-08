import unittest
from pathlib import Path

from presentation.schemas.chat_schemas import ChatRequest
from presentation.schemas.research_schemas import ResearchChatRequest


class ResearchParentAnchorTest(unittest.TestCase):
    def test_accepts_camel_case_parent_anchor_id_from_java_backend(self):
        request = ResearchChatRequest.model_validate({
            "message": "圆锥角膜患病的成因",
            "doctor_id": "660e8400-e29b-41d4-a716-446655440001",
            "conversation_id": "225f96b2db4891364e8f268d4ac8e398",
            "parentAnchorId": "72de306f26483384cb9acd85355556a0",
        })

        self.assertEqual(
            request.parent_anchor_id,
            "72de306f26483384cb9acd85355556a0",
        )

    def test_research_router_forwards_parent_anchor_to_graph_manager(self):
        router_path = Path(__file__).resolve().parents[1] / "presentation" / "routers" / "research_router.py"
        router_source = router_path.read_text()

        self.assertEqual(
            router_source.count("parent_anchor_id=request.parent_anchor_id"),
            2,
        )

    def test_accepts_snake_case_parent_anchor_id(self):
        request = ResearchChatRequest.model_validate({
            "message": "圆锥角膜患病的成因",
            "doctor_id": "660e8400-e29b-41d4-a716-446655440001",
            "conversation_id": "225f96b2db4891364e8f268d4ac8e398",
            "parent_anchor_id": "72de306f26483384cb9acd85355556a0",
        })

        self.assertEqual(
            request.parent_anchor_id,
            "72de306f26483384cb9acd85355556a0",
        )

    def test_chat_request_accepts_dual_answer_tracking_aliases(self):
        request = ChatRequest.model_validate({
            "message": "帮我分析这份报告",
            "patient_id": "550e8400-e29b-41d4-a716-446655440000",
            "doctor_id": "660e8400-e29b-41d4-a716-446655440001",
            "conversation_id": "225f96b2db4891364e8f268d4ac8e398",
            "dualAnswer": True,
            "requestId": "req-001",
            "clientMessageId": "client-msg-001",
        })

        self.assertTrue(request.dual_answer)
        self.assertEqual("req-001", request.request_id)
        self.assertEqual("client-msg-001", request.client_message_id)

    def test_chat_request_treats_real_dual_payload_without_boolean_as_dual(self):
        request = ChatRequest.model_validate({
            "message": "帮我分析这份报告",
            "patient_id": "550e8400-e29b-41d4-a716-446655440000",
            "doctor_id": "660e8400-e29b-41d4-a716-446655440001",
            "conversation_id": "225f96b2db4891364e8f268d4ac8e398",
            "clientMessageId": "client-user-001",
            "clientAssistantMessageId": "client-assistant-001",
            "executionId": "execution-001",
            "anchorMessageId": "anchor-001",
            "dualAnswerGroupId": "dual-group-001",
            "dualAnswerIndex": 0,
        })

        self.assertTrue(request.dual_answer)
        self.assertEqual("dual-group-001", request.dual_answer_group_id)
        self.assertEqual(0, request.dual_answer_index)

    def test_research_request_accepts_dual_answer_tracking_aliases(self):
        request = ResearchChatRequest.model_validate({
            "message": "圆锥角膜患病的成因",
            "doctor_id": "660e8400-e29b-41d4-a716-446655440001",
            "conversation_id": "225f96b2db4891364e8f268d4ac8e398",
            "dualAnswer": True,
            "requestId": "req-002",
            "clientMessageId": "client-msg-002",
        })

        self.assertTrue(request.dual_answer)
        self.assertEqual("req-002", request.request_id)
        self.assertEqual("client-msg-002", request.client_message_id)


if __name__ == "__main__":
    unittest.main()

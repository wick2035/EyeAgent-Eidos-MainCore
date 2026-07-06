import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime

from domain.models.chat_entity import ChatConversationEntity, ChatMessageEntity


class ChatTreeEntityTest(unittest.TestCase):
    def test_entities_expose_tree_fields(self):
        conv = ChatConversationEntity(
            id="c1",
            user_type="doctor",
            host_id="doctor-1",
            title="新对话",
            active_node_id="root-1",
        )
        msg = ChatMessageEntity(
            id="u1",
            chat_id="c1",
            parent_id="root-1",
            siblings_group_id="sg-user-root-1",
            message_order=2,
            message_content="眼睛干涩",
            message_type="user",
            create_time=datetime.now(),
            update_time=datetime.now(),
        )

        self.assertEqual(conv.active_node_id, "root-1")
        self.assertEqual(msg.parent_id, "root-1")
        self.assertEqual(msg.siblings_group_id, "sg-user-root-1")


if __name__ == "__main__":
    unittest.main()

"""
测试聊天消息保存修复
"""
from database.chat_service import ChatService

def test_save_message():
    """测试保存消息到对话"""
    print("=" * 60)
    print("测试: 保存消息到对话")
    print("=" * 60)

    service = ChatService()

    # 创建一个测试对话
    chat_uuid = service.create_chat_for_patient(
        patient_id=1,
        title="测试消息保存",
        conversation_type="general",
        ai_agent="agent_1"
    )

    if not chat_uuid:
        print("[FAILED] 创建对话失败")
        return False

    print(f"[SUCCESS] 创建对话: Chat_UUID={chat_uuid}")

    # 测试保存用户消息
    message_uuid_1 = service.save_message(
        chat_id=chat_uuid,
        message_content="你好，这是测试消息1",
        message_type='user',
        sender_info='patient_1',
        context={'test': 'value1'}
    )

    if not message_uuid_1:
        print("[FAILED] 保存用户消息失败")
        return False

    print(f"[SUCCESS] 保存用户消息: Message_UUID={message_uuid_1}")

    # 测试保存AI消息
    message_uuid_2 = service.save_message(
        chat_id=chat_uuid,
        message_content="你好，我是AI助手",
        message_type='ai',
        sender_info='agent_1',
        context={'test': 'value2'}
    )

    if not message_uuid_2:
        print("[FAILED] 保存AI消息失败")
        return False

    print(f"[SUCCESS] 保存AI消息: Message_UUID={message_uuid_2}")

    # 验证消息已保存
    messages = service.get_chat_messages(chat_id=chat_uuid)

    print(f"\n查询到 {len(messages)} 条消息:")
    for msg in messages:
        print(f"  - Message_ID={msg['Message_ID']}, UUID={msg['Message_UUID']}")
        print(f"    Type={msg['Message_Type']}, Order={msg['Message_Order']}")
        print(f"    Content={msg['Message_Content'][:30]}...")
        print(f"    Chat_ID={msg['Chat_ID']}, Chat_UUID={msg['Chat_UUID']}")

    # 验证对话消息数更新
    chat_info = service.get_chat_by_id(chat_uuid)
    if chat_info:
        print(f"\n对话信息:")
        print(f"  Total_Messages: {chat_info['Total_Messages']}")
        if chat_info['Total_Messages'] == 2:
            print("  [OK] 消息总数正确")
        else:
            print("  [ERROR] 消息总数不正确")
            return False

    print("\n" + "=" * 60)
    print("[SUCCESS] 所有测试通过!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        success = test_save_message()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

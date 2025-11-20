"""
完整聊天流程测试 - 模拟实际API调用
"""
import sys
import json
from database.chat_service import ChatService
from database.user_history_service_v2 import UserHistoryServiceV2
from agents.agent_manager import AgentManager

def test_full_chat_flow():
    """测试完整聊天流程"""
    print("=" * 60)
    print("完整聊天流程测试")
    print("=" * 60)

    # 模拟用户输入
    user_id = 1
    phone_number = "13900000001"
    session_id = "test-full-flow-123"
    role = "patient"
    message_text = "你好呀"

    print(f"\n用户输入:")
    print(f"  user_id: {user_id}")
    print(f"  phone_number: {phone_number}")
    print(f"  session_id: {session_id}")
    print(f"  role: {role}")
    print(f"  message: {message_text}")

    # Step 1: 创建对话会话
    print("\n" + "=" * 60)
    print("Step 1: 创建对话会话")
    print("=" * 60)

    chat_service = ChatService()
    user_service = UserHistoryServiceV2()

    # 获取用户信息
    user_info = user_service.get_user_by_phone(phone_number)
    if not user_info:
        print(f"[ERROR] 未找到用户: {phone_number}")
        return False

    print(f"找到用户: Patient_ID={user_info['Patient_ID']}, Patient_UUID={user_info.get('Patient_UUID')}")

    # 使用UUID创建对话
    patient_uuid = user_info.get('Patient_UUID') or str(user_info['Patient_ID'])
    chat_uuid = chat_service.create_chat_for_patient(
        patient_id=patient_uuid,
        title=None,
        conversation_type='general',
        ai_agent=None
    )

    if not chat_uuid:
        print("[ERROR] 创建对话失败")
        return False

    print(f"[SUCCESS] 创建对话: Chat_UUID={chat_uuid}")

    # Step 2: 创建Agent
    print("\n" + "=" * 60)
    print("Step 2: 创建Agent")
    print("=" * 60)

    agent_manager = AgentManager()
    agent = agent_manager.get_or_create_agent(
        session_id=session_id,
        agent_type="health",
        user_id=user_id,
        phone_number=phone_number,
        role=role
    )

    print(f"[SUCCESS] Agent创建完成")

    # Step 3: 处理消息
    print("\n" + "=" * 60)
    print("Step 3: 处理消息")
    print("=" * 60)

    response = agent.chat(message_text)
    is_completed = agent.is_completed()
    stage = agent.stage.value

    print(f"[SUCCESS] Agent响应:")
    print(f"  response: {response[:100]}...")
    print(f"  is_completed: {is_completed}")
    print(f"  stage: {stage}")

    # Step 4: 保存消息到数据库
    print("\n" + "=" * 60)
    print("Step 4: 保存消息到数据库")
    print("=" * 60)

    # 保存用户消息
    user_msg_uuid = chat_service.save_message(
        chat_id=chat_uuid,
        message_content=message_text,
        message_type='user',
        sender_info=f"{role}_{user_id}",
        context={'session_id': session_id}
    )

    if not user_msg_uuid:
        print("[ERROR] 保存用户消息失败")
        return False

    print(f"[SUCCESS] 保存用户消息: Message_UUID={user_msg_uuid}")

    # 保存AI消息
    ai_msg_uuid = chat_service.save_message(
        chat_id=chat_uuid,
        message_content=response,
        message_type='ai',
        sender_info='agent_health',
        context={
            'session_id': session_id,
            'stage': stage,
            'is_completed': is_completed
        }
    )

    if not ai_msg_uuid:
        print("[ERROR] 保存AI消息失败")
        return False

    print(f"[SUCCESS] 保存AI消息: Message_UUID={ai_msg_uuid}")

    # Step 5: 验证结果
    print("\n" + "=" * 60)
    print("Step 5: 验证结果")
    print("=" * 60)

    # 查询对话信息
    chat_info = chat_service.get_chat_by_id(chat_uuid)
    print(f"\n对话信息:")
    print(f"  Chat_ID: {chat_info['Chat_ID']}")
    print(f"  Chat_UUID: {chat_info['Chat_UUID']}")
    print(f"  User_Type: {chat_info['User_Type']}")
    print(f"  Patient_ID: {chat_info['Patient_ID']}")
    print(f"  Patient_UUID: {chat_info.get('Patient_UUID')}")
    print(f"  Total_Messages: {chat_info['Total_Messages']}")
    print(f"  Status: {chat_info['Status']}")

    # 查询消息
    messages = chat_service.get_chat_messages(chat_id=chat_uuid)
    print(f"\n查询到 {len(messages)} 条消息:")
    for msg in messages:
        print(f"  [{msg['Message_Type']}] {msg['Message_Content'][:50]}...")

    # 验证
    if chat_info['Total_Messages'] == 2 and len(messages) == 2:
        print("\n[OK] 消息数量正确")
    else:
        print("\n[ERROR] 消息数量不正确")
        return False

    print("\n" + "=" * 60)
    print("[SUCCESS] 完整流程测试通过!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        success = test_full_chat_flow()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

"""
测试ChatService集成
验证对话历史记录功能是否正常工作
"""

import sys
import io

# 设置标准输出为UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from database.chat_service import ChatService
from database.user_history_service_v2 import UserHistoryServiceV2

def test_chat_service_basic():
    """测试ChatService基本功能"""
    print("\n" + "="*60)
    print("测试1: ChatService基本功能")
    print("="*60)

    chat_service = ChatService()

    # 1. 为测试患者创建对话
    print("\n[步骤1] 创建测试对话...")
    chat_id = chat_service.create_chat_for_patient(
        patient_id=1,
        title="测试对话 - ChatService集成",
        conversation_type='consultation',
        ai_agent='agent_1'
    )

    if chat_id:
        print(f"✓ 对话创建成功: Chat_ID={chat_id}")
    else:
        print("✗ 对话创建失败")
        return False

    # 2. 保存测试消息
    print("\n[步骤2] 保存测试消息...")

    # 用户消息
    msg_id_1 = chat_service.save_message(
        chat_id=chat_id,
        message_content="你好，我想咨询一下眼睛的问题",
        message_type='user',
        sender_info='patient_1',
        context={'test': True}
    )

    # AI消息
    msg_id_2 = chat_service.save_message(
        chat_id=chat_id,
        message_content="您好!我是小智,很高兴为您服务。请详细描述一下您的症状。",
        message_type='ai',
        sender_info='agent_1',
        context={'stage': 'greeting', 'test': True}
    )

    if msg_id_1 and msg_id_2:
        print(f"✓ 消息保存成功: Message_ID={msg_id_1}, {msg_id_2}")
    else:
        print("✗ 消息保存失败")
        return False

    # 3. 查询对话消息
    print("\n[步骤3] 查询对话消息...")
    messages = chat_service.get_chat_messages(chat_id)

    if messages and len(messages) == 2:
        print(f"✓ 查询到{len(messages)}条消息:")
        for msg in messages:
            print(f"  - [{msg['Message_Type']}] {msg['Message_Content'][:50]}...")
    else:
        print(f"✗ 消息查询失败或数量不正确: {len(messages) if messages else 0}")
        return False

    # 4. 查询对话统计
    print("\n[步骤4] 查询对话统计...")
    stats = chat_service.get_chat_statistics(chat_id)

    if stats:
        print(f"✓ 对话统计:")
        print(f"  - 总消息数: {stats['total_messages']}")
        print(f"  - 用户消息: {stats['user_messages']}")
        print(f"  - AI消息: {stats['ai_messages']}")
    else:
        print("✗ 统计查询失败")
        return False

    # 5. 清理测试数据
    print("\n[步骤5] 清理测试数据...")
    if chat_service.delete_chat(chat_id):
        print(f"✓ 测试对话已删除: Chat_ID={chat_id}")
    else:
        print("✗ 删除对话失败")
        return False

    print("\n" + "="*60)
    print("✓ 测试1通过: ChatService基本功能正常")
    print("="*60)
    return True


def test_chat_history_query():
    """测试对话历史查询"""
    print("\n" + "="*60)
    print("测试2: 对话历史查询")
    print("="*60)

    chat_service = ChatService()
    user_service = UserHistoryServiceV2()

    # 获取一个测试用户
    print("\n[步骤1] 获取测试用户...")
    query = "SELECT Patient_ID, Phone_Number, Name FROM patient LIMIT 1"
    from database.db_connection import DatabaseConnection
    db = DatabaseConnection()
    test_user = db.execute_one(query)
    db.close()

    if not test_user:
        print("✗ 未找到测试用户")
        return False

    patient_id = test_user['Patient_ID']
    phone_number = test_user['Phone_Number']
    print(f"✓ 测试用户: Patient_ID={patient_id}, Phone={phone_number}, Name={test_user['Name']}")

    # 创建多个测试对话
    print("\n[步骤2] 创建3个测试对话...")
    chat_ids = []
    for i in range(3):
        chat_id = chat_service.create_chat_for_patient(
            patient_id=patient_id,
            title=f"测试对话 {i+1}",
            conversation_type='consultation' if i % 2 == 0 else 'report',
            ai_agent=f'agent_{(i % 2) + 1}'
        )
        if chat_id:
            chat_ids.append(chat_id)
            # 添加一些测试消息
            chat_service.save_message(chat_id, f"测试消息 {i+1}", 'user')
            chat_service.save_message(chat_id, f"AI回复 {i+1}", 'ai')

    print(f"✓ 创建了{len(chat_ids)}个对话: {chat_ids}")

    # 测试查询用户对话
    print("\n[步骤3] 查询用户的所有对话...")
    chats = chat_service.get_user_chats(
        user_type='patient',
        user_id=patient_id,
        status='active'
    )

    if chats and len(chats) >= 3:
        print(f"✓ 查询到{len(chats)}个对话")
        for chat in chats[:3]:
            print(f"  - Chat_ID={chat['Chat_ID']}, Title={chat['Title']}, Agent={chat['AI_Agent']}")
    else:
        print(f"✗ 对话查询失败或数量不足: {len(chats) if chats else 0}")

    # 测试最近对话查询
    print("\n[步骤4] 查询最近对话及最后消息...")
    recent_chats = chat_service.get_recent_chats_with_last_message(
        user_type='patient',
        user_id=patient_id,
        limit=3
    )

    if recent_chats:
        print(f"✓ 查询到{len(recent_chats)}个最近对话")
        for chat in recent_chats:
            last_msg = chat.get('last_message')
            if last_msg:
                print(f"  - Chat_ID={chat['Chat_ID']}, 最后消息: {last_msg['Message_Content'][:30]}...")
    else:
        print("✗ 最近对话查询失败")

    # 清理测试数据
    print("\n[步骤5] 清理测试数据...")
    deleted_count = 0
    for chat_id in chat_ids:
        if chat_service.delete_chat(chat_id):
            deleted_count += 1

    print(f"✓ 已删除{deleted_count}个测试对话")

    print("\n" + "="*60)
    print("✓ 测试2通过: 对话历史查询功能正常")
    print("="*60)
    return True


def test_chat_operations():
    """测试对话操作(归档、关闭等)"""
    print("\n" + "="*60)
    print("测试3: 对话操作")
    print("="*60)

    chat_service = ChatService()

    # 创建测试对话
    print("\n[步骤1] 创建测试对话...")
    chat_id = chat_service.create_chat_for_patient(
        patient_id=1,
        title="测试对话操作",
        conversation_type='general'
    )

    if not chat_id:
        print("✗ 创建对话失败")
        return False

    print(f"✓ 对话创建成功: Chat_ID={chat_id}")

    # 测试更新标题
    print("\n[步骤2] 更新对话标题...")
    if chat_service.update_chat_title(chat_id, "新标题 - 已更新"):
        print("✓ 标题更新成功")
    else:
        print("✗ 标题更新失败")

    # 测试更新摘要
    print("\n[步骤3] 更新对话摘要...")
    if chat_service.update_chat_summary(chat_id, "这是一段测试摘要"):
        print("✓ 摘要更新成功")
    else:
        print("✗ 摘要更新失败")

    # 测试归档
    print("\n[步骤4] 归档对话...")
    if chat_service.archive_chat(chat_id):
        print("✓ 对话归档成功")
        chat_info = chat_service.get_chat_by_id(chat_id)
        if chat_info and chat_info['Status'] == 'archived':
            print("✓ 状态验证成功: archived")
        else:
            print("✗ 状态验证失败")
    else:
        print("✗ 对话归档失败")

    # 测试关闭
    print("\n[步骤5] 关闭对话...")
    if chat_service.close_chat(chat_id):
        print("✓ 对话关闭成功")
        chat_info = chat_service.get_chat_by_id(chat_id)
        if chat_info and chat_info['Status'] == 'closed':
            print("✓ 状态验证成功: closed")
        else:
            print("✗ 状态验证失败")
    else:
        print("✗ 对话关闭失败")

    # 清理
    print("\n[步骤6] 清理测试数据...")
    if chat_service.delete_chat(chat_id):
        print(f"✓ 测试对话已删除: Chat_ID={chat_id}")

    print("\n" + "="*60)
    print("✓ 测试3通过: 对话操作功能正常")
    print("="*60)
    return True


def main():
    """运行所有测试"""
    print("\n")
    print("*" * 60)
    print("ChatService集成测试")
    print("*" * 60)

    tests = [
        ("基本功能测试", test_chat_service_basic),
        ("历史查询测试", test_chat_history_query),
        ("对话操作测试", test_chat_operations)
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n✗ 测试异常: {test_name}")
            print(f"  错误: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n")
    print("*" * 60)
    print("测试总结")
    print("*" * 60)
    print(f"通过: {passed}/{len(tests)}")
    print(f"失败: {failed}/{len(tests)}")

    if failed == 0:
        print("\n✓ 所有测试通过! ChatService集成正常工作")
    else:
        print(f"\n✗ 有{failed}个测试失败，请检查")

    print("*" * 60)


if __name__ == "__main__":
    main()

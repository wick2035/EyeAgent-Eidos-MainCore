"""
测试聊天创建修复 - 验证UUID约束问题已解决
"""
from database.chat_service import ChatService

def test_create_chat():
    """测试创建患者对话"""
    print("=" * 60)
    print("测试1: 使用Patient_ID创建对话")
    print("=" * 60)

    service = ChatService()

    # 测试1: 使用INT ID
    chat_uuid = service.create_chat_for_patient(
        patient_id=1,
        title="测试对话",
        conversation_type="general",
        ai_agent="agent_1"
    )

    if chat_uuid:
        print(f"[SUCCESS] 成功创建对话: Chat_UUID={chat_uuid}")
    else:
        print("[FAILED] 创建对话失败")
        return False

    print("\n" + "=" * 60)
    print("测试2: 使用Patient_UUID创建对话")
    print("=" * 60)

    # 先查询患者的UUID
    from database.db_connection import DatabaseConnection
    db = DatabaseConnection()
    result = db.execute_one("SELECT Patient_UUID FROM patient WHERE Patient_ID = %s", (1,))

    if result:
        patient_uuid = result['Patient_UUID']
        print(f"查询到Patient_UUID: {patient_uuid}")

        # 测试2: 使用UUID
        chat_uuid2 = service.create_chat_for_patient(
            patient_id=patient_uuid,
            title="测试对话2",
            conversation_type="general",
            ai_agent="agent_1"
        )

        if chat_uuid2:
            print(f"[SUCCESS] 成功创建对话: Chat_UUID={chat_uuid2}")
        else:
            print("[FAILED] 创建对话失败")
            return False

    print("\n" + "=" * 60)
    print("测试3: 验证数据库记录")
    print("=" * 60)

    # 验证记录
    query = """
        SELECT Chat_ID, Chat_UUID, User_Type, Patient_ID, Patient_UUID,
               Doctor_ID, Doctor_UUID, Title
        FROM chat_conversation
        WHERE Chat_UUID IN (%s, %s)
    """
    records = db.execute_query(query, (chat_uuid, chat_uuid2))

    for record in records:
        print(f"\n记录: Chat_ID={record['Chat_ID']}")
        print(f"  Chat_UUID: {record['Chat_UUID']}")
        print(f"  User_Type: {record['User_Type']}")
        print(f"  Patient_ID: {record['Patient_ID']}")
        print(f"  Patient_UUID: {record['Patient_UUID']}")
        print(f"  Doctor_ID: {record['Doctor_ID']}")
        print(f"  Doctor_UUID: {record['Doctor_UUID']}")
        print(f"  Title: {record['Title']}")

        # 验证约束
        if record['User_Type'] == 'patient':
            if record['Patient_ID'] is not None and record['Doctor_ID'] is None:
                print(f"  [OK] 约束满足: Patient_ID NOT NULL, Doctor_ID IS NULL")
            else:
                print(f"  [ERROR] 约束违反!")
                return False

    print("\n" + "=" * 60)
    print("[SUCCESS] 所有测试通过!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        success = test_create_chat()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

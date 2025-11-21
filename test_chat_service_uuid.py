"""
测试chat_service的UUID支持
"""
from database.chat_service import ChatService
from database.db_connection import DatabaseConnection

def test_create_chat_for_patient():
    """测试为患者创建对话"""
    print("=" * 60)
    print("测试为患者创建对话（使用UUID）")
    print("=" * 60)

    db = DatabaseConnection()
    chat_service = ChatService()

    try:
        # 先查询一个存在的患者UUID
        patient_query = "SELECT Patient_UUID, Name FROM patient WHERE Deleted = 0 LIMIT 1"
        patient = db.execute_one(patient_query)

        if not patient:
            print("[ERROR] 数据库中没有患者记录")
            return

        patient_uuid = patient['Patient_UUID']
        patient_name = patient['Name']
        print(f"\n使用患者: {patient_name} (UUID: {patient_uuid})")

        # 创建对话
        print("\n正在创建对话...")
        chat_uuid = chat_service.create_chat_for_patient(
            patient_id=patient_uuid,
            title="测试对话",
            conversation_type="general",
            ai_agent="agent_1"
        )

        if chat_uuid:
            print(f"[OK] 对话创建成功: Chat_UUID={chat_uuid}")

            # 验证对话是否真的创建成功
            verify_query = """
                SELECT Chat_UUID, User_Type, Patient_UUID, Title
                FROM chat_conversation
                WHERE Chat_UUID = %s
            """
            chat = db.execute_one(verify_query, (chat_uuid,))
            if chat:
                print(f"[OK] 验证成功，对话详情: {chat}")
            else:
                print(f"[ERROR] 验证失败，未找到刚创建的对话")
        else:
            print("[ERROR] 对话创建失败")

    except Exception as e:
        print(f"[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def test_create_chat_for_doctor():
    """测试为医生创建对话"""
    print("\n" + "=" * 60)
    print("测试为医生创建对话（使用UUID）")
    print("=" * 60)

    db = DatabaseConnection()
    chat_service = ChatService()

    try:
        # 先查询一个存在的医生UUID
        doctor_query = "SELECT Doctor_UUID, Name FROM doctor WHERE Deleted = 0 AND is_active = 1 LIMIT 1"
        doctor = db.execute_one(doctor_query)

        if not doctor:
            print("[ERROR] 数据库中没有医生记录")
            return

        doctor_uuid = doctor['Doctor_UUID']
        doctor_name = doctor['Name']
        print(f"\n使用医生: {doctor_name} (UUID: {doctor_uuid})")

        # 创建对话
        print("\n正在创建对话...")
        chat_uuid = chat_service.create_chat_for_doctor(
            doctor_id=doctor_uuid,
            title="医生测试对话",
            conversation_type="general",
            ai_agent="agent_2"
        )

        if chat_uuid:
            print(f"[OK] 对话创建成功: Chat_UUID={chat_uuid}")

            # 验证对话是否真的创建成功
            verify_query = """
                SELECT Chat_UUID, User_Type, Doctor_UUID, Title
                FROM chat_conversation
                WHERE Chat_UUID = %s
            """
            chat = db.execute_one(verify_query, (chat_uuid,))
            if chat:
                print(f"[OK] 验证成功，对话详情: {chat}")
            else:
                print(f"[ERROR] 验证失败，未找到刚创建的对话")
        else:
            print("[ERROR] 对话创建失败")

    except Exception as e:
        print(f"[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    print("开始测试chat_service的UUID支持...\n")

    test_create_chat_for_patient()
    test_create_chat_for_doctor()

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

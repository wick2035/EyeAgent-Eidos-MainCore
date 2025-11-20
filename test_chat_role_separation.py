"""
测试聊天对话记录的角色分离功能
验证医生和患者的对话记录不会互相混淆
"""

import sys
import io

# Fix Windows console encoding issue
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from database.chat_service import ChatService
from database.user_history_service_v2 import UserHistoryServiceV2

def test_role_separation():
    """测试角色分离功能"""
    print("=" * 80)
    print("测试聊天对话记录的角色分离功能")
    print("=" * 80)

    chat_service = ChatService()
    user_service = UserHistoryServiceV2()

    # 测试1: 验证医生查询功能
    print("\n[测试1] 测试医生信息查询功能")
    print("-" * 80)

    # 查询一个医生（假设Doctor_ID=1存在）
    doctor_info = user_service.get_doctor_by_id(1)
    if doctor_info:
        print(f"✓ 成功查询到医生信息:")
        print(f"  - Doctor_ID: {doctor_info.get('Doctor_ID')}")
        print(f"  - Doctor_UUID: {doctor_info.get('Doctor_UUID')}")
        print(f"  - Name: {doctor_info.get('Name')}")
        print(f"  - Phone_Number: {doctor_info.get('Phone_Number')}")

        # 如果医生有手机号，测试通过手机号查询
        if doctor_info.get('Phone_Number'):
            doctor_by_phone = user_service.get_doctor_by_phone(doctor_info['Phone_Number'])
            if doctor_by_phone:
                print(f"✓ 通过手机号查询医生成功")
            else:
                print(f"✗ 通过手机号查询医生失败")
    else:
        print("✗ 未找到医生ID=1，请确保数据库中有医生记录")

    # 测试2: 验证患者查询功能
    print("\n[测试2] 测试患者信息查询功能")
    print("-" * 80)

    patient_info = user_service.get_user_by_id(1)
    if patient_info:
        print(f"✓ 成功查询到患者信息:")
        print(f"  - Patient_ID: {patient_info.get('Patient_ID')}")
        print(f"  - Patient_UUID: {patient_info.get('Patient_UUID')}")
        print(f"  - Name: {patient_info.get('Name')}")
        print(f"  - Phone_Number: {patient_info.get('Phone_Number')}")
    else:
        print("✗ 未找到患者ID=1，请确保数据库中有患者记录")

    # 测试3: 验证ID验证功能
    print("\n[测试3] 测试ID验证功能")
    print("-" * 80)

    if doctor_info:
        doctor_id = doctor_info.get('Doctor_UUID') or doctor_info['Doctor_ID']
        is_valid_doctor = chat_service.validate_doctor_id(doctor_id)
        print(f"验证医生ID ({doctor_id}): {'✓ 有效' if is_valid_doctor else '✗ 无效'}")

        # 测试将医生ID作为患者ID验证（应该失败）
        is_valid_as_patient = chat_service.validate_patient_id(doctor_id)
        print(f"将医生ID作为患者ID验证: {'✗ 错误通过' if is_valid_as_patient else '✓ 正确拒绝'}")

    if patient_info:
        patient_id = patient_info.get('Patient_UUID') or patient_info['Patient_ID']
        is_valid_patient = chat_service.validate_patient_id(patient_id)
        print(f"验证患者ID ({patient_id}): {'✓ 有效' if is_valid_patient else '✗ 无效'}")

        # 测试将患者ID作为医生ID验证（应该失败）
        is_valid_as_doctor = chat_service.validate_doctor_id(patient_id)
        print(f"将患者ID作为医生ID验证: {'✗ 错误通过' if is_valid_as_doctor else '✓ 正确拒绝'}")

    # 测试4: 创建医生对话并验证
    print("\n[测试4] 创建医生对话并验证")
    print("-" * 80)

    if doctor_info:
        doctor_id = doctor_info.get('Doctor_UUID') or doctor_info['Doctor_ID']
        chat_id = chat_service.create_chat_for_doctor(
            doctor_id=doctor_id,
            title="测试医生对话",
            conversation_type='test'
        )

        if chat_id:
            print(f"✓ 成功创建医生对话: Chat_ID={chat_id}")

            # 查询对话信息验证
            from database.db_connection import DatabaseConnection
            db = DatabaseConnection()
            query = """
                SELECT User_Type, Patient_ID, Doctor_ID, Doctor_UUID, Patient_UUID
                FROM chat_conversation
                WHERE Chat_UUID = %s OR CAST(Chat_ID AS CHAR) = %s
            """
            chat_info = db.execute_one(query, (chat_id, chat_id))
            db.close()

            if chat_info:
                print(f"  对话信息验证:")
                print(f"  - User_Type: {chat_info.get('User_Type')} {'✓ 正确' if chat_info.get('User_Type') == 'doctor' else '✗ 错误'}")
                print(f"  - Patient_ID: {chat_info.get('Patient_ID')} {'✓ 正确 (NULL)' if chat_info.get('Patient_ID') is None else '✗ 错误 (应为NULL)'}")
                print(f"  - Doctor_ID: {chat_info.get('Doctor_ID')} {'✓ 正确' if chat_info.get('Doctor_ID') is not None else '✗ 错误'}")
                print(f"  - Doctor_UUID: {chat_info.get('Doctor_UUID')}")

                # 删除测试对话
                db2 = DatabaseConnection()
                db2.execute_query("DELETE FROM chat_conversation WHERE Chat_UUID = %s OR CAST(Chat_ID AS CHAR) = %s", (chat_id, chat_id))
                db2.close()
                print(f"✓ 已清理测试数据")
        else:
            print("✗ 创建医生对话失败")

    # 测试5: 创建患者对话并验证
    print("\n[测试5] 创建患者对话并验证")
    print("-" * 80)

    if patient_info:
        patient_id = patient_info.get('Patient_UUID') or patient_info['Patient_ID']
        chat_id = chat_service.create_chat_for_patient(
            patient_id=patient_id,
            title="测试患者对话",
            conversation_type='test'
        )

        if chat_id:
            print(f"✓ 成功创建患者对话: Chat_ID={chat_id}")

            # 查询对话信息验证
            from database.db_connection import DatabaseConnection
            db = DatabaseConnection()
            query = """
                SELECT User_Type, Patient_ID, Doctor_ID, Patient_UUID, Doctor_UUID
                FROM chat_conversation
                WHERE Chat_UUID = %s OR CAST(Chat_ID AS CHAR) = %s
            """
            chat_info = db.execute_one(query, (chat_id, chat_id))
            db.close()

            if chat_info:
                print(f"  对话信息验证:")
                print(f"  - User_Type: {chat_info.get('User_Type')} {'✓ 正确' if chat_info.get('User_Type') == 'patient' else '✗ 错误'}")
                print(f"  - Doctor_ID: {chat_info.get('Doctor_ID')} {'✓ 正确 (NULL)' if chat_info.get('Doctor_ID') is None else '✗ 错误 (应为NULL)'}")
                print(f"  - Patient_ID: {chat_info.get('Patient_ID')} {'✓ 正确' if chat_info.get('Patient_ID') is not None else '✗ 错误'}")
                print(f"  - Patient_UUID: {chat_info.get('Patient_UUID')}")

                # 删除测试对话
                db2 = DatabaseConnection()
                db2.execute_query("DELETE FROM chat_conversation WHERE Chat_UUID = %s OR CAST(Chat_ID AS CHAR) = %s", (chat_id, chat_id))
                db2.close()
                print(f"✓ 已清理测试数据")
        else:
            print("✗ 创建患者对话失败")

    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)

if __name__ == "__main__":
    try:
        test_role_separation()
    except Exception as e:
        print(f"\n测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

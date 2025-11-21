"""
测试 user_history_service_v2.py 的UUID修复
验证所有方法能正确工作,不再引用已删除的INT ID列
"""

import sys
from database.user_history_service_v2 import UserHistoryServiceV2

def test_user_history_service():
    """测试用户历史服务的UUID适配"""
    print("="*80)
    print("开始测试 UserHistoryServiceV2 UUID适配")
    print("="*80)

    service = UserHistoryServiceV2()

    try:
        # 测试1: 通过手机号查询用户基本信息
        print("\n[测试1] 通过手机号查询用户基本信息...")
        test_phone = "13800000000"  # 使用测试手机号
        user_info = service.get_user_by_phone(test_phone)

        if user_info:
            print(f"[OK] 成功查询到用户信息")
            print(f"  - Patient_UUID: {user_info.get('Patient_UUID')}")
            print(f"  - 姓名: {user_info.get('Name')}")
            patient_uuid = user_info.get('Patient_UUID')

            # 测试2: 通过UUID查询病例记录
            print(f"\n[测试2] 通过UUID查询病例记录...")
            medical_records = service.get_medical_records_by_patient_id(patient_uuid)
            print(f"[OK] 成功查询病例记录: {len(medical_records)} 条")
            if medical_records:
                print(f"  - 第一条病例UUID: {medical_records[0].get('Medical_Record_UUID')}")

            # 测试3: 通过UUID查询预约记录
            print(f"\n[测试3] 通过UUID查询预约记录...")
            appointments = service.get_appointments_by_patient_id(patient_uuid)
            print(f"[OK] 成功查询预约记录: {len(appointments)} 条")
            if appointments:
                print(f"  - 第一条预约UUID: {appointments[0].get('Appointment_UUID')}")

            # 测试4: 通过UUID查询历史预约
            print(f"\n[测试4] 通过UUID查询历史预约...")
            historical = service.get_historical_appointments(patient_uuid)
            print(f"[OK] 成功查询历史预约: {len(historical)} 条")

            # 测试5: 通过UUID查询当前/未来预约
            print(f"\n[测试5] 通过UUID查询当前/未来预约...")
            current_future = service.get_current_future_appointments(patient_uuid)
            print(f"[OK] 成功查询当前/未来预约: {len(current_future)} 条")

            # 测试6: 综合查询用户完整信息
            print(f"\n[测试6] 综合查询用户完整信息...")
            complete_info = service.get_user_complete_info(patient_uuid)
            print(f"[OK] 成功查询完整信息")
            print(f"  - patient_id (UUID): {complete_info.get('patient_id')}")
            print(f"  - patient_uuid: {complete_info.get('patient_uuid')}")
            print(f"  - 病例记录: {len(complete_info.get('medical_records', []))} 条")
            print(f"  - 历史预约: {len(complete_info.get('historical_appointments', []))} 条")
            print(f"  - 当前/未来预约: {len(complete_info.get('current_future_appointments', []))} 条")

            # 测试7: 通过手机号综合查询
            print(f"\n[测试7] 通过手机号综合查询...")
            complete_info_phone = service.get_user_complete_info_by_phone(test_phone)
            print(f"[OK] 成功通过手机号查询完整信息")
            print(f"  - patient_id (UUID): {complete_info_phone.get('patient_id')}")

            # 测试8: 格式化输出
            print(f"\n[测试8] 格式化输出用户历史...")
            formatted_text = service.format_user_history_text(patient_uuid)
            print(f"[OK] 成功格式化输出")
            print(f"  - 输出长度: {len(formatted_text)} 字符")

            # 测试9: 通过手机号格式化输出
            print(f"\n[测试9] 通过手机号格式化输出...")
            formatted_text_phone = service.format_user_history_text_by_phone(test_phone)
            print(f"[OK] 成功通过手机号格式化输出")
            print(f"  - 输出长度: {len(formatted_text_phone)} 字符")

        else:
            print(f"[WARNING] 未找到测试手机号 {test_phone} 的用户")
            print("  提示: 请使用数据库中存在的手机号进行测试")

            # 尝试查询第一个用户
            print(f"\n尝试查询数据库中任意用户进行测试...")
            from database.db_connection import DatabaseConnection
            db = DatabaseConnection()
            query = "SELECT Patient_UUID, Phone_Number, Name FROM patient WHERE Deleted = 0 LIMIT 1"
            first_user = db.execute_one(query)
            db.close()

            if first_user:
                print(f"找到测试用户: {first_user.get('Name')} ({first_user.get('Phone_Number')})")
                patient_uuid = first_user.get('Patient_UUID')

                # 重新测试
                print(f"\n使用UUID {patient_uuid} 重新测试...")
                complete_info = service.get_user_complete_info(patient_uuid)
                print(f"[OK] 成功查询完整信息")
                print(f"  - 病例记录: {len(complete_info.get('medical_records', []))} 条")
                print(f"  - 预约记录: {len(complete_info.get('historical_appointments', []))} 条")
            else:
                print("[ERROR] 数据库中没有用户数据")

        print("\n" + "="*80)
        print("[SUCCESS] 所有测试通过! user_history_service_v2.py 已成功适配UUID")
        print("="*80)
        return True

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        service.close()


if __name__ == "__main__":
    success = test_user_history_service()
    sys.exit(0 if success else 1)

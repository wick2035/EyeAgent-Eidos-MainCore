"""
测试完整预约流程 - UUID迁移后
"""
import sys
sys.path.append('d:\\Agent\\pythonProject1')

from database.appointment_service_v3 import AppointmentServiceV3

def test_full_appointment_flow():
    """测试完整的预约流程"""
    service = AppointmentServiceV3()

    print("=== 测试UUID迁移后的预约流程 ===\n")

    # 准备测试数据
    patient_data = {
        'patient_info': {
            'name': 'UUID测试患者',
            'contact': '13900000888',
            'phone': '13900000888',
            'gender': '男',
            'age': 35
        },
        'appointment': {
            'department': '眼科',
            'preferred_time': '明天上午',
            'urgency': '普通'
        },
        'chief_complaint': '视力模糊',
        'present_illness': '近期视力下降明显',
        'medical_history': '无',
        'allergy_history': '无',
        'family_history': '无',
        'medication_history': '无'
    }

    try:
        print("步骤1: 开始预约流程...")
        result = service.process_appointment(patient_data)

        print(f"\n预约结果: {result['success']}")
        print(f"消息: {result['message']}")

        if result['success']:
            print(f"\n✅ 预约成功!")
            print(f"预约ID (UUID): {result['appointment_id']}")

            details = result.get('appointment_details', {})
            print(f"\n预约详情:")
            print(f"  - 患者UUID: {details.get('patient_id', '')[:8]}...")
            print(f"  - 患者姓名: {details.get('patient_name')}")
            print(f"  - 病例UUID: {details.get('medical_record_id', '')[:8]}...")
            print(f"  - 医生: {details.get('doctor_name')} ({details.get('doctor_title')})")
            print(f"  - 预约时间: {details.get('appointment_time')}")
            print(f"  - 科室: {details.get('department')}")
            print(f"  - 时间段UUID: {details.get('slot_id', '')[:8]}...")

            # 验证数据库
            print(f"\n步骤2: 验证数据库记录...")
            verify_db_query = """
                SELECT Appointment_UUID, Patient_UUID, Medical_Record_UUID,
                       Doctor_UUID, Patient_Name, Appointment_Time
                FROM appointment
                WHERE Appointment_UUID = %s
            """
            db_result = service.db.execute_one(verify_db_query, (result['appointment_id'],))

            if db_result:
                print(f"✅ 数据库验证成功:")
                print(f"  - Appointment_UUID: {db_result['Appointment_UUID'][:8]}...")
                print(f"  - Patient_UUID: {db_result['Patient_UUID'][:8]}...")
                print(f"  - Medical_Record_UUID: {db_result['Medical_Record_UUID'][:8]}...")
                print(f"  - Doctor_UUID: {db_result['Doctor_UUID'][:8]}...")
                print(f"  - 患者姓名: {db_result['Patient_Name']}")
                print(f"  - 预约时间: {db_result['Appointment_Time']}")

                print(f"\n✅✅✅ 所有测试通过! UUID迁移成功!")
            else:
                print(f"❌ 数据库验证失败: 未找到预约记录")
        else:
            print(f"\n❌ 预约失败")
            print(f"失败原因: {result['message']}")

    except Exception as e:
        print(f"\n❌❌❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_full_appointment_flow()

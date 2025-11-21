"""
测试预约流程中的UUID问题
"""
import sys
sys.path.append('d:\\Agent\\pythonProject1')

from database.appointment_service_v3 import AppointmentServiceV3

def test_medical_record_creation():
    """测试病例创建是否正确返回UUID"""
    service = AppointmentServiceV3()

    # 准备测试数据
    patient_info = {
        'name': 'UUID测试患者',
        'phone': '13900000999',
        'gender': '男',
        'age': 30
    }

    patient_data = {
        'patient_info': patient_info,
        'appointment': {
            'department': '眼科',
            'urgency': '普通'
        },
        'chief_complaint': 'UUID测试主诉',
        'present_illness': 'UUID测试现病史'
    }

    # 步骤1：创建患者
    print("=== 步骤1：创建患者 ===")
    patient_uuid = service.create_or_get_patient(patient_info)
    print(f"患者UUID: {patient_uuid}")
    print(f"UUID类型: {type(patient_uuid)}")

    # 步骤2：创建病例
    print("\n=== 步骤2：创建病例 ===")
    medical_record_uuid = service.create_medical_record(patient_uuid, patient_data)
    print(f"病例UUID: {medical_record_uuid}")
    print(f"UUID类型: {type(medical_record_uuid)}")

    # 步骤3：验证病例UUID在数据库中存在
    print("\n=== 步骤3：验证UUID在数据库中 ===")
    mr_query = "SELECT Medical_Record_ID, Medical_Record_UUID FROM medical_record WHERE Medical_Record_UUID = %s"
    mr_result = service.db.execute_one(mr_query, (medical_record_uuid,))

    if mr_result:
        print(f"✅ 找到记录:")
        print(f"  - Medical_Record_ID: {mr_result['Medical_Record_ID']}")
        print(f"  - Medical_Record_UUID: {mr_result['Medical_Record_UUID']}")
    else:
        print(f"❌ 未找到记录! UUID: {medical_record_uuid}")

        # 尝试查询最近的记录
        recent_query = "SELECT Medical_Record_ID, Medical_Record_UUID FROM medical_record ORDER BY Created_At DESC LIMIT 1"
        recent = service.db.execute_one(recent_query, ())
        if recent:
            print(f"\n最近创建的记录:")
            print(f"  - Medical_Record_ID: {recent['Medical_Record_ID']}")
            print(f"  - Medical_Record_UUID: {recent['Medical_Record_UUID']}")

if __name__ == "__main__":
    test_medical_record_creation()

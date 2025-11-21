"""
测试预约功能的UUID支持
"""
from database.appointment_service_v3 import AppointmentServiceV3

def test_create_patient():
    """测试创建患者"""
    print("=" * 60)
    print("测试创建或获取患者（使用UUID）")
    print("=" * 60)

    service = AppointmentServiceV3()

    try:
        patient_info = {
            'name': '测试患者UUID',
            'phone': '13900000099',
            'gender': '男',
            'age': 30
        }

        print(f"\n创建患者信息: {patient_info}")
        patient_uuid = service.create_or_get_patient(patient_info)

        if patient_uuid:
            print(f"[OK] 患者创建/获取成功: Patient_UUID={patient_uuid}")
        else:
            print("[ERROR] 患者创建/获取失败")

    except Exception as e:
        print(f"[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        service.db.close()


def test_create_medical_record():
    """测试创建病例"""
    print("\n" + "=" * 60)
    print("测试创建病例（使用UUID）")
    print("=" * 60)

    service = AppointmentServiceV3()

    try:
        # 先获取一个患者UUID
        from database.db_connection import DatabaseConnection
        db = DatabaseConnection()
        patient = db.execute_one("SELECT Patient_UUID, Name FROM patient WHERE Deleted = 0 LIMIT 1")
        db.close()

        if not patient:
            print("[ERROR] 没有找到患者记录")
            return

        patient_uuid = patient['Patient_UUID']
        patient_name = patient['Name']
        print(f"\n使用患者: {patient_name} (UUID: {patient_uuid})")

        patient_data = {
            'department': '眼科',
            'chief_complaint': '视力下降',
            'present_illness': '近期视力模糊',
            'medical_history': '无特殊病史',
            'diagnosis': '近视',
            'treatment_plan': '配镜'
        }

        print(f"\n创建病例...")
        medical_record_uuid = service.create_medical_record(patient_uuid, patient_data)

        if medical_record_uuid:
            print(f"[OK] 病例创建成功: Medical_Record_UUID={medical_record_uuid}")
        else:
            print("[ERROR] 病例创建失败")

    except Exception as e:
        print(f"[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        service.db.close()


if __name__ == "__main__":
    print("开始测试预约服务的UUID支持...\n")

    test_create_patient()
    test_create_medical_record()

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

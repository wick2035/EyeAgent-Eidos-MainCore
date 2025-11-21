"""
测试UUID迁移后的API端点
"""
from database.db_connection import DatabaseConnection

def test_users_endpoint_query():
    """测试 /api/users 端点的查询"""
    print("=" * 60)
    print("测试 /api/users 端点")
    print("=" * 60)

    db = DatabaseConnection()

    try:
        # 测试患者查询
        print("\n1. 测试患者查询（使用UUID）:")
        patients_query = """
            SELECT
                Patient_UUID as user_id,
                Name,
                Phone_Number,
                Gender,
                Age,
                'patient' as user_type
            FROM patient
            WHERE Deleted = 0
            ORDER BY Created_At DESC
            LIMIT 10
        """
        patients = db.execute_query(patients_query)
        print(f"   找到 {len(patients)} 个患者")
        if patients:
            print(f"   第一个患者: {patients[0]}")

        # 测试医生查询
        print("\n2. 测试医生查询（使用UUID）:")
        doctors_query = """
            SELECT
                Doctor_UUID as user_id,
                Name,
                Phone_Number,
                Gender,
                Age,
                'doctor' as user_type,
                Title,
                Specialty
            FROM doctor
            WHERE is_active = 1 AND Deleted = 0
            ORDER BY Doctor_UUID DESC
            LIMIT 10
        """
        doctors = db.execute_query(doctors_query)
        print(f"   找到 {len(doctors)} 个医生")
        if doctors:
            print(f"   第一个医生: {doctors[0]}")

        # 合并结果
        users = patients + doctors
        print(f"\n[OK] 总共: {len(users)} 个用户 (患者: {len(patients)}, 医生: {len(doctors)})")

    except Exception as e:
        print(f"[ERROR] 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def test_patients_endpoint_query():
    """测试 /api/patients 端点的查询"""
    print("\n" + "=" * 60)
    print("测试 /api/patients 端点")
    print("=" * 60)

    db = DatabaseConnection()

    try:
        query = """
            SELECT
                Patient_UUID,
                Name,
                Gender,
                Age,
                Phone_Number,
                Email,
                Address,
                Created_At,
                Updated_At
            FROM patient
            WHERE Deleted = 0
            ORDER BY Created_At DESC
            LIMIT 50
        """
        patients = db.execute_query(query)
        print(f"[OK] 找到 {len(patients)} 个患者记录")
        if patients:
            print(f"   示例记录: {patients[0]}")

    except Exception as e:
        print(f"[ERROR] 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def test_appointments_endpoint_query():
    """测试 /api/appointments 端点的查询"""
    print("\n" + "=" * 60)
    print("测试 /api/appointments 端点")
    print("=" * 60)

    db = DatabaseConnection()

    try:
        query = """
            SELECT
                a.Appointment_UUID,
                a.Patient_UUID,
                a.Doctor_UUID,
                a.Patient_Name,
                a.Appointment_Time,
                a.Appointment_Status,
                a.Appointment_Category,
                a.Severity_Level,
                d.Name as Doctor_Name,
                d.Title as Doctor_Title,
                d.Specialty as Doctor_Specialty,
                p.Name as Patient_Full_Name,
                p.Phone_Number as Patient_Phone,
                a.Created_At,
                a.Updated_At
            FROM appointment a
            LEFT JOIN doctor d ON a.Doctor_UUID = d.Doctor_UUID
            LEFT JOIN patient p ON a.Patient_UUID = p.Patient_UUID
            WHERE a.Deleted = 0
            ORDER BY a.Appointment_Time DESC
            LIMIT 50
        """
        appointments = db.execute_query(query)
        print(f"[OK] 找到 {len(appointments)} 个预约记录")
        if appointments:
            print(f"   示例记录: {appointments[0]}")

    except Exception as e:
        print(f"[ERROR] 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    print("开始测试UUID迁移后的API端点查询...\n")

    test_users_endpoint_query()
    test_patients_endpoint_query()
    test_appointments_endpoint_query()

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

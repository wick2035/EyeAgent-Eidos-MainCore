"""
测试预约提醒创建功能
验证预约成功后自动创建提醒是否正常工作
"""
import sys
import io
from datetime import datetime, timedelta
from database.reminder_service import ReminderService
from database.appointment_service_v3 import AppointmentServiceV3
from database.db_connection import DatabaseConnection

# 设置标准输出编码为UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_reminder_creation():
    """测试提醒创建功能"""
    print("\n" + "="*60)
    print("测试预约提醒创建功能")
    print("="*60)

    reminder_service = ReminderService()
    appointment_service = AppointmentServiceV3()
    db = DatabaseConnection()

    try:
        # 1. 查找一个现有的患者UUID（用于测试）
        print("\n1. 查找测试用患者...")
        patient_query = "SELECT Patient_UUID, Phone_Number, Name FROM patient WHERE Deleted = 0 LIMIT 1"
        patient = db.execute_one(patient_query)

        if not patient:
            print("❌ 没有找到患者记录，请先创建患者")
            return

        patient_uuid = patient['Patient_UUID']
        print(f"✅ 找到测试患者: {patient['Name']} (UUID: {patient_uuid})")

        # 2. 查找该患者的一个预约记录
        print("\n2. 查找患者的预约记录...")
        appointment_query = """
            SELECT Appointment_UUID, Appointment_Time, Appointment_Status
            FROM appointment
            WHERE Patient_UUID = %s AND Deleted = 0
            ORDER BY Created_At DESC LIMIT 1
        """
        appointment = db.execute_one(appointment_query, (patient_uuid,))

        if not appointment:
            print("⚠️  该患者没有预约记录")
            print("   创建一个测试预约...")
            # 这里可以创建一个测试预约，但为了简单起见，我们跳过
            print("   请先创建一个预约，然后再运行此测试")
            return

        appointment_uuid = appointment['Appointment_UUID']
        appointment_time = appointment['Appointment_Time']
        print(f"✅ 找到预约记录: UUID={appointment_uuid}, 时间={appointment_time}")

        # 3. 检查是否已存在该预约的提醒
        print("\n3. 检查现有提醒...")
        existing_reminder_query = """
            SELECT Reminder_UUID, Status, Scheduled_Time
            FROM reminder
            WHERE Appointment_UUID = %s
        """
        existing_reminders = db.execute_query(existing_reminder_query, (appointment_uuid,))

        if existing_reminders:
            print(f"✅ 找到 {len(existing_reminders)} 个现有提醒:")
            for r in existing_reminders:
                print(f"   - UUID: {r['Reminder_UUID']}, 状态: {r['Status']}, 时间: {r['Scheduled_Time']}")
        else:
            print("⚠️  该预约还没有创建提醒")

        # 4. 创建新的预约提醒
        print("\n4. 创建新的预约提醒...")
        result = reminder_service.create_appointment_reminder(
            patient_uuid=patient_uuid,
            appointment_uuid=appointment_uuid,
            appointment_time=appointment_time,
            advance_days=1
        )

        if result['success']:
            reminder_uuid = result['reminder_uuid']
            print(f"✅ 预约提醒创建成功!")
            print(f"   Reminder UUID: {reminder_uuid}")

            # 5. 验证提醒是否真的插入到数据库
            print("\n5. 验证数据库中的提醒记录...")
            verify_query = """
                SELECT r.*, p.Name as Patient_Name
                FROM reminder r
                LEFT JOIN patient p ON r.Patient_UUID = p.Patient_UUID
                WHERE r.Reminder_UUID = %s
            """
            reminder_record = db.execute_one(verify_query, (reminder_uuid,))

            if reminder_record:
                print("✅ 提醒记录已成功插入数据库:")
                print(f"   患者姓名: {reminder_record['Patient_Name']}")
                print(f"   提醒类型: {reminder_record['Reminder_Type']}")
                print(f"   提醒标题: {reminder_record['Reminder_Title']}")
                print(f"   提醒内容: {reminder_record['Reminder_Content']}")
                print(f"   计划时间: {reminder_record['Scheduled_Time']}")
                print(f"   提前天数: {reminder_record['Advance_Days']}")
                print(f"   状态: {reminder_record['Status']}")
                print(f"   创建时间: {reminder_record['Created_At']}")
            else:
                print("❌ 提醒记录未找到！数据可能未成功插入")
        else:
            print(f"❌ 创建提醒失败: {result['message']}")

        # 6. 查询该患者的所有提醒
        print("\n6. 查询该患者的所有提醒记录...")
        all_reminders = reminder_service.get_reminders_by_patient(patient_uuid)
        print(f"✅ 该患者共有 {len(all_reminders)} 个提醒:")
        for reminder in all_reminders:
            print(f"   - {reminder['Reminder_Title']} | 状态: {reminder['Status']} | 时间: {reminder['Scheduled_Time']}")

        print("\n" + "="*60)
        print("测试完成!")
        print("="*60)

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()
        reminder_service.close()


if __name__ == "__main__":
    test_reminder_creation()

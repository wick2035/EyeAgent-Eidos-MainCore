"""
修复剩余的5个INT ID列
解决check约束和唯一键冲突问题
"""

import pymysql
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 数据库配置
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME', 'medical_db'),
    'charset': 'utf8mb4',
}

def execute_sql(conn, sql, description):
    """执行SQL并打印结果"""
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()
        print(f"[OK] {description}")
        return True
    except Exception as e:
        print(f"[ERROR] {description}: {e}")
        return False

def main():
    print("="*80)
    print("[START] 修复剩余的INT ID列")
    print("="*80)

    conn = pymysql.connect(**DB_CONFIG)

    try:
        # 禁用外键检查
        execute_sql(conn, "SET FOREIGN_KEY_CHECKS = 0", "禁用外键检查")

        # 1. 修复 chat_conversation 表
        print("\n[INFO] 修复 chat_conversation 表...")

        # 删除check约束
        execute_sql(conn,
            "ALTER TABLE chat_conversation DROP CHECK chat_conversation_chk_1",
            "删除check约束")

        # 删除列
        execute_sql(conn,
            "ALTER TABLE chat_conversation DROP COLUMN Patient_ID",
            "删除Patient_ID列")

        execute_sql(conn,
            "ALTER TABLE chat_conversation DROP COLUMN Doctor_ID",
            "删除Doctor_ID列")

        # 2. 修复 chat_message 表
        print("\n[INFO] 修复 chat_message 表...")

        # 删除唯一键
        execute_sql(conn,
            "ALTER TABLE chat_message DROP INDEX unique_chat_order",
            "删除unique_chat_order索引")

        # 删除列
        execute_sql(conn,
            "ALTER TABLE chat_message DROP COLUMN Chat_ID",
            "删除Chat_ID列")

        # 重新创建唯一键
        execute_sql(conn,
            "ALTER TABLE chat_message ADD UNIQUE KEY unique_chat_uuid_order (Chat_UUID, Message_Order)",
            "创建新的UUID唯一键")

        # 3. 修复 doctor_time_slots 表
        print("\n[INFO] 修复 doctor_time_slots 表...")

        # 删除唯一键
        execute_sql(conn,
            "ALTER TABLE doctor_time_slots DROP INDEX unique_doctor_slot_time",
            "删除unique_doctor_slot_time索引")

        # 删除列
        execute_sql(conn,
            "ALTER TABLE doctor_time_slots DROP COLUMN Doctor_ID",
            "删除Doctor_ID列")

        # 重新创建唯一键
        execute_sql(conn,
            "ALTER TABLE doctor_time_slots ADD UNIQUE KEY unique_doctor_uuid_slot_time (Doctor_UUID, Slot_Date, Slot_Start_Time)",
            "创建新的UUID唯一键")

        # 4. 修复 doctor_working_schedule 表
        print("\n[INFO] 修复 doctor_working_schedule 表...")

        # 删除唯一键
        execute_sql(conn,
            "ALTER TABLE doctor_working_schedule DROP INDEX unique_doctor_day_shift",
            "删除unique_doctor_day_shift索引")

        # 删除列
        execute_sql(conn,
            "ALTER TABLE doctor_working_schedule DROP COLUMN Doctor_ID",
            "删除Doctor_ID列")

        # 重新创建唯一键
        execute_sql(conn,
            "ALTER TABLE doctor_working_schedule ADD UNIQUE KEY unique_doctor_uuid_day_shift (Doctor_UUID, Day_Of_Week, Shift_Type)",
            "创建新的UUID唯一键")

        # 重新启用外键检查
        execute_sql(conn, "SET FOREIGN_KEY_CHECKS = 1", "启用外键检查")

        # 验证结果
        print("\n" + "="*80)
        print("[CHECK] 验证结果...")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
              AND COLUMN_NAME IN ('Patient_ID', 'Doctor_ID', 'Chat_ID', 'Medical_Record_ID',
                                   'Appointment_ID', 'Prescription_ID', 'Reminder_ID',
                                   'Slot_ID', 'Message_ID', 'Detail_ID', 'History_ID',
                                   'Config_ID', 'Schedule_ID', 'Exception_ID', 'Scan_ID')
            ORDER BY TABLE_NAME, COLUMN_NAME
        """, (DB_CONFIG['database'],))

        remaining = cursor.fetchall()

        if remaining:
            print("[WARNING] 以下INT ID列仍然存在:")
            for table, column, col_type in remaining:
                print(f"  - {table}.{column} ({col_type})")
            print(f"\n共 {len(remaining)} 个INT ID列未删除")
        else:
            print("[SUCCESS] 所有INT ID列已成功删除!")
            print("\n只保留以下4种特殊ID格式:")
            print("  1. drugs.drug_id (EYD0001)")
            print("  2. prescription.Prescription_Number (RX20251117001)")
            print("  3. medical_record.Visit_Card_Number (20251111-000001)")
            print("  4. medical_record.Report_ID (FILE-20251111-00005)")

        print("="*80)

    except Exception as e:
        print(f"\n[ERROR] 执行过程中发生错误: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    main()

"""
安全删除所有INT ID列 - 改进版
采用逐表、逐列策略,避免元数据锁问题
"""

import pymysql
import os
import sys
from dotenv import load_dotenv
from datetime import datetime
import time

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

# 定义所有需要删除的表及其INT ID列
# 格式: {表名: [(外键约束名, 列名), ...]}
TABLES_TO_PROCESS = {
    # 核心表
    'patient': [
        (None, 'Patient_ID'),
    ],
    'doctor': [
        (None, 'Doctor_ID'),
    ],
    'medical_record': [
        ('fk_medical_record_patient_id', 'Patient_ID'),
        (None, 'Medical_Record_ID'),
    ],

    # 预约相关
    'appointment': [
        ('fk_appointment_medical_record_id', 'Medical_Record_ID'),
        ('fk_appointment_patient_id', 'Patient_ID'),
        ('fk_appointment_doctor_id', 'Doctor_ID'),
        ('fk_appointment_time_slot_id', 'Time_Slot_ID'),
        (None, 'Appointment_ID'),
    ],

    # 时间槽管理
    'doctor_time_slots': [
        ('fk_time_slot_doctor_id', 'Doctor_ID'),
        (None, 'Slot_ID'),
    ],
    'doctor_working_schedule': [
        ('fk_working_schedule_doctor_id', 'Doctor_ID'),
        (None, 'Schedule_ID'),
    ],
    'doctor_schedule_exceptions': [
        ('fk_schedule_exceptions_doctor_id', 'Doctor_ID'),
        (None, 'Exception_ID'),
    ],

    # 处方相关
    'prescription': [
        ('fk_prescription_medical_record_id', 'Medical_Record_ID'),
        ('fk_prescription_doctor_id', 'Doctor_ID'),
        ('fk_prescription_patient_id', 'Patient_ID'),
        (None, 'Prescription_ID'),
    ],
    'prescription_detail': [
        ('fk_prescription_detail_prescription_id', 'Prescription_ID'),
        (None, 'Detail_ID'),
    ],

    # 提醒系统
    'reminder': [
        ('fk_reminder_appointment_id', 'Appointment_ID'),
        ('fk_reminder_patient_id', 'Patient_ID'),
        ('fk_reminder_medical_record_id', 'Medical_Record_ID'),
        ('fk_reminder_prescription_id', 'Prescription_ID'),
        (None, 'Reminder_ID'),
    ],
    'reminder_history': [
        ('fk_reminder_history_reminder_id', 'Reminder_ID'),
        (None, 'History_ID'),
    ],
    'reminder_config': [
        ('fk_reminder_config_patient_id', 'Patient_ID'),
        (None, 'Config_ID'),
    ],

    # 生物力学扫描
    'biomechanics_scan': [
        ('fk_biomechanics_patient_id', 'Patient_ID'),
        ('fk_biomechanics_medical_record_id', 'Medical_Record_ID'),
        (None, 'Scan_ID'),
    ],

    # 聊天系统
    'chat_conversation': [
        ('fk_chat_conversation_patient_id', 'Patient_ID'),
        ('fk_chat_conversation_doctor_id', 'Doctor_ID'),
        (None, 'Chat_ID'),
    ],
    'chat_message': [
        ('fk_chat_message_chat_id', 'Chat_ID'),
        (None, 'Message_ID'),
    ],
}


def create_connection():
    """创建数据库连接"""
    return pymysql.connect(**DB_CONFIG)


def check_column_exists(cursor, table_name, column_name):
    """检查列是否存在"""
    cursor.execute("""
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
    """, (DB_CONFIG['database'], table_name, column_name))
    return cursor.fetchone()[0] > 0


def check_fk_exists(cursor, table_name, fk_name):
    """检查外键是否存在"""
    if not fk_name:
        return False
    cursor.execute("""
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME = %s
          AND CONSTRAINT_NAME = %s
          AND CONSTRAINT_TYPE = 'FOREIGN KEY'
    """, (DB_CONFIG['database'], table_name, fk_name))
    return cursor.fetchone()[0] > 0


def drop_foreign_key(cursor, table_name, fk_name):
    """删除外键约束"""
    if not check_fk_exists(cursor, table_name, fk_name):
        print(f"  [WARNING]  外键 {fk_name} 不存在,跳过")
        return True

    try:
        sql = f"ALTER TABLE {table_name} DROP FOREIGN KEY {fk_name}"
        print(f"  [FIX] 删除外键: {fk_name}")
        cursor.execute(sql)
        print(f"  [OK] 外键 {fk_name} 已删除")
        return True
    except Exception as e:
        print(f"  [ERROR] 删除外键失败: {e}")
        return False


def drop_column(cursor, table_name, column_name):
    """删除列"""
    if not check_column_exists(cursor, table_name, column_name):
        print(f"  [WARNING]  列 {table_name}.{column_name} 不存在,跳过")
        return True

    try:
        sql = f"ALTER TABLE {table_name} DROP COLUMN {column_name}"
        print(f"  [FIX] 删除列: {column_name}")
        cursor.execute(sql)
        print(f"  [OK] 列 {column_name} 已删除")
        return True
    except Exception as e:
        print(f"  [ERROR] 删除列失败: {e}")
        return False


def process_table(table_name, operations):
    """处理单个表的所有操作"""
    print(f"\n{'='*80}")
    print(f"[INFO] 处理表: {table_name}")
    print(f"{'='*80}")

    # 为每个表创建新连接,避免锁积累
    conn = create_connection()

    try:
        # 设置超时
        conn.cursor().execute("SET SESSION lock_wait_timeout = 10")

        # 禁用外键检查
        conn.cursor().execute("SET FOREIGN_KEY_CHECKS = 0")

        cursor = conn.cursor()
        success_count = 0
        fail_count = 0

        for fk_name, column_name in operations:
            # 1. 先删除外键(如果有)
            if fk_name:
                if drop_foreign_key(cursor, table_name, fk_name):
                    conn.commit()
                    time.sleep(0.1)  # 短暂延迟让MySQL释放锁
                else:
                    fail_count += 1
                    continue

            # 2. 再删除列
            if drop_column(cursor, table_name, column_name):
                conn.commit()
                success_count += 1
                time.sleep(0.1)  # 短暂延迟
            else:
                fail_count += 1

        # 重新启用外键检查
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()

        print(f"\n[REPORT] {table_name} 处理完成: 成功 {success_count}, 失败 {fail_count}")
        return fail_count == 0

    except Exception as e:
        print(f"[ERROR] 处理 {table_name} 时发生错误: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def verify_migration():
    """验证迁移结果"""
    print(f"\n{'='*80}")
    print(f"[CHECK] 验证迁移结果")
    print(f"{'='*80}\n")

    conn = create_connection()
    cursor = conn.cursor()

    # 检查所有需要删除的INT ID列
    all_int_ids = [
        'Patient_ID', 'Medical_Record_ID', 'Doctor_ID', 'Appointment_ID',
        'Prescription_ID', 'Reminder_ID', 'Slot_ID', 'Chat_ID', 'Message_ID',
        'Detail_ID', 'History_ID', 'Config_ID', 'Schedule_ID', 'Exception_ID', 'Scan_ID'
    ]

    cursor.execute(f"""
        SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s
          AND COLUMN_NAME IN ({','.join(['%s'] * len(all_int_ids))})
        ORDER BY TABLE_NAME, COLUMN_NAME
    """, (DB_CONFIG['database'], *all_int_ids))

    remaining = cursor.fetchall()

    if remaining:
        print("[WARNING]  以下INT ID列仍然存在:")
        for table, column, col_type in remaining:
            print(f"  - {table}.{column} ({col_type})")
        print(f"\n共 {len(remaining)} 个INT ID列未删除")
        success = False
    else:
        print("[OK] 所有INT ID列已成功删除!")
        success = True

    # 显示所有UUID列
    cursor.execute("""
        SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, COLUMN_KEY
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s
          AND COLUMN_NAME LIKE '%UUID%'
        ORDER BY TABLE_NAME, COLUMN_NAME
    """, (DB_CONFIG['database'],))

    uuid_columns = cursor.fetchall()
    print(f"\n[OK] 当前数据库UUID列列表 ({len(uuid_columns)} 个):")
    for table, column, col_type, key in uuid_columns:
        key_info = f" [{key}]" if key else ""
        print(f"  - {table}.{column} ({col_type}){key_info}")

    conn.close()
    return success


def main():
    print("="*80)
    print("[START] 开始安全删除所有INT ID列")
    print("="*80)
    print(f"[TIME] 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[DB] 数据库: {DB_CONFIG['database']}")
    print(f"[COUNT] 待处理表数量: {len(TABLES_TO_PROCESS)}")
    print("="*80)

    # 测试连接
    try:
        conn = create_connection()
        print("[OK] 数据库连接成功")
        conn.close()
    except Exception as e:
        print(f"[ERROR] 数据库连接失败: {e}")
        return

    # 提示用户确认
    print("\n[WARNING] 警告: 此操作将删除所有INT ID列,这是不可逆的!")
    print("[WARNING] 请确保已经备份数据库!")
    confirm = input("\n是否继续? (输入 'YES' 确认): ")

    if confirm != 'YES':
        print("[ERROR] 操作已取消")
        return

    # 处理所有表
    total_success = 0
    total_failed = 0

    for table_name, operations in TABLES_TO_PROCESS.items():
        if process_table(table_name, operations):
            total_success += 1
        else:
            total_failed += 1

        # 每个表之间延迟,让MySQL有时间释放资源
        time.sleep(0.5)

    # 验证结果
    print("\n" + "="*80)
    verification_success = verify_migration()

    # 最终报告
    print("\n" + "="*80)
    print("[REPORT] 最终报告")
    print("="*80)
    print(f"[OK] 成功处理的表: {total_success}/{len(TABLES_TO_PROCESS)}")
    print(f"[ERROR] 失败的表: {total_failed}/{len(TABLES_TO_PROCESS)}")
    print(f"{'[OK]' if verification_success else '[WARNING]'} 验证结果: {'所有INT ID列已删除' if verification_success else '仍有INT ID列残留'}")
    print(f"[TIME] 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    if verification_success and total_failed == 0:
        print("\n[SUCCESS] 迁移完全成功! 数据库现在只使用UUID作为主键!")
    else:
        print("\n[WARNING]  迁移未完全成功,请检查上述错误信息")


if __name__ == '__main__':
    main()

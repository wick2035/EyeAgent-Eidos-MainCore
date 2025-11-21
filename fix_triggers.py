"""
修复所有UUID触发器，移除对INT ID列的引用
"""
from database.db_connection import DatabaseConnection

# 表名到UUID列名的映射
TABLE_UUID_COLUMNS = {
    'medical_record': 'Medical_Record_UUID',
    'patient': 'Patient_UUID',
    'doctor': 'Doctor_UUID',
    'prescription': 'Prescription_UUID',
    'prescription_detail': 'Detail_UUID',
    'reminder': 'Reminder_UUID',
    'biomechanics_scan': 'Scan_UUID',
    'chat_message': 'Message_UUID',
    'doctor_time_slots': 'Slot_UUID',
    'doctor_working_schedule': 'Schedule_UUID'
}

def fix_triggers():
    """修复所有UUID触发器"""
    db = DatabaseConnection()

    try:
        for table, uuid_column in TABLE_UUID_COLUMNS.items():
            trigger_name = f'trg_{table}_uuid_insert'

            print(f"修复触发器: {trigger_name}")

            # 删除旧触发器
            drop_sql = f'DROP TRIGGER IF EXISTS {trigger_name}'
            db.execute_update(drop_sql)

            # 创建新触发器（只处理UUID生成，不引用INT ID）
            create_sql = f'''
                CREATE TRIGGER {trigger_name}
                BEFORE INSERT ON {table}
                FOR EACH ROW
                BEGIN
                    IF NEW.{uuid_column} IS NULL OR NEW.{uuid_column} = '' THEN
                        SET NEW.{uuid_column} = UUID();
                    END IF;
                END
            '''
            db.execute_update(create_sql)

            print(f"  [OK] {trigger_name} 已更新")

        print("\n所有触发器已成功更新！")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    fix_triggers()

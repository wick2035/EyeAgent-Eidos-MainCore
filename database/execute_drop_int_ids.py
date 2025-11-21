"""
直接执行删除INT ID列的Python脚本
避免SQL脚本的锁问题
"""
import pymysql
import time

DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '20041118',
    'database': 'medical_db',
    'charset': 'utf8mb4',
}

def drop_int_id_columns():
    """删除所有INT ID列"""
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        print("=== 开始删除INT ID列 ===\n")

        # 禁用外键检查
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

        # 定义要删除的列
        tables_and_columns = [
            ('appointment', ['Appointment_ID', 'Medical_Record_ID', 'Patient_ID', 'Doctor_ID', 'Time_Slot_ID']),
            ('medical_record', ['Medical_Record_ID', 'Patient_ID']),
            ('patient', ['Patient_ID']),
            ('doctor', ['Doctor_ID']),
        ]

        for table_name, columns in tables_and_columns:
            print(f"--- 处理表: {table_name} ---")
            for column_name in columns:
                try:
                    # 检查列是否存在
                    cursor.execute(f"""
                        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_SCHEMA = 'medical_db'
                          AND TABLE_NAME = '{table_name}'
                          AND COLUMN_NAME = '{column_name}'
                    """)
                    exists = cursor.fetchone()[0]

                    if exists:
                        print(f"  删除列: {column_name}")
                        cursor.execute(f"ALTER TABLE {table_name} DROP COLUMN {column_name}")
                        conn.commit()
                        print(f"  ✅ 成功删除: {table_name}.{column_name}")
                    else:
                        print(f"  ℹ️  列不存在: {column_name}")

                except Exception as e:
                    print(f"  ❌ 删除失败 {table_name}.{column_name}: {e}")
                    conn.rollback()

            print()

        # 启用外键检查
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()

        print("=== 所有INT ID列删除完成 ===\n")

        # 验证结果
        print("=== 验证结果 ===")
        for table_name,_ in tables_and_columns:
            cursor.execute(f"DESC {table_name}")
            columns = cursor.fetchall()
            id_columns = [col[0] for col in columns if col[0].endswith('_ID') or col[0].endswith('_UUID')]
            print(f"{table_name}: {', '.join(id_columns)}")

    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    drop_int_id_columns()

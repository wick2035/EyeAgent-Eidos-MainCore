"""
简单直接的删除INT ID列脚本
每次只执行一个ALTER TABLE,避免锁问题
"""
import pymysql
import sys

# 数据库配置
conn = pymysql.connect(
    host='localhost',
    port=3306,
    user='root',
    password='20041118',
    database='medical_db',
    autocommit=False
)

cursor = conn.cursor()

# 要删除的列定义
drops = [
    ("appointment", "Appointment_ID"),
    ("appointment", "Medical_Record_ID"),
    ("appointment", "Patient_ID"),
    ("appointment", "Doctor_ID"),
    ("appointment", "Time_Slot_ID"),
    ("medical_record", "Medical_Record_ID"),
    ("medical_record", "Patient_ID"),
    ("patient", "Patient_ID"),
    ("doctor", "Doctor_ID"),
]

print("开始删除INT ID列...")
cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

for table, column in drops:
    try:
        sql = f"ALTER TABLE {table} DROP COLUMN {column}"
        print(f"执行: {sql}")
        cursor.execute(sql)
        conn.commit()
        print(f"✅ 成功删除: {table}.{column}")
    except Exception as e:
        print(f"❌ 失败: {table}.{column} - {e}")
        conn.rollback()

cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
conn.commit()

# 验证
print("\n验证结果:")
for table in ["appointment", "medical_record", "patient", "doctor"]:
    cursor.execute(f"DESC {table}")
    cols = [row[0] for row in cursor.fetchall() if 'UUID' in row[0] or row[0].endswith('_ID')]
    print(f"{table}: {cols}")

cursor.close()
conn.close()
print("\n完成!")

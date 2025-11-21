"""
修复预约表触发器 - 将 Time_Slot_ID 更新为 Time_Slot_UUID
Created: 2025-11-21
"""

import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME', 'medical_db'),
    'charset': 'utf8mb4'
}

def fix_triggers():
    """修复appointment表的触发器,将Time_Slot_ID改为Time_Slot_UUID"""

    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        print("开始修复触发器...")

        # 1. 删除旧的触发器
        print("\n1. 删除旧触发器...")
        drop_triggers = [
            "DROP TRIGGER IF EXISTS trg_appointment_insert",
            "DROP TRIGGER IF EXISTS trg_appointment_update",
            "DROP TRIGGER IF EXISTS trg_appointment_cancel"
        ]

        for sql in drop_triggers:
            cursor.execute(sql)
            print(f"  执行: {sql}")

        # 2. 创建新的触发器(使用UUID字段)
        print("\n2. 创建新触发器(UUID版本)...")

        # 触发器1: INSERT时增加时间段预约数
        trigger_insert = """
        CREATE TRIGGER trg_appointment_insert
        AFTER INSERT ON appointment
        FOR EACH ROW
        BEGIN
            IF NEW.Time_Slot_UUID IS NOT NULL AND NEW.Appointment_Status IN ('已预约', '已确认') THEN
                UPDATE doctor_time_slots
                SET Current_Bookings = Current_Bookings + 1,
                    Updated_At = CURRENT_TIMESTAMP
                WHERE Slot_UUID = NEW.Time_Slot_UUID;
            END IF;
        END
        """
        cursor.execute(trigger_insert)
        print("  ✓ 创建 trg_appointment_insert (INSERT触发器)")

        # 触发器2: UPDATE时处理状态变更
        trigger_update = """
        CREATE TRIGGER trg_appointment_update
        AFTER UPDATE ON appointment
        FOR EACH ROW
        BEGIN
            -- 状态从未预约/已取消 改为 已预约/已确认: 增加预约数
            IF OLD.Appointment_Status IN ('未预约', '已取消')
               AND NEW.Appointment_Status IN ('已预约', '已确认')
               AND NEW.Time_Slot_UUID IS NOT NULL THEN
                UPDATE doctor_time_slots
                SET Current_Bookings = Current_Bookings + 1,
                    Updated_At = CURRENT_TIMESTAMP
                WHERE Slot_UUID = NEW.Time_Slot_UUID;
            END IF;

            -- 状态从已预约/已确认 改为 已取消/已完成: 减少预约数
            IF OLD.Appointment_Status IN ('已预约', '已确认')
               AND NEW.Appointment_Status IN ('已取消', '已完成')
               AND OLD.Time_Slot_UUID IS NOT NULL THEN
                UPDATE doctor_time_slots
                SET Current_Bookings = GREATEST(Current_Bookings - 1, 0),
                    Updated_At = CURRENT_TIMESTAMP
                WHERE Slot_UUID = OLD.Time_Slot_UUID;
            END IF;
        END
        """
        cursor.execute(trigger_update)
        print("  ✓ 创建 trg_appointment_update (UPDATE触发器)")

        # 触发器3: DELETE时减少预约数
        trigger_delete = """
        CREATE TRIGGER trg_appointment_delete
        AFTER DELETE ON appointment
        FOR EACH ROW
        BEGIN
            IF OLD.Time_Slot_UUID IS NOT NULL
               AND OLD.Appointment_Status IN ('已预约', '已确认') THEN
                UPDATE doctor_time_slots
                SET Current_Bookings = GREATEST(Current_Bookings - 1, 0),
                    Updated_At = CURRENT_TIMESTAMP
                WHERE Slot_UUID = OLD.Time_Slot_UUID;
            END IF;
        END
        """
        cursor.execute(trigger_delete)
        print("  ✓ 创建 trg_appointment_delete (DELETE触发器)")

        conn.commit()

        # 3. 验证触发器
        print("\n3. 验证触发器创建情况...")
        cursor.execute("SHOW TRIGGERS WHERE `Table` = 'appointment'")
        triggers = cursor.fetchall()

        if triggers:
            print(f"  找到 {len(triggers)} 个触发器:")
            for trigger in triggers:
                print(f"    - {trigger[0]} ({trigger[1]})")
        else:
            print("  ⚠️ 未找到触发器")

        print("\n✅ 触发器修复完成!")
        return True

    except Exception as e:
        print(f"\n❌ 修复失败: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("修复预约表触发器 - Time_Slot_ID → Time_Slot_UUID")
    print("=" * 60)

    success = fix_triggers()

    if success:
        print("\n现在可以重新测试预约功能了!")
    else:
        print("\n请检查错误信息并手动修复")

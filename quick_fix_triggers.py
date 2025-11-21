"""Quick trigger fix"""
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

conn = pymysql.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    port=int(os.getenv('DB_PORT', '3306')),
    user=os.getenv('DB_USER', 'root'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME', 'medical_db')
)

cursor = conn.cursor()

# Drop old triggers
print("Dropping old triggers...")
cursor.execute("DROP TRIGGER IF EXISTS trg_appointment_insert")
cursor.execute("DROP TRIGGER IF EXISTS trg_appointment_update")
cursor.execute("DROP TRIGGER IF EXISTS trg_appointment_delete")
print("OK")

# Create INSERT trigger
print("Creating INSERT trigger...")
cursor.execute("""
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
""")
print("OK")

# Create UPDATE trigger
print("Creating UPDATE trigger...")
cursor.execute("""
CREATE TRIGGER trg_appointment_update
AFTER UPDATE ON appointment
FOR EACH ROW
BEGIN
    IF OLD.Appointment_Status IN ('未预约', '已取消')
       AND NEW.Appointment_Status IN ('已预约', '已确认')
       AND NEW.Time_Slot_UUID IS NOT NULL THEN
        UPDATE doctor_time_slots
        SET Current_Bookings = Current_Bookings + 1,
            Updated_At = CURRENT_TIMESTAMP
        WHERE Slot_UUID = NEW.Time_Slot_UUID;
    END IF;

    IF OLD.Appointment_Status IN ('已预约', '已确认')
       AND NEW.Appointment_Status IN ('已取消', '已完成')
       AND OLD.Time_Slot_UUID IS NOT NULL THEN
        UPDATE doctor_time_slots
        SET Current_Bookings = GREATEST(Current_Bookings - 1, 0),
            Updated_At = CURRENT_TIMESTAMP
        WHERE Slot_UUID = OLD.Time_Slot_UUID;
    END IF;
END
""")
print("OK")

# Create DELETE trigger
print("Creating DELETE trigger...")
cursor.execute("""
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
""")
print("OK")

conn.commit()

# Verify
cursor.execute("SHOW TRIGGERS WHERE `Table` = 'appointment'")
triggers = cursor.fetchall()
print(f"\nTriggers created: {len(triggers)}")
for t in triggers:
    print(f"  - {t[0]}")

cursor.close()
conn.close()
print("\nDone!")

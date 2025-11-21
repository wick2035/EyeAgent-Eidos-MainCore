-- ========================================
-- 修复预约表触发器 - UUID迁移修复
-- 将 Time_Slot_ID 改为 Time_Slot_UUID
-- Created: 2025-11-21
-- ========================================

USE medical_db;

-- 1. 删除旧触发器
DROP TRIGGER IF EXISTS trg_appointment_insert;
DROP TRIGGER IF EXISTS trg_appointment_update;
DROP TRIGGER IF EXISTS trg_appointment_cancel;
DROP TRIGGER IF EXISTS trg_appointment_delete;

-- 2. 创建新触发器(UUID版本)

-- 触发器1: INSERT时增加时间段预约数
DELIMITER $$
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
END$$
DELIMITER ;

-- 触发器2: UPDATE时处理状态变更
DELIMITER $$
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
END$$
DELIMITER ;

-- 触发器3: DELETE时减少预约数
DELIMITER $$
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
END$$
DELIMITER ;

-- 验证触发器
SHOW TRIGGERS WHERE `Table` = 'appointment';

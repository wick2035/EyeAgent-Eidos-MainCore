-- 升级到 V3 版本 - 补充修改脚本
-- 只添加新表和新字段，不删除现有数据
-- 执行前请先备份数据库
-- 日期: 2025-11-19

USE medical_db;

-- ==================== 第一部分：修改现有表 ====================

-- 检查并添加字段的存储过程
DELIMITER $$

CREATE PROCEDURE IF NOT EXISTS add_column_if_not_exists(
    IN p_table_name VARCHAR(64),
    IN p_column_name VARCHAR(64),
    IN p_column_definition TEXT
)
BEGIN
    DECLARE column_count INT;
    
    SELECT COUNT(*) INTO column_count
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = p_table_name
      AND COLUMN_NAME = p_column_name;
    
    IF column_count = 0 THEN
        SET @sql = CONCAT('ALTER TABLE ', p_table_name, ' ADD COLUMN ', p_column_name, ' ', p_column_definition);
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END$$

DELIMITER ;

-- 1. 为 doctor 表添加 V3 新字段
CALL add_column_if_not_exists('doctor', 'default_slot_duration_minutes', "INT DEFAULT 60 COMMENT '默认时间段时长（分钟）'");
CALL add_column_if_not_exists('doctor', 'default_max_patients_per_slot', "INT DEFAULT 5 COMMENT '默认每时段最大接诊人数'");
CALL add_column_if_not_exists('doctor', 'booking_window_days', "INT DEFAULT 3 COMMENT '预约开放天数（今天起往后几天）'");
CALL add_column_if_not_exists('doctor', 'is_active', "BOOLEAN DEFAULT TRUE COMMENT '医生是否在职'");

-- 2. 为 appointment 表添加 Time_Slot_ID 字段
CALL add_column_if_not_exists('appointment', 'Time_Slot_ID', "INT COMMENT '时间段ID（V3新增，关联到doctor_time_slots）'");

-- 清理存储过程
DROP PROCEDURE IF EXISTS add_column_if_not_exists;

-- ==================== 第二部分：创建新表 ====================

-- 4. 医生每周工作时间模板表
CREATE TABLE IF NOT EXISTS doctor_working_schedule (
    Schedule_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '排班ID',
    Doctor_ID INT NOT NULL COMMENT '医生ID',
    Day_of_Week TINYINT NOT NULL COMMENT '星期几（0=周日，1=周一，...，6=周六）',
    Shift_Start_Time TIME NOT NULL COMMENT '班次开始时间',
    Shift_End_Time TIME NOT NULL COMMENT '班次结束时间',
    Is_Active BOOLEAN DEFAULT TRUE COMMENT '是否启用此排班',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (Doctor_ID) REFERENCES doctor(Doctor_ID) ON DELETE CASCADE,
    UNIQUE KEY unique_doctor_day_shift (Doctor_ID, Day_of_Week, Shift_Start_Time),
    INDEX idx_doctor (Doctor_ID),
    INDEX idx_day_of_week (Day_of_Week),
    INDEX idx_is_active (Is_Active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='医生每周工作时间模板';

-- 5. 医生具体时间段表
CREATE TABLE IF NOT EXISTS doctor_time_slots (
    Slot_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '时间段ID',
    Doctor_ID INT NOT NULL COMMENT '医生ID',
    Slot_Date DATE NOT NULL COMMENT '时间段日期',
    Slot_Start_Time TIME NOT NULL COMMENT '时间段开始时间',
    Slot_End_Time TIME NOT NULL COMMENT '时间段结束时间',
    Max_Capacity INT NOT NULL DEFAULT 5 COMMENT '最大接诊人数',
    Current_Bookings INT NOT NULL DEFAULT 0 COMMENT '当前已预约人数',
    Is_Available BOOLEAN DEFAULT TRUE COMMENT '是否可预约',
    Slot_Type VARCHAR(20) DEFAULT '普通' COMMENT '时间段类型（普通/加号/特殊）',
    Notes TEXT COMMENT '备注',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (Doctor_ID) REFERENCES doctor(Doctor_ID) ON DELETE CASCADE,
    UNIQUE KEY unique_doctor_slot_time (Doctor_ID, Slot_Date, Slot_Start_Time),
    INDEX idx_doctor_date (Doctor_ID, Slot_Date),
    INDEX idx_slot_date (Slot_Date),
    INDEX idx_is_available (Is_Available),
    CONSTRAINT chk_capacity CHECK (Current_Bookings <= Max_Capacity),
    CONSTRAINT chk_positive_capacity CHECK (Max_Capacity > 0),
    CONSTRAINT chk_non_negative_bookings CHECK (Current_Bookings >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='医生具体时间段（自动生成的可预约单位）';

-- 6. 医生排班例外情况表
CREATE TABLE IF NOT EXISTS doctor_schedule_exceptions (
    Exception_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '例外ID',
    Doctor_ID INT NOT NULL COMMENT '医生ID',
    Exception_Date DATE NOT NULL COMMENT '例外日期',
    Exception_Type VARCHAR(20) NOT NULL COMMENT '例外类型（请假/节假日/临时调整）',
    Start_Time TIME COMMENT '开始时间（如果是部分时间调整）',
    End_Time TIME COMMENT '结束时间（如果是部分时间调整）',
    Is_Full_Day BOOLEAN DEFAULT TRUE COMMENT '是否全天',
    Reason TEXT COMMENT '原因说明',
    Replacement_Schedule TEXT COMMENT '替代安排（如有）',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (Doctor_ID) REFERENCES doctor(Doctor_ID) ON DELETE CASCADE,
    INDEX idx_doctor_date (Doctor_ID, Exception_Date),
    INDEX idx_exception_date (Exception_Date),
    INDEX idx_exception_type (Exception_Type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='医生排班例外情况（请假、节假日等）';

-- 7. 添加患者重复预约防护（如果还未添加）
-- 注意：如果已存在会报错，但不影响升级
-- ALTER TABLE appointment
-- ADD UNIQUE KEY unique_patient_appointment_time (Patient_ID, Appointment_Time);

-- 8. 添加外键约束到 appointment 表（如果Time_Slot_ID字段已存在且表已创建）
-- 注意：这个约束需要等doctor_time_slots表创建后才能添加
-- 如果已有此约束会报错，但不影响升级
-- ALTER TABLE appointment
-- ADD CONSTRAINT fk_appointment_time_slot 
-- FOREIGN KEY (Time_Slot_ID) REFERENCES doctor_time_slots(Slot_ID) ON DELETE SET NULL;

-- ==================== 第三部分：创建触发器 ====================

-- 删除旧触发器（如果存在）
DROP TRIGGER IF EXISTS trg_appointment_insert;
DROP TRIGGER IF EXISTS trg_appointment_update;
DROP TRIGGER IF EXISTS trg_appointment_delete;

DELIMITER $$

-- 触发器1：创建预约时增加 current_bookings
CREATE TRIGGER trg_appointment_insert
AFTER INSERT ON appointment
FOR EACH ROW
BEGIN
    IF NEW.Time_Slot_ID IS NOT NULL AND NEW.Appointment_Status IN ('已预约', '已确认') THEN
        UPDATE doctor_time_slots
        SET Current_Bookings = Current_Bookings + 1,
            Updated_At = CURRENT_TIMESTAMP
        WHERE Slot_ID = NEW.Time_Slot_ID;
    END IF;
END$$

-- 触发器2：取消预约时减少 current_bookings
CREATE TRIGGER trg_appointment_update
AFTER UPDATE ON appointment
FOR EACH ROW
BEGIN
    -- 预约被取消
    IF OLD.Appointment_Status IN ('已预约', '已确认')
       AND NEW.Appointment_Status IN ('已取消', '已完成', '未到')
       AND OLD.Time_Slot_ID IS NOT NULL THEN
        UPDATE doctor_time_slots
        SET Current_Bookings = Current_Bookings - 1,
            Updated_At = CURRENT_TIMESTAMP
        WHERE Slot_ID = OLD.Time_Slot_ID
          AND Current_Bookings > 0;
    END IF;

    -- 预约被重新激活
    IF OLD.Appointment_Status IN ('已取消', '未到')
       AND NEW.Appointment_Status IN ('已预约', '已确认')
       AND NEW.Time_Slot_ID IS NOT NULL THEN
        UPDATE doctor_time_slots
        SET Current_Bookings = Current_Bookings + 1,
            Updated_At = CURRENT_TIMESTAMP
        WHERE Slot_ID = NEW.Time_Slot_ID;
    END IF;

    -- 更换时间段
    IF OLD.Time_Slot_ID != NEW.Time_Slot_ID
       AND NEW.Appointment_Status IN ('已预约', '已确认') THEN
        -- 减少旧时间段
        IF OLD.Time_Slot_ID IS NOT NULL THEN
            UPDATE doctor_time_slots
            SET Current_Bookings = Current_Bookings - 1,
                Updated_At = CURRENT_TIMESTAMP
            WHERE Slot_ID = OLD.Time_Slot_ID
              AND Current_Bookings > 0;
        END IF;
        -- 增加新时间段
        IF NEW.Time_Slot_ID IS NOT NULL THEN
            UPDATE doctor_time_slots
            SET Current_Bookings = Current_Bookings + 1,
                Updated_At = CURRENT_TIMESTAMP
            WHERE Slot_ID = NEW.Time_Slot_ID;
        END IF;
    END IF;
END$$

-- 触发器3：删除预约时减少 current_bookings
CREATE TRIGGER trg_appointment_delete
AFTER DELETE ON appointment
FOR EACH ROW
BEGIN
    IF OLD.Time_Slot_ID IS NOT NULL AND OLD.Appointment_Status IN ('已预约', '已确认') THEN
        UPDATE doctor_time_slots
        SET Current_Bookings = Current_Bookings - 1,
            Updated_At = CURRENT_TIMESTAMP
        WHERE Slot_ID = OLD.Time_Slot_ID
          AND Current_Bookings > 0;
    END IF;
END$$

DELIMITER ;

-- ==================== 升级完成信息 ====================

SELECT '========================================' AS '';
SELECT 'V3 数据库升级完成！' AS message;
SELECT '========================================' AS '';
SELECT '升级内容：' AS '';
SELECT '1. doctor 表新增 V3 字段' AS upgrade_1;
SELECT '2. appointment 表新增 Time_Slot_ID 字段' AS upgrade_2;
SELECT '3. 新增 doctor_working_schedule 表' AS upgrade_3;
SELECT '4. 新增 doctor_time_slots 表' AS upgrade_4;
SELECT '5. 新增 doctor_schedule_exceptions 表' AS upgrade_5;
SELECT '6. 新增 3 个预约触发器' AS upgrade_6;
SELECT '========================================' AS '';
SELECT '下一步：' AS '';
SELECT '1. 运行 Python 脚本初始化医生排班' AS next_step_1;
SELECT '2. 生成未来3天时间段' AS next_step_2;
SELECT '========================================' AS '';


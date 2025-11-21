/*
================================================================================
修复所有表的 INT ID 列的 AUTO_INCREMENT 属性
================================================================================

问题:
  切换到 UUID 主键后, 所有的 INT ID 列失去了 AUTO_INCREMENT 属性
  导致插入记录时报错: Field 'XXX_ID' doesn't have a default value

解决方案:
  为所有核心表的 INT ID 列重新添加 AUTO_INCREMENT 属性
  这样触发器可以自动填充 INT ID, 向后兼容旧代码

影响表:
  - patient
  - medical_record
  - doctor
  - prescription
  - reminder
  - doctor_time_slots

日期: 2025-11-21
================================================================================
*/

USE medical_db;

SELECT '=== 开始修复 AUTO_INCREMENT 属性 ===' AS message;

SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================================
-- 1. patient 表
-- ============================================================================

SELECT '--- 修复 patient.Patient_ID ---' AS step;

-- 删除旧索引(如果存在)
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'patient'
           AND INDEX_NAME = 'idx_patient_id_legacy'),
    'ALTER TABLE patient DROP INDEX idx_patient_id_legacy',
    'SELECT "Index idx_patient_id_legacy does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 添加 AUTO_INCREMENT 并创建唯一索引
ALTER TABLE patient
    MODIFY COLUMN Patient_ID INT NOT NULL AUTO_INCREMENT COMMENT '患者ID(向后兼容)',
    ADD UNIQUE INDEX idx_patient_id_legacy (Patient_ID);

SELECT '✅ patient.Patient_ID 已修复' AS result;

-- ============================================================================
-- 2. medical_record 表
-- ============================================================================

SELECT '--- 修复 medical_record.Medical_Record_ID ---' AS step;

-- 删除旧索引(如果存在)
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'medical_record'
           AND INDEX_NAME = 'idx_medical_record_id_legacy'),
    'ALTER TABLE medical_record DROP INDEX idx_medical_record_id_legacy',
    'SELECT "Index idx_medical_record_id_legacy does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 添加 AUTO_INCREMENT 并创建唯一索引
ALTER TABLE medical_record
    MODIFY COLUMN Medical_Record_ID INT NOT NULL AUTO_INCREMENT COMMENT '病例ID(向后兼容)',
    ADD UNIQUE INDEX idx_medical_record_id_legacy (Medical_Record_ID);

SELECT '✅ medical_record.Medical_Record_ID 已修复' AS result;

-- ============================================================================
-- 3. doctor 表
-- ============================================================================

SELECT '--- 修复 doctor.Doctor_ID ---' AS step;

-- 删除旧索引(如果存在)
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'doctor'
           AND INDEX_NAME = 'idx_doctor_id_legacy'),
    'ALTER TABLE doctor DROP INDEX idx_doctor_id_legacy',
    'SELECT "Index idx_doctor_id_legacy does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 添加 AUTO_INCREMENT 并创建唯一索引
ALTER TABLE doctor
    MODIFY COLUMN Doctor_ID INT NOT NULL AUTO_INCREMENT COMMENT '医生ID(向后兼容)',
    ADD UNIQUE INDEX idx_doctor_id_legacy (Doctor_ID);

SELECT '✅ doctor.Doctor_ID 已修复' AS result;

-- ============================================================================
-- 4. prescription 表 (如果存在)
-- ============================================================================

SELECT '--- 检查并修复 prescription.Prescription_ID ---' AS step;

-- 检查 prescription 表是否存在
SET @has_prescription = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'medical_db'
      AND TABLE_NAME = 'prescription'
);

SET @sql = IF(
    @has_prescription > 0,
    CONCAT(
        'ALTER TABLE prescription ',
        'MODIFY COLUMN Prescription_ID INT NOT NULL AUTO_INCREMENT COMMENT \'处方ID(向后兼容)\', ',
        'ADD UNIQUE INDEX IF NOT EXISTS idx_prescription_id_legacy (Prescription_ID)'
    ),
    'SELECT "prescription table does not exist" AS notice'
);

-- 注意: MySQL不支持 IF NOT EXISTS 在 ADD INDEX 中, 所以需要先删除
SET @sql_drop = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'prescription'
           AND INDEX_NAME = 'idx_prescription_id_legacy'),
    'ALTER TABLE prescription DROP INDEX idx_prescription_id_legacy',
    'SELECT "Index idx_prescription_id_legacy does not exist" AS notice'
));
PREPARE stmt FROM @sql_drop;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 执行修复
SET @sql = IF(
    @has_prescription > 0,
    'ALTER TABLE prescription MODIFY COLUMN Prescription_ID INT NOT NULL AUTO_INCREMENT COMMENT \'处方ID(向后兼容)\', ADD UNIQUE INDEX idx_prescription_id_legacy (Prescription_ID)',
    'SELECT "prescription table does not exist" AS notice'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT IF(@has_prescription > 0, '✅ prescription.Prescription_ID 已修复', 'ℹ️  prescription 表不存在') AS result;

-- ============================================================================
-- 5. reminder 表 (如果存在)
-- ============================================================================

SELECT '--- 检查并修复 reminder.Reminder_ID ---' AS step;

-- 检查 reminder 表是否存在
SET @has_reminder = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'medical_db'
      AND TABLE_NAME = 'reminder'
);

-- 删除旧索引
SET @sql_drop = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'reminder'
           AND INDEX_NAME = 'idx_reminder_id_legacy'),
    'ALTER TABLE reminder DROP INDEX idx_reminder_id_legacy',
    'SELECT "Index idx_reminder_id_legacy does not exist" AS notice'
));
PREPARE stmt FROM @sql_drop;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 执行修复
SET @sql = IF(
    @has_reminder > 0,
    'ALTER TABLE reminder MODIFY COLUMN Reminder_ID INT NOT NULL AUTO_INCREMENT COMMENT \'提醒ID(向后兼容)\', ADD UNIQUE INDEX idx_reminder_id_legacy (Reminder_ID)',
    'SELECT "reminder table does not exist" AS notice'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT IF(@has_reminder > 0, '✅ reminder.Reminder_ID 已修复', 'ℹ️  reminder 表不存在') AS result;

-- ============================================================================
-- 6. doctor_time_slots 表 (如果存在)
-- ============================================================================

SELECT '--- 检查并修复 doctor_time_slots.Slot_ID ---' AS step;

-- 检查 doctor_time_slots 表是否存在
SET @has_time_slots = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'medical_db'
      AND TABLE_NAME = 'doctor_time_slots'
);

-- 删除旧索引
SET @sql_drop = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'doctor_time_slots'
           AND INDEX_NAME = 'idx_slot_id_legacy'),
    'ALTER TABLE doctor_time_slots DROP INDEX idx_slot_id_legacy',
    'SELECT "Index idx_slot_id_legacy does not exist" AS notice'
));
PREPARE stmt FROM @sql_drop;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 执行修复
SET @sql = IF(
    @has_time_slots > 0,
    'ALTER TABLE doctor_time_slots MODIFY COLUMN Slot_ID INT NOT NULL AUTO_INCREMENT COMMENT \'时间段ID(向后兼容)\', ADD UNIQUE INDEX idx_slot_id_legacy (Slot_ID)',
    'SELECT "doctor_time_slots table does not exist" AS notice'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT IF(@has_time_slots > 0, '✅ doctor_time_slots.Slot_ID 已修复', 'ℹ️  doctor_time_slots 表不存在') AS result;

-- ============================================================================
-- 7. 更新触发器 (确保触发器不依赖 INT ID)
-- ============================================================================

SELECT '=== 验证触发器 ===' AS message;

DELIMITER //

-- 7.1 patient 触发器
DROP TRIGGER IF EXISTS trg_patient_uuid_insert//
CREATE TRIGGER trg_patient_uuid_insert
BEFORE INSERT ON patient
FOR EACH ROW
BEGIN
    -- UUID 是主键,必须有值
    IF NEW.Patient_UUID IS NULL OR NEW.Patient_UUID = '' THEN
        SET NEW.Patient_UUID = UUID();
    END IF;

    -- Patient_ID 现在有 AUTO_INCREMENT, MySQL 会自动处理
END//

-- 7.2 medical_record 触发器
DROP TRIGGER IF EXISTS trg_medical_record_uuid_insert//
CREATE TRIGGER trg_medical_record_uuid_insert
BEFORE INSERT ON medical_record
FOR EACH ROW
BEGIN
    -- UUID 是主键,必须有值
    IF NEW.Medical_Record_UUID IS NULL OR NEW.Medical_Record_UUID = '' THEN
        SET NEW.Medical_Record_UUID = UUID();
    END IF;

    -- 自动填充外键UUID (如果只提供了 INT ID)
    IF NEW.Patient_UUID IS NULL AND NEW.Patient_ID IS NOT NULL THEN
        SET NEW.Patient_UUID = (SELECT Patient_UUID FROM patient WHERE Patient_ID = NEW.Patient_ID LIMIT 1);
    END IF;

    -- Medical_Record_ID 现在有 AUTO_INCREMENT, MySQL 会自动处理
END//

-- 7.3 doctor 触发器
DROP TRIGGER IF EXISTS trg_doctor_uuid_insert//
CREATE TRIGGER trg_doctor_uuid_insert
BEFORE INSERT ON doctor
FOR EACH ROW
BEGIN
    -- UUID 是主键,必须有值
    IF NEW.Doctor_UUID IS NULL OR NEW.Doctor_UUID = '' THEN
        SET NEW.Doctor_UUID = UUID();
    END IF;

    -- Doctor_ID 现在有 AUTO_INCREMENT, MySQL 会自动处理
END//

DELIMITER ;

SELECT '✅ 触发器已更新' AS result;

-- ============================================================================
-- 8. 验证修复结果
-- ============================================================================

SELECT '=== 验证 AUTO_INCREMENT 属性 ===' AS message;

SELECT
    TABLE_NAME,
    COLUMN_NAME,
    COLUMN_KEY,
    EXTRA,
    COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'medical_db'
  AND COLUMN_NAME IN ('Patient_ID', 'Medical_Record_ID', 'Doctor_ID', 'Appointment_ID',
                       'Prescription_ID', 'Reminder_ID', 'Slot_ID', 'Chat_ID')
  AND TABLE_NAME IN ('patient', 'medical_record', 'doctor', 'appointment',
                     'prescription', 'reminder', 'doctor_time_slots', 'chat_conversation')
ORDER BY TABLE_NAME, COLUMN_NAME;

SET FOREIGN_KEY_CHECKS = 1;

SELECT '=== 修复完成 ===' AS message;
SELECT '✅ 所有 INT ID 列已恢复 AUTO_INCREMENT 属性' AS status;
SELECT '✅ 触发器已更新为依赖 AUTO_INCREMENT' AS note;
SELECT 'ℹ️  现在可以正常插入记录,不会再出现 "doesn\'t have a default value" 错误' AS info;

/*
================================================================================
测试验证:
================================================================================

1. 测试患者创建:
   INSERT INTO patient (Patient_UUID, Name, Phone_Number, Gender, Age)
   VALUES (UUID(), '测试患者', '13900000000', '男', 30);

   -- 验证 Patient_ID 是否自动生成
   SELECT Patient_ID, Patient_UUID, Name FROM patient ORDER BY Patient_ID DESC LIMIT 1;

2. 测试病例创建:
   INSERT INTO medical_record (Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date)
   VALUES (UUID(), (SELECT Patient_UUID FROM patient LIMIT 1), '2025-000001', '2025-11-21');

   -- 验证 Medical_Record_ID 是否自动生成
   SELECT Medical_Record_ID, Medical_Record_UUID FROM medical_record ORDER BY Medical_Record_ID DESC LIMIT 1;

3. 运行应用测试:
   python test_appointment_uuid_debug.py

================================================================================
*/

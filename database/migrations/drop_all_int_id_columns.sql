/*
================================================================================
彻底删除所有INT ID列，只保留UUID主键
================================================================================

目标:
  1. 删除所有表的INT ID列 (Patient_ID, Medical_Record_ID, Doctor_ID等)
  2. 删除相关的外键约束和索引
  3. 更新触发器，移除INT ID相关逻辑
  4. 简化数据库结构，只使用UUID

警告: 这是破坏性操作，请确保已备份数据库！

日期: 2025-11-21
================================================================================
*/

USE medical_db;

SELECT '⚠️  警告: 即将删除所有INT ID列，此操作不可逆！' AS warning;
SELECT '✅ 请确认已备份数据库' AS notice;

SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================================
-- 阶段 1: 删除 appointment 表的INT ID相关字段
-- ============================================================================

SELECT '=== 处理 appointment 表 ===' AS message;

-- 1.1 删除 appointment 表中引用其他表INT ID的外键
-- (由于我们要删除这些列，需要先删除约束)

-- 删除与 Medical_Record_ID 相关的索引和外键
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'appointment'
           AND CONSTRAINT_NAME = 'fk_appointment_medical_record_id'),
    'ALTER TABLE appointment DROP FOREIGN KEY fk_appointment_medical_record_id',
    'SELECT "FK fk_appointment_medical_record_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 删除与 Patient_ID 相关的索引和外键
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'appointment'
           AND CONSTRAINT_NAME = 'fk_appointment_patient_id'),
    'ALTER TABLE appointment DROP FOREIGN KEY fk_appointment_patient_id',
    'SELECT "FK fk_appointment_patient_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 删除与 Doctor_ID 相关的索引和外键
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'appointment'
           AND CONSTRAINT_NAME = 'fk_appointment_doctor_id'),
    'ALTER TABLE appointment DROP FOREIGN KEY fk_appointment_doctor_id',
    'SELECT "FK fk_appointment_doctor_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 删除与 Time_Slot_ID 相关的索引和外键
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'appointment'
           AND CONSTRAINT_NAME = 'fk_appointment_time_slot_id'),
    'ALTER TABLE appointment DROP FOREIGN KEY fk_appointment_time_slot_id',
    'SELECT "FK fk_appointment_time_slot_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 1.2 删除 appointment 表中的所有INT ID列 (逐个删除,忽略不存在的列)
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'appointment' AND COLUMN_NAME = 'Appointment_ID'),
    'ALTER TABLE appointment DROP COLUMN Appointment_ID',
    'SELECT "Column Appointment_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'appointment' AND COLUMN_NAME = 'Medical_Record_ID'),
    'ALTER TABLE appointment DROP COLUMN Medical_Record_ID',
    'SELECT "Column Medical_Record_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'appointment' AND COLUMN_NAME = 'Patient_ID'),
    'ALTER TABLE appointment DROP COLUMN Patient_ID',
    'SELECT "Column Patient_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'appointment' AND COLUMN_NAME = 'Doctor_ID'),
    'ALTER TABLE appointment DROP COLUMN Doctor_ID',
    'SELECT "Column Doctor_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'appointment' AND COLUMN_NAME = 'Time_Slot_ID'),
    'ALTER TABLE appointment DROP COLUMN Time_Slot_ID',
    'SELECT "Column Time_Slot_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT '✅ appointment 表的INT ID列已删除' AS result;

-- ============================================================================
-- 阶段 2: 删除 medical_record 表的INT ID相关字段
-- ============================================================================

SELECT '=== 处理 medical_record 表 ===' AS message;

-- 2.1 删除外键约束
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'medical_record'
           AND CONSTRAINT_NAME = 'fk_medical_record_patient_id'),
    'ALTER TABLE medical_record DROP FOREIGN KEY fk_medical_record_patient_id',
    'SELECT "FK fk_medical_record_patient_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2.2 删除INT ID列 (逐个删除)
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'medical_record' AND COLUMN_NAME = 'Medical_Record_ID'),
    'ALTER TABLE medical_record DROP COLUMN Medical_Record_ID',
    'SELECT "Column Medical_Record_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'medical_record' AND COLUMN_NAME = 'Patient_ID'),
    'ALTER TABLE medical_record DROP COLUMN Patient_ID',
    'SELECT "Column Patient_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT '✅ medical_record 表的INT ID列已删除' AS result;

-- ============================================================================
-- 阶段 3: 删除 patient 表的INT ID
-- ============================================================================

SELECT '=== 处理 patient 表 ===' AS message;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'patient' AND COLUMN_NAME = 'Patient_ID'),
    'ALTER TABLE patient DROP COLUMN Patient_ID',
    'SELECT "Column Patient_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT '✅ patient 表的INT ID列已删除' AS result;

-- ============================================================================
-- 阶段 4: 删除 doctor 表的INT ID
-- ============================================================================

SELECT '=== 处理 doctor 表 ===' AS message;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'doctor' AND COLUMN_NAME = 'Doctor_ID'),
    'ALTER TABLE doctor DROP COLUMN Doctor_ID',
    'SELECT "Column Doctor_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT '✅ doctor 表的INT ID列已删除' AS result;

-- ============================================================================
-- 阶段 5: 删除 prescription 表的INT ID (如果存在)
-- ============================================================================

SELECT '=== 处理 prescription 表 ===' AS message;

SET @has_prescription = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'prescription'
);

-- 删除外键
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'prescription'
           AND CONSTRAINT_NAME = 'fk_prescription_medical_record_id'),
    'ALTER TABLE prescription DROP FOREIGN KEY fk_prescription_medical_record_id',
    'SELECT "FK fk_prescription_medical_record_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'prescription'
           AND CONSTRAINT_NAME = 'fk_prescription_doctor_id'),
    'ALTER TABLE prescription DROP FOREIGN KEY fk_prescription_doctor_id',
    'SELECT "FK fk_prescription_doctor_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 删除INT ID列 (需要逐列删除)
-- Prescription_ID
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'prescription' AND COLUMN_NAME = 'Prescription_ID'),
    'ALTER TABLE prescription DROP COLUMN Prescription_ID',
    'SELECT "Column Prescription_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Medical_Record_ID
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'prescription' AND COLUMN_NAME = 'Medical_Record_ID'),
    'ALTER TABLE prescription DROP COLUMN Medical_Record_ID',
    'SELECT "Column Medical_Record_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Doctor_ID
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'prescription' AND COLUMN_NAME = 'Doctor_ID'),
    'ALTER TABLE prescription DROP COLUMN Doctor_ID',
    'SELECT "Column Doctor_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT IF(@has_prescription > 0, '✅ prescription 表的INT ID列已删除', 'ℹ️  prescription 表不存在') AS result;

-- ============================================================================
-- 阶段 6: 删除 reminder 表的INT ID (如果存在)
-- ============================================================================

SELECT '=== 处理 reminder 表 ===' AS message;

SET @has_reminder = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'reminder'
);

-- 删除外键
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'reminder'
           AND CONSTRAINT_NAME = 'fk_reminder_appointment_id'),
    'ALTER TABLE reminder DROP FOREIGN KEY fk_reminder_appointment_id',
    'SELECT "FK fk_reminder_appointment_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'reminder'
           AND CONSTRAINT_NAME = 'fk_reminder_patient_id'),
    'ALTER TABLE reminder DROP FOREIGN KEY fk_reminder_patient_id',
    'SELECT "FK fk_reminder_patient_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 删除INT ID列 (需要逐列删除)
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'reminder' AND COLUMN_NAME = 'Reminder_ID'),
    'ALTER TABLE reminder DROP COLUMN Reminder_ID',
    'SELECT "Column Reminder_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'reminder' AND COLUMN_NAME = 'Appointment_ID'),
    'ALTER TABLE reminder DROP COLUMN Appointment_ID',
    'SELECT "Column Appointment_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'reminder' AND COLUMN_NAME = 'Patient_ID'),
    'ALTER TABLE reminder DROP COLUMN Patient_ID',
    'SELECT "Column Patient_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT IF(@has_reminder > 0, '✅ reminder 表的INT ID列已删除', 'ℹ️  reminder 表不存在') AS result;

-- ============================================================================
-- 阶段 7: 删除 doctor_time_slots 表的INT ID (如果存在)
-- ============================================================================

SELECT '=== 处理 doctor_time_slots 表 ===' AS message;

SET @has_time_slots = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'doctor_time_slots'
);

-- 删除外键
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'doctor_time_slots'
           AND CONSTRAINT_NAME = 'fk_time_slot_doctor_id'),
    'ALTER TABLE doctor_time_slots DROP FOREIGN KEY fk_time_slot_doctor_id',
    'SELECT "FK fk_time_slot_doctor_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 删除INT ID列 (需要逐列删除)
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'doctor_time_slots' AND COLUMN_NAME = 'Slot_ID'),
    'ALTER TABLE doctor_time_slots DROP COLUMN Slot_ID',
    'SELECT "Column Slot_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'doctor_time_slots' AND COLUMN_NAME = 'Doctor_ID'),
    'ALTER TABLE doctor_time_slots DROP COLUMN Doctor_ID',
    'SELECT "Column Doctor_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT IF(@has_time_slots > 0, '✅ doctor_time_slots 表的INT ID列已删除', 'ℹ️  doctor_time_slots 表不存在') AS result;

-- ============================================================================
-- 阶段 8: 删除 chat_conversation 和 chat_message 表的INT ID
-- ============================================================================

SELECT '=== 处理 chat_conversation 表 ===' AS message;

-- 删除 chat_message 中的外键
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'chat_message'
           AND CONSTRAINT_NAME = 'fk_chat_message_chat_id'),
    'ALTER TABLE chat_message DROP FOREIGN KEY fk_chat_message_chat_id',
    'SELECT "FK fk_chat_message_chat_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 删除 chat_conversation 的外键
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'chat_conversation'
           AND CONSTRAINT_NAME = 'fk_chat_conversation_patient_id'),
    'ALTER TABLE chat_conversation DROP FOREIGN KEY fk_chat_conversation_patient_id',
    'SELECT "FK fk_chat_conversation_patient_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'chat_conversation'
           AND CONSTRAINT_NAME = 'fk_chat_conversation_doctor_id'),
    'ALTER TABLE chat_conversation DROP FOREIGN KEY fk_chat_conversation_doctor_id',
    'SELECT "FK fk_chat_conversation_doctor_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 删除INT ID列 (需要逐列删除)
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'chat_conversation' AND COLUMN_NAME = 'Chat_ID'),
    'ALTER TABLE chat_conversation DROP COLUMN Chat_ID',
    'SELECT "Column Chat_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'chat_conversation' AND COLUMN_NAME = 'Patient_ID'),
    'ALTER TABLE chat_conversation DROP COLUMN Patient_ID',
    'SELECT "Column Patient_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'chat_conversation' AND COLUMN_NAME = 'Doctor_ID'),
    'ALTER TABLE chat_conversation DROP COLUMN Doctor_ID',
    'SELECT "Column Doctor_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT '✅ chat_conversation 表的INT ID列已删除' AS result;

SELECT '=== 处理 chat_message 表 ===' AS message;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'chat_message' AND COLUMN_NAME = 'Message_ID'),
    'ALTER TABLE chat_message DROP COLUMN Message_ID',
    'SELECT "Column Message_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'chat_message' AND COLUMN_NAME = 'Chat_ID'),
    'ALTER TABLE chat_message DROP COLUMN Chat_ID',
    'SELECT "Column Chat_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT '✅ chat_message 表的INT ID列已删除' AS result;

-- ============================================================================
-- 阶段 9: 删除 biomechanics_scan 表的INT ID
-- ============================================================================

SELECT '=== 处理 biomechanics_scan 表 ===' AS message;

-- 删除外键
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'biomechanics_scan'
           AND CONSTRAINT_NAME = 'fk_biomechanics_patient_id'),
    'ALTER TABLE biomechanics_scan DROP FOREIGN KEY fk_biomechanics_patient_id',
    'SELECT "FK fk_biomechanics_patient_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'biomechanics_scan'
           AND CONSTRAINT_NAME = 'fk_biomechanics_medical_record_id'),
    'ALTER TABLE biomechanics_scan DROP FOREIGN KEY fk_biomechanics_medical_record_id',
    'SELECT "FK fk_biomechanics_medical_record_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 删除INT ID列
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'biomechanics_scan' AND COLUMN_NAME = 'Scan_ID'),
    'ALTER TABLE biomechanics_scan DROP COLUMN Scan_ID',
    'SELECT "Column Scan_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'biomechanics_scan' AND COLUMN_NAME = 'Patient_ID'),
    'ALTER TABLE biomechanics_scan DROP COLUMN Patient_ID',
    'SELECT "Column Patient_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'biomechanics_scan' AND COLUMN_NAME = 'Medical_Record_ID'),
    'ALTER TABLE biomechanics_scan DROP COLUMN Medical_Record_ID',
    'SELECT "Column Medical_Record_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT '✅ biomechanics_scan 表的INT ID列已删除' AS result;

-- ============================================================================
-- 阶段 10: 删除 doctor_working_schedule 表的INT ID
-- ============================================================================

SELECT '=== 处理 doctor_working_schedule 表 ===' AS message;

-- 删除外键
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'doctor_working_schedule'
           AND CONSTRAINT_NAME = 'fk_working_schedule_doctor_id'),
    'ALTER TABLE doctor_working_schedule DROP FOREIGN KEY fk_working_schedule_doctor_id',
    'SELECT "FK fk_working_schedule_doctor_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 删除INT ID列
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'doctor_working_schedule' AND COLUMN_NAME = 'Schedule_ID'),
    'ALTER TABLE doctor_working_schedule DROP COLUMN Schedule_ID',
    'SELECT "Column Schedule_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'doctor_working_schedule' AND COLUMN_NAME = 'Doctor_ID'),
    'ALTER TABLE doctor_working_schedule DROP COLUMN Doctor_ID',
    'SELECT "Column Doctor_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT '✅ doctor_working_schedule 表的INT ID列已删除' AS result;

-- ============================================================================
-- 阶段 11: 删除 doctor_schedule_exceptions 表的INT ID
-- ============================================================================

SELECT '=== 处理 doctor_schedule_exceptions 表 ===' AS message;

-- 删除外键
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'doctor_schedule_exceptions'
           AND CONSTRAINT_NAME = 'fk_schedule_exceptions_doctor_id'),
    'ALTER TABLE doctor_schedule_exceptions DROP FOREIGN KEY fk_schedule_exceptions_doctor_id',
    'SELECT "FK fk_schedule_exceptions_doctor_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 删除INT ID列
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'doctor_schedule_exceptions' AND COLUMN_NAME = 'Exception_ID'),
    'ALTER TABLE doctor_schedule_exceptions DROP COLUMN Exception_ID',
    'SELECT "Column Exception_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'doctor_schedule_exceptions' AND COLUMN_NAME = 'Doctor_ID'),
    'ALTER TABLE doctor_schedule_exceptions DROP COLUMN Doctor_ID',
    'SELECT "Column Doctor_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT '✅ doctor_schedule_exceptions 表的INT ID列已删除' AS result;

-- ============================================================================
-- 阶段 12: 删除 prescription_detail 表的INT ID
-- ============================================================================

SELECT '=== 处理 prescription_detail 表 ===' AS message;

-- 删除外键
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'prescription_detail'
           AND CONSTRAINT_NAME = 'fk_prescription_detail_prescription_id'),
    'ALTER TABLE prescription_detail DROP FOREIGN KEY fk_prescription_detail_prescription_id',
    'SELECT "FK fk_prescription_detail_prescription_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'prescription_detail'
           AND CONSTRAINT_NAME = 'fk_prescription_detail_drug_id'),
    'ALTER TABLE prescription_detail DROP FOREIGN KEY fk_prescription_detail_drug_id',
    'SELECT "FK fk_prescription_detail_drug_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 删除INT ID列
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'prescription_detail' AND COLUMN_NAME = 'Detail_ID'),
    'ALTER TABLE prescription_detail DROP COLUMN Detail_ID',
    'SELECT "Column Detail_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'prescription_detail' AND COLUMN_NAME = 'Prescription_ID'),
    'ALTER TABLE prescription_detail DROP COLUMN Prescription_ID',
    'SELECT "Column Prescription_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT '✅ prescription_detail 表的INT ID列已删除' AS result;

-- ============================================================================
-- 阶段 13: 删除 reminder_history 表的INT ID
-- ============================================================================

SELECT '=== 处理 reminder_history 表 ===' AS message;

-- 删除外键
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'reminder_history'
           AND CONSTRAINT_NAME = 'fk_reminder_history_reminder_id'),
    'ALTER TABLE reminder_history DROP FOREIGN KEY fk_reminder_history_reminder_id',
    'SELECT "FK fk_reminder_history_reminder_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 删除INT ID列
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'reminder_history' AND COLUMN_NAME = 'History_ID'),
    'ALTER TABLE reminder_history DROP COLUMN History_ID',
    'SELECT "Column History_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'reminder_history' AND COLUMN_NAME = 'Reminder_ID'),
    'ALTER TABLE reminder_history DROP COLUMN Reminder_ID',
    'SELECT "Column Reminder_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT '✅ reminder_history 表的INT ID列已删除' AS result;

-- ============================================================================
-- 阶段 14: 删除 reminder_config 表的INT ID
-- ============================================================================

SELECT '=== 处理 reminder_config 表 ===' AS message;

-- 删除外键
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'reminder_config'
           AND CONSTRAINT_NAME = 'fk_reminder_config_patient_id'),
    'ALTER TABLE reminder_config DROP FOREIGN KEY fk_reminder_config_patient_id',
    'SELECT "FK fk_reminder_config_patient_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 删除INT ID列
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'reminder_config' AND COLUMN_NAME = 'Config_ID'),
    'ALTER TABLE reminder_config DROP COLUMN Config_ID',
    'SELECT "Column Config_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = 'reminder_config' AND COLUMN_NAME = 'Patient_ID'),
    'ALTER TABLE reminder_config DROP COLUMN Patient_ID',
    'SELECT "Column Patient_ID does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT '✅ reminder_config 表的INT ID列已删除' AS result;

-- ============================================================================
-- 阶段 15: 更新所有触发器 (移除INT ID逻辑)
-- ============================================================================

SELECT '=== 更新触发器 ===' AS message;

DELIMITER //

-- 9.1 patient 触发器
DROP TRIGGER IF EXISTS trg_patient_uuid_insert//
CREATE TRIGGER trg_patient_uuid_insert
BEFORE INSERT ON patient
FOR EACH ROW
BEGIN
    IF NEW.Patient_UUID IS NULL OR NEW.Patient_UUID = '' THEN
        SET NEW.Patient_UUID = UUID();
    END IF;
END//

-- 9.2 medical_record 触发器
DROP TRIGGER IF EXISTS trg_medical_record_uuid_insert//
CREATE TRIGGER trg_medical_record_uuid_insert
BEFORE INSERT ON medical_record
FOR EACH ROW
BEGIN
    IF NEW.Medical_Record_UUID IS NULL OR NEW.Medical_Record_UUID = '' THEN
        SET NEW.Medical_Record_UUID = UUID();
    END IF;

    -- Patient_UUID 必须提供 (不再从 Patient_ID 查询)
END//

-- 9.3 doctor 触发器
DROP TRIGGER IF EXISTS trg_doctor_uuid_insert//
CREATE TRIGGER trg_doctor_uuid_insert
BEFORE INSERT ON doctor
FOR EACH ROW
BEGIN
    IF NEW.Doctor_UUID IS NULL OR NEW.Doctor_UUID = '' THEN
        SET NEW.Doctor_UUID = UUID();
    END IF;
END//

-- 9.4 appointment 触发器
DROP TRIGGER IF EXISTS trg_appointment_uuid_insert//
CREATE TRIGGER trg_appointment_uuid_insert
BEFORE INSERT ON appointment
FOR EACH ROW
BEGIN
    IF NEW.Appointment_UUID IS NULL OR NEW.Appointment_UUID = '' THEN
        SET NEW.Appointment_UUID = UUID();
    END IF;

    -- 所有UUID字段必须由应用层提供
END//

-- 9.5 chat_conversation 触发器
DROP TRIGGER IF EXISTS trg_chat_conversation_uuid_insert//
CREATE TRIGGER trg_chat_conversation_uuid_insert
BEFORE INSERT ON chat_conversation
FOR EACH ROW
BEGIN
    IF NEW.Chat_UUID IS NULL OR NEW.Chat_UUID = '' THEN
        SET NEW.Chat_UUID = UUID();
    END IF;
END//

-- 9.6 chat_message 触发器
DROP TRIGGER IF EXISTS trg_chat_message_uuid_insert//
CREATE TRIGGER trg_chat_message_uuid_insert
BEFORE INSERT ON chat_message
FOR EACH ROW
BEGIN
    IF NEW.Message_UUID IS NULL OR NEW.Message_UUID = '' THEN
        SET NEW.Message_UUID = UUID();
    END IF;
END//

DELIMITER ;

SELECT '✅ 所有触发器已更新' AS result;

-- ============================================================================
-- 阶段 10: 验证结果
-- ============================================================================

SELECT '=== 验证INT ID列是否已删除 ===' AS message;

SELECT
    TABLE_NAME,
    COLUMN_NAME,
    COLUMN_TYPE,
    IS_NULLABLE,
    COLUMN_KEY
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'medical_db'
  AND (
    COLUMN_NAME LIKE '%_ID'
    OR COLUMN_NAME LIKE '%_UUID'
  )
  AND TABLE_NAME IN ('patient', 'medical_record', 'doctor', 'appointment',
                     'prescription', 'prescription_detail', 'reminder', 'reminder_history', 'reminder_config',
                     'doctor_time_slots', 'doctor_working_schedule', 'doctor_schedule_exceptions',
                     'biomechanics_scan', 'chat_conversation', 'chat_message')
ORDER BY TABLE_NAME, COLUMN_NAME;

-- 检查是否还有INT ID列残留
SELECT
    TABLE_NAME,
    COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'medical_db'
  AND COLUMN_NAME IN ('Patient_ID', 'Medical_Record_ID', 'Doctor_ID',
                      'Appointment_ID', 'Prescription_ID', 'Reminder_ID',
                      'Slot_ID', 'Chat_ID', 'Message_ID', 'Detail_ID',
                      'History_ID', 'Config_ID', 'Schedule_ID', 'Exception_ID', 'Scan_ID')
  AND TABLE_NAME IN ('patient', 'medical_record', 'doctor', 'appointment',
                     'prescription', 'prescription_detail', 'reminder', 'reminder_history', 'reminder_config',
                     'doctor_time_slots', 'doctor_working_schedule', 'doctor_schedule_exceptions',
                     'biomechanics_scan', 'chat_conversation', 'chat_message');

SET FOREIGN_KEY_CHECKS = 1;

SELECT '=== 迁移完成 ===' AS message;
SELECT '✅ 所有INT ID列已删除' AS status;
SELECT '✅ 数据库现在只使用UUID作为主键和外键' AS info;
SELECT '⚠️  请立即更新应用代码以适配新的数据库结构' AS warning;

/*
================================================================================
后续步骤:
================================================================================

1. 更新Python代码:
   - appointment_service_v3.py: 移除所有查询INT ID的代码
   - 所有service类: 移除normalize_id()和INT兼容逻辑
   - agent_1.py, agent_2.py: 移除提取INT ID的正则表达式
   - main.py: 更新API接口参数类型

2. 测试所有功能:
   - 患者创建
   - 病例创建
   - 预约创建
   - 报告生成
   - 处方生成
   - 聊天功能

3. 确认没有遗留问题后，可以删除备份文件

================================================================================
*/

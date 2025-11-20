/*
================================================================================
UUID迁移 - 回滚脚本 (全部阶段)
================================================================================

用途: 完全回滚UUID迁移,恢复到迁移前状态

警告: 此脚本将删除所有UUID列和相关索引/触发器
      仅在迁移失败或需要回退时使用

使用方法:
    mysql -u root -p medical_db < rollback_uuid_migration.sql

作者: System Migration
日期: 2025-11-20
================================================================================
*/

USE medical_db;

SELECT '=== 开始回滚UUID迁移 ===' AS message;
SELECT '警告: 将删除所有UUID列、索引和触发器' AS warning;
SELECT '按Ctrl+C取消,或等待5秒继续...' AS prompt;

-- 等待5秒(MySQL不支持SLEEP在脚本中,此行仅为提示)
-- DO SLEEP(5);

-- ============================================================================
-- 步骤 1: 删除所有UUID触发器
-- ============================================================================

SELECT '>>> 删除触发器...' AS step;

DROP TRIGGER IF EXISTS trg_patient_uuid_insert;
DROP TRIGGER IF EXISTS trg_medical_record_uuid_insert;
DROP TRIGGER IF EXISTS trg_doctor_uuid_insert;
DROP TRIGGER IF EXISTS trg_appointment_uuid_insert;
DROP TRIGGER IF EXISTS trg_prescription_uuid_insert;
DROP TRIGGER IF EXISTS trg_prescription_detail_uuid_insert;
DROP TRIGGER IF EXISTS trg_chat_conversation_uuid_insert;
DROP TRIGGER IF EXISTS trg_chat_message_uuid_insert;
DROP TRIGGER IF EXISTS trg_doctor_working_schedule_uuid_insert;
DROP TRIGGER IF EXISTS trg_doctor_time_slots_uuid_insert;
DROP TRIGGER IF EXISTS trg_reminder_uuid_insert;
DROP TRIGGER IF EXISTS trg_biomechanics_scan_uuid_insert;

-- ============================================================================
-- 步骤 2: 第一阶段回滚 - 核心表
-- ============================================================================

SELECT '>>> 回滚第一阶段 (核心表)...' AS step;

-- 2.1 patient表
ALTER TABLE patient
    DROP INDEX IF EXISTS idx_patient_uuid,
    DROP INDEX IF EXISTS idx_patient_migration,
    DROP COLUMN IF EXISTS Patient_UUID,
    DROP COLUMN IF EXISTS _migration_flag;

-- 2.2 medical_record表
ALTER TABLE medical_record
    DROP INDEX IF EXISTS idx_medical_record_uuid,
    DROP INDEX IF EXISTS idx_medical_record_patient_uuid,
    DROP INDEX IF EXISTS idx_medical_record_migration,
    DROP COLUMN IF EXISTS Medical_Record_UUID,
    DROP COLUMN IF EXISTS Patient_UUID,
    DROP COLUMN IF EXISTS _migration_flag;

-- 2.3 doctor表
ALTER TABLE doctor
    DROP INDEX IF EXISTS idx_doctor_uuid,
    DROP INDEX IF EXISTS idx_doctor_migration,
    DROP COLUMN IF EXISTS Doctor_UUID,
    DROP COLUMN IF EXISTS _migration_flag;

-- ============================================================================
-- 步骤 3: 第二阶段回滚 - 业务表
-- ============================================================================

SELECT '>>> 回滚第二阶段 (业务表)...' AS step;

-- 3.1 appointment表
ALTER TABLE appointment
    DROP INDEX IF EXISTS idx_appointment_uuid,
    DROP INDEX IF EXISTS idx_appointment_patient_uuid,
    DROP INDEX IF EXISTS idx_appointment_doctor_uuid,
    DROP INDEX IF EXISTS idx_appointment_medical_record_uuid,
    DROP INDEX IF EXISTS idx_appointment_time_slot_uuid,
    DROP INDEX IF EXISTS idx_appointment_migration,
    DROP COLUMN IF EXISTS Appointment_UUID,
    DROP COLUMN IF EXISTS Patient_UUID,
    DROP COLUMN IF EXISTS Doctor_UUID,
    DROP COLUMN IF EXISTS Medical_Record_UUID,
    DROP COLUMN IF EXISTS Time_Slot_UUID,
    DROP COLUMN IF EXISTS _migration_flag;

-- 3.2 prescription表
ALTER TABLE prescription
    DROP INDEX IF EXISTS idx_prescription_uuid,
    DROP INDEX IF EXISTS idx_prescription_patient_uuid,
    DROP INDEX IF EXISTS idx_prescription_doctor_uuid,
    DROP INDEX IF EXISTS idx_prescription_medical_record_uuid,
    DROP INDEX IF EXISTS idx_prescription_migration,
    DROP COLUMN IF EXISTS Prescription_UUID,
    DROP COLUMN IF EXISTS Patient_UUID,
    DROP COLUMN IF EXISTS Doctor_UUID,
    DROP COLUMN IF EXISTS Medical_Record_UUID,
    DROP COLUMN IF EXISTS _migration_flag;

-- 3.3 prescription_detail表
ALTER TABLE prescription_detail
    DROP INDEX IF EXISTS idx_prescription_detail_uuid,
    DROP INDEX IF EXISTS idx_prescription_detail_prescription_uuid,
    DROP INDEX IF EXISTS idx_prescription_detail_migration,
    DROP COLUMN IF EXISTS Detail_UUID,
    DROP COLUMN IF EXISTS Prescription_UUID,
    DROP COLUMN IF EXISTS _migration_flag;

-- 3.4 chat_conversation表
ALTER TABLE chat_conversation
    DROP INDEX IF EXISTS idx_chat_conversation_uuid,
    DROP INDEX IF EXISTS idx_chat_conversation_patient_uuid,
    DROP INDEX IF EXISTS idx_chat_conversation_doctor_uuid,
    DROP INDEX IF EXISTS idx_chat_conversation_migration,
    DROP COLUMN IF EXISTS Chat_UUID,
    DROP COLUMN IF EXISTS Patient_UUID,
    DROP COLUMN IF EXISTS Doctor_UUID,
    DROP COLUMN IF EXISTS _migration_flag;

-- 3.5 chat_message表
ALTER TABLE chat_message
    DROP INDEX IF EXISTS idx_chat_message_uuid,
    DROP INDEX IF EXISTS idx_chat_message_chat_uuid,
    DROP INDEX IF EXISTS idx_chat_message_chat_uuid_order,
    DROP INDEX IF EXISTS idx_chat_message_migration,
    DROP COLUMN IF EXISTS Message_UUID,
    DROP COLUMN IF EXISTS Chat_UUID,
    DROP COLUMN IF EXISTS _migration_flag;

-- ============================================================================
-- 步骤 4: 第三阶段回滚 - 辅助表
-- ============================================================================

SELECT '>>> 回滚第三阶段 (辅助表)...' AS step;

-- 4.1 doctor_working_schedule表
ALTER TABLE doctor_working_schedule
    DROP INDEX IF EXISTS idx_doctor_working_schedule_uuid,
    DROP INDEX IF EXISTS idx_doctor_working_schedule_doctor_uuid,
    DROP COLUMN IF EXISTS Schedule_UUID,
    DROP COLUMN IF EXISTS Doctor_UUID,
    DROP COLUMN IF EXISTS _migration_flag;

-- 4.2 doctor_time_slots表
ALTER TABLE doctor_time_slots
    DROP INDEX IF EXISTS idx_doctor_time_slots_uuid,
    DROP INDEX IF EXISTS idx_doctor_time_slots_doctor_uuid,
    DROP COLUMN IF EXISTS Slot_UUID,
    DROP COLUMN IF EXISTS Doctor_UUID,
    DROP COLUMN IF EXISTS _migration_flag;

-- 4.3 doctor_schedule_exceptions表
ALTER TABLE doctor_schedule_exceptions
    DROP INDEX IF EXISTS idx_doctor_schedule_exceptions_uuid,
    DROP INDEX IF EXISTS idx_doctor_schedule_exceptions_doctor_uuid,
    DROP COLUMN IF EXISTS Exception_UUID,
    DROP COLUMN IF EXISTS Doctor_UUID,
    DROP COLUMN IF EXISTS _migration_flag;

-- 4.4 reminder表
ALTER TABLE reminder
    DROP INDEX IF EXISTS idx_reminder_uuid,
    DROP INDEX IF EXISTS idx_reminder_patient_uuid,
    DROP INDEX IF EXISTS idx_reminder_medical_record_uuid,
    DROP INDEX IF EXISTS idx_reminder_appointment_uuid,
    DROP INDEX IF EXISTS idx_reminder_prescription_uuid,
    DROP COLUMN IF EXISTS Reminder_UUID,
    DROP COLUMN IF EXISTS Patient_UUID,
    DROP COLUMN IF EXISTS Medical_Record_UUID,
    DROP COLUMN IF EXISTS Appointment_UUID,
    DROP COLUMN IF EXISTS Prescription_UUID,
    DROP COLUMN IF EXISTS _migration_flag;

-- 4.5 reminder_history表
ALTER TABLE reminder_history
    DROP INDEX IF EXISTS idx_reminder_history_uuid,
    DROP INDEX IF EXISTS idx_reminder_history_reminder_uuid,
    DROP COLUMN IF EXISTS History_UUID,
    DROP COLUMN IF EXISTS Reminder_UUID,
    DROP COLUMN IF EXISTS _migration_flag;

-- 4.6 reminder_config表
ALTER TABLE reminder_config
    DROP INDEX IF EXISTS idx_reminder_config_uuid,
    DROP INDEX IF EXISTS idx_reminder_config_patient_uuid,
    DROP COLUMN IF EXISTS Config_UUID,
    DROP COLUMN IF EXISTS Patient_UUID,
    DROP COLUMN IF EXISTS _migration_flag;

-- 4.7 biomechanics_scan表
ALTER TABLE biomechanics_scan
    DROP INDEX IF EXISTS idx_biomechanics_scan_uuid,
    DROP INDEX IF EXISTS idx_biomechanics_scan_patient_uuid,
    DROP INDEX IF EXISTS idx_biomechanics_scan_medical_record_uuid,
    DROP COLUMN IF EXISTS Scan_UUID,
    DROP COLUMN IF EXISTS Patient_UUID,
    DROP COLUMN IF EXISTS Medical_Record_UUID,
    DROP COLUMN IF EXISTS _migration_flag;

-- ============================================================================
-- 步骤 5: 删除迁移日志表
-- ============================================================================

SELECT '>>> 删除迁移日志表...' AS step;

DROP TABLE IF EXISTS _uuid_migration_log;

-- ============================================================================
-- 步骤 6: 验证回滚结果
-- ============================================================================

SELECT '=== 回滚完成验证 ===' AS message;

-- 验证patient表(应只有Patient_ID主键)
SELECT
    'patient' AS table_name,
    COLUMN_NAME,
    DATA_TYPE,
    COLUMN_KEY
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'medical_db'
  AND TABLE_NAME = 'patient'
  AND COLUMN_NAME LIKE '%UUID%';
-- 应返回0行

-- 检查所有表是否还有UUID列残留
SELECT
    TABLE_NAME,
    COLUMN_NAME,
    DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'medical_db'
  AND (COLUMN_NAME LIKE '%UUID%' OR COLUMN_NAME = '_migration_flag')
ORDER BY TABLE_NAME, COLUMN_NAME;
-- 应返回0行

-- 检查触发器是否已删除
SELECT
    TRIGGER_NAME,
    EVENT_OBJECT_TABLE
FROM INFORMATION_SCHEMA.TRIGGERS
WHERE TRIGGER_SCHEMA = 'medical_db'
  AND TRIGGER_NAME LIKE '%uuid%';
-- 应返回0行

-- ============================================================================
-- 完成信息
-- ============================================================================

SELECT '=== UUID迁移回滚完成 ===' AS message;
SELECT '所有UUID列、索引和触发器已删除' AS status;
SELECT '数据库已恢复到迁移前状态' AS result;
SELECT 'INT AUTO_INCREMENT主键继续有效' AS note;

/*
================================================================================
回滚完成后的操作:
================================================================================

1. 验证应用程序功能:
   - 所有API端点应正常工作
   - 数据查询应使用INT ID

2. 检查数据完整性:
   - 所有外键关联应正常
   - 自增ID功能正常

3. 如需重新迁移:
   - 从phase1开始重新执行迁移脚本
   - 确保修复导致回滚的问题

================================================================================
注意事项:
================================================================================

⚠️  回滚后的数据库结构与迁移前完全相同
⚠️  如果在迁移期间创建了新记录,这些记录的INT ID将保留
⚠️  确保应用程序代码已恢复为使用INT ID的版本

================================================================================
*/

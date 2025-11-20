/*
================================================================================
添加系统管理字段 + 扩展appointment表 (简化版)
================================================================================

目标:
  1. 为所有表添加系统管理字段 (Create_By, Update_By, Version, Deleted)
  2. 扩展appointment表支持通用日程功能
  3. 添加必要的索引

执行时间: 预计 5-10分钟
作者: System Migration
日期: 2025-11-20
================================================================================
*/

USE medical_db;

SET FOREIGN_KEY_CHECKS = 0;
SET NAMES utf8mb4;

SELECT '========================================' AS '';
SELECT 'Starting Migration: Add System Fields' AS message;
SELECT '========================================' AS '';

-- ============================================================================
-- 第1步: patient表 - 添加系统字段
-- ============================================================================

SELECT 'Step 1: Adding system fields to patient table' AS status;

ALTER TABLE patient
    ADD COLUMN IF NOT EXISTS Create_By VARCHAR(36) COMMENT '创建人UUID',
    ADD COLUMN IF NOT EXISTS Update_By VARCHAR(36) COMMENT '更新人UUID',
    ADD COLUMN IF NOT EXISTS Version INT DEFAULT 0 COMMENT '乐观锁版本号',
    ADD COLUMN IF NOT EXISTS Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记(0-未删除,1-已删除)';

-- ============================================================================
-- 第2步: medical_record表
-- ============================================================================

SELECT 'Step 2: Adding system fields to medical_record table' AS status;

ALTER TABLE medical_record
    ADD COLUMN IF NOT EXISTS Create_By VARCHAR(36) COMMENT '创建人UUID',
    ADD COLUMN IF NOT EXISTS Update_By VARCHAR(36) COMMENT '更新人UUID',
    ADD COLUMN IF NOT EXISTS Version INT DEFAULT 0 COMMENT '乐观锁版本号',
    ADD COLUMN IF NOT EXISTS Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

-- ============================================================================
-- 第3步: doctor表
-- ============================================================================

SELECT 'Step 3: Adding system fields to doctor table' AS status;

ALTER TABLE doctor
    ADD COLUMN IF NOT EXISTS Create_By VARCHAR(36) COMMENT '创建人UUID',
    ADD COLUMN IF NOT EXISTS Update_By VARCHAR(36) COMMENT '更新人UUID',
    ADD COLUMN IF NOT EXISTS Version INT DEFAULT 0 COMMENT '乐观锁版本号',
    ADD COLUMN IF NOT EXISTS Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

-- ============================================================================
-- 第4步: drugs表
-- ============================================================================

SELECT 'Step 4: Adding system fields to drugs table' AS status;

ALTER TABLE drugs
    ADD COLUMN IF NOT EXISTS Create_By VARCHAR(36) COMMENT '创建人UUID',
    ADD COLUMN IF NOT EXISTS Update_By VARCHAR(36) COMMENT '更新人UUID',
    ADD COLUMN IF NOT EXISTS Version INT DEFAULT 0 COMMENT '乐观锁版本号',
    ADD COLUMN IF NOT EXISTS Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

-- ============================================================================
-- 第5步: prescription表
-- ============================================================================

SELECT 'Step 5: Adding system fields to prescription table' AS status;

ALTER TABLE prescription
    ADD COLUMN IF NOT EXISTS Create_By VARCHAR(36) COMMENT '创建人UUID',
    ADD COLUMN IF NOT EXISTS Update_By VARCHAR(36) COMMENT '更新人UUID',
    ADD COLUMN IF NOT EXISTS Version INT DEFAULT 0 COMMENT '乐观锁版本号',
    ADD COLUMN IF NOT EXISTS Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

-- ============================================================================
-- 第6步: prescription_detail表
-- ============================================================================

SELECT 'Step 6: Adding system fields to prescription_detail table' AS status;

ALTER TABLE prescription_detail
    ADD COLUMN IF NOT EXISTS Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    ADD COLUMN IF NOT EXISTS Create_By VARCHAR(36) COMMENT '创建人UUID',
    ADD COLUMN IF NOT EXISTS Update_By VARCHAR(36) COMMENT '更新人UUID',
    ADD COLUMN IF NOT EXISTS Version INT DEFAULT 0 COMMENT '乐观锁版本号',
    ADD COLUMN IF NOT EXISTS Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

-- ============================================================================
-- 第7步: appointment表 - 添加系统字段 + 通用日程支持
-- ============================================================================

SELECT 'Step 7: Extending appointment table' AS status;

ALTER TABLE appointment
    ADD COLUMN IF NOT EXISTS Create_By VARCHAR(36) COMMENT '创建人UUID',
    ADD COLUMN IF NOT EXISTS Update_By VARCHAR(36) COMMENT '更新人UUID',
    ADD COLUMN IF NOT EXISTS Version INT DEFAULT 0 COMMENT '乐观锁版本号',
    ADD COLUMN IF NOT EXISTS Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记',
    ADD COLUMN IF NOT EXISTS Is_Generic_Event BOOLEAN DEFAULT FALSE COMMENT '是否为通用日程事件(非患者预约)',
    ADD COLUMN IF NOT EXISTS Event_Type VARCHAR(50) DEFAULT 'appointment' COMMENT '事件类型(appointment/meeting/personal_task/reminder)',
    ADD COLUMN IF NOT EXISTS Notes TEXT COMMENT '日程备注(补充Description字段)';

-- ============================================================================
-- 第8步: reminder_config表
-- ============================================================================

SELECT 'Step 8: Adding system fields to reminder_config table' AS status;

ALTER TABLE reminder_config
    ADD COLUMN IF NOT EXISTS Create_By VARCHAR(36) COMMENT '创建人UUID',
    ADD COLUMN IF NOT EXISTS Update_By VARCHAR(36) COMMENT '更新人UUID',
    ADD COLUMN IF NOT EXISTS Version INT DEFAULT 0 COMMENT '乐观锁版本号',
    ADD COLUMN IF NOT EXISTS Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

-- ============================================================================
-- 第9步: reminder表
-- ============================================================================

SELECT 'Step 9: Adding system fields to reminder table' AS status;

ALTER TABLE reminder
    ADD COLUMN IF NOT EXISTS Update_By VARCHAR(36) COMMENT '更新人UUID',
    ADD COLUMN IF NOT EXISTS Version INT DEFAULT 0 COMMENT '乐观锁版本号',
    ADD COLUMN IF NOT EXISTS Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

-- ============================================================================
-- 第10步: reminder_history表
-- ============================================================================

SELECT 'Step 10: Adding system fields to reminder_history table' AS status;

ALTER TABLE reminder_history
    ADD COLUMN IF NOT EXISTS Create_Time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    ADD COLUMN IF NOT EXISTS Create_By VARCHAR(36) COMMENT '创建人UUID',
    ADD COLUMN IF NOT EXISTS Update_Time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    ADD COLUMN IF NOT EXISTS Update_By VARCHAR(36) COMMENT '更新人UUID',
    ADD COLUMN IF NOT EXISTS Version INT DEFAULT 0 COMMENT '乐观锁版本号',
    ADD COLUMN IF NOT EXISTS Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

-- ============================================================================
-- 第11步: 辅助表 (doctor_working_schedule, doctor_time_slots等)
-- ============================================================================

SELECT 'Step 11: Adding system fields to auxiliary tables' AS status;

ALTER TABLE doctor_working_schedule
    ADD COLUMN IF NOT EXISTS Create_By VARCHAR(36) COMMENT '创建人UUID',
    ADD COLUMN IF NOT EXISTS Update_By VARCHAR(36) COMMENT '更新人UUID',
    ADD COLUMN IF NOT EXISTS Version INT DEFAULT 0 COMMENT '乐观锁版本号',
    ADD COLUMN IF NOT EXISTS Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

ALTER TABLE doctor_time_slots
    ADD COLUMN IF NOT EXISTS Create_By VARCHAR(36) COMMENT '创建人UUID',
    ADD COLUMN IF NOT EXISTS Update_By VARCHAR(36) COMMENT '更新人UUID',
    ADD COLUMN IF NOT EXISTS Version INT DEFAULT 0 COMMENT '乐观锁版本号',
    ADD COLUMN IF NOT EXISTS Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

ALTER TABLE doctor_schedule_exceptions
    ADD COLUMN IF NOT EXISTS Create_By VARCHAR(36) COMMENT '创建人UUID',
    ADD COLUMN IF NOT EXISTS Update_By VARCHAR(36) COMMENT '更新人UUID',
    ADD COLUMN IF NOT EXISTS Version INT DEFAULT 0 COMMENT '乐观锁版本号',
    ADD COLUMN IF NOT EXISTS Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

ALTER TABLE biomechanics_scan
    ADD COLUMN IF NOT EXISTS Create_By VARCHAR(36) COMMENT '创建人UUID',
    ADD COLUMN IF NOT EXISTS Update_By VARCHAR(36) COMMENT '更新人UUID',
    ADD COLUMN IF NOT EXISTS Version INT DEFAULT 0 COMMENT '乐观锁版本号',
    ADD COLUMN IF NOT EXISTS Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

ALTER TABLE chat_conversation
    ADD COLUMN IF NOT EXISTS Create_By VARCHAR(36) COMMENT '创建人UUID',
    ADD COLUMN IF NOT EXISTS Update_By VARCHAR(36) COMMENT '更新人UUID',
    ADD COLUMN IF NOT EXISTS Version INT DEFAULT 0 COMMENT '乐观锁版本号',
    ADD COLUMN IF NOT EXISTS Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

ALTER TABLE chat_message
    ADD COLUMN IF NOT EXISTS Create_By VARCHAR(36) COMMENT '创建人UUID',
    ADD COLUMN IF NOT EXISTS Update_By VARCHAR(36) COMMENT '更新人UUID',
    ADD COLUMN IF NOT EXISTS Version INT DEFAULT 0 COMMENT '乐观锁版本号',
    ADD COLUMN IF NOT EXISTS Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

-- ============================================================================
-- 第12步: 添加索引
-- ============================================================================

SELECT 'Step 12: Adding indexes' AS status;

-- 为所有表的Deleted字段添加索引 (如果不存在会报错，但不影响)
ALTER TABLE patient ADD INDEX idx_deleted (Deleted);
ALTER TABLE medical_record ADD INDEX idx_deleted (Deleted);
ALTER TABLE doctor ADD INDEX idx_deleted (Deleted);
ALTER TABLE drugs ADD INDEX idx_deleted (Deleted);
ALTER TABLE prescription ADD INDEX idx_deleted (Deleted);
ALTER TABLE prescription_detail ADD INDEX idx_deleted (Deleted);
ALTER TABLE appointment ADD INDEX idx_deleted (Deleted);
ALTER TABLE reminder ADD INDEX idx_deleted (Deleted);
ALTER TABLE reminder_config ADD INDEX idx_deleted (Deleted);
ALTER TABLE reminder_history ADD INDEX idx_deleted (Deleted);
ALTER TABLE doctor_working_schedule ADD INDEX idx_deleted (Deleted);
ALTER TABLE doctor_time_slots ADD INDEX idx_deleted (Deleted);
ALTER TABLE doctor_schedule_exceptions ADD INDEX idx_deleted (Deleted);
ALTER TABLE biomechanics_scan ADD INDEX idx_deleted (Deleted);
ALTER TABLE chat_conversation ADD INDEX idx_deleted (Deleted);
ALTER TABLE chat_message ADD INDEX idx_deleted (Deleted);

-- 为appointment表添加通用日程相关索引
ALTER TABLE appointment ADD INDEX idx_event_type (Event_Type);
ALTER TABLE appointment ADD INDEX idx_is_generic (Is_Generic_Event);

-- ============================================================================
-- 完成总结
-- ============================================================================

SELECT '========================================' AS '';
SELECT 'Migration Completed!' AS message;
SELECT '========================================' AS '';

SELECT 'Summary:' AS '';
SELECT '  1. System fields added to all tables (Create_By, Update_By, Version, Deleted)' AS item_1;
SELECT '  2. Appointment table extended (Is_Generic_Event, Event_Type, Notes)' AS item_2;
SELECT '  3. Deleted indexes added to all tables' AS item_3;
SELECT '  4. Appointment agenda indexes added' AS item_4;
SELECT '========================================' AS '';

SET FOREIGN_KEY_CHECKS = 1;

/*
================================================================================
Migration Complete!
================================================================================

Next Steps:
1. Verify migration: python verify_migration.py
2. Update application code to use new fields
3. Test all functionality

================================================================================
*/

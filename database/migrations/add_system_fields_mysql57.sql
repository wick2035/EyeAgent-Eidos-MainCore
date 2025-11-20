/*
================================================================================
添加系统管理字段 + 扩展appointment表 (MySQL 5.7兼容版)
================================================================================

执行时间: 预计 5-10分钟
作者: System Migration
日期: 2025-11-20
================================================================================
*/

USE medical_db;

SET FOREIGN_KEY_CHECKS = 0;
SET NAMES utf8mb4;

SELECT '========================================' AS '';
SELECT 'Starting Migration' AS message;
SELECT '========================================' AS '';

-- ============================================================================
-- 第1-11步: 添加系统字段 (尝试添加，如果存在会报错但继续执行)
-- ============================================================================

-- patient表
SELECT 'Step 1: patient table' AS status;
ALTER TABLE patient ADD COLUMN Create_By VARCHAR(36) COMMENT '创建人UUID';
ALTER TABLE patient ADD COLUMN Update_By VARCHAR(36) COMMENT '更新人UUID';
ALTER TABLE patient ADD COLUMN Version INT DEFAULT 0 COMMENT '乐观锁版本号';
ALTER TABLE patient ADD COLUMN Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

-- medical_record表
SELECT 'Step 2: medical_record table' AS status;
ALTER TABLE medical_record ADD COLUMN Create_By VARCHAR(36) COMMENT '创建人UUID';
ALTER TABLE medical_record ADD COLUMN Update_By VARCHAR(36) COMMENT '更新人UUID';
ALTER TABLE medical_record ADD COLUMN Version INT DEFAULT 0 COMMENT '乐观锁版本号';
ALTER TABLE medical_record ADD COLUMN Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

-- doctor表
SELECT 'Step 3: doctor table' AS status;
ALTER TABLE doctor ADD COLUMN Create_By VARCHAR(36) COMMENT '创建人UUID';
ALTER TABLE doctor ADD COLUMN Update_By VARCHAR(36) COMMENT '更新人UUID';
ALTER TABLE doctor ADD COLUMN Version INT DEFAULT 0 COMMENT '乐观锁版本号';
ALTER TABLE doctor ADD COLUMN Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

-- drugs表
SELECT 'Step 4: drugs table' AS status;
ALTER TABLE drugs ADD COLUMN Create_By VARCHAR(36) COMMENT '创建人UUID';
ALTER TABLE drugs ADD COLUMN Update_By VARCHAR(36) COMMENT '更新人UUID';
ALTER TABLE drugs ADD COLUMN Version INT DEFAULT 0 COMMENT '乐观锁版本号';
ALTER TABLE drugs ADD COLUMN Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

-- prescription表
SELECT 'Step 5: prescription table' AS status;
ALTER TABLE prescription ADD COLUMN Create_By VARCHAR(36) COMMENT '创建人UUID';
ALTER TABLE prescription ADD COLUMN Update_By VARCHAR(36) COMMENT '更新人UUID';
ALTER TABLE prescription ADD COLUMN Version INT DEFAULT 0 COMMENT '乐观锁版本号';
ALTER TABLE prescription ADD COLUMN Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

-- prescription_detail表
SELECT 'Step 6: prescription_detail table' AS status;
ALTER TABLE prescription_detail ADD COLUMN Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间';
ALTER TABLE prescription_detail ADD COLUMN Create_By VARCHAR(36) COMMENT '创建人UUID';
ALTER TABLE prescription_detail ADD COLUMN Update_By VARCHAR(36) COMMENT '更新人UUID';
ALTER TABLE prescription_detail ADD COLUMN Version INT DEFAULT 0 COMMENT '乐观锁版本号';
ALTER TABLE prescription_detail ADD COLUMN Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

-- appointment表 (系统字段 + 通用日程)
SELECT 'Step 7: appointment table (system fields + agenda extension)' AS status;
ALTER TABLE appointment ADD COLUMN Create_By VARCHAR(36) COMMENT '创建人UUID';
ALTER TABLE appointment ADD COLUMN Update_By VARCHAR(36) COMMENT '更新人UUID';
ALTER TABLE appointment ADD COLUMN Version INT DEFAULT 0 COMMENT '乐观锁版本号';
ALTER TABLE appointment ADD COLUMN Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';
ALTER TABLE appointment ADD COLUMN Is_Generic_Event BOOLEAN DEFAULT FALSE COMMENT '是否为通用日程事件';
ALTER TABLE appointment ADD COLUMN Event_Type VARCHAR(50) DEFAULT 'appointment' COMMENT '事件类型';
ALTER TABLE appointment ADD COLUMN Notes TEXT COMMENT '日程备注';

-- reminder_config表
SELECT 'Step 8: reminder_config table' AS status;
ALTER TABLE reminder_config ADD COLUMN Create_By VARCHAR(36) COMMENT '创建人UUID';
ALTER TABLE reminder_config ADD COLUMN Update_By VARCHAR(36) COMMENT '更新人UUID';
ALTER TABLE reminder_config ADD COLUMN Version INT DEFAULT 0 COMMENT '乐观锁版本号';
ALTER TABLE reminder_config ADD COLUMN Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

-- reminder表
SELECT 'Step 9: reminder table' AS status;
ALTER TABLE reminder ADD COLUMN Update_By VARCHAR(36) COMMENT '更新人UUID';
ALTER TABLE reminder ADD COLUMN Version INT DEFAULT 0 COMMENT '乐观锁版本号';
ALTER TABLE reminder ADD COLUMN Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

-- reminder_history表
SELECT 'Step 10: reminder_history table' AS status;
ALTER TABLE reminder_history ADD COLUMN Create_Time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间';
ALTER TABLE reminder_history ADD COLUMN Create_By VARCHAR(36) COMMENT '创建人UUID';
ALTER TABLE reminder_history ADD COLUMN Update_Time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间';
ALTER TABLE reminder_history ADD COLUMN Update_By VARCHAR(36) COMMENT '更新人UUID';
ALTER TABLE reminder_history ADD COLUMN Version INT DEFAULT 0 COMMENT '乐观锁版本号';
ALTER TABLE reminder_history ADD COLUMN Deleted TINYINT DEFAULT 0 COMMENT '逻辑删除标记';

-- 辅助表
SELECT 'Step 11: auxiliary tables' AS status;
ALTER TABLE doctor_working_schedule ADD COLUMN Create_By VARCHAR(36);
ALTER TABLE doctor_working_schedule ADD COLUMN Update_By VARCHAR(36);
ALTER TABLE doctor_working_schedule ADD COLUMN Version INT DEFAULT 0;
ALTER TABLE doctor_working_schedule ADD COLUMN Deleted TINYINT DEFAULT 0;

ALTER TABLE doctor_time_slots ADD COLUMN Create_By VARCHAR(36);
ALTER TABLE doctor_time_slots ADD COLUMN Update_By VARCHAR(36);
ALTER TABLE doctor_time_slots ADD COLUMN Version INT DEFAULT 0;
ALTER TABLE doctor_time_slots ADD COLUMN Deleted TINYINT DEFAULT 0;

ALTER TABLE doctor_schedule_exceptions ADD COLUMN Create_By VARCHAR(36);
ALTER TABLE doctor_schedule_exceptions ADD COLUMN Update_By VARCHAR(36);
ALTER TABLE doctor_schedule_exceptions ADD COLUMN Version INT DEFAULT 0;
ALTER TABLE doctor_schedule_exceptions ADD COLUMN Deleted TINYINT DEFAULT 0;

ALTER TABLE biomechanics_scan ADD COLUMN Create_By VARCHAR(36);
ALTER TABLE biomechanics_scan ADD COLUMN Update_By VARCHAR(36);
ALTER TABLE biomechanics_scan ADD COLUMN Version INT DEFAULT 0;
ALTER TABLE biomechanics_scan ADD COLUMN Deleted TINYINT DEFAULT 0;

ALTER TABLE chat_conversation ADD COLUMN Create_By VARCHAR(36);
ALTER TABLE chat_conversation ADD COLUMN Update_By VARCHAR(36);
ALTER TABLE chat_conversation ADD COLUMN Version INT DEFAULT 0;
ALTER TABLE chat_conversation ADD COLUMN Deleted TINYINT DEFAULT 0;

ALTER TABLE chat_message ADD COLUMN Create_By VARCHAR(36);
ALTER TABLE chat_message ADD COLUMN Update_By VARCHAR(36);
ALTER TABLE chat_message ADD COLUMN Version INT DEFAULT 0;
ALTER TABLE chat_message ADD COLUMN Deleted TINYINT DEFAULT 0;

-- ============================================================================
-- 第12步: 添加索引
-- ============================================================================

SELECT 'Step 12: Adding indexes' AS status;

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

ALTER TABLE appointment ADD INDEX idx_event_type (Event_Type);
ALTER TABLE appointment ADD INDEX idx_is_generic (Is_Generic_Event);

-- ============================================================================
-- 完成
-- ============================================================================

SELECT '========================================' AS '';
SELECT 'Migration Completed Successfully!' AS message;
SELECT '========================================' AS '';

SET FOREIGN_KEY_CHECKS = 1;

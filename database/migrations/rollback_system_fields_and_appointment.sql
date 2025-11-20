/*
================================================================================
回滚脚本: 移除系统管理字段和appointment扩展
================================================================================

用途: 回滚 add_system_fields_and_extend_appointment.sql 的所有更改

警告:
  ⚠️  此操作将删除以下字段及其数据:
  - Create_By, Update_By, Version, Deleted (所有表)
  - Is_Generic_Event, Event_Type, Notes (appointment表)
  ⚠️  执行前请确保已备份数据库！

作者: System Migration
日期: 2025-11-20
================================================================================
*/

USE medical_db;

SET FOREIGN_KEY_CHECKS = 0;

SELECT '========================================' AS '';
SELECT '开始回滚: 移除系统管理字段和appointment扩展' AS message;
SELECT NOW() AS rollback_start_time;
SELECT '========================================' AS '';

-- ============================================================================
-- 创建辅助存储过程: 安全删除列（如果存在）
-- ============================================================================

DELIMITER //

DROP PROCEDURE IF EXISTS drop_column_if_exists//
CREATE PROCEDURE drop_column_if_exists(
    IN p_table_name VARCHAR(64),
    IN p_column_name VARCHAR(64)
)
BEGIN
    DECLARE column_count INT;

    SELECT COUNT(*)
    INTO column_count
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = p_table_name
      AND COLUMN_NAME = p_column_name;

    IF column_count > 0 THEN
        SET @sql = CONCAT('ALTER TABLE `', p_table_name, '` DROP COLUMN `', p_column_name, '`');
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
        SELECT CONCAT('✓ 已删除列: ', p_table_name, '.', p_column_name) AS result;
    ELSE
        SELECT CONCAT('⊙ 列不存在: ', p_table_name, '.', p_column_name) AS result;
    END IF;
END//

DROP PROCEDURE IF EXISTS drop_index_if_exists//
CREATE PROCEDURE drop_index_if_exists(
    IN p_table_name VARCHAR(64),
    IN p_index_name VARCHAR(64)
)
BEGIN
    DECLARE index_count INT;

    SELECT COUNT(*)
    INTO index_count
    FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = p_table_name
      AND INDEX_NAME = p_index_name;

    IF index_count > 0 THEN
        SET @sql = CONCAT('ALTER TABLE `', p_table_name, '` DROP INDEX `', p_index_name, '`');
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
        SELECT CONCAT('✓ 已删除索引: ', p_table_name, '.', p_index_name) AS result;
    ELSE
        SELECT CONCAT('⊙ 索引不存在: ', p_table_name, '.', p_index_name) AS result;
    END IF;
END//

DELIMITER ;

-- ============================================================================
-- 删除所有Deleted索引
-- ============================================================================

SELECT '========================================' AS '';
SELECT '删除Deleted索引' AS step;
SELECT '========================================' AS '';

CALL drop_index_if_exists('patient', 'idx_deleted');
CALL drop_index_if_exists('medical_record', 'idx_deleted');
CALL drop_index_if_exists('doctor', 'idx_deleted');
CALL drop_index_if_exists('drugs', 'idx_deleted');
CALL drop_index_if_exists('prescription', 'idx_deleted');
CALL drop_index_if_exists('prescription_detail', 'idx_deleted');
CALL drop_index_if_exists('appointment', 'idx_deleted');
CALL drop_index_if_exists('reminder', 'idx_deleted');
CALL drop_index_if_exists('reminder_config', 'idx_deleted');
CALL drop_index_if_exists('reminder_history', 'idx_deleted');
CALL drop_index_if_exists('doctor_working_schedule', 'idx_deleted');
CALL drop_index_if_exists('doctor_time_slots', 'idx_deleted');
CALL drop_index_if_exists('doctor_schedule_exceptions', 'idx_deleted');
CALL drop_index_if_exists('biomechanics_scan', 'idx_deleted');
CALL drop_index_if_exists('chat_conversation', 'idx_deleted');
CALL drop_index_if_exists('chat_message', 'idx_deleted');

-- ============================================================================
-- 删除appointment表的通用日程索引
-- ============================================================================

CALL drop_index_if_exists('appointment', 'idx_event_type');
CALL drop_index_if_exists('appointment', 'idx_is_generic');

-- ============================================================================
-- 删除系统管理字段 - patient表
-- ============================================================================

SELECT '========================================' AS '';
SELECT '删除系统管理字段 - patient表' AS step;
SELECT '========================================' AS '';

CALL drop_column_if_exists('patient', 'Deleted');
CALL drop_column_if_exists('patient', 'Version');
CALL drop_column_if_exists('patient', 'Update_By');
CALL drop_column_if_exists('patient', 'Create_By');

-- ============================================================================
-- 删除系统管理字段 - medical_record表
-- ============================================================================

SELECT '========================================' AS '';
SELECT '删除系统管理字段 - medical_record表' AS step;
SELECT '========================================' AS '';

CALL drop_column_if_exists('medical_record', 'Deleted');
CALL drop_column_if_exists('medical_record', 'Version');
CALL drop_column_if_exists('medical_record', 'Update_By');
CALL drop_column_if_exists('medical_record', 'Create_By');

-- ============================================================================
-- 删除系统管理字段 - doctor表
-- ============================================================================

SELECT '========================================' AS '';
SELECT '删除系统管理字段 - doctor表' AS step;
SELECT '========================================' AS '';

CALL drop_column_if_exists('doctor', 'Deleted');
CALL drop_column_if_exists('doctor', 'Version');
CALL drop_column_if_exists('doctor', 'Update_By');
CALL drop_column_if_exists('doctor', 'Create_By');

-- ============================================================================
-- 删除系统管理字段 - drugs表
-- ============================================================================

SELECT '========================================' AS '';
SELECT '删除系统管理字段 - drugs表' AS step;
SELECT '========================================' AS '';

CALL drop_column_if_exists('drugs', 'Deleted');
CALL drop_column_if_exists('drugs', 'Version');
CALL drop_column_if_exists('drugs', 'Update_By');
CALL drop_column_if_exists('drugs', 'Create_By');

-- ============================================================================
-- 删除系统管理字段 - prescription表
-- ============================================================================

SELECT '========================================' AS '';
SELECT '删除系统管理字段 - prescription表' AS step;
SELECT '========================================' AS '';

CALL drop_column_if_exists('prescription', 'Deleted');
CALL drop_column_if_exists('prescription', 'Version');
CALL drop_column_if_exists('prescription', 'Update_By');
CALL drop_column_if_exists('prescription', 'Create_By');

-- ============================================================================
-- 删除系统管理字段 - prescription_detail表
-- ============================================================================

SELECT '========================================' AS '';
SELECT '删除系统管理字段 - prescription_detail表' AS step;
SELECT '========================================' AS '';

CALL drop_column_if_exists('prescription_detail', 'Deleted');
CALL drop_column_if_exists('prescription_detail', 'Version');
CALL drop_column_if_exists('prescription_detail', 'Update_By');
CALL drop_column_if_exists('prescription_detail', 'Create_By');
CALL drop_column_if_exists('prescription_detail', 'Updated_At');

-- ============================================================================
-- 删除系统管理字段 + 通用日程字段 - appointment表
-- ============================================================================

SELECT '========================================' AS '';
SELECT '删除系统管理字段和通用日程字段 - appointment表' AS step;
SELECT '========================================' AS '';

-- 通用日程字段
CALL drop_column_if_exists('appointment', 'Notes');
CALL drop_column_if_exists('appointment', 'Event_Type');
CALL drop_column_if_exists('appointment', 'Is_Generic_Event');

-- 系统管理字段
CALL drop_column_if_exists('appointment', 'Deleted');
CALL drop_column_if_exists('appointment', 'Version');
CALL drop_column_if_exists('appointment', 'Update_By');
CALL drop_column_if_exists('appointment', 'Create_By');

-- ============================================================================
-- 删除系统管理字段 - reminder_config表
-- ============================================================================

SELECT '========================================' AS '';
SELECT '删除系统管理字段 - reminder_config表' AS step;
SELECT '========================================' AS '';

CALL drop_column_if_exists('reminder_config', 'Deleted');
CALL drop_column_if_exists('reminder_config', 'Version');
CALL drop_column_if_exists('reminder_config', 'Update_By');
CALL drop_column_if_exists('reminder_config', 'Create_By');

-- ============================================================================
-- 删除系统管理字段 - reminder表
-- ============================================================================

SELECT '========================================' AS '';
SELECT '删除系统管理字段 - reminder表' AS step;
SELECT '========================================' AS '';

CALL drop_column_if_exists('reminder', 'Deleted');
CALL drop_column_if_exists('reminder', 'Version');
CALL drop_column_if_exists('reminder', 'Update_By');

-- ============================================================================
-- 删除系统管理字段 - reminder_history表
-- ============================================================================

SELECT '========================================' AS '';
SELECT '删除系统管理字段 - reminder_history表' AS step;
SELECT '========================================' AS '';

CALL drop_column_if_exists('reminder_history', 'Deleted');
CALL drop_column_if_exists('reminder_history', 'Version');
CALL drop_column_if_exists('reminder_history', 'Update_By');
CALL drop_column_if_exists('reminder_history', 'Update_Time');
CALL drop_column_if_exists('reminder_history', 'Create_By');
CALL drop_column_if_exists('reminder_history', 'Create_Time');

-- ============================================================================
-- 删除系统管理字段 - 辅助表
-- ============================================================================

SELECT '========================================' AS '';
SELECT '删除系统管理字段 - 辅助表' AS step;
SELECT '========================================' AS '';

-- doctor_working_schedule
CALL drop_column_if_exists('doctor_working_schedule', 'Deleted');
CALL drop_column_if_exists('doctor_working_schedule', 'Version');
CALL drop_column_if_exists('doctor_working_schedule', 'Update_By');
CALL drop_column_if_exists('doctor_working_schedule', 'Create_By');

-- doctor_time_slots
CALL drop_column_if_exists('doctor_time_slots', 'Deleted');
CALL drop_column_if_exists('doctor_time_slots', 'Version');
CALL drop_column_if_exists('doctor_time_slots', 'Update_By');
CALL drop_column_if_exists('doctor_time_slots', 'Create_By');

-- doctor_schedule_exceptions
CALL drop_column_if_exists('doctor_schedule_exceptions', 'Deleted');
CALL drop_column_if_exists('doctor_schedule_exceptions', 'Version');
CALL drop_column_if_exists('doctor_schedule_exceptions', 'Update_By');
CALL drop_column_if_exists('doctor_schedule_exceptions', 'Create_By');

-- biomechanics_scan
CALL drop_column_if_exists('biomechanics_scan', 'Deleted');
CALL drop_column_if_exists('biomechanics_scan', 'Version');
CALL drop_column_if_exists('biomechanics_scan', 'Update_By');
CALL drop_column_if_exists('biomechanics_scan', 'Create_By');

-- chat_conversation
CALL drop_column_if_exists('chat_conversation', 'Deleted');
CALL drop_column_if_exists('chat_conversation', 'Version');
CALL drop_column_if_exists('chat_conversation', 'Update_By');
CALL drop_column_if_exists('chat_conversation', 'Create_By');

-- chat_message
CALL drop_column_if_exists('chat_message', 'Deleted');
CALL drop_column_if_exists('chat_message', 'Version');
CALL drop_column_if_exists('chat_message', 'Update_By');
CALL drop_column_if_exists('chat_message', 'Create_By');

-- ============================================================================
-- 清理辅助存储过程
-- ============================================================================

DROP PROCEDURE IF EXISTS drop_column_if_exists;
DROP PROCEDURE IF EXISTS drop_index_if_exists;

-- ============================================================================
-- 回滚完成
-- ============================================================================

SELECT '========================================' AS '';
SELECT '✅ 回滚完成！' AS message;
SELECT NOW() AS rollback_end_time;
SELECT '========================================' AS '';

SELECT '已移除的内容:' AS '';
SELECT '  ✓ 所有表的系统管理字段 (Create_By, Update_By, Version, Deleted)' AS item_1;
SELECT '  ✓ appointment表的通用日程字段 (Is_Generic_Event, Event_Type, Notes)' AS item_2;
SELECT '  ✓ 所有相关索引' AS item_3;
SELECT '========================================' AS '';

SET FOREIGN_KEY_CHECKS = 1;

/*
================================================================================
回滚完成
================================================================================

数据库已恢复到迁移前的状态。

如需重新迁移，请执行:
  source database/migrations/add_system_fields_and_extend_appointment.sql

================================================================================
*/

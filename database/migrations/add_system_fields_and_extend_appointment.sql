/*
================================================================================
添加系统管理字段 + 扩展appointment表
================================================================================

目标:
  1. 为所有表添加系统管理字段 (Create_By, Update_By, Version, Deleted)
  2. 扩展appointment表支持通用日程功能
  3. 添加必要的索引

注意: 此脚本安全可重复执行（使用存储过程检查列是否存在）

执行时间: 预计 5-10分钟
作者: System Migration
日期: 2025-11-20
================================================================================
*/

USE medical_db;

SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================================
-- 创建辅助存储过程: 安全添加列（如果不存在）
-- ============================================================================

DELIMITER //

DROP PROCEDURE IF EXISTS add_column_if_not_exists//
CREATE PROCEDURE add_column_if_not_exists(
    IN p_table_name VARCHAR(64),
    IN p_column_name VARCHAR(64),
    IN p_column_definition TEXT
)
BEGIN
    DECLARE column_count INT;

    SELECT COUNT(*)
    INTO column_count
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = p_table_name
      AND COLUMN_NAME = p_column_name;

    IF column_count = 0 THEN
        SET @sql = CONCAT('ALTER TABLE `', p_table_name, '` ADD COLUMN `', p_column_name, '` ', p_column_definition);
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
        SELECT CONCAT('✓ 已添加列: ', p_table_name, '.', p_column_name) AS result;
    ELSE
        SELECT CONCAT('⊙ 列已存在: ', p_table_name, '.', p_column_name) AS result;
    END IF;
END//

DELIMITER ;

-- ============================================================================
-- 第1步: patient表 - 添加系统字段
-- ============================================================================

SELECT '========================================' AS '';
SELECT '添加系统管理字段到 patient 表' AS message;
SELECT '========================================' AS '';

CALL add_column_if_not_exists('patient', 'Create_By', 'VARCHAR(36) COMMENT \'创建人UUID\'');
CALL add_column_if_not_exists('patient', 'Update_By', 'VARCHAR(36) COMMENT \'更新人UUID\'');
CALL add_column_if_not_exists('patient', 'Version', 'INT DEFAULT 0 COMMENT \'乐观锁版本号\'');
CALL add_column_if_not_exists('patient', 'Deleted', 'TINYINT DEFAULT 0 COMMENT \'逻辑删除标记(0-未删除,1-已删除)\'');

-- ============================================================================
-- 第2步: medical_record表
-- ============================================================================

SELECT '========================================' AS '';
SELECT '添加系统管理字段到 medical_record 表' AS message;
SELECT '========================================' AS '';

CALL add_column_if_not_exists('medical_record', 'Create_By', 'VARCHAR(36) COMMENT \'创建人UUID\'');
CALL add_column_if_not_exists('medical_record', 'Update_By', 'VARCHAR(36) COMMENT \'更新人UUID\'');
CALL add_column_if_not_exists('medical_record', 'Version', 'INT DEFAULT 0 COMMENT \'乐观锁版本号\'');
CALL add_column_if_not_exists('medical_record', 'Deleted', 'TINYINT DEFAULT 0 COMMENT \'逻辑删除标记\'');

-- ============================================================================
-- 第3步: doctor表
-- ============================================================================

SELECT '========================================' AS '';
SELECT '添加系统管理字段到 doctor 表' AS message;
SELECT '========================================' AS '';

CALL add_column_if_not_exists('doctor', 'Create_By', 'VARCHAR(36) COMMENT \'创建人UUID\'');
CALL add_column_if_not_exists('doctor', 'Update_By', 'VARCHAR(36) COMMENT \'更新人UUID\'');
CALL add_column_if_not_exists('doctor', 'Version', 'INT DEFAULT 0 COMMENT \'乐观锁版本号\'');
CALL add_column_if_not_exists('doctor', 'Deleted', 'TINYINT DEFAULT 0 COMMENT \'逻辑删除标记\'');

-- ============================================================================
-- 第4步: drugs表
-- ============================================================================

SELECT '========================================' AS '';
SELECT '添加系统管理字段到 drugs 表' AS message;
SELECT '========================================' AS '';

CALL add_column_if_not_exists('drugs', 'Create_By', 'VARCHAR(36) COMMENT \'创建人UUID\'');
CALL add_column_if_not_exists('drugs', 'Update_By', 'VARCHAR(36) COMMENT \'更新人UUID\'');
CALL add_column_if_not_exists('drugs', 'Version', 'INT DEFAULT 0 COMMENT \'乐观锁版本号\'');
CALL add_column_if_not_exists('drugs', 'Deleted', 'TINYINT DEFAULT 0 COMMENT \'逻辑删除标记\'');

-- ============================================================================
-- 第5步: prescription表
-- ============================================================================

SELECT '========================================' AS '';
SELECT '添加系统管理字段到 prescription 表' AS message;
SELECT '========================================' AS '';

CALL add_column_if_not_exists('prescription', 'Create_By', 'VARCHAR(36) COMMENT \'创建人UUID\'');
CALL add_column_if_not_exists('prescription', 'Update_By', 'VARCHAR(36) COMMENT \'更新人UUID\'');
CALL add_column_if_not_exists('prescription', 'Version', 'INT DEFAULT 0 COMMENT \'乐观锁版本号\'');
CALL add_column_if_not_exists('prescription', 'Deleted', 'TINYINT DEFAULT 0 COMMENT \'逻辑删除标记\'');

-- ============================================================================
-- 第6步: prescription_detail表
-- ============================================================================

SELECT '========================================' AS '';
SELECT '添加系统管理字段到 prescription_detail 表' AS message;
SELECT '========================================' AS '';

CALL add_column_if_not_exists('prescription_detail', 'Updated_At', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT \'更新时间\'');
CALL add_column_if_not_exists('prescription_detail', 'Create_By', 'VARCHAR(36) COMMENT \'创建人UUID\'');
CALL add_column_if_not_exists('prescription_detail', 'Update_By', 'VARCHAR(36) COMMENT \'更新人UUID\'');
CALL add_column_if_not_exists('prescription_detail', 'Version', 'INT DEFAULT 0 COMMENT \'乐观锁版本号\'');
CALL add_column_if_not_exists('prescription_detail', 'Deleted', 'TINYINT DEFAULT 0 COMMENT \'逻辑删除标记\'');

-- ============================================================================
-- 第7步: appointment表 - 添加系统字段 + 通用日程支持
-- ============================================================================

SELECT '========================================' AS '';
SELECT '扩展 appointment 表（系统字段 + 通用日程功能）' AS message;
SELECT '========================================' AS '';

-- 系统管理字段
CALL add_column_if_not_exists('appointment', 'Create_By', 'VARCHAR(36) COMMENT \'创建人UUID\'');
CALL add_column_if_not_exists('appointment', 'Update_By', 'VARCHAR(36) COMMENT \'更新人UUID\'');
CALL add_column_if_not_exists('appointment', 'Version', 'INT DEFAULT 0 COMMENT \'乐观锁版本号\'');
CALL add_column_if_not_exists('appointment', 'Deleted', 'TINYINT DEFAULT 0 COMMENT \'逻辑删除标记\'');

-- 通用日程支持字段
CALL add_column_if_not_exists('appointment', 'Is_Generic_Event', 'BOOLEAN DEFAULT FALSE COMMENT \'是否为通用日程事件(非患者预约)\'');
CALL add_column_if_not_exists('appointment', 'Event_Type', 'VARCHAR(50) DEFAULT \'appointment\' COMMENT \'事件类型(appointment/meeting/personal_task/reminder)\'');
CALL add_column_if_not_exists('appointment', 'Notes', 'TEXT COMMENT \'日程备注(补充Description字段)\'');

-- ============================================================================
-- 第8步: reminder_config表
-- ============================================================================

SELECT '========================================' AS '';
SELECT '添加系统管理字段到 reminder_config 表' AS message;
SELECT '========================================' AS '';

CALL add_column_if_not_exists('reminder_config', 'Create_By', 'VARCHAR(36) COMMENT \'创建人UUID\'');
CALL add_column_if_not_exists('reminder_config', 'Update_By', 'VARCHAR(36) COMMENT \'更新人UUID\'');
CALL add_column_if_not_exists('reminder_config', 'Version', 'INT DEFAULT 0 COMMENT \'乐观锁版本号\'');
CALL add_column_if_not_exists('reminder_config', 'Deleted', 'TINYINT DEFAULT 0 COMMENT \'逻辑删除标记\'');

-- ============================================================================
-- 第9步: reminder表
-- ============================================================================

SELECT '========================================' AS '';
SELECT '添加系统管理字段到 reminder 表' AS message;
SELECT '========================================' AS '';

CALL add_column_if_not_exists('reminder', 'Update_By', 'VARCHAR(36) COMMENT \'更新人UUID\'');
CALL add_column_if_not_exists('reminder', 'Version', 'INT DEFAULT 0 COMMENT \'乐观锁版本号\'');
CALL add_column_if_not_exists('reminder', 'Deleted', 'TINYINT DEFAULT 0 COMMENT \'逻辑删除标记\'');

-- ============================================================================
-- 第10步: reminder_history表
-- ============================================================================

SELECT '========================================' AS '';
SELECT '添加系统管理字段到 reminder_history 表' AS message;
SELECT '========================================' AS '';

CALL add_column_if_not_exists('reminder_history', 'Create_Time', 'DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT \'创建时间\'');
CALL add_column_if_not_exists('reminder_history', 'Create_By', 'VARCHAR(36) COMMENT \'创建人UUID\'');
CALL add_column_if_not_exists('reminder_history', 'Update_Time', 'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT \'更新时间\'');
CALL add_column_if_not_exists('reminder_history', 'Update_By', 'VARCHAR(36) COMMENT \'更新人UUID\'');
CALL add_column_if_not_exists('reminder_history', 'Version', 'INT DEFAULT 0 COMMENT \'乐观锁版本号\'');
CALL add_column_if_not_exists('reminder_history', 'Deleted', 'TINYINT DEFAULT 0 COMMENT \'逻辑删除标记\'');

-- ============================================================================
-- 第11步: 辅助表 (doctor_working_schedule, doctor_time_slots等)
-- ============================================================================

SELECT '========================================' AS '';
SELECT '添加系统管理字段到辅助表' AS message;
SELECT '========================================' AS '';

-- doctor_working_schedule
CALL add_column_if_not_exists('doctor_working_schedule', 'Create_By', 'VARCHAR(36) COMMENT \'创建人UUID\'');
CALL add_column_if_not_exists('doctor_working_schedule', 'Update_By', 'VARCHAR(36) COMMENT \'更新人UUID\'');
CALL add_column_if_not_exists('doctor_working_schedule', 'Version', 'INT DEFAULT 0 COMMENT \'乐观锁版本号\'');
CALL add_column_if_not_exists('doctor_working_schedule', 'Deleted', 'TINYINT DEFAULT 0 COMMENT \'逻辑删除标记\'');

-- doctor_time_slots
CALL add_column_if_not_exists('doctor_time_slots', 'Create_By', 'VARCHAR(36) COMMENT \'创建人UUID\'');
CALL add_column_if_not_exists('doctor_time_slots', 'Update_By', 'VARCHAR(36) COMMENT \'更新人UUID\'');
CALL add_column_if_not_exists('doctor_time_slots', 'Version', 'INT DEFAULT 0 COMMENT \'乐观锁版本号\'');
CALL add_column_if_not_exists('doctor_time_slots', 'Deleted', 'TINYINT DEFAULT 0 COMMENT \'逻辑删除标记\'');

-- doctor_schedule_exceptions
CALL add_column_if_not_exists('doctor_schedule_exceptions', 'Create_By', 'VARCHAR(36) COMMENT \'创建人UUID\'');
CALL add_column_if_not_exists('doctor_schedule_exceptions', 'Update_By', 'VARCHAR(36) COMMENT \'更新人UUID\'');
CALL add_column_if_not_exists('doctor_schedule_exceptions', 'Version', 'INT DEFAULT 0 COMMENT \'乐观锁版本号\'');
CALL add_column_if_not_exists('doctor_schedule_exceptions', 'Deleted', 'TINYINT DEFAULT 0 COMMENT \'逻辑删除标记\'');

-- biomechanics_scan
CALL add_column_if_not_exists('biomechanics_scan', 'Create_By', 'VARCHAR(36) COMMENT \'创建人UUID\'');
CALL add_column_if_not_exists('biomechanics_scan', 'Update_By', 'VARCHAR(36) COMMENT \'更新人UUID\'');
CALL add_column_if_not_exists('biomechanics_scan', 'Version', 'INT DEFAULT 0 COMMENT \'乐观锁版本号\'');
CALL add_column_if_not_exists('biomechanics_scan', 'Deleted', 'TINYINT DEFAULT 0 COMMENT \'逻辑删除标记\'');

-- chat_conversation
CALL add_column_if_not_exists('chat_conversation', 'Create_By', 'VARCHAR(36) COMMENT \'创建人UUID\'');
CALL add_column_if_not_exists('chat_conversation', 'Update_By', 'VARCHAR(36) COMMENT \'更新人UUID\'');
CALL add_column_if_not_exists('chat_conversation', 'Version', 'INT DEFAULT 0 COMMENT \'乐观锁版本号\'');
CALL add_column_if_not_exists('chat_conversation', 'Deleted', 'TINYINT DEFAULT 0 COMMENT \'逻辑删除标记\'');

-- chat_message
CALL add_column_if_not_exists('chat_message', 'Create_By', 'VARCHAR(36) COMMENT \'创建人UUID\'');
CALL add_column_if_not_exists('chat_message', 'Update_By', 'VARCHAR(36) COMMENT \'更新人UUID\'');
CALL add_column_if_not_exists('chat_message', 'Version', 'INT DEFAULT 0 COMMENT \'乐观锁版本号\'');
CALL add_column_if_not_exists('chat_message', 'Deleted', 'TINYINT DEFAULT 0 COMMENT \'逻辑删除标记\'');

-- ============================================================================
-- 第12步: 添加索引
-- ============================================================================

SELECT '========================================' AS '';
SELECT '添加索引到所有表' AS message;
SELECT '========================================' AS '';

DELIMITER //

DROP PROCEDURE IF EXISTS add_index_if_not_exists//
CREATE PROCEDURE add_index_if_not_exists(
    IN p_table_name VARCHAR(64),
    IN p_index_name VARCHAR(64),
    IN p_index_definition TEXT
)
BEGIN
    DECLARE index_count INT;

    SELECT COUNT(*)
    INTO index_count
    FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = p_table_name
      AND INDEX_NAME = p_index_name;

    IF index_count = 0 THEN
        SET @sql = CONCAT('ALTER TABLE `', p_table_name, '` ADD INDEX `', p_index_name, '` ', p_index_definition);
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
        SELECT CONCAT('✓ 已添加索引: ', p_table_name, '.', p_index_name) AS result;
    ELSE
        SELECT CONCAT('⊙ 索引已存在: ', p_table_name, '.', p_index_name) AS result;
    END IF;
END//

DELIMITER ;

-- 为所有表的Deleted字段添加索引
CALL add_index_if_not_exists('patient', 'idx_deleted', '(Deleted)');
CALL add_index_if_not_exists('medical_record', 'idx_deleted', '(Deleted)');
CALL add_index_if_not_exists('doctor', 'idx_deleted', '(Deleted)');
CALL add_index_if_not_exists('drugs', 'idx_deleted', '(Deleted)');
CALL add_index_if_not_exists('prescription', 'idx_deleted', '(Deleted)');
CALL add_index_if_not_exists('prescription_detail', 'idx_deleted', '(Deleted)');
CALL add_index_if_not_exists('appointment', 'idx_deleted', '(Deleted)');
CALL add_index_if_not_exists('reminder', 'idx_deleted', '(Deleted)');
CALL add_index_if_not_exists('reminder_config', 'idx_deleted', '(Deleted)');
CALL add_index_if_not_exists('reminder_history', 'idx_deleted', '(Deleted)');
CALL add_index_if_not_exists('doctor_working_schedule', 'idx_deleted', '(Deleted)');
CALL add_index_if_not_exists('doctor_time_slots', 'idx_deleted', '(Deleted)');
CALL add_index_if_not_exists('doctor_schedule_exceptions', 'idx_deleted', '(Deleted)');
CALL add_index_if_not_exists('biomechanics_scan', 'idx_deleted', '(Deleted)');
CALL add_column_if_not_exists('chat_conversation', 'idx_deleted', '(Deleted)');
CALL add_index_if_not_exists('chat_message', 'idx_deleted', '(Deleted)');

-- 为appointment表添加通用日程相关索引
CALL add_index_if_not_exists('appointment', 'idx_event_type', '(Event_Type)');
CALL add_index_if_not_exists('appointment', 'idx_is_generic', '(Is_Generic_Event)');

-- ============================================================================
-- 清理辅助存储过程
-- ============================================================================

DROP PROCEDURE IF EXISTS add_column_if_not_exists;
DROP PROCEDURE IF EXISTS add_index_if_not_exists;

-- ============================================================================
-- 完成总结
-- ============================================================================

SELECT '========================================' AS '';
SELECT '✅ 迁移完成！' AS message;
SELECT '========================================' AS '';

SELECT '已完成的工作:' AS '';
SELECT '  1. ✓ 所有表添加系统管理字段 (Create_By, Update_By, Version, Deleted)' AS item_1;
SELECT '  2. ✓ appointment表扩展为通用日程表 (Is_Generic_Event, Event_Type, Notes)' AS item_2;
SELECT '  3. ✓ 所有表添加Deleted字段索引' AS item_3;
SELECT '  4. ✓ appointment表添加通用日程索引' AS item_4;
SELECT '' AS '';

SELECT '系统字段使用说明:' AS '';
SELECT '  • Create_By / Update_By: 存储创建/更新人的UUID' AS usage_1;
SELECT '  • Version: 乐观锁版本号，每次UPDATE时递增' AS usage_2;
SELECT '  • Deleted: 逻辑删除标记 (0=未删除, 1=已删除)' AS usage_3;
SELECT '  • 查询时需要添加: WHERE Deleted = 0' AS usage_4;
SELECT '' AS '';

SELECT 'appointment表新功能:' AS '';
SELECT '  • Is_Generic_Event=TRUE: 表示通用日程（非患者预约）' AS appointment_1;
SELECT '  • Event_Type: appointment/meeting/personal_task/reminder' AS appointment_2;
SELECT '  • Notes: 补充备注信息' AS appointment_3;
SELECT '========================================' AS '';

SET FOREIGN_KEY_CHECKS = 1;

/*
================================================================================
后续步骤:
================================================================================

1. 验证迁移结果:
   SELECT TABLE_NAME, COLUMN_NAME
   FROM INFORMATION_SCHEMA.COLUMNS
   WHERE TABLE_SCHEMA = 'medical_db'
   AND COLUMN_NAME IN ('Create_By', 'Update_By', 'Version', 'Deleted')
   ORDER BY TABLE_NAME, COLUMN_NAME;

2. 更新应用代码:
   - 所有INSERT操作需要设置 Create_By
   - 所有UPDATE操作需要设置 Update_By 和递增 Version
   - 所有DELETE操作改为 UPDATE SET Deleted=1
   - 所有SELECT查询添加 WHERE Deleted=0

3. 下一步迁移:
   - 执行 phase1-3 UUID迁移脚本（如果需要UUID主键）
   - 或继续使用当前的INT主键

================================================================================
*/

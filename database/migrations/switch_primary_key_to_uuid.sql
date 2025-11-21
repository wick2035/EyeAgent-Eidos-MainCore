/*
================================================================================
将 appointment 和 chat_conversation 表的主键切换为 UUID
================================================================================

目标:
  1. 将 Appointment_UUID 设置为 appointment 表的主键
  2. 将 Chat_UUID 设置为 chat_conversation 表的主键
  3. 移除 INT 主键,保留为普通列(用于向后兼容)
  4. 更新所有外键引用

警告: 这是破坏性操作,请先备份数据库!

日期: 2025-11-20
================================================================================
*/

USE medical_db;

-- 备份提示
SELECT '⚠️  警告: 即将执行主键切换,请确保已备份数据库!' AS warning;
SELECT '按 Ctrl+C 取消, 或等待5秒后继续...' AS notice;

-- DO SLEEP(5);  -- 取消注释以添加5秒延迟

SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================================
-- 阶段 1: chat_conversation 表主键切换
-- ============================================================================

SELECT '=== 开始处理 chat_conversation 表 ===' AS message;

-- 1.1 删除 chat_message 表中引用 Chat_ID 的外键 (忽略不存在的约束)
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'chat_message'
           AND CONSTRAINT_NAME = 'chat_message_ibfk_1'),
    'ALTER TABLE chat_message DROP FOREIGN KEY chat_message_ibfk_1',
    'SELECT "Foreign key chat_message_ibfk_1 does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'chat_message'
           AND CONSTRAINT_NAME = 'fk_chat_message_chat_id'),
    'ALTER TABLE chat_message DROP FOREIGN KEY fk_chat_message_chat_id',
    'SELECT "Foreign key fk_chat_message_chat_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 1.2 删除 chat_conversation 的原主键
ALTER TABLE chat_conversation DROP PRIMARY KEY;

-- 1.3 将 Chat_UUID 设置为主键
ALTER TABLE chat_conversation
    MODIFY COLUMN Chat_UUID CHAR(36) NOT NULL COMMENT 'UUID主键',
    ADD PRIMARY KEY (Chat_UUID);

-- 1.4 将 Chat_ID 改为普通列(保留用于向后兼容,添加唯一索引)
-- 先删除旧索引(如果存在)
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'chat_conversation'
           AND INDEX_NAME = 'idx_chat_id_legacy'),
    'ALTER TABLE chat_conversation DROP INDEX idx_chat_id_legacy',
    'SELECT "Index idx_chat_id_legacy does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

ALTER TABLE chat_conversation
    MODIFY COLUMN Chat_ID INT NOT NULL AUTO_INCREMENT COMMENT '对话ID(向后兼容)',
    ADD UNIQUE INDEX idx_chat_id_legacy (Chat_ID);

-- 1.5 重建 chat_message 的外键(使用 Chat_UUID)
-- 先删除旧索引 (如果存在)
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'chat_message'
           AND INDEX_NAME = 'idx_chat'),
    'ALTER TABLE chat_message DROP INDEX idx_chat',
    'SELECT "Index idx_chat does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 确保 chat_message.Chat_UUID 的类型与 chat_conversation.Chat_UUID 一致
ALTER TABLE chat_message
    MODIFY COLUMN Chat_UUID CHAR(36) NOT NULL COMMENT '会话UUID外键';

-- 删除旧索引和外键(如果存在)
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'chat_message'
           AND INDEX_NAME = 'idx_chat_uuid'),
    'ALTER TABLE chat_message DROP INDEX idx_chat_uuid',
    'SELECT "Index idx_chat_uuid does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'chat_message'
           AND CONSTRAINT_NAME = 'fk_chat_message_chat_uuid'),
    'ALTER TABLE chat_message DROP FOREIGN KEY fk_chat_message_chat_uuid',
    'SELECT "Foreign key fk_chat_message_chat_uuid does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 添加新索引和外键
ALTER TABLE chat_message
    ADD INDEX idx_chat_uuid (Chat_UUID),
    ADD CONSTRAINT fk_chat_message_chat_uuid
        FOREIGN KEY (Chat_UUID)
        REFERENCES chat_conversation(Chat_UUID)
        ON DELETE CASCADE;

SELECT '✅ chat_conversation 表主键已切换为 Chat_UUID' AS result;

-- ============================================================================
-- 阶段 2: appointment 表主键切换
-- ============================================================================

SELECT '=== 开始处理 appointment 表 ===' AS message;

-- 2.1 删除 reminder 表中引用 Appointment_ID 的外键(如果存在)
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'reminder'
           AND CONSTRAINT_NAME = 'reminder_ibfk_3'),
    'ALTER TABLE reminder DROP FOREIGN KEY reminder_ibfk_3',
    'SELECT "Foreign key reminder_ibfk_3 does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'reminder'
           AND CONSTRAINT_NAME = 'fk_reminder_appointment_id'),
    'ALTER TABLE reminder DROP FOREIGN KEY fk_reminder_appointment_id',
    'SELECT "Foreign key fk_reminder_appointment_id does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2.2 删除 appointment 的原主键
ALTER TABLE appointment DROP PRIMARY KEY;

-- 2.3 将 Appointment_UUID 设置为主键
ALTER TABLE appointment
    MODIFY COLUMN Appointment_UUID CHAR(36) NOT NULL COMMENT 'UUID主键',
    ADD PRIMARY KEY (Appointment_UUID);

-- 2.4 将 Appointment_ID 改为普通列(保留用于向后兼容,添加唯一索引)
-- 先删除旧索引(如果存在)
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'appointment'
           AND INDEX_NAME = 'idx_appointment_id_legacy'),
    'ALTER TABLE appointment DROP INDEX idx_appointment_id_legacy',
    'SELECT "Index idx_appointment_id_legacy does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

ALTER TABLE appointment
    MODIFY COLUMN Appointment_ID INT NOT NULL AUTO_INCREMENT COMMENT '预约ID(向后兼容)',
    ADD UNIQUE INDEX idx_appointment_id_legacy (Appointment_ID);

-- 2.5 重建 reminder 的外键(使用 Appointment_UUID,如果 reminder 表有 Appointment_UUID 列)
-- 检查 reminder 表是否有 Appointment_UUID 列
SET @has_appointment_uuid = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'medical_db'
      AND TABLE_NAME = 'reminder'
      AND COLUMN_NAME = 'Appointment_UUID'
);

-- 如果没有 Appointment_UUID 列,先添加
SET @sql = IF(
    @has_appointment_uuid = 0,
    'ALTER TABLE reminder ADD COLUMN Appointment_UUID CHAR(36) NULL COMMENT "预约UUID外键" AFTER Appointment_ID',
    'SELECT "Appointment_UUID column already exists" AS notice'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 同步 Appointment_UUID 数据
UPDATE reminder r
INNER JOIN appointment a ON r.Appointment_ID = a.Appointment_ID
SET r.Appointment_UUID = a.Appointment_UUID
WHERE r.Appointment_ID IS NOT NULL;

-- 确保 reminder.Appointment_UUID 的类型一致
ALTER TABLE reminder
    MODIFY COLUMN Appointment_UUID CHAR(36) NULL COMMENT '预约UUID外键';

-- 删除旧索引和外键(如果存在) - 必须先删除外键，再删除索引
-- 检查所有可能的外键名称
SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'reminder'
           AND CONSTRAINT_NAME = 'fk_reminder_appointment'),
    'ALTER TABLE reminder DROP FOREIGN KEY fk_reminder_appointment',
    'SELECT "Foreign key fk_reminder_appointment does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'reminder'
           AND CONSTRAINT_NAME = 'fk_reminder_appointment_uuid'),
    'ALTER TABLE reminder DROP FOREIGN KEY fk_reminder_appointment_uuid',
    'SELECT "Foreign key fk_reminder_appointment_uuid does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
           WHERE TABLE_SCHEMA = 'medical_db'
           AND TABLE_NAME = 'reminder'
           AND INDEX_NAME = 'idx_reminder_appointment_uuid'),
    'ALTER TABLE reminder DROP INDEX idx_reminder_appointment_uuid',
    'SELECT "Index idx_reminder_appointment_uuid does not exist" AS notice'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 添加外键约束
ALTER TABLE reminder
    ADD INDEX idx_reminder_appointment_uuid (Appointment_UUID),
    ADD CONSTRAINT fk_reminder_appointment_uuid
        FOREIGN KEY (Appointment_UUID)
        REFERENCES appointment(Appointment_UUID)
        ON DELETE SET NULL;

SELECT '✅ appointment 表主键已切换为 Appointment_UUID' AS result;

-- ============================================================================
-- 阶段 3: 更新触发器
-- ============================================================================

SELECT '=== 更新触发器 ===' AS message;

DELIMITER //

-- 3.1 更新 chat_conversation 触发器
DROP TRIGGER IF EXISTS trg_chat_conversation_uuid_insert//
CREATE TRIGGER trg_chat_conversation_uuid_insert
BEFORE INSERT ON chat_conversation
FOR EACH ROW
BEGIN
    -- UUID 是主键,必须有值
    IF NEW.Chat_UUID IS NULL OR NEW.Chat_UUID = '' THEN
        SET NEW.Chat_UUID = UUID();
    END IF;

    -- 自动填充外键UUID
    IF NEW.Patient_UUID IS NULL AND NEW.Patient_ID IS NOT NULL THEN
        SET NEW.Patient_UUID = (SELECT Patient_UUID FROM patient WHERE Patient_ID = NEW.Patient_ID LIMIT 1);
    END IF;

    IF NEW.Doctor_UUID IS NULL AND NEW.Doctor_ID IS NOT NULL THEN
        SET NEW.Doctor_UUID = (SELECT Doctor_UUID FROM doctor WHERE Doctor_ID = NEW.Doctor_ID LIMIT 1);
    END IF;

    -- Chat_ID 保留自动递增(向后兼容)
    -- MySQL 会自动处理 AUTO_INCREMENT
END//

-- 3.2 更新 chat_message 触发器
DROP TRIGGER IF EXISTS trg_chat_message_uuid_insert//
CREATE TRIGGER trg_chat_message_uuid_insert
BEFORE INSERT ON chat_message
FOR EACH ROW
BEGIN
    IF NEW.Message_UUID IS NULL OR NEW.Message_UUID = '' THEN
        SET NEW.Message_UUID = UUID();
    END IF;

    -- 自动同步 Chat_UUID (如果只提供了 Chat_ID)
    IF NEW.Chat_UUID IS NULL AND NEW.Chat_ID IS NOT NULL THEN
        SET NEW.Chat_UUID = (SELECT Chat_UUID FROM chat_conversation WHERE Chat_ID = NEW.Chat_ID LIMIT 1);
    END IF;
END//

-- 3.3 更新 appointment 触发器
DROP TRIGGER IF EXISTS trg_appointment_uuid_insert//
CREATE TRIGGER trg_appointment_uuid_insert
BEFORE INSERT ON appointment
FOR EACH ROW
BEGIN
    -- UUID 是主键,必须有值
    IF NEW.Appointment_UUID IS NULL OR NEW.Appointment_UUID = '' THEN
        SET NEW.Appointment_UUID = UUID();
    END IF;

    -- 自动填充外键UUID
    IF NEW.Patient_UUID IS NULL AND NEW.Patient_ID IS NOT NULL THEN
        SET NEW.Patient_UUID = (SELECT Patient_UUID FROM patient WHERE Patient_ID = NEW.Patient_ID LIMIT 1);
    END IF;

    IF NEW.Doctor_UUID IS NULL AND NEW.Doctor_ID IS NOT NULL THEN
        SET NEW.Doctor_UUID = (SELECT Doctor_UUID FROM doctor WHERE Doctor_ID = NEW.Doctor_ID LIMIT 1);
    END IF;

    IF NEW.Medical_Record_UUID IS NULL AND NEW.Medical_Record_ID IS NOT NULL THEN
        SET NEW.Medical_Record_UUID = (SELECT Medical_Record_UUID FROM medical_record WHERE Medical_Record_ID = NEW.Medical_Record_ID LIMIT 1);
    END IF;

    -- Appointment_ID 保留自动递增(向后兼容)
END//

DELIMITER ;

SELECT '✅ 触发器已更新' AS result;

-- ============================================================================
-- 阶段 4: 验证迁移结果
-- ============================================================================

SELECT '=== 验证迁移结果 ===' AS message;

-- 检查 chat_conversation 主键
SELECT
    'chat_conversation' AS table_name,
    COLUMN_NAME,
    COLUMN_KEY,
    EXTRA
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'medical_db'
  AND TABLE_NAME = 'chat_conversation'
  AND COLUMN_NAME IN ('Chat_ID', 'Chat_UUID')
ORDER BY ORDINAL_POSITION;

-- 检查 appointment 主键
SELECT
    'appointment' AS table_name,
    COLUMN_NAME,
    COLUMN_KEY,
    EXTRA
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'medical_db'
  AND TABLE_NAME = 'appointment'
  AND COLUMN_NAME IN ('Appointment_ID', 'Appointment_UUID')
ORDER BY ORDINAL_POSITION;

-- 检查外键约束
SELECT
    TABLE_NAME,
    CONSTRAINT_NAME,
    COLUMN_NAME,
    REFERENCED_TABLE_NAME,
    REFERENCED_COLUMN_NAME
FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = 'medical_db'
  AND REFERENCED_TABLE_NAME IN ('chat_conversation', 'appointment')
ORDER BY TABLE_NAME, CONSTRAINT_NAME;

SET FOREIGN_KEY_CHECKS = 1;

SELECT '=== 主键切换完成 ===' AS message;
SELECT '✅ Appointment_UUID 和 Chat_UUID 现在是主键' AS status;
SELECT '✅ Appointment_ID 和 Chat_ID 保留为向后兼容的唯一列' AS note;
SELECT '⚠️  请更新应用代码以使用 UUID 而不是 INT ID' AS warning;

/*
================================================================================
后续步骤:
================================================================================

1. 验证数据完整性:
   - 检查所有记录的 UUID 都不为空
   - 检查外键关联正确

2. 更新应用代码:
   - ChatService: 使用 Chat_UUID 作为主键
   - AppointmentService: 使用 Appointment_UUID 作为主键
   - 更新所有查询和插入语句

3. 测试功能:
   - 创建新对话
   - 创建新预约
   - 查询历史记录

4. 清理(可选,谨慎执行):
   - 如果确认不再需要 INT ID,可以考虑移除 Chat_ID 和 Appointment_ID 列
   - 但建议保留一段时间用于向后兼容

================================================================================
*/

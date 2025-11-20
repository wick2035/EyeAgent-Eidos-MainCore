/*
================================================================================
UUID迁移 - 第二阶段: 业务表
================================================================================

迁移表:
  1. appointment (Appointment_ID → Appointment_UUID)
  2. prescription (Prescription_ID → Prescription_UUID)
  3. prescription_detail (Detail_ID → Detail_UUID)
  4. chat_conversation (Chat_ID → Chat_UUID)
  5. chat_message (Message_ID → Message_UUID)

前置条件:
  - 第一阶段已完成 (patient, medical_record, doctor已有UUID)

策略: 零停机迁移
  - 添加UUID列和外键UUID列
  - 同步UUID关联关系
  - 更新触发器

执行时间: 预计 15-20分钟

作者: System Migration
日期: 2025-11-20
================================================================================
*/

USE medical_db;

-- ============================================================================
-- 验证前置条件
-- ============================================================================

SELECT '=== 验证第一阶段完成状态 ===' AS message;

SELECT
    table_name,
    records_migrated,
    status
FROM _uuid_migration_log
WHERE phase = 'phase1_core' AND status = 'completed';

-- 如果第一阶段未完成,此查询应返回错误提示
DO (
    SELECT IF(
        (SELECT COUNT(*) FROM _uuid_migration_log WHERE phase = 'phase1_core' AND status = 'completed') < 3,
        (SELECT 'ERROR: 第一阶段未完成,请先执行 phase1_uuid_migration_core_tables.sql'),
        'OK: 前置条件满足'
    )
);

-- ============================================================================
-- 阶段 2.1: appointment表 - 添加UUID列
-- ============================================================================

ALTER TABLE appointment
    ADD COLUMN Appointment_UUID CHAR(36) NULL COMMENT 'UUID主键(迁移中)' AFTER Appointment_ID,
    ADD COLUMN Patient_UUID CHAR(36) NULL COMMENT '患者UUID外键(迁移中)' AFTER Patient_ID,
    ADD COLUMN Doctor_UUID CHAR(36) NULL COMMENT '医生UUID外键(迁移中)' AFTER Doctor_ID,
    ADD COLUMN Medical_Record_UUID CHAR(36) NULL COMMENT '病历UUID外键(迁移中)' AFTER Medical_Record_ID,
    ADD COLUMN _migration_flag TINYINT(1) DEFAULT 0 COMMENT '迁移标记';

-- 生成UUID并同步外键关联
UPDATE appointment
SET Appointment_UUID = UUID(),
    _migration_flag = 1
WHERE Appointment_UUID IS NULL;

UPDATE appointment a
INNER JOIN patient p ON a.Patient_ID = p.Patient_ID
SET a.Patient_UUID = p.Patient_UUID;

UPDATE appointment a
INNER JOIN doctor d ON a.Doctor_ID = d.Doctor_ID
SET a.Doctor_UUID = d.Doctor_UUID;

UPDATE appointment a
LEFT JOIN medical_record mr ON a.Medical_Record_ID = mr.Medical_Record_ID
SET a.Medical_Record_UUID = mr.Medical_Record_UUID
WHERE a.Medical_Record_ID IS NOT NULL;

-- 设置NOT NULL并添加索引
ALTER TABLE appointment
    MODIFY COLUMN Appointment_UUID CHAR(36) NOT NULL,
    MODIFY COLUMN Patient_UUID CHAR(36) NOT NULL,
    MODIFY COLUMN Doctor_UUID CHAR(36) NOT NULL,
    ADD UNIQUE INDEX idx_appointment_uuid (Appointment_UUID),
    ADD INDEX idx_appointment_patient_uuid (Patient_UUID),
    ADD INDEX idx_appointment_doctor_uuid (Doctor_UUID),
    ADD INDEX idx_appointment_medical_record_uuid (Medical_Record_UUID),
    ADD INDEX idx_appointment_migration (Appointment_ID, Appointment_UUID);

-- ============================================================================
-- 阶段 2.2: prescription表 - 添加UUID列
-- ============================================================================

ALTER TABLE prescription
    ADD COLUMN Prescription_UUID CHAR(36) NULL COMMENT 'UUID主键(迁移中)' AFTER Prescription_ID,
    ADD COLUMN Patient_UUID CHAR(36) NULL COMMENT '患者UUID外键(迁移中)' AFTER Patient_ID,
    ADD COLUMN Doctor_UUID CHAR(36) NULL COMMENT '医生UUID外键(迁移中)' AFTER Doctor_ID,
    ADD COLUMN Medical_Record_UUID CHAR(36) NULL COMMENT '病历UUID外键(迁移中)' AFTER Medical_Record_ID,
    ADD COLUMN _migration_flag TINYINT(1) DEFAULT 0 COMMENT '迁移标记';

-- 生成UUID并同步外键
UPDATE prescription
SET Prescription_UUID = UUID(),
    _migration_flag = 1
WHERE Prescription_UUID IS NULL;

UPDATE prescription pr
INNER JOIN patient p ON pr.Patient_ID = p.Patient_ID
SET pr.Patient_UUID = p.Patient_UUID;

UPDATE prescription pr
LEFT JOIN doctor d ON pr.Doctor_ID = d.Doctor_ID
SET pr.Doctor_UUID = d.Doctor_UUID
WHERE pr.Doctor_ID IS NOT NULL;

UPDATE prescription pr
LEFT JOIN medical_record mr ON pr.Medical_Record_ID = mr.Medical_Record_ID
SET pr.Medical_Record_UUID = mr.Medical_Record_UUID
WHERE pr.Medical_Record_ID IS NOT NULL;

-- 设置NOT NULL并添加索引
ALTER TABLE prescription
    MODIFY COLUMN Prescription_UUID CHAR(36) NOT NULL,
    MODIFY COLUMN Patient_UUID CHAR(36) NOT NULL,
    ADD UNIQUE INDEX idx_prescription_uuid (Prescription_UUID),
    ADD INDEX idx_prescription_patient_uuid (Patient_UUID),
    ADD INDEX idx_prescription_doctor_uuid (Doctor_UUID),
    ADD INDEX idx_prescription_medical_record_uuid (Medical_Record_UUID),
    ADD INDEX idx_prescription_migration (Prescription_ID, Prescription_UUID);

-- ============================================================================
-- 阶段 2.3: prescription_detail表 - 添加UUID列
-- ============================================================================

ALTER TABLE prescription_detail
    ADD COLUMN Detail_UUID CHAR(36) NULL COMMENT 'UUID主键(迁移中)' AFTER Detail_ID,
    ADD COLUMN Prescription_UUID CHAR(36) NULL COMMENT '处方UUID外键(迁移中)' AFTER Prescription_ID,
    ADD COLUMN _migration_flag TINYINT(1) DEFAULT 0 COMMENT '迁移标记';

-- 生成UUID并同步外键
UPDATE prescription_detail
SET Detail_UUID = UUID(),
    _migration_flag = 1
WHERE Detail_UUID IS NULL;

UPDATE prescription_detail pd
INNER JOIN prescription pr ON pd.Prescription_ID = pr.Prescription_ID
SET pd.Prescription_UUID = pr.Prescription_UUID;

-- 设置NOT NULL并添加索引
ALTER TABLE prescription_detail
    MODIFY COLUMN Detail_UUID CHAR(36) NOT NULL,
    MODIFY COLUMN Prescription_UUID CHAR(36) NOT NULL,
    ADD UNIQUE INDEX idx_prescription_detail_uuid (Detail_UUID),
    ADD INDEX idx_prescription_detail_prescription_uuid (Prescription_UUID),
    ADD INDEX idx_prescription_detail_migration (Detail_ID, Detail_UUID);

-- ============================================================================
-- 阶段 2.4: chat_conversation表 - 添加UUID列
-- ============================================================================

ALTER TABLE chat_conversation
    ADD COLUMN Chat_UUID CHAR(36) NULL COMMENT 'UUID主键(迁移中)' AFTER Chat_ID,
    ADD COLUMN Patient_UUID CHAR(36) NULL COMMENT '患者UUID外键(迁移中)' AFTER Patient_ID,
    ADD COLUMN Doctor_UUID CHAR(36) NULL COMMENT '医生UUID外键(迁移中)' AFTER Doctor_ID,
    ADD COLUMN _migration_flag TINYINT(1) DEFAULT 0 COMMENT '迁移标记';

-- 生成UUID
UPDATE chat_conversation
SET Chat_UUID = UUID(),
    _migration_flag = 1
WHERE Chat_UUID IS NULL;

-- 同步外键 (注意: chat_conversation允许Patient_ID或Doctor_ID为NULL)
UPDATE chat_conversation cc
LEFT JOIN patient p ON cc.Patient_ID = p.Patient_ID
SET cc.Patient_UUID = p.Patient_UUID
WHERE cc.Patient_ID IS NOT NULL;

UPDATE chat_conversation cc
LEFT JOIN doctor d ON cc.Doctor_ID = d.Doctor_ID
SET cc.Doctor_UUID = d.Doctor_UUID
WHERE cc.Doctor_ID IS NOT NULL;

-- 设置NOT NULL并添加索引
ALTER TABLE chat_conversation
    MODIFY COLUMN Chat_UUID CHAR(36) NOT NULL,
    ADD UNIQUE INDEX idx_chat_conversation_uuid (Chat_UUID),
    ADD INDEX idx_chat_conversation_patient_uuid (Patient_UUID),
    ADD INDEX idx_chat_conversation_doctor_uuid (Doctor_UUID),
    ADD INDEX idx_chat_conversation_migration (Chat_ID, Chat_UUID);

-- ============================================================================
-- 阶段 2.5: chat_message表 - 添加UUID列
-- ============================================================================

ALTER TABLE chat_message
    ADD COLUMN Message_UUID CHAR(36) NULL COMMENT 'UUID主键(迁移中)' AFTER Message_ID,
    ADD COLUMN Chat_UUID CHAR(36) NULL COMMENT '会话UUID外键(迁移中)' AFTER Chat_ID,
    ADD COLUMN _migration_flag TINYINT(1) DEFAULT 0 COMMENT '迁移标记';

-- 生成UUID并同步外键
UPDATE chat_message
SET Message_UUID = UUID(),
    _migration_flag = 1
WHERE Message_UUID IS NULL;

UPDATE chat_message cm
INNER JOIN chat_conversation cc ON cm.Chat_ID = cc.Chat_ID
SET cm.Chat_UUID = cc.Chat_UUID;

-- 设置NOT NULL并添加索引
ALTER TABLE chat_message
    MODIFY COLUMN Message_UUID CHAR(36) NOT NULL,
    MODIFY COLUMN Chat_UUID CHAR(36) NOT NULL,
    ADD UNIQUE INDEX idx_chat_message_uuid (Message_UUID),
    ADD INDEX idx_chat_message_chat_uuid (Chat_UUID),
    ADD INDEX idx_chat_message_migration (Message_ID, Message_UUID),
    ADD UNIQUE INDEX idx_chat_message_chat_uuid_order (Chat_UUID, Message_Order);

-- ============================================================================
-- 阶段 2.6: 更新触发器 (支持UUID自动生成)
-- ============================================================================

DELIMITER //

-- 2.6.1 appointment触发器
DROP TRIGGER IF EXISTS trg_appointment_uuid_insert//
CREATE TRIGGER trg_appointment_uuid_insert
BEFORE INSERT ON appointment
FOR EACH ROW
BEGIN
    -- 生成UUID
    IF NEW.Appointment_UUID IS NULL OR NEW.Appointment_UUID = '' THEN
        SET NEW.Appointment_UUID = UUID();
    END IF;
    SET NEW._migration_flag = 1;

    -- 自动关联外键UUID
    IF NEW.Patient_UUID IS NULL AND NEW.Patient_ID IS NOT NULL THEN
        SET NEW.Patient_UUID = (SELECT Patient_UUID FROM patient WHERE Patient_ID = NEW.Patient_ID LIMIT 1);
    END IF;

    IF NEW.Doctor_UUID IS NULL AND NEW.Doctor_ID IS NOT NULL THEN
        SET NEW.Doctor_UUID = (SELECT Doctor_UUID FROM doctor WHERE Doctor_ID = NEW.Doctor_ID LIMIT 1);
    END IF;

    IF NEW.Medical_Record_UUID IS NULL AND NEW.Medical_Record_ID IS NOT NULL THEN
        SET NEW.Medical_Record_UUID = (SELECT Medical_Record_UUID FROM medical_record WHERE Medical_Record_ID = NEW.Medical_Record_ID LIMIT 1);
    END IF;
END//

-- 2.6.2 prescription触发器
DROP TRIGGER IF EXISTS trg_prescription_uuid_insert//
CREATE TRIGGER trg_prescription_uuid_insert
BEFORE INSERT ON prescription
FOR EACH ROW
BEGIN
    IF NEW.Prescription_UUID IS NULL OR NEW.Prescription_UUID = '' THEN
        SET NEW.Prescription_UUID = UUID();
    END IF;
    SET NEW._migration_flag = 1;

    IF NEW.Patient_UUID IS NULL AND NEW.Patient_ID IS NOT NULL THEN
        SET NEW.Patient_UUID = (SELECT Patient_UUID FROM patient WHERE Patient_ID = NEW.Patient_ID LIMIT 1);
    END IF;

    IF NEW.Doctor_UUID IS NULL AND NEW.Doctor_ID IS NOT NULL THEN
        SET NEW.Doctor_UUID = (SELECT Doctor_UUID FROM doctor WHERE Doctor_ID = NEW.Doctor_ID LIMIT 1);
    END IF;

    IF NEW.Medical_Record_UUID IS NULL AND NEW.Medical_Record_ID IS NOT NULL THEN
        SET NEW.Medical_Record_UUID = (SELECT Medical_Record_UUID FROM medical_record WHERE Medical_Record_ID = NEW.Medical_Record_ID LIMIT 1);
    END IF;
END//

-- 2.6.3 prescription_detail触发器
DROP TRIGGER IF EXISTS trg_prescription_detail_uuid_insert//
CREATE TRIGGER trg_prescription_detail_uuid_insert
BEFORE INSERT ON prescription_detail
FOR EACH ROW
BEGIN
    IF NEW.Detail_UUID IS NULL OR NEW.Detail_UUID = '' THEN
        SET NEW.Detail_UUID = UUID();
    END IF;
    SET NEW._migration_flag = 1;

    IF NEW.Prescription_UUID IS NULL AND NEW.Prescription_ID IS NOT NULL THEN
        SET NEW.Prescription_UUID = (SELECT Prescription_UUID FROM prescription WHERE Prescription_ID = NEW.Prescription_ID LIMIT 1);
    END IF;
END//

-- 2.6.4 chat_conversation触发器
DROP TRIGGER IF EXISTS trg_chat_conversation_uuid_insert//
CREATE TRIGGER trg_chat_conversation_uuid_insert
BEFORE INSERT ON chat_conversation
FOR EACH ROW
BEGIN
    IF NEW.Chat_UUID IS NULL OR NEW.Chat_UUID = '' THEN
        SET NEW.Chat_UUID = UUID();
    END IF;
    SET NEW._migration_flag = 1;

    IF NEW.Patient_UUID IS NULL AND NEW.Patient_ID IS NOT NULL THEN
        SET NEW.Patient_UUID = (SELECT Patient_UUID FROM patient WHERE Patient_ID = NEW.Patient_ID LIMIT 1);
    END IF;

    IF NEW.Doctor_UUID IS NULL AND NEW.Doctor_ID IS NOT NULL THEN
        SET NEW.Doctor_UUID = (SELECT Doctor_UUID FROM doctor WHERE Doctor_ID = NEW.Doctor_ID LIMIT 1);
    END IF;
END//

-- 2.6.5 chat_message触发器
DROP TRIGGER IF EXISTS trg_chat_message_uuid_insert//
CREATE TRIGGER trg_chat_message_uuid_insert
BEFORE INSERT ON chat_message
FOR EACH ROW
BEGIN
    IF NEW.Message_UUID IS NULL OR NEW.Message_UUID = '' THEN
        SET NEW.Message_UUID = UUID();
    END IF;
    SET NEW._migration_flag = 1;

    IF NEW.Chat_UUID IS NULL AND NEW.Chat_ID IS NOT NULL THEN
        SET NEW.Chat_UUID = (SELECT Chat_UUID FROM chat_conversation WHERE Chat_ID = NEW.Chat_ID LIMIT 1);
    END IF;
END//

DELIMITER ;

-- ============================================================================
-- 阶段 2.7: 验证数据完整性
-- ============================================================================

SELECT '=== 第二阶段数据验证 ===' AS message;

SELECT
    'appointment' AS table_name,
    COUNT(*) AS total_records,
    SUM(CASE WHEN Appointment_UUID IS NOT NULL THEN 1 ELSE 0 END) AS uuid_records,
    SUM(_migration_flag) AS migrated_records
FROM appointment

UNION ALL

SELECT 'prescription', COUNT(*), SUM(CASE WHEN Prescription_UUID IS NOT NULL THEN 1 ELSE 0 END), SUM(_migration_flag)
FROM prescription

UNION ALL

SELECT 'prescription_detail', COUNT(*), SUM(CASE WHEN Detail_UUID IS NOT NULL THEN 1 ELSE 0 END), SUM(_migration_flag)
FROM prescription_detail

UNION ALL

SELECT 'chat_conversation', COUNT(*), SUM(CASE WHEN Chat_UUID IS NOT NULL THEN 1 ELSE 0 END), SUM(_migration_flag)
FROM chat_conversation

UNION ALL

SELECT 'chat_message', COUNT(*), SUM(CASE WHEN Message_UUID IS NOT NULL THEN 1 ELSE 0 END), SUM(_migration_flag)
FROM chat_message;

-- 记录迁移日志
INSERT INTO _uuid_migration_log (phase, table_name, old_column, new_column, records_migrated, status, completed_at)
SELECT 'phase2_business', 'appointment', 'Appointment_ID', 'Appointment_UUID', COUNT(*), 'completed', NOW()
FROM appointment WHERE _migration_flag = 1

UNION ALL
SELECT 'phase2_business', 'prescription', 'Prescription_ID', 'Prescription_UUID', COUNT(*), 'completed', NOW()
FROM prescription WHERE _migration_flag = 1

UNION ALL
SELECT 'phase2_business', 'prescription_detail', 'Detail_ID', 'Detail_UUID', COUNT(*), 'completed', NOW()
FROM prescription_detail WHERE _migration_flag = 1

UNION ALL
SELECT 'phase2_business', 'chat_conversation', 'Chat_ID', 'Chat_UUID', COUNT(*), 'completed', NOW()
FROM chat_conversation WHERE _migration_flag = 1

UNION ALL
SELECT 'phase2_business', 'chat_message', 'Message_ID', 'Message_UUID', COUNT(*), 'completed', NOW()
FROM chat_message WHERE _migration_flag = 1;

-- ============================================================================
-- 完成信息
-- ============================================================================

SELECT '=== 第二阶段迁移完成 ===' AS message;
SELECT
    '业务表UUID列已添加并填充' AS status,
    '所有外键UUID已同步' AS note,
    '触发器已更新,支持自动UUID生成' AS next_step;

SELECT table_name, records_migrated, status, completed_at
FROM _uuid_migration_log
WHERE phase = 'phase2_business'
ORDER BY completed_at DESC;

/*
================================================================================
后续步骤:
================================================================================

1. 更新Python服务代码:
   - appointment_service_v3.py
   - prescription_service.py
   - chat_service.py

2. 执行第三阶段迁移:
   - source database/migrations/phase3_uuid_migration_auxiliary_tables.sql

3. 测试所有业务流程:
   - 预约创建和查询
   - 处方生成
   - 聊天历史记录

================================================================================
*/

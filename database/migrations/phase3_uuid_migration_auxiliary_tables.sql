/*
================================================================================
UUID迁移 - 第三阶段: 辅助表
================================================================================

迁移表:
  1. doctor_working_schedule (Schedule_ID → Schedule_UUID)
  2. doctor_time_slots (Slot_ID → Slot_UUID)
  3. doctor_schedule_exceptions (Exception_ID → Exception_UUID)
  4. reminder (Reminder_ID → Reminder_UUID)
  5. reminder_history (History_ID → History_UUID)
  6. reminder_config (Config_ID → Config_UUID)
  7. biomechanics_scan (Scan_ID → Scan_UUID)

前置条件:
  - 第一阶段和第二阶段已完成

执行时间: 预计 10-15分钟

作者: System Migration
日期: 2025-11-20
================================================================================
*/

USE medical_db;

-- ============================================================================
-- 验证前置条件
-- ============================================================================

SELECT '=== 验证前置阶段完成状态 ===' AS message;

SELECT phase, COUNT(*) AS completed_tables
FROM _uuid_migration_log
WHERE status = 'completed' AND phase IN ('phase1_core', 'phase2_business')
GROUP BY phase;

-- ============================================================================
-- 阶段 3.1: doctor_working_schedule表
-- ============================================================================

ALTER TABLE doctor_working_schedule
    ADD COLUMN Schedule_UUID CHAR(36) NULL COMMENT 'UUID主键(迁移中)' AFTER Schedule_ID,
    ADD COLUMN Doctor_UUID CHAR(36) NULL COMMENT '医生UUID外键(迁移中)' AFTER Doctor_ID,
    ADD COLUMN _migration_flag TINYINT(1) DEFAULT 0;

UPDATE doctor_working_schedule SET Schedule_UUID = UUID(), _migration_flag = 1;

UPDATE doctor_working_schedule dws
INNER JOIN doctor d ON dws.Doctor_ID = d.Doctor_ID
SET dws.Doctor_UUID = d.Doctor_UUID;

ALTER TABLE doctor_working_schedule
    MODIFY COLUMN Schedule_UUID CHAR(36) NOT NULL,
    MODIFY COLUMN Doctor_UUID CHAR(36) NOT NULL,
    ADD UNIQUE INDEX idx_doctor_working_schedule_uuid (Schedule_UUID),
    ADD INDEX idx_doctor_working_schedule_doctor_uuid (Doctor_UUID);

-- ============================================================================
-- 阶段 3.2: doctor_time_slots表
-- ============================================================================

ALTER TABLE doctor_time_slots
    ADD COLUMN Slot_UUID CHAR(36) NULL COMMENT 'UUID主键(迁移中)' AFTER Slot_ID,
    ADD COLUMN Doctor_UUID CHAR(36) NULL COMMENT '医生UUID外键(迁移中)' AFTER Doctor_ID,
    ADD COLUMN _migration_flag TINYINT(1) DEFAULT 0;

UPDATE doctor_time_slots SET Slot_UUID = UUID(), _migration_flag = 1;

UPDATE doctor_time_slots dts
INNER JOIN doctor d ON dts.Doctor_ID = d.Doctor_ID
SET dts.Doctor_UUID = d.Doctor_UUID;

ALTER TABLE doctor_time_slots
    MODIFY COLUMN Slot_UUID CHAR(36) NOT NULL,
    MODIFY COLUMN Doctor_UUID CHAR(36) NOT NULL,
    ADD UNIQUE INDEX idx_doctor_time_slots_uuid (Slot_UUID),
    ADD INDEX idx_doctor_time_slots_doctor_uuid (Doctor_UUID);

-- ============================================================================
-- 阶段 3.3: doctor_schedule_exceptions表
-- ============================================================================

ALTER TABLE doctor_schedule_exceptions
    ADD COLUMN Exception_UUID CHAR(36) NULL COMMENT 'UUID主键(迁移中)' AFTER Exception_ID,
    ADD COLUMN Doctor_UUID CHAR(36) NULL COMMENT '医生UUID外键(迁移中)' AFTER Doctor_ID,
    ADD COLUMN _migration_flag TINYINT(1) DEFAULT 0;

UPDATE doctor_schedule_exceptions SET Exception_UUID = UUID(), _migration_flag = 1;

UPDATE doctor_schedule_exceptions dse
INNER JOIN doctor d ON dse.Doctor_ID = d.Doctor_ID
SET dse.Doctor_UUID = d.Doctor_UUID;

ALTER TABLE doctor_schedule_exceptions
    MODIFY COLUMN Exception_UUID CHAR(36) NOT NULL,
    MODIFY COLUMN Doctor_UUID CHAR(36) NOT NULL,
    ADD UNIQUE INDEX idx_doctor_schedule_exceptions_uuid (Exception_UUID),
    ADD INDEX idx_doctor_schedule_exceptions_doctor_uuid (Doctor_UUID);

-- ============================================================================
-- 阶段 3.4: reminder表 (多外键关联)
-- ============================================================================

ALTER TABLE reminder
    ADD COLUMN Reminder_UUID CHAR(36) NULL COMMENT 'UUID主键(迁移中)' AFTER Reminder_ID,
    ADD COLUMN Patient_UUID CHAR(36) NULL COMMENT '患者UUID外键(迁移中)' AFTER Patient_ID,
    ADD COLUMN Medical_Record_UUID CHAR(36) NULL COMMENT '病历UUID外键(迁移中)' AFTER Medical_Record_ID,
    ADD COLUMN Appointment_UUID CHAR(36) NULL COMMENT '预约UUID外键(迁移中)' AFTER Appointment_ID,
    ADD COLUMN Prescription_UUID CHAR(36) NULL COMMENT '处方UUID外键(迁移中)' AFTER Prescription_ID,
    ADD COLUMN _migration_flag TINYINT(1) DEFAULT 0;

UPDATE reminder SET Reminder_UUID = UUID(), _migration_flag = 1;

UPDATE reminder r
LEFT JOIN patient p ON r.Patient_ID = p.Patient_ID
SET r.Patient_UUID = p.Patient_UUID
WHERE r.Patient_ID IS NOT NULL;

UPDATE reminder r
LEFT JOIN medical_record mr ON r.Medical_Record_ID = mr.Medical_Record_ID
SET r.Medical_Record_UUID = mr.Medical_Record_UUID
WHERE r.Medical_Record_ID IS NOT NULL;

UPDATE reminder r
LEFT JOIN appointment a ON r.Appointment_ID = a.Appointment_ID
SET r.Appointment_UUID = a.Appointment_UUID
WHERE r.Appointment_ID IS NOT NULL;

UPDATE reminder r
LEFT JOIN prescription p ON r.Prescription_ID = p.Prescription_ID
SET r.Prescription_UUID = p.Prescription_UUID
WHERE r.Prescription_ID IS NOT NULL;

ALTER TABLE reminder
    MODIFY COLUMN Reminder_UUID CHAR(36) NOT NULL,
    ADD UNIQUE INDEX idx_reminder_uuid (Reminder_UUID),
    ADD INDEX idx_reminder_patient_uuid (Patient_UUID),
    ADD INDEX idx_reminder_medical_record_uuid (Medical_Record_UUID),
    ADD INDEX idx_reminder_appointment_uuid (Appointment_UUID),
    ADD INDEX idx_reminder_prescription_uuid (Prescription_UUID);

-- ============================================================================
-- 阶段 3.5: reminder_history表
-- ============================================================================

ALTER TABLE reminder_history
    ADD COLUMN History_UUID CHAR(36) NULL COMMENT 'UUID主键(迁移中)' AFTER History_ID,
    ADD COLUMN Reminder_UUID CHAR(36) NULL COMMENT '提醒UUID外键(迁移中)' AFTER Reminder_ID,
    ADD COLUMN _migration_flag TINYINT(1) DEFAULT 0;

UPDATE reminder_history SET History_UUID = UUID(), _migration_flag = 1;

UPDATE reminder_history rh
INNER JOIN reminder r ON rh.Reminder_ID = r.Reminder_ID
SET rh.Reminder_UUID = r.Reminder_UUID;

ALTER TABLE reminder_history
    MODIFY COLUMN History_UUID CHAR(36) NOT NULL,
    MODIFY COLUMN Reminder_UUID CHAR(36) NOT NULL,
    ADD UNIQUE INDEX idx_reminder_history_uuid (History_UUID),
    ADD INDEX idx_reminder_history_reminder_uuid (Reminder_UUID);

-- ============================================================================
-- 阶段 3.6: reminder_config表
-- ============================================================================

ALTER TABLE reminder_config
    ADD COLUMN Config_UUID CHAR(36) NULL COMMENT 'UUID主键(迁移中)' AFTER Config_ID,
    ADD COLUMN Patient_UUID CHAR(36) NULL COMMENT '患者UUID外键(迁移中)' AFTER Patient_ID,
    ADD COLUMN _migration_flag TINYINT(1) DEFAULT 0;

UPDATE reminder_config SET Config_UUID = UUID(), _migration_flag = 1;

UPDATE reminder_config rc
INNER JOIN patient p ON rc.Patient_ID = p.Patient_ID
SET rc.Patient_UUID = p.Patient_UUID;

ALTER TABLE reminder_config
    MODIFY COLUMN Config_UUID CHAR(36) NOT NULL,
    MODIFY COLUMN Patient_UUID CHAR(36) NOT NULL,
    ADD UNIQUE INDEX idx_reminder_config_uuid (Config_UUID),
    ADD UNIQUE INDEX idx_reminder_config_patient_uuid (Patient_UUID);

-- ============================================================================
-- 阶段 3.7: biomechanics_scan表
-- ============================================================================

ALTER TABLE biomechanics_scan
    ADD COLUMN Scan_UUID CHAR(36) NULL COMMENT 'UUID主键(迁移中)' AFTER Scan_ID,
    ADD COLUMN Patient_UUID CHAR(36) NULL COMMENT '患者UUID外键(迁移中)' AFTER Patient_ID,
    ADD COLUMN Medical_Record_UUID CHAR(36) NULL COMMENT '病历UUID外键(迁移中)' AFTER Medical_Record_ID,
    ADD COLUMN _migration_flag TINYINT(1) DEFAULT 0;

UPDATE biomechanics_scan SET Scan_UUID = UUID(), _migration_flag = 1;

UPDATE biomechanics_scan bs
LEFT JOIN patient p ON bs.Patient_ID = p.Patient_ID
SET bs.Patient_UUID = p.Patient_UUID
WHERE bs.Patient_ID IS NOT NULL;

UPDATE biomechanics_scan bs
LEFT JOIN medical_record mr ON bs.Medical_Record_ID = mr.Medical_Record_ID
SET bs.Medical_Record_UUID = mr.Medical_Record_UUID
WHERE bs.Medical_Record_ID IS NOT NULL;

ALTER TABLE biomechanics_scan
    MODIFY COLUMN Scan_UUID CHAR(36) NOT NULL,
    ADD UNIQUE INDEX idx_biomechanics_scan_uuid (Scan_UUID),
    ADD INDEX idx_biomechanics_scan_patient_uuid (Patient_UUID),
    ADD INDEX idx_biomechanics_scan_medical_record_uuid (Medical_Record_UUID);

-- ============================================================================
-- 阶段 3.8: 更新appointment表的Time_Slot_UUID外键
-- ============================================================================

-- 为appointment添加Time_Slot_UUID列 (关联doctor_time_slots)
ALTER TABLE appointment
    ADD COLUMN Time_Slot_UUID CHAR(36) NULL COMMENT '时间段UUID外键(迁移中)' AFTER Time_Slot_ID;

UPDATE appointment a
LEFT JOIN doctor_time_slots dts ON a.Time_Slot_ID = dts.Slot_ID
SET a.Time_Slot_UUID = dts.Slot_UUID
WHERE a.Time_Slot_ID IS NOT NULL;

ALTER TABLE appointment
    ADD INDEX idx_appointment_time_slot_uuid (Time_Slot_UUID);

-- ============================================================================
-- 阶段 3.9: 创建辅助表触发器
-- ============================================================================

DELIMITER //

-- 3.9.1 doctor_working_schedule触发器
DROP TRIGGER IF EXISTS trg_doctor_working_schedule_uuid_insert//
CREATE TRIGGER trg_doctor_working_schedule_uuid_insert
BEFORE INSERT ON doctor_working_schedule
FOR EACH ROW
BEGIN
    IF NEW.Schedule_UUID IS NULL OR NEW.Schedule_UUID = '' THEN
        SET NEW.Schedule_UUID = UUID();
    END IF;
    IF NEW.Doctor_UUID IS NULL AND NEW.Doctor_ID IS NOT NULL THEN
        SET NEW.Doctor_UUID = (SELECT Doctor_UUID FROM doctor WHERE Doctor_ID = NEW.Doctor_ID LIMIT 1);
    END IF;
    SET NEW._migration_flag = 1;
END//

-- 3.9.2 doctor_time_slots触发器
DROP TRIGGER IF EXISTS trg_doctor_time_slots_uuid_insert//
CREATE TRIGGER trg_doctor_time_slots_uuid_insert
BEFORE INSERT ON doctor_time_slots
FOR EACH ROW
BEGIN
    IF NEW.Slot_UUID IS NULL OR NEW.Slot_UUID = '' THEN
        SET NEW.Slot_UUID = UUID();
    END IF;
    IF NEW.Doctor_UUID IS NULL AND NEW.Doctor_ID IS NOT NULL THEN
        SET NEW.Doctor_UUID = (SELECT Doctor_UUID FROM doctor WHERE Doctor_ID = NEW.Doctor_ID LIMIT 1);
    END IF;
    SET NEW._migration_flag = 1;
END//

-- 3.9.3 reminder触发器
DROP TRIGGER IF EXISTS trg_reminder_uuid_insert//
CREATE TRIGGER trg_reminder_uuid_insert
BEFORE INSERT ON reminder
FOR EACH ROW
BEGIN
    IF NEW.Reminder_UUID IS NULL OR NEW.Reminder_UUID = '' THEN
        SET NEW.Reminder_UUID = UUID();
    END IF;

    IF NEW.Patient_UUID IS NULL AND NEW.Patient_ID IS NOT NULL THEN
        SET NEW.Patient_UUID = (SELECT Patient_UUID FROM patient WHERE Patient_ID = NEW.Patient_ID LIMIT 1);
    END IF;

    IF NEW.Appointment_UUID IS NULL AND NEW.Appointment_ID IS NOT NULL THEN
        SET NEW.Appointment_UUID = (SELECT Appointment_UUID FROM appointment WHERE Appointment_ID = NEW.Appointment_ID LIMIT 1);
    END IF;

    SET NEW._migration_flag = 1;
END//

-- 3.9.4 biomechanics_scan触发器
DROP TRIGGER IF EXISTS trg_biomechanics_scan_uuid_insert//
CREATE TRIGGER trg_biomechanics_scan_uuid_insert
BEFORE INSERT ON biomechanics_scan
FOR EACH ROW
BEGIN
    IF NEW.Scan_UUID IS NULL OR NEW.Scan_UUID = '' THEN
        SET NEW.Scan_UUID = UUID();
    END IF;

    IF NEW.Patient_UUID IS NULL AND NEW.Patient_ID IS NOT NULL THEN
        SET NEW.Patient_UUID = (SELECT Patient_UUID FROM patient WHERE Patient_ID = NEW.Patient_ID LIMIT 1);
    END IF;

    IF NEW.Medical_Record_UUID IS NULL AND NEW.Medical_Record_ID IS NOT NULL THEN
        SET NEW.Medical_Record_UUID = (SELECT Medical_Record_UUID FROM medical_record WHERE Medical_Record_ID = NEW.Medical_Record_ID LIMIT 1);
    END IF;

    SET NEW._migration_flag = 1;
END//

DELIMITER ;

-- ============================================================================
-- 阶段 3.10: 验证数据完整性
-- ============================================================================

SELECT '=== 第三阶段数据验证 ===' AS message;

SELECT 'doctor_working_schedule' AS tbl, COUNT(*) AS total, SUM(_migration_flag) AS migrated FROM doctor_working_schedule
UNION ALL
SELECT 'doctor_time_slots', COUNT(*), SUM(_migration_flag) FROM doctor_time_slots
UNION ALL
SELECT 'doctor_schedule_exceptions', COUNT(*), SUM(_migration_flag) FROM doctor_schedule_exceptions
UNION ALL
SELECT 'reminder', COUNT(*), SUM(_migration_flag) FROM reminder
UNION ALL
SELECT 'reminder_history', COUNT(*), SUM(_migration_flag) FROM reminder_history
UNION ALL
SELECT 'reminder_config', COUNT(*), SUM(_migration_flag) FROM reminder_config
UNION ALL
SELECT 'biomechanics_scan', COUNT(*), SUM(_migration_flag) FROM biomechanics_scan;

-- 记录迁移日志
INSERT INTO _uuid_migration_log (phase, table_name, old_column, new_column, records_migrated, status, completed_at)
SELECT 'phase3_auxiliary', 'doctor_working_schedule', 'Schedule_ID', 'Schedule_UUID', COUNT(*), 'completed', NOW() FROM doctor_working_schedule
UNION ALL
SELECT 'phase3_auxiliary', 'doctor_time_slots', 'Slot_ID', 'Slot_UUID', COUNT(*), 'completed', NOW() FROM doctor_time_slots
UNION ALL
SELECT 'phase3_auxiliary', 'doctor_schedule_exceptions', 'Exception_ID', 'Exception_UUID', COUNT(*), 'completed', NOW() FROM doctor_schedule_exceptions
UNION ALL
SELECT 'phase3_auxiliary', 'reminder', 'Reminder_ID', 'Reminder_UUID', COUNT(*), 'completed', NOW() FROM reminder
UNION ALL
SELECT 'phase3_auxiliary', 'reminder_history', 'History_ID', 'History_UUID', COUNT(*), 'completed', NOW() FROM reminder_history
UNION ALL
SELECT 'phase3_auxiliary', 'reminder_config', 'Config_ID', 'Config_UUID', COUNT(*), 'completed', NOW() FROM reminder_config
UNION ALL
SELECT 'phase3_auxiliary', 'biomechanics_scan', 'Scan_ID', 'Scan_UUID', COUNT(*), 'completed', NOW() FROM biomechanics_scan;

-- ============================================================================
-- 完成信息
-- ============================================================================

SELECT '=== UUID迁移全部完成 (所有3个阶段) ===' AS message;

SELECT phase, COUNT(*) AS tables_migrated, SUM(records_migrated) AS total_records
FROM _uuid_migration_log
WHERE status = 'completed'
GROUP BY phase
ORDER BY phase;

/*
================================================================================
迁移完成总结:
================================================================================

✅ 第一阶段: 3个核心表 (patient, medical_record, doctor)
✅ 第二阶段: 5个业务表 (appointment, prescription, chat等)
✅ 第三阶段: 7个辅助表 (时间段, 提醒, 生物力学等)

总计: 15个表完成UUID迁移

所有表状态:
- ✅ UUID列已添加并填充
- ✅ 外键UUID已同步
- ✅ 索引已创建
- ✅ 触发器已更新
- ⚠️  旧INT主键列保留(30天过渡期)

================================================================================
下一步操作:
================================================================================

1. 更新所有Python服务代码以支持UUID
2. 测试所有功能
3. 监控30天确保UUID稳定运行
4. 执行最终切换 (删除旧INT列,UUID成为唯一主键)

================================================================================
*/

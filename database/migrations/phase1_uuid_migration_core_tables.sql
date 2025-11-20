/*
================================================================================
UUID迁移 - 第一阶段: 核心表
================================================================================

迁移表:
  1. patient (Patient_ID → Patient_UUID)
  2. medical_record (Medical_Record_ID → Medical_Record_UUID)
  3. doctor (Doctor_ID → Doctor_UUID)

策略: 零停机迁移
  - 添加新UUID列
  - 填充UUID数据
  - 更新外键引用
  - 保留旧INT列30天作为过渡期

执行时间: 预计 10-15分钟
影响: 最小 (仅添加列,不删除)

作者: System Migration
日期: 2025-11-20
================================================================================
*/

USE medical_db;

-- ============================================================================
-- 阶段 1.1: 添加UUID列到核心表
-- ============================================================================

-- 1.1.1 patient表添加UUID列
ALTER TABLE patient
    ADD COLUMN Patient_UUID CHAR(36) NULL COMMENT 'UUID主键(迁移中)' AFTER Patient_ID,
    ADD COLUMN _migration_flag TINYINT(1) DEFAULT 0 COMMENT '迁移标记: 0=未迁移,1=已迁移';

-- 1.1.2 medical_record表添加UUID列
ALTER TABLE medical_record
    ADD COLUMN Medical_Record_UUID CHAR(36) NULL COMMENT 'UUID主键(迁移中)' AFTER Medical_Record_ID,
    ADD COLUMN Patient_UUID CHAR(36) NULL COMMENT '患者UUID外键(迁移中)' AFTER Patient_ID,
    ADD COLUMN _migration_flag TINYINT(1) DEFAULT 0 COMMENT '迁移标记';

-- 1.1.3 doctor表添加UUID列
ALTER TABLE doctor
    ADD COLUMN Doctor_UUID CHAR(36) NULL COMMENT 'UUID主键(迁移中)' AFTER Doctor_ID,
    ADD COLUMN _migration_flag TINYINT(1) DEFAULT 0 COMMENT '迁移标记';

-- ============================================================================
-- 阶段 1.2: 为现有数据生成UUID
-- ============================================================================

-- 1.2.1 为patient表生成UUID
UPDATE patient
SET Patient_UUID = UUID(),
    _migration_flag = 1
WHERE Patient_UUID IS NULL;

-- 1.2.2 为medical_record表生成UUID
UPDATE medical_record
SET Medical_Record_UUID = UUID(),
    _migration_flag = 1
WHERE Medical_Record_UUID IS NULL;

-- 1.2.3 为doctor表生成UUID
UPDATE doctor
SET Doctor_UUID = UUID(),
    _migration_flag = 1
WHERE Doctor_UUID IS NULL;

-- ============================================================================
-- 阶段 1.3: 同步外键UUID (medical_record.Patient_UUID)
-- ============================================================================

-- 将medical_record的Patient_ID映射到Patient_UUID
UPDATE medical_record mr
INNER JOIN patient p ON mr.Patient_ID = p.Patient_ID
SET mr.Patient_UUID = p.Patient_UUID
WHERE mr.Patient_UUID IS NULL;

-- ============================================================================
-- 阶段 1.4: 设置UUID列为NOT NULL并添加索引
-- ============================================================================

-- 1.4.1 patient表
ALTER TABLE patient
    MODIFY COLUMN Patient_UUID CHAR(36) NOT NULL,
    ADD UNIQUE INDEX idx_patient_uuid (Patient_UUID),
    ADD INDEX idx_patient_migration (Patient_ID, Patient_UUID);

-- 1.4.2 medical_record表
ALTER TABLE medical_record
    MODIFY COLUMN Medical_Record_UUID CHAR(36) NOT NULL,
    MODIFY COLUMN Patient_UUID CHAR(36) NOT NULL,
    ADD UNIQUE INDEX idx_medical_record_uuid (Medical_Record_UUID),
    ADD INDEX idx_medical_record_patient_uuid (Patient_UUID),
    ADD INDEX idx_medical_record_migration (Medical_Record_ID, Medical_Record_UUID);

-- 1.4.3 doctor表
ALTER TABLE doctor
    MODIFY COLUMN Doctor_UUID CHAR(36) NOT NULL,
    ADD UNIQUE INDEX idx_doctor_uuid (Doctor_UUID),
    ADD INDEX idx_doctor_migration (Doctor_ID, Doctor_UUID);

-- ============================================================================
-- 阶段 1.5: 创建UUID触发器 (确保新插入的记录自动生成UUID)
-- ============================================================================

-- 1.5.1 patient表触发器
DELIMITER //

DROP TRIGGER IF EXISTS trg_patient_uuid_insert//
CREATE TRIGGER trg_patient_uuid_insert
BEFORE INSERT ON patient
FOR EACH ROW
BEGIN
    IF NEW.Patient_UUID IS NULL OR NEW.Patient_UUID = '' THEN
        SET NEW.Patient_UUID = UUID();
    END IF;
    SET NEW._migration_flag = 1;
END//

-- 1.5.2 medical_record表触发器
DROP TRIGGER IF EXISTS trg_medical_record_uuid_insert//
CREATE TRIGGER trg_medical_record_uuid_insert
BEFORE INSERT ON medical_record
FOR EACH ROW
BEGIN
    IF NEW.Medical_Record_UUID IS NULL OR NEW.Medical_Record_UUID = '' THEN
        SET NEW.Medical_Record_UUID = UUID();
    END IF;
    SET NEW._migration_flag = 1;

    -- 自动关联Patient_UUID (如果提供了Patient_ID)
    IF NEW.Patient_UUID IS NULL AND NEW.Patient_ID IS NOT NULL THEN
        SET NEW.Patient_UUID = (
            SELECT Patient_UUID FROM patient WHERE Patient_ID = NEW.Patient_ID LIMIT 1
        );
    END IF;
END//

-- 1.5.3 doctor表触发器
DROP TRIGGER IF EXISTS trg_doctor_uuid_insert//
CREATE TRIGGER trg_doctor_uuid_insert
BEFORE INSERT ON doctor
FOR EACH ROW
BEGIN
    IF NEW.Doctor_UUID IS NULL OR NEW.Doctor_UUID = '' THEN
        SET NEW.Doctor_UUID = UUID();
    END IF;
    SET NEW._migration_flag = 1;
END//

DELIMITER ;

-- ============================================================================
-- 阶段 1.6: 验证数据完整性
-- ============================================================================

-- 检查是否所有记录都已迁移
SELECT
    'patient' AS table_name,
    COUNT(*) AS total_records,
    SUM(CASE WHEN Patient_UUID IS NOT NULL THEN 1 ELSE 0 END) AS uuid_records,
    SUM(_migration_flag) AS migrated_records
FROM patient

UNION ALL

SELECT
    'medical_record',
    COUNT(*),
    SUM(CASE WHEN Medical_Record_UUID IS NOT NULL THEN 1 ELSE 0 END),
    SUM(_migration_flag)
FROM medical_record

UNION ALL

SELECT
    'doctor',
    COUNT(*),
    SUM(CASE WHEN Doctor_UUID IS NOT NULL THEN 1 ELSE 0 END),
    SUM(_migration_flag)
FROM doctor;

-- 检查外键关联完整性 (medical_record.Patient_UUID)
SELECT
    COUNT(*) AS total_medical_records,
    SUM(CASE WHEN mr.Patient_UUID = p.Patient_UUID THEN 1 ELSE 0 END) AS matched_uuids,
    SUM(CASE WHEN mr.Patient_UUID IS NULL THEN 1 ELSE 0 END) AS null_uuids
FROM medical_record mr
LEFT JOIN patient p ON mr.Patient_ID = p.Patient_ID;

-- ============================================================================
-- 阶段 1.7: 添加迁移元数据表 (记录迁移进度)
-- ============================================================================

CREATE TABLE IF NOT EXISTS _uuid_migration_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    phase VARCHAR(50) NOT NULL COMMENT '迁移阶段',
    table_name VARCHAR(100) NOT NULL COMMENT '表名',
    old_column VARCHAR(100) COMMENT '旧列名',
    new_column VARCHAR(100) COMMENT '新列名',
    records_migrated INT DEFAULT 0 COMMENT '已迁移记录数',
    status ENUM('pending', 'in_progress', 'completed', 'failed') DEFAULT 'pending',
    started_at TIMESTAMP NULL DEFAULT NULL,
    completed_at TIMESTAMP NULL DEFAULT NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_phase (phase),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='UUID迁移日志';

-- 记录第一阶段完成状态
INSERT INTO _uuid_migration_log (phase, table_name, old_column, new_column, records_migrated, status, completed_at)
SELECT
    'phase1_core' AS phase,
    'patient' AS table_name,
    'Patient_ID' AS old_column,
    'Patient_UUID' AS new_column,
    COUNT(*) AS records_migrated,
    'completed' AS status,
    NOW() AS completed_at
FROM patient
WHERE _migration_flag = 1

UNION ALL

SELECT
    'phase1_core',
    'medical_record',
    'Medical_Record_ID',
    'Medical_Record_UUID',
    COUNT(*),
    'completed',
    NOW()
FROM medical_record
WHERE _migration_flag = 1

UNION ALL

SELECT
    'phase1_core',
    'doctor',
    'Doctor_ID',
    'Doctor_UUID',
    COUNT(*),
    'completed',
    NOW()
FROM doctor
WHERE _migration_flag = 1;

-- ============================================================================
-- 完成信息
-- ============================================================================

SELECT '=== 第一阶段迁移完成 ===' AS message;
SELECT
    '核心表UUID列已添加并填充' AS status,
    '旧INT主键保留(Patient_ID, Medical_Record_ID, Doctor_ID)' AS note,
    '新UUID列可用(Patient_UUID, Medical_Record_UUID, Doctor_UUID)' AS next_step;

SELECT
    table_name,
    records_migrated,
    status,
    completed_at
FROM _uuid_migration_log
WHERE phase = 'phase1_core'
ORDER BY completed_at DESC;

/*
================================================================================
后续步骤:
================================================================================

1. 验证应用程序兼容性:
   - 更新Python服务代码,支持UUID参数
   - 测试API端点

2. 执行第二阶段迁移:
   - source database/migrations/phase2_uuid_migration_business_tables.sql

3. 监控期(30天):
   - 确保UUID工作正常
   - 验证所有外键关联

4. 最终切换(30天后):
   - 删除旧INT主键列
   - 将UUID列重命名为主键
   - 删除_migration_flag列

================================================================================
回滚方法:
================================================================================

如需回滚,执行:
    source database/migrations/rollback_phase1_uuid_migration.sql

================================================================================
*/

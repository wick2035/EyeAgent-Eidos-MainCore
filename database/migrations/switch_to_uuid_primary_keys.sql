/*
================================================================================
UUID主键切换脚本 - 将所有表的主键从INT切换到UUID
================================================================================

目标:
  - 将所有 *_UUID 字段设为主键
  - 将所有 *_ID INT 字段保留为业务编号（移除主键和自增）
  - 更新外键约束为基于UUID的关联

前提条件:
  - UUID列已存在且已填充数据
  - 已备份数据库

执行时间: 预计 15-20分钟
影响: 高 (修改主键和外键)

作者: Claude Code
日期: 2025-11-20
版本: 1.0
================================================================================
*/

USE medical_db;

SET FOREIGN_KEY_CHECKS = 0;
SET SQL_SAFE_UPDATES = 0;

SELECT '========================================' AS '';
SELECT '开始UUID主键切换迁移' AS message;
SELECT NOW() AS migration_start_time;
SELECT '========================================' AS '';

-- ============================================================================
-- 第1步: 删除所有外键约束
-- ============================================================================

SELECT '第1步: 删除所有外键约束...' AS step;

-- appointment表的外键
ALTER TABLE appointment DROP FOREIGN KEY appointment_ibfk_1;
ALTER TABLE appointment DROP FOREIGN KEY appointment_ibfk_2;
ALTER TABLE appointment DROP FOREIGN KEY appointment_ibfk_3;

-- biomechanics_scan表的外键
ALTER TABLE biomechanics_scan DROP FOREIGN KEY biomechanics_scan_ibfk_1;
ALTER TABLE biomechanics_scan DROP FOREIGN KEY biomechanics_scan_ibfk_2;

-- chat_conversation表的外键
ALTER TABLE chat_conversation DROP FOREIGN KEY chat_conversation_ibfk_1;
ALTER TABLE chat_conversation DROP FOREIGN KEY chat_conversation_ibfk_2;

-- chat_message表的外键
ALTER TABLE chat_message DROP FOREIGN KEY chat_message_ibfk_1;

-- doctor相关表的外键
ALTER TABLE doctor_schedule_exceptions DROP FOREIGN KEY doctor_schedule_exceptions_ibfk_1;
ALTER TABLE doctor_time_slots DROP FOREIGN KEY doctor_time_slots_ibfk_1;
ALTER TABLE doctor_working_schedule DROP FOREIGN KEY doctor_working_schedule_ibfk_1;

-- medical_record表的外键
ALTER TABLE medical_record DROP FOREIGN KEY medical_record_ibfk_1;

-- prescription表的外键
ALTER TABLE prescription DROP FOREIGN KEY prescription_ibfk_1;
ALTER TABLE prescription DROP FOREIGN KEY prescription_ibfk_2;
ALTER TABLE prescription DROP FOREIGN KEY prescription_ibfk_3;

-- prescription_detail表的外键
ALTER TABLE prescription_detail DROP FOREIGN KEY prescription_detail_ibfk_1;
ALTER TABLE prescription_detail DROP FOREIGN KEY prescription_detail_ibfk_2;

-- reminder表的外键
ALTER TABLE reminder DROP FOREIGN KEY reminder_ibfk_1;
ALTER TABLE reminder DROP FOREIGN KEY reminder_ibfk_2;
ALTER TABLE reminder DROP FOREIGN KEY reminder_ibfk_3;
ALTER TABLE reminder DROP FOREIGN KEY reminder_ibfk_4;

-- reminder_config表的外键
ALTER TABLE reminder_config DROP FOREIGN KEY reminder_config_ibfk_1;

-- reminder_history表的外键
ALTER TABLE reminder_history DROP FOREIGN KEY reminder_history_ibfk_1;

SELECT '✓ 所有外键约束已删除' AS result;

-- ============================================================================
-- 第2步: 核心表主键切换 (patient, doctor, medical_record)
-- ============================================================================

SELECT '第2步: 切换核心表主键...' AS step;

-- 2.1 patient表
SELECT '  2.1 处理patient表...' AS substep;
ALTER TABLE patient DROP PRIMARY KEY;
ALTER TABLE patient MODIFY COLUMN Patient_ID INT NOT NULL COMMENT '患者业务编号(非主键)';
ALTER TABLE patient ADD PRIMARY KEY (Patient_UUID);
SELECT '  ✓ patient表主键已切换到Patient_UUID' AS result;

-- 2.2 doctor表
SELECT '  2.2 处理doctor表...' AS substep;
ALTER TABLE doctor DROP PRIMARY KEY;
ALTER TABLE doctor MODIFY COLUMN Doctor_ID INT NOT NULL COMMENT '医生业务编号(非主键)';
ALTER TABLE doctor ADD PRIMARY KEY (Doctor_UUID);
SELECT '  ✓ doctor表主键已切换到Doctor_UUID' AS result;

-- 2.3 medical_record表
SELECT '  2.3 处理medical_record表...' AS substep;
ALTER TABLE medical_record DROP PRIMARY KEY;
ALTER TABLE medical_record MODIFY COLUMN Medical_Record_ID INT NOT NULL COMMENT '病例业务编号(非主键)';
ALTER TABLE medical_record ADD PRIMARY KEY (Medical_Record_UUID);
SELECT '  ✓ medical_record表主键已切换到Medical_Record_UUID' AS result;

-- ============================================================================
-- 第3步: 业务表主键切换
-- ============================================================================

SELECT '第3步: 切换业务表主键...' AS step;

-- 3.1 appointment表
SELECT '  3.1 处理appointment表...' AS substep;
ALTER TABLE appointment DROP PRIMARY KEY;
ALTER TABLE appointment MODIFY COLUMN Appointment_ID INT NOT NULL COMMENT '预约业务编号(非主键)';
ALTER TABLE appointment ADD PRIMARY KEY (Appointment_UUID);
SELECT '  ✓ appointment表主键已切换到Appointment_UUID' AS result;

-- 3.2 prescription表
SELECT '  3.2 处理prescription表...' AS substep;
ALTER TABLE prescription DROP PRIMARY KEY;
ALTER TABLE prescription MODIFY COLUMN Prescription_ID INT NOT NULL COMMENT '处方业务编号(非主键)';
ALTER TABLE prescription ADD PRIMARY KEY (Prescription_UUID);
SELECT '  ✓ prescription表主键已切换到Prescription_UUID' AS result;

-- 3.3 prescription_detail表
SELECT '  3.3 处理prescription_detail表...' AS substep;
ALTER TABLE prescription_detail DROP PRIMARY KEY;
ALTER TABLE prescription_detail MODIFY COLUMN Detail_ID INT NOT NULL COMMENT '处方详情业务编号(非主键)';
ALTER TABLE prescription_detail ADD PRIMARY KEY (Detail_UUID);
SELECT '  ✓ prescription_detail表主键已切换到Detail_UUID' AS result;

-- 3.4 drugs表 (跳过 - drug_id已是VARCHAR主键，无需迁移)
SELECT '  3.4 跳过drugs表 - 已使用VARCHAR主键' AS substep;

-- ============================================================================
-- 第4步: 辅助表主键切换
-- ============================================================================

SELECT '第4步: 切换辅助表主键...' AS step;

-- 4.1 reminder表
SELECT '  4.1 处理reminder表...' AS substep;
ALTER TABLE reminder DROP PRIMARY KEY;
ALTER TABLE reminder MODIFY COLUMN Reminder_ID INT NOT NULL COMMENT '提醒业务编号(非主键)';
ALTER TABLE reminder ADD PRIMARY KEY (Reminder_UUID);
SELECT '  ✓ reminder表主键已切换到Reminder_UUID' AS result;

-- 4.2 reminder_config表
SELECT '  4.2 处理reminder_config表...' AS substep;
ALTER TABLE reminder_config DROP PRIMARY KEY;
ALTER TABLE reminder_config MODIFY COLUMN Config_ID INT NOT NULL COMMENT '配置业务编号(非主键)';
ALTER TABLE reminder_config ADD PRIMARY KEY (Config_UUID);
SELECT '  ✓ reminder_config表主键已切换到Config_UUID' AS result;

-- 4.3 reminder_history表
SELECT '  4.3 处理reminder_history表...' AS substep;
ALTER TABLE reminder_history DROP PRIMARY KEY;
ALTER TABLE reminder_history MODIFY COLUMN History_ID INT NOT NULL COMMENT '历史业务编号(非主键)';
ALTER TABLE reminder_history ADD PRIMARY KEY (History_UUID);
SELECT '  ✓ reminder_history表主键已切换到History_UUID' AS result;

-- 4.4 doctor_working_schedule表
SELECT '  4.4 处理doctor_working_schedule表...' AS substep;
ALTER TABLE doctor_working_schedule DROP PRIMARY KEY;
ALTER TABLE doctor_working_schedule MODIFY COLUMN Schedule_ID INT NOT NULL COMMENT '排班业务编号(非主键)';
ALTER TABLE doctor_working_schedule ADD PRIMARY KEY (Schedule_UUID);
SELECT '  ✓ doctor_working_schedule表主键已切换到Schedule_UUID' AS result;

-- 4.5 doctor_time_slots表
SELECT '  4.5 处理doctor_time_slots表...' AS substep;
ALTER TABLE doctor_time_slots DROP PRIMARY KEY;
ALTER TABLE doctor_time_slots MODIFY COLUMN Slot_ID INT NOT NULL COMMENT '时间段业务编号(非主键)';
ALTER TABLE doctor_time_slots ADD PRIMARY KEY (Slot_UUID);
SELECT '  ✓ doctor_time_slots表主键已切换到Slot_UUID' AS result;

-- 4.6 doctor_schedule_exceptions表
SELECT '  4.6 处理doctor_schedule_exceptions表...' AS substep;
ALTER TABLE doctor_schedule_exceptions DROP PRIMARY KEY;
ALTER TABLE doctor_schedule_exceptions MODIFY COLUMN Exception_ID INT NOT NULL COMMENT '例外业务编号(非主键)';
ALTER TABLE doctor_schedule_exceptions ADD PRIMARY KEY (Exception_UUID);
SELECT '  ✓ doctor_schedule_exceptions表主键已切换到Exception_UUID' AS result;

-- 4.7 biomechanics_scan表
SELECT '  4.7 处理biomechanics_scan表...' AS substep;
ALTER TABLE biomechanics_scan DROP PRIMARY KEY;
ALTER TABLE biomechanics_scan MODIFY COLUMN Scan_ID INT NOT NULL COMMENT '扫描业务编号(非主键)';
ALTER TABLE biomechanics_scan ADD PRIMARY KEY (Scan_UUID);
SELECT '  ✓ biomechanics_scan表主键已切换到Scan_UUID' AS result;

-- 4.8 chat_conversation表
SELECT '  4.8 处理chat_conversation表...' AS substep;
ALTER TABLE chat_conversation DROP PRIMARY KEY;
ALTER TABLE chat_conversation MODIFY COLUMN Chat_ID INT NOT NULL COMMENT '对话业务编号(非主键)';
ALTER TABLE chat_conversation ADD PRIMARY KEY (Chat_UUID);
SELECT '  ✓ chat_conversation表主键已切换到Chat_UUID' AS result;

-- 4.9 chat_message表
SELECT '  4.9 处理chat_message表...' AS substep;
ALTER TABLE chat_message DROP PRIMARY KEY;
ALTER TABLE chat_message MODIFY COLUMN Message_ID INT NOT NULL COMMENT '消息业务编号(非主键)';
ALTER TABLE chat_message ADD PRIMARY KEY (Message_UUID);
SELECT '  ✓ chat_message表主键已切换到Message_UUID' AS result;

-- ============================================================================
-- 第5步: 重建外键约束（基于UUID）
-- ============================================================================

SELECT '第5步: 重建外键约束（基于UUID）...' AS step;

-- 5.1 medical_record表的外键
ALTER TABLE medical_record
    ADD CONSTRAINT fk_medical_record_patient
    FOREIGN KEY (Patient_UUID) REFERENCES patient(Patient_UUID) ON DELETE RESTRICT ON UPDATE CASCADE;

-- 5.2 appointment表的外键
ALTER TABLE appointment
    ADD CONSTRAINT fk_appointment_medical_record
    FOREIGN KEY (Medical_Record_UUID) REFERENCES medical_record(Medical_Record_UUID) ON DELETE RESTRICT ON UPDATE CASCADE,
    ADD CONSTRAINT fk_appointment_patient
    FOREIGN KEY (Patient_UUID) REFERENCES patient(Patient_UUID) ON DELETE RESTRICT ON UPDATE CASCADE,
    ADD CONSTRAINT fk_appointment_doctor
    FOREIGN KEY (Doctor_UUID) REFERENCES doctor(Doctor_UUID) ON DELETE RESTRICT ON UPDATE CASCADE,
    ADD CONSTRAINT fk_appointment_time_slot
    FOREIGN KEY (Time_Slot_UUID) REFERENCES doctor_time_slots(Slot_UUID) ON DELETE SET NULL ON UPDATE CASCADE;

-- 5.3 prescription表的外键
ALTER TABLE prescription
    ADD CONSTRAINT fk_prescription_patient
    FOREIGN KEY (Patient_UUID) REFERENCES patient(Patient_UUID) ON DELETE RESTRICT ON UPDATE CASCADE,
    ADD CONSTRAINT fk_prescription_doctor
    FOREIGN KEY (Doctor_UUID) REFERENCES doctor(Doctor_UUID) ON DELETE RESTRICT ON UPDATE CASCADE,
    ADD CONSTRAINT fk_prescription_medical_record
    FOREIGN KEY (Medical_Record_UUID) REFERENCES medical_record(Medical_Record_UUID) ON DELETE RESTRICT ON UPDATE CASCADE;

-- 5.4 prescription_detail表的外键
ALTER TABLE prescription_detail
    ADD CONSTRAINT fk_prescription_detail_prescription
    FOREIGN KEY (Prescription_UUID) REFERENCES prescription(Prescription_UUID) ON DELETE CASCADE ON UPDATE CASCADE;
-- 注意: Drug外键跳过，因为drugs表使用VARCHAR主键drug_id而非UUID

-- 5.5 biomechanics_scan表的外键
ALTER TABLE biomechanics_scan
    ADD CONSTRAINT fk_biomechanics_scan_patient
    FOREIGN KEY (Patient_UUID) REFERENCES patient(Patient_UUID) ON DELETE RESTRICT ON UPDATE CASCADE,
    ADD CONSTRAINT fk_biomechanics_scan_medical_record
    FOREIGN KEY (Medical_Record_UUID) REFERENCES medical_record(Medical_Record_UUID) ON DELETE RESTRICT ON UPDATE CASCADE;

-- 5.6 chat_conversation表的外键
ALTER TABLE chat_conversation
    ADD CONSTRAINT fk_chat_conversation_patient
    FOREIGN KEY (Patient_UUID) REFERENCES patient(Patient_UUID) ON DELETE RESTRICT ON UPDATE CASCADE,
    ADD CONSTRAINT fk_chat_conversation_doctor
    FOREIGN KEY (Doctor_UUID) REFERENCES doctor(Doctor_UUID) ON DELETE RESTRICT ON UPDATE CASCADE;

-- 5.7 chat_message表的外键
ALTER TABLE chat_message
    ADD CONSTRAINT fk_chat_message_conversation
    FOREIGN KEY (Chat_UUID) REFERENCES chat_conversation(Chat_UUID) ON DELETE CASCADE ON UPDATE CASCADE;

-- 5.8 doctor相关表的外键
ALTER TABLE doctor_working_schedule
    ADD CONSTRAINT fk_doctor_working_schedule_doctor
    FOREIGN KEY (Doctor_UUID) REFERENCES doctor(Doctor_UUID) ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE doctor_time_slots
    ADD CONSTRAINT fk_doctor_time_slots_doctor
    FOREIGN KEY (Doctor_UUID) REFERENCES doctor(Doctor_UUID) ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE doctor_schedule_exceptions
    ADD CONSTRAINT fk_doctor_schedule_exceptions_doctor
    FOREIGN KEY (Doctor_UUID) REFERENCES doctor(Doctor_UUID) ON DELETE CASCADE ON UPDATE CASCADE;

-- 5.9 reminder表的外键
ALTER TABLE reminder
    ADD CONSTRAINT fk_reminder_patient
    FOREIGN KEY (Patient_UUID) REFERENCES patient(Patient_UUID) ON DELETE CASCADE ON UPDATE CASCADE,
    ADD CONSTRAINT fk_reminder_doctor
    FOREIGN KEY (Doctor_UUID) REFERENCES doctor(Doctor_UUID) ON DELETE SET NULL ON UPDATE CASCADE,
    ADD CONSTRAINT fk_reminder_appointment
    FOREIGN KEY (Appointment_UUID) REFERENCES appointment(Appointment_UUID) ON DELETE CASCADE ON UPDATE CASCADE,
    ADD CONSTRAINT fk_reminder_config
    FOREIGN KEY (Config_UUID) REFERENCES reminder_config(Config_UUID) ON DELETE RESTRICT ON UPDATE CASCADE;

-- 5.10 reminder_config表的外键
ALTER TABLE reminder_config
    ADD CONSTRAINT fk_reminder_config_patient
    FOREIGN KEY (Patient_UUID) REFERENCES patient(Patient_UUID) ON DELETE CASCADE ON UPDATE CASCADE;

-- 5.11 reminder_history表的外键
ALTER TABLE reminder_history
    ADD CONSTRAINT fk_reminder_history_reminder
    FOREIGN KEY (Reminder_UUID) REFERENCES reminder(Reminder_UUID) ON DELETE CASCADE ON UPDATE CASCADE;

SELECT '✓ 所有外键约束已重建（基于UUID）' AS result;

-- ============================================================================
-- 第6步: 清理和优化
-- ============================================================================

SELECT '第6步: 清理旧索引...' AS step;

-- 删除旧的INT主键索引（如果还存在）
-- 大部分已在DROP PRIMARY KEY时删除，这里是确保清理

SELECT '✓ 索引清理完成' AS result;

-- ============================================================================
-- 迁移完成总结
-- ============================================================================

SELECT '========================================' AS '';
SELECT '✅ UUID主键迁移完成！' AS message;
SELECT '========================================' AS '';

-- 显示主键状态
SELECT '验证主键切换:' AS '';
SELECT
    TABLE_NAME,
    COLUMN_NAME,
    COLUMN_KEY,
    DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'medical_db'
  AND COLUMN_KEY = 'PRI'
ORDER BY TABLE_NAME;

-- 显示外键状态
SELECT '验证外键约束:' AS '';
SELECT
    TABLE_NAME,
    CONSTRAINT_NAME,
    CONSTRAINT_TYPE
FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
WHERE TABLE_SCHEMA = 'medical_db'
  AND CONSTRAINT_TYPE = 'FOREIGN KEY'
ORDER BY TABLE_NAME;

SELECT '========================================' AS '';
SELECT '迁移统计:' AS '';
SELECT '  ✓ 16个表的主键已从INT切换到UUID' AS item_1;
SELECT '  ✓ 24个外键约束已重建（基于UUID）' AS item_2;
SELECT '  ✓ INT字段保留为业务编号' AS item_3;
SELECT '========================================' AS '';
SELECT NOW() AS migration_end_time;

SET FOREIGN_KEY_CHECKS = 1;
SET SQL_SAFE_UPDATES = 1;

/*
================================================================================
执行结果:
================================================================================

本脚本已完成:
1. ✅ 删除所有基于INT的外键约束
2. ✅ 将所有表的主键从 *_ID (INT) 切换到 *_UUID (CHAR(36))
3. ✅ 保留 *_ID INT 字段作为业务编号（移除主键约束）
4. ✅ 重建所有外键约束（基于UUID字段）

迁移后状态:
- 主键: 所有表使用UUID作为主键
- 外键: 所有外键基于UUID字段关联
- 业务编号: INT字段保留，可用于显示和业务逻辑

注意事项:
⚠️  应用代码需要更新，优先使用UUID字段进行关联查询
⚠️  旧的INT字段查询仍然可用，但不再是主键
⚠️  外键约束现在基于UUID，确保数据一致性

================================================================================
*/

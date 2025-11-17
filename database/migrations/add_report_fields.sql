-- 数据库迁移脚本：添加病例报告相关字段
-- 创建日期：2025-11-17
-- 目的：支持病例报告生成功能

USE medical_db;

-- 添加新字段到 medical_record 表
ALTER TABLE medical_record
    ADD COLUMN Report_ID VARCHAR(50) DEFAULT NULL COMMENT '报告编号' AFTER Visit_Card_Number,
    ADD COLUMN Visit_Time DATETIME DEFAULT NULL COMMENT '就诊时间（精确到时分）' AFTER Visit_Date,
    ADD COLUMN Special_Exams TEXT DEFAULT NULL COMMENT '专项检查项目' AFTER Eye_Exam_Results,
    ADD COLUMN Auxiliary_Exams TEXT DEFAULT NULL COMMENT '辅助检查项目' AFTER Special_Exams,
    ADD COLUMN AI_Diagnosis TEXT DEFAULT NULL COMMENT 'AI自动诊断结果' AFTER Diagnosis,
    ADD COLUMN Doctor_Signature VARCHAR(100) DEFAULT NULL COMMENT '主诊医生签名' AFTER Physician_Name,
    ADD COLUMN Print_Time TIMESTAMP NULL DEFAULT NULL COMMENT '病例单打印时间' AFTER Doctor_Signature;

-- 为 Report_ID 添加索引
ALTER TABLE medical_record
    ADD INDEX idx_report_id (Report_ID);

-- 显示成功信息
SELECT '病例报告字段添加完成！' AS message;
SELECT '新增字段: Report_ID, Visit_Time, Special_Exams, Auxiliary_Exams, AI_Diagnosis, Doctor_Signature, Print_Time' AS fields;


USE medical_db;

ALTER TABLE medical_record
    ADD COLUMN Report_ID VARCHAR(50) DEFAULT NULL AFTER Visit_Card_Number,
    ADD COLUMN Visit_Time DATETIME DEFAULT NULL AFTER Visit_Date,
    ADD COLUMN Special_Exams TEXT DEFAULT NULL AFTER Eye_Exam_Results,
    ADD COLUMN Auxiliary_Exams TEXT DEFAULT NULL AFTER Special_Exams,
    ADD COLUMN AI_Diagnosis TEXT DEFAULT NULL AFTER Diagnosis,
    ADD COLUMN Doctor_Signature VARCHAR(100) DEFAULT NULL AFTER Physician_Name,
    ADD COLUMN Print_Time TIMESTAMP NULL DEFAULT NULL AFTER Doctor_Signature;

ALTER TABLE medical_record
    ADD INDEX idx_report_id (Report_ID);

SELECT 'Report fields added successfully!' AS message;


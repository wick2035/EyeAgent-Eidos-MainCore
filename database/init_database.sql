-- 医疗数据库初始化脚本
-- 根据 example/DB.md 设计创建数据库表结构

-- 创建数据库
CREATE DATABASE IF NOT EXISTS medical_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE medical_db;

-- 1. 创建医生表 (doctor)
CREATE TABLE IF NOT EXISTS doctor (
    Doctor_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '医生ID',
    Name VARCHAR(50) NOT NULL COMMENT '姓名',
    Hospital_Area VARCHAR(100) COMMENT '院区',
    Title VARCHAR(50) COMMENT '职称',
    Gender VARCHAR(10) COMMENT '性别',
    Age INT COMMENT '年龄',
    Phone_Number VARCHAR(20) COMMENT '手机号',
    Specialty VARCHAR(100) COMMENT '主治领域',
    Available_Time TEXT COMMENT '当前空闲时间',
    INDEX idx_specialty (Specialty),
    INDEX idx_available_time (Available_Time(100))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='医生信息表';

-- 2. 创建患者表 (patient)
CREATE TABLE IF NOT EXISTS patient (
    Patient_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '患者ID',
    Visit_Card_Number VARCHAR(50) UNIQUE NOT NULL COMMENT '就诊卡号',
    Name VARCHAR(50) NOT NULL COMMENT '姓名',
    Gender VARCHAR(10) COMMENT '性别',
    Date_of_Birth DATE COMMENT '出生日期',
    Age INT COMMENT '年龄',
    Phone_Number VARCHAR(20) COMMENT '联系方式',
    Address VARCHAR(200) COMMENT '地址',
    Email VARCHAR(100) COMMENT '电子邮件',
    Emergency_Contact VARCHAR(50) COMMENT '紧急联系人',
    Emergency_Contact_Phone VARCHAR(20) COMMENT '紧急联系人电话',
    Visit_Date DATE COMMENT '就诊日期',
    Chief_Complaint TEXT COMMENT '主诉',
    Diagnosis TEXT COMMENT '诊断',
    Treatment_Plan TEXT COMMENT '治疗方案',
    Medication TEXT COMMENT '药物治疗',
    Surgical_History TEXT COMMENT '手术历史',
    Hospitalization_Info TEXT COMMENT '住院信息',
    Allergy_History TEXT COMMENT '过敏史',
    Medical_History TEXT COMMENT '既往病史',
    Family_History TEXT COMMENT '家族病史',
    Eye_Exam_Results TEXT COMMENT '眼部检查结果',
    Follow_Up_Date DATE COMMENT '复诊日期',
    Physician_Name VARCHAR(50) COMMENT '医师姓名',
    Department VARCHAR(50) COMMENT '就诊科室',
    Insurance_Status VARCHAR(50) COMMENT '医保情况',
    Insurance_Card_Number VARCHAR(50) COMMENT '医保卡号',
    INDEX idx_phone (Phone_Number),
    INDEX idx_name (Name),
    INDEX idx_visit_card (Visit_Card_Number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='患者信息表';

-- 3. 创建预约表 (appointment)
CREATE TABLE IF NOT EXISTS appointment (
    Appointment_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '预约ID',
    Patient_ID INT NOT NULL COMMENT '患者ID',
    Doctor_ID INT NOT NULL COMMENT '医生ID',
    Patient_Name VARCHAR(50) COMMENT '患者名字',
    Appointment_Time DATETIME COMMENT '预约时间',
    Appointment_Category VARCHAR(50) COMMENT '预约分类',
    Severity_Level VARCHAR(20) COMMENT '严重等级',
    Description TEXT COMMENT '简要描述',
    Appointment_Status VARCHAR(20) COMMENT '预约状态',
    Appointment_Time_Change_Record TEXT COMMENT '预约时间变化记录',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (Patient_ID) REFERENCES patient(Patient_ID) ON DELETE CASCADE,
    FOREIGN KEY (Doctor_ID) REFERENCES doctor(Doctor_ID) ON DELETE CASCADE,
    INDEX idx_patient (Patient_ID),
    INDEX idx_doctor (Doctor_ID),
    INDEX idx_appointment_time (Appointment_Time),
    INDEX idx_status (Appointment_Status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='预约信息表';

-- 插入测试医生数据
INSERT INTO doctor (Name, Hospital_Area, Title, Gender, Age, Phone_Number, Specialty, Available_Time)
VALUES 
    ('张医生', '眼科医院', '主任医师', '男', 45, '13800000001', '眼科', '2025-11-15, 09:00-12:00, 是'),
    ('李医生', '眼科医院', '副主任医师', '女', 38, '13800000002', '眼科', '2025-11-15, 14:00-17:00, 是'),
    ('王医生', '眼科医院', '主治医师', '男', 35, '13800000003', '眼科', '2025-11-16, 09:00-12:00, 是'),
    ('赵医生', '眼科医院', '主任医师', '女', 50, '13800000004', '眼科', '2025-11-16, 14:00-17:00, 是'),
    ('刘医生', '眼科医院', '副主任医师', '男', 42, '13800000005', '眼科', '2025-11-17, 09:00-12:00, 是');

-- 查看创建的表
SHOW TABLES;

-- 显示成功信息
SELECT '数据库初始化完成！' AS message;
SELECT CONCAT('创建了 ', COUNT(*), ' 位测试医生') AS doctors_info FROM doctor;


-- ========================================
-- 医疗数据库完整初始化脚本
-- 整合版本: V3 + 聊天历史 + 提醒功能 + 生物力学
-- 创建日期: 2025-11-20
-- 说明: 这是所有数据库初始化脚本的归并版本,包含:
--   1. V3核心表结构(患者、病例、医生、预约、处方等)
--   2. V3智能预约时间段管理系统
--   3. 聊天历史记录表
--   4. 提醒功能表
--   5. 生物力学检查表(已在V3中,此处增加示例数据)
-- ========================================

-- 创建数据库
CREATE DATABASE IF NOT EXISTS medical_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE medical_db;

-- 禁用外键检查
SET FOREIGN_KEY_CHECKS = 0;

-- ==================================================
-- 删除旧表(如果存在) - 完整清理
-- ==================================================

-- 提醒相关表
DROP TABLE IF EXISTS reminder_history;
DROP TABLE IF EXISTS reminder_config;
DROP TABLE IF EXISTS reminder;

-- 聊天相关表
DROP TABLE IF EXISTS chat_message;
DROP TABLE IF EXISTS chat_conversation;

-- V3时间段管理表
DROP TABLE IF EXISTS doctor_schedule_exceptions;
DROP TABLE IF EXISTS doctor_time_slots;
DROP TABLE IF EXISTS doctor_working_schedule;

-- 核心业务表
DROP TABLE IF EXISTS biomechanics_scan;
DROP TABLE IF EXISTS prescription_detail;
DROP TABLE IF EXISTS prescription;
DROP TABLE IF EXISTS appointment;
DROP TABLE IF EXISTS medical_record;
DROP TABLE IF EXISTS patient;
DROP TABLE IF EXISTS drugs;
DROP TABLE IF EXISTS doctor;

-- 启用外键检查
SET FOREIGN_KEY_CHECKS = 1;

-- ==================================================
-- 第一部分: 核心表 (Patient, Medical Record, Doctor)
-- ==================================================

-- 1. 用户表 (patient) - 存储用户基本信息(一个人)
CREATE TABLE patient (
    Patient_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '用户ID(唯一标识一个人)',
    Name VARCHAR(50) NOT NULL COMMENT '姓名',
    Gender VARCHAR(10) COMMENT '性别',
    Date_of_Birth DATE COMMENT '出生日期',
    Age INT COMMENT '年龄',
    Phone_Number VARCHAR(20) UNIQUE NOT NULL COMMENT '手机号(唯一)',
    Address VARCHAR(200) COMMENT '地址',
    Email VARCHAR(100) COMMENT '电子邮件',
    Emergency_Contact VARCHAR(50) COMMENT '紧急联系人',
    Emergency_Contact_Phone VARCHAR(20) COMMENT '紧急联系人电话',
    Insurance_Status VARCHAR(50) COMMENT '医保情况',
    Insurance_Card_Number VARCHAR(50) COMMENT '医保卡号',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_phone (Phone_Number),
    INDEX idx_name (Name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户基本信息表(一条记录代表一个人)';

-- 2. 病例表 (medical_record) - 存储每次就诊的病例记录
CREATE TABLE medical_record (
    Medical_Record_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '病例ID(唯一标识一次就诊)',
    Patient_ID INT NOT NULL COMMENT '用户ID(外键)',
    Visit_Card_Number VARCHAR(50) UNIQUE NOT NULL COMMENT '就诊卡号',
    Report_ID VARCHAR(50) DEFAULT NULL COMMENT '报告编号',
    Visit_Date DATE NOT NULL COMMENT '就诊日期',
    Visit_Time DATETIME DEFAULT NULL COMMENT '就诊时间(精确到时分)',
    Department VARCHAR(50) COMMENT '就诊科室',
    Chief_Complaint TEXT COMMENT '主诉',
    Present_Illness TEXT COMMENT '现病史',
    Medical_History TEXT COMMENT '既往病史',
    Allergy_History TEXT COMMENT '过敏史',
    Family_History TEXT COMMENT '家族病史',
    Medication_History TEXT COMMENT '用药史',
    Physical_Examination TEXT COMMENT '体格检查',
    Eye_Exam_Results TEXT COMMENT '眼部检查结果',
    Special_Exams TEXT DEFAULT NULL COMMENT '专项检查项目',
    Auxiliary_Exams TEXT DEFAULT NULL COMMENT '辅助检查项目',
    Diagnosis TEXT COMMENT '诊断',
    AI_Diagnosis TEXT DEFAULT NULL COMMENT 'AI自动诊断结果',
    Treatment_Plan TEXT COMMENT '治疗方案',
    Medication TEXT COMMENT '处方药物',
    Surgical_History TEXT COMMENT '手术历史',
    Hospitalization_Info TEXT COMMENT '住院信息',
    Follow_Up_Date DATE COMMENT '复诊日期',
    Physician_Name VARCHAR(50) COMMENT '主治医生姓名',
    Doctor_Signature VARCHAR(100) DEFAULT NULL COMMENT '主诊医生签名',
    Print_Time TIMESTAMP NULL DEFAULT NULL COMMENT '病例单打印时间',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (Patient_ID) REFERENCES patient(Patient_ID) ON DELETE CASCADE,
    INDEX idx_patient (Patient_ID),
    INDEX idx_visit_date (Visit_Date),
    INDEX idx_visit_card (Visit_Card_Number),
    INDEX idx_report_id (Report_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='病例记录表(一条记录代表一次就诊)';

-- 3. 医生表 (doctor) - V3版本
CREATE TABLE doctor (
    Doctor_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '医生ID',
    Name VARCHAR(50) NOT NULL COMMENT '姓名',
    Hospital_Area VARCHAR(100) COMMENT '院区',
    Title VARCHAR(50) COMMENT '职称',
    Gender VARCHAR(10) COMMENT '性别',
    Age INT COMMENT '年龄',
    Phone_Number VARCHAR(20) COMMENT '手机号',
    Specialty VARCHAR(100) COMMENT '主治领域',
    -- V3新增字段
    default_slot_duration_minutes INT DEFAULT 60 COMMENT '默认时间段时长(分钟)',
    default_max_patients_per_slot INT DEFAULT 5 COMMENT '默认每时段最大接诊人数',
    booking_window_days INT DEFAULT 3 COMMENT '预约开放天数(今天起往后几天)',
    is_active BOOLEAN DEFAULT TRUE COMMENT '医生是否在职',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_specialty (Specialty),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='医生信息表(V3版本)';

-- ==================================================
-- 第二部分: V3预约时间段管理系统
-- ==================================================

-- 4. 医生每周工作时间模板 (doctor_working_schedule)
CREATE TABLE doctor_working_schedule (
    Schedule_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '排班ID',
    Doctor_ID INT NOT NULL COMMENT '医生ID',
    Day_of_Week TINYINT NOT NULL COMMENT '星期几(0=周日,1=周一,...,6=周六)',
    Shift_Start_Time TIME NOT NULL COMMENT '班次开始时间',
    Shift_End_Time TIME NOT NULL COMMENT '班次结束时间',
    Is_Active BOOLEAN DEFAULT TRUE COMMENT '是否启用此排班',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (Doctor_ID) REFERENCES doctor(Doctor_ID) ON DELETE CASCADE,
    UNIQUE KEY unique_doctor_day_shift (Doctor_ID, Day_of_Week, Shift_Start_Time),
    INDEX idx_doctor (Doctor_ID),
    INDEX idx_day_of_week (Day_of_Week),
    INDEX idx_is_active (Is_Active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='医生每周工作时间模板';

-- 5. 医生具体时间段 (doctor_time_slots)
CREATE TABLE doctor_time_slots (
    Slot_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '时间段ID',
    Doctor_ID INT NOT NULL COMMENT '医生ID',
    Slot_Date DATE NOT NULL COMMENT '时间段日期',
    Slot_Start_Time TIME NOT NULL COMMENT '时间段开始时间',
    Slot_End_Time TIME NOT NULL COMMENT '时间段结束时间',
    Max_Capacity INT NOT NULL DEFAULT 5 COMMENT '最大接诊人数',
    Current_Bookings INT NOT NULL DEFAULT 0 COMMENT '当前已预约人数',
    Is_Available BOOLEAN DEFAULT TRUE COMMENT '是否可预约',
    Slot_Type VARCHAR(20) DEFAULT 'normal' COMMENT '时间段类型(normal/extra/special)',
    Notes TEXT COMMENT '备注',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (Doctor_ID) REFERENCES doctor(Doctor_ID) ON DELETE CASCADE,
    UNIQUE KEY unique_doctor_slot_time (Doctor_ID, Slot_Date, Slot_Start_Time),
    INDEX idx_doctor_date (Doctor_ID, Slot_Date),
    INDEX idx_slot_date (Slot_Date),
    INDEX idx_is_available (Is_Available),
    CONSTRAINT chk_capacity CHECK (Current_Bookings <= Max_Capacity),
    CONSTRAINT chk_positive_capacity CHECK (Max_Capacity > 0),
    CONSTRAINT chk_non_negative_bookings CHECK (Current_Bookings >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='医生具体时间段(自动生成的可预约单位)';

-- 6. 医生排班例外情况 (doctor_schedule_exceptions)
CREATE TABLE doctor_schedule_exceptions (
    Exception_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '例外ID',
    Doctor_ID INT NOT NULL COMMENT '医生ID',
    Exception_Date DATE NOT NULL COMMENT '例外日期',
    Exception_Type VARCHAR(20) NOT NULL COMMENT '例外类型(请假/节假日/临时调整)',
    Start_Time TIME COMMENT '开始时间(如果是部分时间调整)',
    End_Time TIME COMMENT '结束时间(如果是部分时间调整)',
    Is_Full_Day BOOLEAN DEFAULT TRUE COMMENT '是否全天',
    Reason TEXT COMMENT '原因说明',
    Replacement_Schedule TEXT COMMENT '替代安排(如有)',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (Doctor_ID) REFERENCES doctor(Doctor_ID) ON DELETE CASCADE,
    INDEX idx_doctor_date (Doctor_ID, Exception_Date),
    INDEX idx_exception_date (Exception_Date),
    INDEX idx_exception_type (Exception_Type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='医生排班例外情况(请假、节假日等)';

-- ==================================================
-- 第三部分: 预约表 (V3版本)
-- ==================================================

-- 7. 预约表 (appointment)
CREATE TABLE appointment (
    Appointment_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '预约ID',
    Medical_Record_ID INT NOT NULL COMMENT '病例ID(外键)',
    Patient_ID INT NOT NULL COMMENT '用户ID(冗余字段,便于查询)',
    Doctor_ID INT NOT NULL COMMENT '医生ID',
    Time_Slot_ID INT COMMENT '时间段ID(V3新增,关联到doctor_time_slots)',
    Patient_Name VARCHAR(50) COMMENT '患者姓名(冗余字段)',
    Appointment_Time DATETIME COMMENT '预约时间',
    Appointment_Category VARCHAR(50) COMMENT '预约分类(普通/紧急)',
    Severity_Level VARCHAR(20) COMMENT '严重等级',
    Description TEXT COMMENT '简要描述',
    Appointment_Status VARCHAR(20) DEFAULT 'booked' COMMENT '预约状态(booked/completed/cancelled)',
    Appointment_Time_Change_Record TEXT COMMENT '预约时间变化记录',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (Medical_Record_ID) REFERENCES medical_record(Medical_Record_ID) ON DELETE CASCADE,
    FOREIGN KEY (Patient_ID) REFERENCES patient(Patient_ID) ON DELETE CASCADE,
    FOREIGN KEY (Doctor_ID) REFERENCES doctor(Doctor_ID) ON DELETE CASCADE,
    FOREIGN KEY (Time_Slot_ID) REFERENCES doctor_time_slots(Slot_ID) ON DELETE SET NULL,
    UNIQUE KEY unique_patient_appointment_time (Patient_ID, Appointment_Time),
    INDEX idx_medical_record (Medical_Record_ID),
    INDEX idx_patient (Patient_ID),
    INDEX idx_doctor (Doctor_ID),
    INDEX idx_appointment_time (Appointment_Time),
    INDEX idx_status (Appointment_Status),
    INDEX idx_time_slot (Time_Slot_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='预约信息表(V3版本)';

-- ==================================================
-- 第四部分: 药物和处方表
-- ==================================================

-- 8. 药物表 (drugs)
CREATE TABLE drugs (
    drug_id VARCHAR(20) PRIMARY KEY COMMENT '药物编号',
    drug_name VARCHAR(255) NOT NULL COMMENT '药物名称',
    drug_category VARCHAR(100) COMMENT '药物类别',
    drug_specification VARCHAR(100) COMMENT '药物规格',
    drug_dosage_form VARCHAR(50) COMMENT '剂型',
    manufacturer VARCHAR(255) COMMENT '生产厂家',
    batch_number VARCHAR(50) COMMENT '批号',
    expiry_date DATE COMMENT '有效期',
    price DECIMAL(10, 2) COMMENT '价格',
    stock_quantity INT DEFAULT 0 COMMENT '库存量',
    is_prescription_drug BOOLEAN DEFAULT TRUE COMMENT '是否处方药',
    drug_status ENUM('active', 'inactive', 'discontinued') DEFAULT 'active' COMMENT '药物状态',
    warning_info TEXT COMMENT '警示信息',
    drug_description TEXT COMMENT '药物描述',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    insurance_category VARCHAR(100) COMMENT '医保类别',
    INDEX idx_drug_name (drug_name),
    INDEX idx_drug_category (drug_category),
    INDEX idx_drug_status (drug_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='药物信息表';

-- 9. 处方表 (prescription)
CREATE TABLE prescription (
    Prescription_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '处方ID',
    Patient_ID INT NOT NULL COMMENT '患者ID',
    Doctor_ID INT NOT NULL COMMENT '医生ID',
    Medical_Record_ID INT NOT NULL COMMENT '病例ID',
    Prescription_Number VARCHAR(50) UNIQUE NOT NULL COMMENT '处方编号',
    Prescription_Date DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '开方日期',
    Prescription_Type VARCHAR(20) COMMENT '处方类型(普通/急诊/儿科等)',
    Diagnosis_Description TEXT COMMENT '诊断说明',
    Usage_Instruction TEXT COMMENT '用药说明',
    Prescription_Status ENUM('pending', 'approved', 'dispensed', 'completed', 'cancelled') DEFAULT 'pending' COMMENT '处方状态',
    Total_Amount DECIMAL(10, 2) DEFAULT 0.00 COMMENT '处方总金额',
    Notes TEXT COMMENT '备注',
    Prescriber_Name VARCHAR(50) COMMENT '开方医生姓名',
    Prescriber_Signature VARCHAR(100) COMMENT '医生签名',
    Pharmacist_Name VARCHAR(50) COMMENT '配药药师姓名',
    Pharmacist_Signature VARCHAR(100) COMMENT '药师签名',
    Dispensed_Date DATETIME COMMENT '配药日期',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (Patient_ID) REFERENCES patient(Patient_ID) ON DELETE CASCADE,
    FOREIGN KEY (Doctor_ID) REFERENCES doctor(Doctor_ID) ON DELETE CASCADE,
    FOREIGN KEY (Medical_Record_ID) REFERENCES medical_record(Medical_Record_ID) ON DELETE CASCADE,
    INDEX idx_patient (Patient_ID),
    INDEX idx_doctor (Doctor_ID),
    INDEX idx_medical_record (Medical_Record_ID),
    INDEX idx_prescription_date (Prescription_Date),
    INDEX idx_status (Prescription_Status),
    INDEX idx_prescription_number (Prescription_Number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='处方主表';

-- 10. 处方详情表 (prescription_detail)
CREATE TABLE prescription_detail (
    Detail_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '详情ID',
    Prescription_ID INT NOT NULL COMMENT '处方ID',
    Drug_ID VARCHAR(20) NOT NULL COMMENT '药物ID',
    Drug_Name VARCHAR(255) COMMENT '药物名称(冗余字段)',
    Drug_Specification VARCHAR(100) COMMENT '药物规格(冗余字段)',
    Quantity INT NOT NULL DEFAULT 1 COMMENT '数量',
    Unit VARCHAR(20) DEFAULT 'box' COMMENT '单位',
    Dosage VARCHAR(100) COMMENT '用法用量',
    Frequency VARCHAR(50) COMMENT '用药频率(如:一日三次)',
    Duration VARCHAR(50) COMMENT '用药疗程(如:7天)',
    Administration_Route VARCHAR(50) COMMENT '给药途径(如:口服/外用/滴眼等)',
    Unit_Price DECIMAL(10, 2) COMMENT '单价',
    Subtotal DECIMAL(10, 2) COMMENT '小计金额',
    Special_Instructions TEXT COMMENT '特殊说明',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (Prescription_ID) REFERENCES prescription(Prescription_ID) ON DELETE CASCADE,
    FOREIGN KEY (Drug_ID) REFERENCES drugs(drug_id) ON DELETE RESTRICT,
    INDEX idx_prescription (Prescription_ID),
    INDEX idx_drug (Drug_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='处方详情表';

-- ==================================================
-- 第五部分: 生物力学检查表
-- ==================================================

-- 11. 生物力学检查表 (biomechanics_scan)
CREATE TABLE biomechanics_scan (
    Scan_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '扫描ID(唯一标识一次检查)',
    Patient_ID INT NOT NULL COMMENT '患者ID(外键)',
    Medical_Record_ID INT DEFAULT NULL COMMENT '关联病例ID(可选)',
    Patient_Name VARCHAR(50) COMMENT '患者姓名(冗余字段,便于查询)',
    Gender VARCHAR(10) COMMENT '性别(冗余字段)',
    Birth_Date DATE COMMENT '出生日期',
    Age INT COMMENT '年龄',
    Scan_Date DATE NOT NULL COMMENT '扫描日期',
    Scan_Time DATETIME DEFAULT NULL COMMENT '扫描时间(精确到时分)',
    Operator VARCHAR(50) NOT NULL COMMENT '操作员/检查医生',
    AXL_R DECIMAL(5,2) COMMENT '右眼眼轴长度 (mm)',
    AXL_L DECIMAL(5,2) COMMENT '左眼眼轴长度 (mm)',
    CCT_R DECIMAL(5,1) COMMENT '右眼中央角膜厚度 (μm)',
    CCT_L DECIMAL(5,1) COMMENT '左眼中央角膜厚度 (μm)',
    ACD_R DECIMAL(4,2) COMMENT '右眼前房深度 (mm)',
    ACD_L DECIMAL(4,2) COMMENT '左眼前房深度 (mm)',
    LT_R DECIMAL(4,2) COMMENT '右眼晶状体厚度 (mm)',
    LT_L DECIMAL(4,2) COMMENT '左眼晶状体厚度 (mm)',
    VT_R DECIMAL(5,2) COMMENT '右眼玻璃体深度 (mm)',
    VT_L DECIMAL(5,2) COMMENT '左眼玻璃体深度 (mm)',
    K1_D_R DECIMAL(5,2) COMMENT '右眼K1屈光力 (D)',
    K1_mm_R DECIMAL(4,2) COMMENT '右眼K1曲率半径 (mm)',
    K1_Axis_R INT COMMENT '右眼K1轴位 (度)',
    K1_D_L DECIMAL(5,2) COMMENT '左眼K1屈光力 (D)',
    K1_mm_L DECIMAL(4,2) COMMENT '左眼K1曲率半径 (mm)',
    K1_Axis_L INT COMMENT '左眼K1轴位 (度)',
    K2_D_R DECIMAL(5,2) COMMENT '右眼K2屈光力 (D)',
    K2_mm_R DECIMAL(4,2) COMMENT '右眼K2曲率半径 (mm)',
    K2_Axis_R INT COMMENT '右眼K2轴位 (度)',
    K2_D_L DECIMAL(5,2) COMMENT '左眼K2屈光力 (D)',
    K2_mm_L DECIMAL(4,2) COMMENT '左眼K2曲率半径 (mm)',
    K2_Axis_L INT COMMENT '左眼K2轴位 (度)',
    Astigmatism_R DECIMAL(4,2) COMMENT '右眼散光度数 (D)',
    Astigmatism_L DECIMAL(4,2) COMMENT '左眼散光度数 (D)',
    WTW_R DECIMAL(4,2) COMMENT '右眼角膜直径 (mm)',
    WTW_L DECIMAL(4,2) COMMENT '左眼角膜直径 (mm)',
    Pupil_Diameter_R DECIMAL(4,2) COMMENT '右眼瞳孔直径 (mm)',
    Pupil_Diameter_L DECIMAL(4,2) COMMENT '左眼瞳孔直径 (mm)',
    TR_R DECIMAL(4,2) COMMENT '右眼地形图参数',
    TR_L DECIMAL(4,2) COMMENT '左眼地形图参数',
    Ac_T1 DECIMAL(5,1), Ac_T2 DECIMAL(5,1), Ac_T3 DECIMAL(5,1), Ac_T4 DECIMAL(5,1),
    Ac_T5 DECIMAL(5,1), Ac_T6 DECIMAL(5,1), Ac_T7 DECIMAL(5,1), Ac_T8 DECIMAL(5,1),
    P_T1 DECIMAL(5,2), P_T2 DECIMAL(5,2), P_T3 DECIMAL(5,2), P_T4 DECIMAL(5,2),
    P_T5 DECIMAL(5,2), P_T6 DECIMAL(5,2), P_T7 DECIMAL(5,2), P_T8 DECIMAL(5,2),
    I1_T1 DECIMAL(6,2), I1_T2 DECIMAL(6,2), I1_T3 DECIMAL(6,2), I1_T4 DECIMAL(6,2),
    I1_T5 DECIMAL(6,2), I1_T6 DECIMAL(6,2), I1_T7 DECIMAL(6,2), I1_T8 DECIMAL(6,2),
    I2_T1 DECIMAL(6,2), I2_T2 DECIMAL(6,2), I2_T3 DECIMAL(6,2), I2_T4 DECIMAL(6,2),
    I2_T5 DECIMAL(6,2), I2_T6 DECIMAL(6,2), I2_T7 DECIMAL(6,2), I2_T8 DECIMAL(6,2),
    I3_T1 DECIMAL(6,2), I3_T2 DECIMAL(6,2), I3_T3 DECIMAL(6,2), I3_T4 DECIMAL(6,2),
    I3_T5 DECIMAL(6,2), I3_T6 DECIMAL(6,2), I3_T7 DECIMAL(6,2), I3_T8 DECIMAL(6,2),
    I4_T1 DECIMAL(6,2), I4_T2 DECIMAL(6,2), I4_T3 DECIMAL(6,2), I4_T4 DECIMAL(6,2),
    I4_T5 DECIMAL(6,2), I4_T6 DECIMAL(6,2), I4_T7 DECIMAL(6,2), I4_T8 DECIMAL(6,2),
    I5_T1 DECIMAL(6,2), I5_T2 DECIMAL(6,2), I5_T3 DECIMAL(6,2), I5_T4 DECIMAL(6,2),
    I5_T5 DECIMAL(6,2), I5_T6 DECIMAL(6,2), I5_T7 DECIMAL(6,2), I5_T8 DECIMAL(6,2),
    R1_T1 DECIMAL(6,2), R1_T2 DECIMAL(6,2), R1_T3 DECIMAL(6,2), R1_T4 DECIMAL(6,2),
    R1_T5 DECIMAL(6,2), R1_T6 DECIMAL(6,2), R1_T7 DECIMAL(6,2), R1_T8 DECIMAL(6,2),
    R2_T1 DECIMAL(6,2), R2_T2 DECIMAL(6,2), R2_T3 DECIMAL(6,2), R2_T4 DECIMAL(6,2),
    R2_T5 DECIMAL(6,2), R2_T6 DECIMAL(6,2), R2_T7 DECIMAL(6,2), R2_T8 DECIMAL(6,2),
    R3_T1 DECIMAL(6,2), R3_T2 DECIMAL(6,2), R3_T3 DECIMAL(6,2), R3_T4 DECIMAL(6,2),
    R3_T5 DECIMAL(6,2), R3_T6 DECIMAL(6,2), R3_T7 DECIMAL(6,2), R3_T8 DECIMAL(6,2),
    R4_T1 DECIMAL(6,2), R4_T2 DECIMAL(6,2), R4_T3 DECIMAL(6,2), R4_T4 DECIMAL(6,2),
    R4_T5 DECIMAL(6,2), R4_T6 DECIMAL(6,2), R4_T7 DECIMAL(6,2), R4_T8 DECIMAL(6,2),
    R5_T1 DECIMAL(6,2), R5_T2 DECIMAL(6,2), R5_T3 DECIMAL(6,2), R5_T4 DECIMAL(6,2),
    R5_T5 DECIMAL(6,2), R5_T6 DECIMAL(6,2), R5_T7 DECIMAL(6,2), R5_T8 DECIMAL(6,2),
    Notes TEXT COMMENT '备注说明',
    Report_Status ENUM('pending', 'generated', 'archived') DEFAULT 'pending' COMMENT '报告状态',
    Report_Type VARCHAR(20) COMMENT '生成的报告类型(basic/detailed)',
    Report_Path VARCHAR(255) COMMENT '生成的报告文件路径',
    Reviewed_By VARCHAR(50) COMMENT '审核医生',
    Reviewed_At DATETIME COMMENT '审核时间',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (Patient_ID) REFERENCES patient(Patient_ID) ON DELETE CASCADE,
    FOREIGN KEY (Medical_Record_ID) REFERENCES medical_record(Medical_Record_ID) ON DELETE SET NULL,
    INDEX idx_patient (Patient_ID),
    INDEX idx_medical_record (Medical_Record_ID),
    INDEX idx_scan_date (Scan_Date),
    INDEX idx_operator (Operator),
    INDEX idx_report_status (Report_Status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='眼科生物力学检查数据表';

-- ==================================================
-- 第六部分: 聊天历史记录表
-- ==================================================

-- 12. 聊天对话主表 (chat_conversation)
CREATE TABLE chat_conversation (
    Chat_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '对话ID(唯一标识一个对话会话)',
    User_Type ENUM('patient', 'doctor') NOT NULL COMMENT '用户类型(patient=患者,doctor=医生)',
    Patient_ID INT DEFAULT NULL COMMENT '患者ID(当User_Type=patient时必填)',
    Doctor_ID INT DEFAULT NULL COMMENT '医生ID(当User_Type=doctor时必填)',
    Title VARCHAR(255) DEFAULT NULL COMMENT '对话标题(可选)',
    Conversation_Type VARCHAR(50) DEFAULT 'general' COMMENT '对话类型(general/consultation/appointment/report等)',
    AI_Agent VARCHAR(100) DEFAULT NULL COMMENT '处理此对话的AI智能体(agent_1/agent_2/agent_3等)',
    Summary TEXT DEFAULT NULL COMMENT '对话摘要(可选)',
    Total_Messages INT DEFAULT 0 COMMENT '消息总数',
    Status ENUM('active', 'archived', 'closed') DEFAULT 'active' COMMENT '对话状态',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
    FOREIGN KEY (Patient_ID) REFERENCES patient(Patient_ID) ON DELETE CASCADE,
    FOREIGN KEY (Doctor_ID) REFERENCES doctor(Doctor_ID) ON DELETE CASCADE,
    INDEX idx_patient (Patient_ID),
    INDEX idx_doctor (Doctor_ID),
    INDEX idx_user_type (User_Type),
    INDEX idx_created_at (Created_At),
    INDEX idx_status (Status),
    INDEX idx_conversation_type (Conversation_Type),
    CHECK (
        (User_Type = 'patient' AND Patient_ID IS NOT NULL AND Doctor_ID IS NULL) OR
        (User_Type = 'doctor' AND Doctor_ID IS NOT NULL AND Patient_ID IS NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='聊天对话主表(支持患者和医生用户)';

-- 13. 聊天消息详情表 (chat_message)
CREATE TABLE chat_message (
    Message_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '消息ID(唯一标识)',
    Chat_ID INT NOT NULL COMMENT '对话ID(外键)',
    Message_Order INT NOT NULL COMMENT '消息序号(会话内的顺序号,从1开始)',
    Message_Content LONGTEXT NOT NULL COMMENT '消息内容',
    Message_Type ENUM('user', 'ai') NOT NULL COMMENT '消息类型(user=用户消息,ai=AI消息)',
    Sender_Info VARCHAR(255) DEFAULT NULL COMMENT '发送者信息(用户名/AI代理名称)',
    Context TEXT DEFAULT NULL COMMENT '消息上下文(可存储JSON格式)',
    Tokens_Used INT DEFAULT NULL COMMENT '此消息消耗的token数',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '消息创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '消息修改时间',
    FOREIGN KEY (Chat_ID) REFERENCES chat_conversation(Chat_ID) ON DELETE CASCADE,
    INDEX idx_chat (Chat_ID),
    INDEX idx_message_type (Message_Type),
    INDEX idx_created_at (Created_At),
    UNIQUE KEY unique_chat_order (Chat_ID, Message_Order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='聊天消息详情表(一条记录代表一条消息)';

-- ==================================================
-- 第七部分: 提醒功能表
-- ==================================================

-- 14. 提醒记录表 (reminder)
CREATE TABLE reminder (
    Reminder_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '提醒ID',
    Patient_ID INT NOT NULL COMMENT '患者ID',
    Medical_Record_ID INT DEFAULT NULL COMMENT '关联病例ID(可选)',
    Appointment_ID INT DEFAULT NULL COMMENT '关联预约ID(可选)',
    Prescription_ID INT DEFAULT NULL COMMENT '关联处方ID(可选)',
    Reminder_Type ENUM('follow_up', 'appointment', 'medication', 'checkup', 'custom') NOT NULL COMMENT '提醒类型',
    Reminder_Title VARCHAR(200) NOT NULL COMMENT '提醒标题',
    Reminder_Content TEXT NOT NULL COMMENT '提醒内容',
    Scheduled_Time DATETIME NOT NULL COMMENT '计划提醒时间',
    Advance_Days INT DEFAULT 1 COMMENT '提前提醒天数',
    Status ENUM('pending', 'sent', 'completed', 'cancelled', 'expired') DEFAULT 'pending' COMMENT '提醒状态',
    Priority ENUM('low', 'normal', 'high', 'urgent') DEFAULT 'normal' COMMENT '优先级',
    Sent_Time DATETIME DEFAULT NULL COMMENT '实际发送时间',
    Completed_Time DATETIME DEFAULT NULL COMMENT '完成时间(用户确认)',
    Cancelled_Time DATETIME DEFAULT NULL COMMENT '取消时间',
    Repeat_Type ENUM('once', 'daily', 'weekly', 'monthly', 'custom') DEFAULT 'once' COMMENT '重复类型',
    Repeat_Count INT DEFAULT 0 COMMENT '已重复次数',
    Max_Repeat_Count INT DEFAULT 1 COMMENT '最大重复次数',
    Notification_Method VARCHAR(100) DEFAULT 'system' COMMENT '通知方式',
    Created_By VARCHAR(50) DEFAULT 'system' COMMENT '创建者',
    Notes TEXT COMMENT '备注信息',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (Patient_ID) REFERENCES patient(Patient_ID) ON DELETE CASCADE,
    FOREIGN KEY (Medical_Record_ID) REFERENCES medical_record(Medical_Record_ID) ON DELETE SET NULL,
    FOREIGN KEY (Appointment_ID) REFERENCES appointment(Appointment_ID) ON DELETE SET NULL,
    FOREIGN KEY (Prescription_ID) REFERENCES prescription(Prescription_ID) ON DELETE SET NULL,
    INDEX idx_patient (Patient_ID),
    INDEX idx_scheduled_time (Scheduled_Time),
    INDEX idx_status (Status),
    INDEX idx_type (Reminder_Type),
    INDEX idx_priority (Priority)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='提醒记录表';

-- 15. 提醒历史表 (reminder_history)
CREATE TABLE reminder_history (
    History_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '历史记录ID',
    Reminder_ID INT NOT NULL COMMENT '提醒ID',
    Action_Type ENUM('created', 'sent', 'read', 'completed', 'cancelled', 'rescheduled') NOT NULL COMMENT '操作类型',
    Action_Time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
    Action_By VARCHAR(50) COMMENT '操作人',
    Action_Details TEXT COMMENT '操作详情',
    FOREIGN KEY (Reminder_ID) REFERENCES reminder(Reminder_ID) ON DELETE CASCADE,
    INDEX idx_reminder (Reminder_ID),
    INDEX idx_action_time (Action_Time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='提醒历史记录表';

-- 16. 提醒配置表 (reminder_config)
CREATE TABLE reminder_config (
    Config_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '配置ID',
    Patient_ID INT NOT NULL COMMENT '患者ID',
    Enable_Follow_Up BOOLEAN DEFAULT TRUE COMMENT '启用复诊提醒',
    Enable_Appointment BOOLEAN DEFAULT TRUE COMMENT '启用预约提醒',
    Enable_Medication BOOLEAN DEFAULT TRUE COMMENT '启用用药提醒',
    Default_Advance_Days INT DEFAULT 1 COMMENT '默认提前天数',
    Preferred_Notification_Method VARCHAR(100) DEFAULT 'system' COMMENT '偏好通知方式',
    Quiet_Hours_Start TIME DEFAULT '22:00:00' COMMENT '免打扰开始时间',
    Quiet_Hours_End TIME DEFAULT '08:00:00' COMMENT '免打扰结束时间',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (Patient_ID) REFERENCES patient(Patient_ID) ON DELETE CASCADE,
    UNIQUE KEY unique_patient (Patient_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='提醒配置表';

-- ==================================================
-- 第八部分: 触发器(自动管理预约容量和提醒配置)
-- ==================================================

DELIMITER $$

-- 触发器1: 创建预约时增加 current_bookings
CREATE TRIGGER trg_appointment_insert
AFTER INSERT ON appointment
FOR EACH ROW
BEGIN
    IF NEW.Time_Slot_ID IS NOT NULL AND NEW.Appointment_Status IN ('已预约', '已确认') THEN
        UPDATE doctor_time_slots
        SET Current_Bookings = Current_Bookings + 1,
            Updated_At = CURRENT_TIMESTAMP
        WHERE Slot_ID = NEW.Time_Slot_ID;
    END IF;
END$$

-- 触发器2: 取消预约时减少 current_bookings
CREATE TRIGGER trg_appointment_update
AFTER UPDATE ON appointment
FOR EACH ROW
BEGIN
    -- 预约被取消
    IF OLD.Appointment_Status IN ('已预约', '已确认')
       AND NEW.Appointment_Status IN ('已取消', '已完成', '未到')
       AND OLD.Time_Slot_ID IS NOT NULL THEN
        UPDATE doctor_time_slots
        SET Current_Bookings = Current_Bookings - 1,
            Updated_At = CURRENT_TIMESTAMP
        WHERE Slot_ID = OLD.Time_Slot_ID
          AND Current_Bookings > 0;
    END IF;

    -- 预约被重新激活
    IF OLD.Appointment_Status IN ('已取消', '未到')
       AND NEW.Appointment_Status IN ('已预约', '已确认')
       AND NEW.Time_Slot_ID IS NOT NULL THEN
        UPDATE doctor_time_slots
        SET Current_Bookings = Current_Bookings + 1,
            Updated_At = CURRENT_TIMESTAMP
        WHERE Slot_ID = NEW.Time_Slot_ID;
    END IF;

    -- 更换时间段
    IF OLD.Time_Slot_ID != NEW.Time_Slot_ID
       AND NEW.Appointment_Status IN ('已预约', '已确认') THEN
        IF OLD.Time_Slot_ID IS NOT NULL THEN
            UPDATE doctor_time_slots
            SET Current_Bookings = Current_Bookings - 1,
                Updated_At = CURRENT_TIMESTAMP
            WHERE Slot_ID = OLD.Time_Slot_ID
              AND Current_Bookings > 0;
        END IF;
        IF NEW.Time_Slot_ID IS NOT NULL THEN
            UPDATE doctor_time_slots
            SET Current_Bookings = Current_Bookings + 1,
                Updated_At = CURRENT_TIMESTAMP
            WHERE Slot_ID = NEW.Time_Slot_ID;
        END IF;
    END IF;
END$$

-- 触发器3: 删除预约时减少 current_bookings
CREATE TRIGGER trg_appointment_delete
AFTER DELETE ON appointment
FOR EACH ROW
BEGIN
    IF OLD.Time_Slot_ID IS NOT NULL AND OLD.Appointment_Status IN ('已预约', '已确认') THEN
        UPDATE doctor_time_slots
        SET Current_Bookings = Current_Bookings - 1,
            Updated_At = CURRENT_TIMESTAMP
        WHERE Slot_ID = OLD.Time_Slot_ID
          AND Current_Bookings > 0;
    END IF;
END$$

-- 触发器4: 新患者自动创建提醒配置
CREATE TRIGGER after_patient_insert
AFTER INSERT ON patient
FOR EACH ROW
BEGIN
    INSERT INTO reminder_config (Patient_ID) VALUES (NEW.Patient_ID);
END$$

DELIMITER ;

-- ==================================================
-- 第九部分: 初始化测试数据
-- ==================================================

-- 插入测试医生
INSERT INTO doctor (Name, Hospital_Area, Title, Gender, Age, Phone_Number, Specialty,
                    default_slot_duration_minutes, default_max_patients_per_slot, booking_window_days, is_active,
                    Create_By, Version, Deleted)
VALUES
    ('张医生', '眼科医院', '主任医师', '男', 45, '13800000001', '眼科', 60, 5, 3, TRUE, 'system', 0, 0),
    ('李医生', '眼科医院', '副主任医师', '女', 38, '13800000002', '眼科', 60, 5, 3, TRUE, 'system', 0, 0),
    ('王医生', '眼科医院', '主治医师', '男', 35, '13800000003', '眼科', 60, 4, 3, TRUE, 'system', 0, 0),
    ('赵医生', '眼科医院', '主任医师', '女', 50, '13800000004', '眼科', 60, 6, 3, TRUE, 'system', 0, 0),
    ('刘医生', '眼科医院', '副主任医师', '男', 42, '13800000005', '眼科', 60, 5, 3, TRUE, 'system', 0, 0);

-- 插入医生工作时间模板
INSERT INTO doctor_working_schedule (Doctor_ID, Day_of_Week, Shift_Start_Time, Shift_End_Time, Is_Active)
VALUES
    -- 张医生: 周一到周五
    (1, 1, '09:00:00', '12:00:00', TRUE), (1, 1, '14:00:00', '17:00:00', TRUE),
    (1, 2, '09:00:00', '12:00:00', TRUE), (1, 2, '14:00:00', '17:00:00', TRUE),
    (1, 3, '09:00:00', '12:00:00', TRUE), (1, 3, '14:00:00', '17:00:00', TRUE),
    (1, 4, '09:00:00', '12:00:00', TRUE), (1, 4, '14:00:00', '17:00:00', TRUE),
    (1, 5, '09:00:00', '12:00:00', TRUE), (1, 5, '14:00:00', '17:00:00', TRUE),
    -- 李医生: 周一到周五全天
    (2, 1, '08:30:00', '17:30:00', TRUE), (2, 2, '08:30:00', '17:30:00', TRUE),
    (2, 3, '08:30:00', '17:30:00', TRUE), (2, 4, '08:30:00', '17:30:00', TRUE),
    (2, 5, '08:30:00', '17:30:00', TRUE),
    -- 王医生: 周二、周四、周六
    (3, 2, '09:00:00', '12:00:00', TRUE), (3, 2, '14:00:00', '17:00:00', TRUE),
    (3, 4, '09:00:00', '12:00:00', TRUE), (3, 4, '14:00:00', '17:00:00', TRUE),
    (3, 6, '09:00:00', '12:00:00', TRUE),
    -- 赵医生: 周一到周五下午,周六上午
    (4, 1, '14:00:00', '18:00:00', TRUE), (4, 2, '14:00:00', '18:00:00', TRUE),
    (4, 3, '14:00:00', '18:00:00', TRUE), (4, 4, '14:00:00', '18:00:00', TRUE),
    (4, 5, '14:00:00', '18:00:00', TRUE), (4, 6, '09:00:00', '12:00:00', TRUE),
    -- 刘医生: 周一、周三、周五
    (5, 1, '09:00:00', '17:00:00', TRUE), (5, 3, '09:00:00', '17:00:00', TRUE),
    (5, 5, '09:00:00', '17:00:00', TRUE);

-- 插入测试患者
INSERT INTO patient (Name, Gender, Age, Phone_Number, Address, Create_By, Version, Deleted)
VALUES
    ('张三', '男', 35, '13900000001', '北京市朝阳区', 'system', 0, 0),
    ('李四', '女', 28, '13900000002', '上海市浦东区', 'system', 0, 0),
    ('王五', '男', 45, '13900000003', '广州市天河区', 'system', 0, 0);

-- 插入测试病例
INSERT INTO medical_record (
    Patient_ID, Visit_Card_Number, Visit_Date, Department,
    Chief_Complaint, Diagnosis, Medical_History, Allergy_History
)
VALUES
    (1, '2025-000001', '2025-11-10', '眼科', '眼睛干涩', '干眼症', '无特殊病史', '无过敏'),
    (1, '2025-000002', '2025-11-15', '眼科', '视力模糊', '待诊断', '干眼症病史', '无过敏'),
    (2, '2025-000003', '2025-11-12', '眼科', '眼红眼痛', '结膜炎', '无', '青霉素过敏');

-- 插入示例药品数据
INSERT INTO drugs (
    drug_id, drug_name, drug_category, drug_specification, drug_dosage_form,
    manufacturer, batch_number, expiry_date, price, stock_quantity,
    is_prescription_drug, drug_status, warning_info, drug_description, insurance_category
)
VALUES
    ('EYD0001', '玻璃酸钠滴眼液', '润滑剂', '10ml:5mg', '滴眼液', '成都华西药业', 'EY20251101A', '2026-11-30', 38.50, 500, TRUE, '在售', '佩戴隐形眼镜前需取下', '用于干眼症及术后角膜润滑', '甲类医保'),
    ('EYD0002', '羟丙甲纤维素滴眼液', '润滑剂', '15ml:5mg', '滴眼液', '北京同仁药业', 'EY20251101B', '2027-01-15', 25.00, 620, FALSE, '在售', '开封后30日内使用完毕', '人工泪液替代品', '乙类医保'),
    ('EYD0003', '氟米龙滴眼液', '糖皮质激素', '5ml:5mg', '滴眼液', '参天制药', 'EY20251101C', '2026-09-01', 52.80, 320, TRUE, '在售', '青光眼患者慎用', '用于过敏性结膜炎', '甲类医保'),
    ('EYD0004', '托百士眼膏', '抗生素', '3.5g:0.3g', '眼膏', '爱尔康制药', 'EY20251101D', '2027-03-20', 46.00, 280, TRUE, '在售', '孕妇及哺乳期慎用', '治疗细菌性角膜结膜感染', '甲类医保'),
    ('EYD0005', '左氧氟沙星滴眼液', '抗生素', '5ml:15mg', '滴眼液', '丽珠集团', 'EY20251101E', '2026-08-10', 29.90, 710, TRUE, '在售', '对喹诺酮类过敏者禁用', '用于细菌性结膜炎、角膜炎', '乙类医保');

-- 插入测试处方
INSERT INTO prescription (
    Patient_ID, Doctor_ID, Medical_Record_ID, Prescription_Number,
    Prescription_Type, Diagnosis_Description, Usage_Instruction,
    Prescription_Status, Prescriber_Name, Total_Amount
)
VALUES
    (1, 1, 1, 'RX20251117001', '普通', '干眼症', '按时用药,注意用眼卫生', '已审核', '张医生', 102.00),
    (2, 2, 3, 'RX20251117002', '普通', '结膜炎', '按医嘱用药,避免用手揉眼', '已配药', '李医生', 167.80);

-- 插入处方详情
INSERT INTO prescription_detail (
    Prescription_ID, Drug_ID, Drug_Name, Drug_Specification,
    Quantity, Unit, Dosage, Frequency, Duration,
    Administration_Route, Unit_Price, Subtotal, Special_Instructions
)
VALUES
    (1, 'EYD0001', '玻璃酸钠滴眼液', '10ml:5mg', 2, '盒', '每次1-2滴', '每日4-6次', '2周', '滴眼', 38.50, 77.00, '佩戴隐形眼镜前需取下'),
    (1, 'EYD0002', '羟丙甲纤维素滴眼液', '15ml:5mg', 1, '盒', '每次1滴', '每日3-4次', '2周', '滴眼', 25.00, 25.00, '开封后30日内使用完毕'),
    (2, 'EYD0005', '左氧氟沙星滴眼液', '5ml:15mg', 2, '盒', '每次1-2滴', '每日4次', '7天', '滴眼', 29.90, 59.80, '对喹诺酮类过敏者禁用'),
    (2, 'EYD0004', '托百士眼膏', '3.5g:0.3g', 1, '支', '适量涂于眼睑', '每晚睡前1次', '7天', '外用', 46.00, 46.00, '孕妇及哺乳期慎用');

-- 为已有患者创建提醒配置
INSERT INTO reminder_config (Patient_ID)
SELECT Patient_ID FROM patient
ON DUPLICATE KEY UPDATE Updated_At = CURRENT_TIMESTAMP;

-- ==================================================
-- 初始化完成信息
-- ==================================================

SELECT '========================================' AS '';
SELECT '数据库初始化完成！' AS message;
SELECT '========================================' AS '';
SELECT '已创建的表:' AS '';
SELECT '核心表: patient, medical_record, doctor' AS tables_1;
SELECT '时间段管理: doctor_working_schedule, doctor_time_slots, doctor_schedule_exceptions' AS tables_2;
SELECT '预约处方: appointment, prescription, prescription_detail, drugs' AS tables_3;
SELECT '生物力学: biomechanics_scan' AS tables_4;
SELECT '聊天历史: chat_conversation, chat_message' AS tables_5;
SELECT '提醒功能: reminder, reminder_history, reminder_config' AS tables_6;
SELECT '========================================' AS '';

-- 统计信息
SELECT CONCAT('创建了 ', COUNT(*), ' 位医生') AS doctors_count FROM doctor;
SELECT CONCAT('配置了 ', COUNT(*), ' 条排班规则') AS schedules_count FROM doctor_working_schedule;
SELECT CONCAT('创建了 ', COUNT(*), ' 位患者') AS patients_count FROM patient;
SELECT CONCAT('创建了 ', COUNT(*), ' 条病例') AS records_count FROM medical_record;
SELECT CONCAT('录入了 ', COUNT(*), ' 种药品') AS drugs_count FROM drugs;
SELECT CONCAT('创建了 ', COUNT(*), ' 条处方') AS prescriptions_count FROM prescription;

SELECT '========================================' AS '';
SELECT '下一步: 运行 utils/schedule_generator.py 生成时间段' AS next_step;
SELECT '========================================' AS '';

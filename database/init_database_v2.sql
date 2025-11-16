-- 医疗数据库重构方案 V2
-- 修复日期：2025-11-16
-- 修复内容：将"用户"和"病例"分离，建立正确的三层关系

-- 创建数据库
CREATE DATABASE IF NOT EXISTS medical_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE medical_db;

-- 禁用外键检查
SET FOREIGN_KEY_CHECKS = 0;

-- 删除旧表（如果存在）
DROP TABLE IF EXISTS appointment;
DROP TABLE IF EXISTS medical_record;
DROP TABLE IF EXISTS patient;

-- 启用外键检查
SET FOREIGN_KEY_CHECKS = 1;

-- 1. 用户表 (patient) - 存储用户基本信息（一个人）
CREATE TABLE patient (
    Patient_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '用户ID（唯一标识一个人）',
    Name VARCHAR(50) NOT NULL COMMENT '姓名',
    Gender VARCHAR(10) COMMENT '性别',
    Date_of_Birth DATE COMMENT '出生日期',
    Age INT COMMENT '年龄',
    Phone_Number VARCHAR(20) UNIQUE NOT NULL COMMENT '手机号（唯一）',
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户基本信息表（一条记录代表一个人）';

-- 2. 病例表 (medical_record) - 存储每次就诊的病例记录
CREATE TABLE medical_record (
    Medical_Record_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '病例ID（唯一标识一次就诊）',
    Patient_ID INT NOT NULL COMMENT '用户ID（外键）',
    Visit_Card_Number VARCHAR(50) UNIQUE NOT NULL COMMENT '就诊卡号',
    Visit_Date DATE NOT NULL COMMENT '就诊日期',
    Department VARCHAR(50) COMMENT '就诊科室',
    Chief_Complaint TEXT COMMENT '主诉',
    Present_Illness TEXT COMMENT '现病史',
    Medical_History TEXT COMMENT '既往病史',
    Allergy_History TEXT COMMENT '过敏史',
    Family_History TEXT COMMENT '家族病史',
    Medication_History TEXT COMMENT '用药史',
    Physical_Examination TEXT COMMENT '体格检查',
    Eye_Exam_Results TEXT COMMENT '眼部检查结果',
    Diagnosis TEXT COMMENT '诊断',
    Treatment_Plan TEXT COMMENT '治疗方案',
    Medication TEXT COMMENT '处方药物',
    Surgical_History TEXT COMMENT '手术历史',
    Hospitalization_Info TEXT COMMENT '住院信息',
    Follow_Up_Date DATE COMMENT '复诊日期',
    Physician_Name VARCHAR(50) COMMENT '主治医生姓名',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (Patient_ID) REFERENCES patient(Patient_ID) ON DELETE CASCADE,
    INDEX idx_patient (Patient_ID),
    INDEX idx_visit_date (Visit_Date),
    INDEX idx_visit_card (Visit_Card_Number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='病例记录表（一条记录代表一次就诊）';

-- 3. 医生表 (doctor) - 保持不变
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

-- 4. 预约表 (appointment) - 关联到病例ID
CREATE TABLE appointment (
    Appointment_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '预约ID',
    Medical_Record_ID INT NOT NULL COMMENT '病例ID（外键）',
    Patient_ID INT NOT NULL COMMENT '用户ID（冗余字段，便于查询）',
    Doctor_ID INT NOT NULL COMMENT '医生ID',
    Patient_Name VARCHAR(50) COMMENT '患者姓名（冗余字段）',
    Appointment_Time DATETIME COMMENT '预约时间',
    Appointment_Category VARCHAR(50) COMMENT '预约分类（普通/紧急）',
    Severity_Level VARCHAR(20) COMMENT '严重等级',
    Description TEXT COMMENT '简要描述',
    Appointment_Status VARCHAR(20) DEFAULT '已预约' COMMENT '预约状态',
    Appointment_Time_Change_Record TEXT COMMENT '预约时间变化记录',
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (Medical_Record_ID) REFERENCES medical_record(Medical_Record_ID) ON DELETE CASCADE,
    FOREIGN KEY (Patient_ID) REFERENCES patient(Patient_ID) ON DELETE CASCADE,
    FOREIGN KEY (Doctor_ID) REFERENCES doctor(Doctor_ID) ON DELETE CASCADE,
    INDEX idx_medical_record (Medical_Record_ID),
    INDEX idx_patient (Patient_ID),
    INDEX idx_doctor (Doctor_ID),
    INDEX idx_appointment_time (Appointment_Time),
    INDEX idx_status (Appointment_Status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='预约信息表';

-- 插入测试医生数据
INSERT INTO doctor (Name, Hospital_Area, Title, Gender, Age, Phone_Number, Specialty, Available_Time)
VALUES 
    ('张医生', '眼科医院', '主任医师', '男', 45, '13800000001', '眼科', '2025-11-17, 09:00-12:00, 是'),
    ('李医生', '眼科医院', '副主任医师', '女', 38, '13800000002', '眼科', '2025-11-17, 14:00-17:00, 是'),
    ('王医生', '眼科医院', '主治医师', '男', 35, '13800000003', '眼科', '2025-11-18, 09:00-12:00, 是'),
    ('赵医生', '眼科医院', '主任医师', '女', 50, '13800000004', '眼科', '2025-11-18, 14:00-17:00, 是'),
    ('刘医生', '眼科医院', '副主任医师', '男', 42, '13800000005', '眼科', '2025-11-19, 09:00-12:00, 是');

-- 插入测试用户数据
INSERT INTO patient (Name, Gender, Age, Phone_Number, Address)
VALUES 
    ('张三', '男', 35, '13900000001', '北京市朝阳区'),
    ('李四', '女', 28, '13900000002', '上海市浦东区'),
    ('王五', '男', 45, '13900000003', '广州市天河区');

-- 插入测试病例数据
INSERT INTO medical_record (
    Patient_ID, Visit_Card_Number, Visit_Date, Department,
    Chief_Complaint, Diagnosis, Medical_History, Allergy_History
)
VALUES 
    (1, '2025-000001', '2025-11-10', '眼科', '眼睛干涩', '干眼症', '无特殊病史', '无过敏'),
    (1, '2025-000002', '2025-11-15', '眼科', '视力模糊', '待诊断', '干眼症病史', '无过敏'),
    (2, '2025-000003', '2025-11-12', '眼科', '眼红眼痛', '结膜炎', '无', '青霉素过敏');

-- 插入测试预约数据
INSERT INTO appointment (
    Medical_Record_ID, Patient_ID, Doctor_ID, Patient_Name,
    Appointment_Time, Appointment_Category, Severity_Level,
    Description, Appointment_Status
)
VALUES 
    (2, 1, 1, '张三', '2025-11-17 09:30:00', '普通', '中等', '视力模糊复查', '已确认'),
    (3, 2, 2, '李四', '2025-11-17 14:30:00', '紧急', '严重', '眼红眼痛', '已确认');

-- 查看创建的表
SHOW TABLES;

-- 显示成功信息
SELECT '数据库重构完成！' AS message;
SELECT '新架构：Patient(用户) → Medical_Record(病例) → Appointment(预约)' AS architecture;
SELECT CONCAT('创建了 ', COUNT(*), ' 位测试用户') AS users_info FROM patient;
SELECT CONCAT('创建了 ', COUNT(*), ' 条测试病例') AS records_info FROM medical_record;
SELECT CONCAT('创建了 ', COUNT(*), ' 个测试预约') AS appointments_info FROM appointment;
SELECT CONCAT('创建了 ', COUNT(*), ' 位测试医生') AS doctors_info FROM doctor;


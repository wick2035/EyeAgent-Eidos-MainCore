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
DROP TABLE IF EXISTS drugs;

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
    Report_ID VARCHAR(50) DEFAULT NULL COMMENT '报告编号',
    Visit_Date DATE NOT NULL COMMENT '就诊日期',
    Visit_Time DATETIME DEFAULT NULL COMMENT '就诊时间（精确到时分）',
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

-- 5. 药物表 (drugs) - 管理药品基础信息
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
    drug_status ENUM('在售', '停用', '下架') DEFAULT '在售' COMMENT '药物状态',
    warning_info TEXT COMMENT '警示信息',
    drug_description TEXT COMMENT '药物描述',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    insurance_category VARCHAR(100) COMMENT '医保类别',
    INDEX idx_drug_name (drug_name),
    INDEX idx_drug_category (drug_category),
    INDEX idx_drug_status (drug_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='药物信息表';

-- 6. 处方表 (prescription) - 处方主表
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
    Prescription_Status ENUM('待审核', '已审核', '已配药', '已完成', '已作废') DEFAULT '待审核' COMMENT '处方状态',
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

-- 7. 处方详情表 (prescription_detail) - 处方药物明细
CREATE TABLE prescription_detail (
    Detail_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '详情ID',
    Prescription_ID INT NOT NULL COMMENT '处方ID',
    Drug_ID VARCHAR(20) NOT NULL COMMENT '药物ID',
    Drug_Name VARCHAR(255) COMMENT '药物名称(冗余字段)',
    Drug_Specification VARCHAR(100) COMMENT '药物规格(冗余字段)',
    Quantity INT NOT NULL DEFAULT 1 COMMENT '数量',
    Unit VARCHAR(20) DEFAULT '盒' COMMENT '单位',
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

-- 插入示例药品数据（20 条眼科常用药）
INSERT INTO drugs (
    drug_id, drug_name, drug_category, drug_specification, drug_dosage_form,
    manufacturer, batch_number, expiry_date, price, stock_quantity,
    is_prescription_drug, drug_status, warning_info, drug_description,
    created_at, updated_at, insurance_category
)
VALUES
    ('EYD0001', '玻璃酸钠滴眼液', '润滑剂', '10ml:5mg', '滴眼液', '成都华西药业', 'EY20251101A', '2026-11-30', 38.50, 500, TRUE, '在售', '佩戴隐形眼镜前需取下', '用于干眼症及术后角膜润滑，缓解异物感', '2025-11-17 10:30:00', '2025-11-17 10:30:00', '甲类医保'),
    ('EYD0002', '羟丙甲纤维素滴眼液', '润滑剂', '15ml:5mg', '滴眼液', '北京同仁药业', 'EY20251101B', '2027-01-15', 25.00, 620, FALSE, '在售', '开封后30日内使用完毕', '人工泪液替代品，缓解干眼与眼疲劳', '2025-11-17 10:31:00', '2025-11-17 10:31:00', '乙类医保'),
    ('EYD0003', '氟米龙滴眼液', '糖皮质激素', '5ml:5mg', '滴眼液', '参天制药', 'EY20251101C', '2026-09-01', 52.80, 320, TRUE, '在售', '青光眼患者慎用，遵医嘱', '用于过敏性结膜炎及术后炎症控制', '2025-11-17 10:32:00', '2025-11-17 10:32:00', '甲类医保'),
    ('EYD0004', '托百士眼膏', '抗生素', '3.5g:0.3g', '眼膏', '爱尔康制药', 'EY20251101D', '2027-03-20', 46.00, 280, TRUE, '在售', '孕妇及哺乳期慎用', '妥布霉素眼膏，治疗细菌性角膜结膜感染', '2025-11-17 10:33:00', '2025-11-17 10:33:00', '甲类医保'),
    ('EYD0005', '左氧氟沙星滴眼液', '抗生素', '5ml:15mg', '滴眼液', '丽珠集团', 'EY20251101E', '2026-08-10', 29.90, 710, TRUE, '在售', '对喹诺酮类过敏者禁用', '用于细菌性结膜炎、角膜炎的治疗', '2025-11-17 10:34:00', '2025-11-17 10:34:00', '乙类医保'),
    ('EYD0006', '环孢素A滴眼液', '免疫调节剂', '5ml:0.05%', '滴眼液', '齐鲁制药', 'EY20251101F', '2027-05-05', 128.00, 180, TRUE, '在售', '使用前轻摇，避免污染滴嘴', '抑制炎症反应，改善中重度干眼', '2025-11-17 10:35:00', '2025-11-17 10:35:00', '甲类医保'),
    ('EYD0007', '盐酸奥洛他定滴眼液', '抗过敏', '5ml:5mg', '滴眼液', '日本参天制药', 'EY20251101G', '2026-10-18', 42.50, 410, TRUE, '在售', '避免接触隐形眼镜，至少间隔15分钟', '缓解季节性过敏性结膜炎瘙痒与红肿', '2025-11-17 10:36:00', '2025-11-17 10:36:00', '乙类医保'),
    ('EYD0008', '布林佐胺滴眼液', '降眼压药', '5ml:1%', '滴眼液', '爱尔康制药', 'EY20251101H', '2026-12-22', 165.00, 150, TRUE, '在售', '肾功能不全者慎用', '用于开角型青光眼或眼压过高', '2025-11-17 10:37:00', '2025-11-17 10:37:00', '甲类医保'),
    ('EYD0009', '溴莫尼定滴眼液', '降眼压药', '5ml:0.2%', '滴眼液', '美国艾尔健', 'EY20251101I', '2026-07-07', 158.00, 140, TRUE, '在售', '与单胺氧化酶抑制剂合用禁忌', '降低青光眼患者房水生成，控制眼压', '2025-11-17 10:38:00', '2025-11-17 10:38:00', '甲类医保'),
    ('EYD0010', '噻吗洛尔滴眼液', 'β受体阻滞剂', '5ml:5mg', '滴眼液', '上海信谊制药', 'EY20251101J', '2027-02-14', 33.00, 360, TRUE, '在售', '哮喘及房室传导阻滞患者禁用', '降低房水生成，控制青光眼眼压', '2025-11-17 10:39:00', '2025-11-17 10:39:00', '甲类医保'),
    ('EYD0011', '匹罗卡品滴眼液', '缩瞳剂', '10ml:10mg', '滴眼液', '湖北远大制药', 'EY20251101K', '2026-06-12', 18.80, 480, TRUE, '在售', '夜间驾驶者慎用，可能导致视物模糊', '用于闭角型青光眼急性控制及激光术后', '2025-11-17 10:40:00', '2025-11-17 10:40:00', '乙类医保'),
    ('EYD0012', '人工泪液Ⅱ号', '润滑剂', '15ml', '滴眼液', '深圳致君制药', 'EY20251101L', '2027-04-08', 22.00, 900, FALSE, '在售', '开封后冷藏，30日内用完', '多聚乙二醇与聚丙烯酸配伍，缓解眼干', '2025-11-17 10:41:00', '2025-11-17 10:41:00', '自费'),
    ('EYD0013', '阿托品滴眼液', '散瞳剂', '5ml:1%', '滴眼液', '武汉诺安德', 'EY20251101M', '2026-05-19', 45.00, 260, TRUE, '在售', '儿童误服可致中毒，务必妥善存放', '散瞳验光、葡萄膜炎及延缓近视进展', '2025-11-17 10:42:00', '2025-11-17 10:42:00', '甲类医保'),
    ('EYD0014', '妥布霉素地塞米松滴眼液', '复方抗炎', '5ml:5mg+1mg', '滴眼液', '爱丽眼科制药', 'EY20251101N', '2026-09-25', 62.00, 330, TRUE, '在售', '禁用于角膜上皮缺损患者', '联合抗菌与抗炎，适用于术后炎症', '2025-11-17 10:43:00', '2025-11-17 10:43:00', '甲类医保'),
    ('EYD0015', '聚乙烯醇滴眼液', '润滑剂', '15ml', '滴眼液', '山东方明药业', 'EY20251101P', '2027-06-16', 19.90, 760, FALSE, '在售', '含防腐剂，隐形眼镜前需摘除', '缓解电脑视觉综合征引起的干涩', '2025-11-17 10:44:00', '2025-11-17 10:44:00', '乙类医保'),
    ('EYD0016', '盐酸左卡巴斯汀滴眼液', '抗过敏', '5ml:5mg', '滴眼液', '法国赛诺菲', 'EY20251101Q', '2026-12-05', 54.00, 290, TRUE, '在售', '可引起短暂苦味，避免触及滴嘴', '快速缓解过敏性结膜炎瘙痒与流泪', '2025-11-17 10:45:00', '2025-11-17 10:45:00', '甲类医保'),
    ('EYD0017', '噻吗洛尔凝胶', 'β受体阻滞剂', '2.5g:2.5mg', '眼用凝胶', '华润双鹤', 'EY20251101R', '2026-11-11', 48.00, 210, TRUE, '在售', '夜间使用可能短暂视物模糊', '延长药物接触时间，提高降压效果', '2025-11-17 10:46:00', '2025-11-17 10:46:00', '甲类医保'),
    ('EYD0018', '聚六芒星玻璃酸钠眼膏', '润滑剂', '5g:5mg', '眼膏', '天津太平洋制药', 'EY20251101S', '2027-01-09', 36.50, 240, TRUE, '在售', '睡前使用，避免短期视力模糊影响', '夜间长效润滑保护角膜上皮', '2025-11-17 10:47:00', '2025-11-17 10:47:00', '乙类医保'),
    ('EYD0019', '氧氟沙星滴眼液', '抗生素', '5ml:15mg', '滴眼液', '扬子江药业', 'EY20251101T', '2026-08-28', 27.80, 640, TRUE, '在售', '对氟喹诺酮过敏者禁用', '覆盖广谱细菌感染，术前预防用药', '2025-11-17 10:48:00', '2025-11-17 10:48:00', '甲类医保'),
    ('EYD0020', '碘伏眼部清洁液', '消毒清洁', '120ml:1%', '洗剂', '江苏亚邦药业', 'EY20251101U', '2027-03-02', 31.00, 370, FALSE, '在售', '仅限外用，避免进入前房', '术前眼睑清洁及角膜接触镜护理', '2025-11-17 10:49:00', '2025-11-17 10:49:00', '自费');

-- 插入测试处方数据
INSERT INTO prescription (
    Patient_ID, Doctor_ID, Medical_Record_ID, Prescription_Number,
    Prescription_Type, Diagnosis_Description, Usage_Instruction,
    Prescription_Status, Prescriber_Name
)
VALUES 
    (1, 1, 1, 'RX20251117001', '普通', '干眼症', '按时用药，注意用眼卫生，避免长时间用眼', '已审核', '张医生'),
    (1, 1, 2, 'RX20251117003', '复诊', '干眼症复查', '继续治疗，注意休息', '待审核', '张医生'),
    (2, 2, 3, 'RX20251117002', '普通', '结膜炎', '按医嘱用药，避免用手揉眼，保持眼部清洁', '已配药', '李医生');

-- 插入测试处方详情数据
INSERT INTO prescription_detail (
    Prescription_ID, Drug_ID, Drug_Name, Drug_Specification,
    Quantity, Unit, Dosage, Frequency, Duration,
    Administration_Route, Unit_Price, Subtotal, Special_Instructions
)
VALUES 
    -- 处方1的药物（干眼症治疗）
    (1, 'EYD0001', '玻璃酸钠滴眼液', '10ml:5mg', 2, '盒', '每次1-2滴', '每日4-6次', '2周', '滴眼', 38.50, 77.00, '佩戴隐形眼镜前需取下'),
    (1, 'EYD0002', '羟丙甲纤维素滴眼液', '15ml:5mg', 1, '盒', '每次1滴', '每日3-4次', '2周', '滴眼', 25.00, 25.00, '开封后30日内使用完毕'),
    -- 处方2的药物（复诊）
    (2, 'EYD0006', '环孢素A滴眼液', '5ml:0.05%', 1, '盒', '每次1滴', '每日2次', '4周', '滴眼', 128.00, 128.00, '使用前轻摇，避免污染滴嘴'),
    -- 处方3的药物（结膜炎治疗）
    (3, 'EYD0005', '左氧氟沙星滴眼液', '5ml:15mg', 2, '盒', '每次1-2滴', '每日4次', '7天', '滴眼', 29.90, 59.80, '对喹诺酮类过敏者禁用'),
    (3, 'EYD0004', '托百士眼膏', '3.5g:0.3g', 1, '支', '适量涂于眼睑', '每晚睡前1次', '7天', '外用', 46.00, 46.00, '孕妇及哺乳期慎用'),
    (3, 'EYD0014', '妥布霉素地塞米松滴眼液', '5ml:5mg+1mg', 1, '盒', '每次1-2滴', '每日3-4次', '5天', '滴眼', 62.00, 62.00, '禁用于角膜上皮缺损患者');

-- 更新处方总金额
UPDATE prescription SET Total_Amount = 102.00 WHERE Prescription_ID = 1;
UPDATE prescription SET Total_Amount = 128.00 WHERE Prescription_ID = 2;
UPDATE prescription SET Total_Amount = 167.80 WHERE Prescription_ID = 3;

-- 查看创建的表
SHOW TABLES;

-- 显示成功信息
SELECT '数据库重构完成！' AS message;
SELECT '新架构：Patient(用户) → Medical_Record(病例) → Appointment(预约) + Prescription(处方)' AS architecture;
SELECT CONCAT('创建了 ', COUNT(*), ' 位测试用户') AS users_info FROM patient;
SELECT CONCAT('创建了 ', COUNT(*), ' 条测试病例') AS records_info FROM medical_record;
SELECT CONCAT('创建了 ', COUNT(*), ' 个测试预约') AS appointments_info FROM appointment;
SELECT CONCAT('创建了 ', COUNT(*), ' 位测试医生') AS doctors_info FROM doctor;
SELECT CONCAT('录入了 ', COUNT(*), ' 条示例药品') AS drugs_info FROM drugs;
SELECT CONCAT('创建了 ', COUNT(*), ' 条测试处方') AS prescriptions_info FROM prescription;
SELECT CONCAT('创建了 ', COUNT(*), ' 条处方详情') AS details_info FROM prescription_detail;


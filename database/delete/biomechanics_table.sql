-- 生物力学检查数据表
-- 用于存储眼科生物力学测量数据
-- 支持两种报告模板：基础测量报告和详细生物力学分析报告

USE medical_db;

-- 创建生物力学扫描表
CREATE TABLE IF NOT EXISTS biomechanics_scan (
    Scan_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '扫描ID（唯一标识一次检查）',
    Patient_ID INT NOT NULL COMMENT '患者ID（外键）',
    Medical_Record_ID INT DEFAULT NULL COMMENT '关联病例ID（可选）',

    -- 基本信息
    Patient_Name VARCHAR(50) COMMENT '患者姓名（冗余字段，便于查询）',
    Gender VARCHAR(10) COMMENT '性别（冗余字段）',
    Birth_Date DATE COMMENT '出生日期',
    Age INT COMMENT '年龄',
    Scan_Date DATE NOT NULL COMMENT '扫描日期',
    Scan_Time DATETIME DEFAULT NULL COMMENT '扫描时间（精确到时分）',
    Operator VARCHAR(50) NOT NULL COMMENT '操作员/检查医生',

    -- 眼轴相关测量（Axial Length）
    AXL_R DECIMAL(5,2) COMMENT '右眼眼轴长度 (mm)',
    AXL_L DECIMAL(5,2) COMMENT '左眼眼轴长度 (mm)',

    -- 角膜厚度（Central Corneal Thickness）
    CCT_R DECIMAL(5,1) COMMENT '右眼中央角膜厚度 (μm)',
    CCT_L DECIMAL(5,1) COMMENT '左眼中央角膜厚度 (μm)',

    -- 前房深度（Anterior Chamber Depth）
    ACD_R DECIMAL(4,2) COMMENT '右眼前房深度 (mm)',
    ACD_L DECIMAL(4,2) COMMENT '左眼前房深度 (mm)',

    -- 晶状体厚度（Lens Thickness）
    LT_R DECIMAL(4,2) COMMENT '右眼晶状体厚度 (mm)',
    LT_L DECIMAL(4,2) COMMENT '左眼晶状体厚度 (mm)',

    -- 玻璃体深度（Vitreous Thickness = AXL - ACD - LT）
    VT_R DECIMAL(5,2) COMMENT '右眼玻璃体深度 (mm)',
    VT_L DECIMAL(5,2) COMMENT '左眼玻璃体深度 (mm)',

    -- 角膜曲率K1（最平曲率）
    K1_D_R DECIMAL(5,2) COMMENT '右眼K1屈光力 (D)',
    K1_mm_R DECIMAL(4,2) COMMENT '右眼K1曲率半径 (mm)',
    K1_Axis_R INT COMMENT '右眼K1轴位 (度)',
    K1_D_L DECIMAL(5,2) COMMENT '左眼K1屈光力 (D)',
    K1_mm_L DECIMAL(4,2) COMMENT '左眼K1曲率半径 (mm)',
    K1_Axis_L INT COMMENT '左眼K1轴位 (度)',

    -- 角膜曲率K2（最陡曲率）
    K2_D_R DECIMAL(5,2) COMMENT '右眼K2屈光力 (D)',
    K2_mm_R DECIMAL(4,2) COMMENT '右眼K2曲率半径 (mm)',
    K2_Axis_R INT COMMENT '右眼K2轴位 (度)',
    K2_D_L DECIMAL(5,2) COMMENT '左眼K2屈光力 (D)',
    K2_mm_L DECIMAL(4,2) COMMENT '左眼K2曲率半径 (mm)',
    K2_Axis_L INT COMMENT '左眼K2轴位 (度)',

    -- 散光（Astigmatism）
    Astigmatism_R DECIMAL(4,2) COMMENT '右眼散光度数 (D)',
    Astigmatism_L DECIMAL(4,2) COMMENT '左眼散光度数 (D)',

    -- 角膜直径（White to White）
    WTW_R DECIMAL(4,2) COMMENT '右眼角膜直径 (mm)',
    WTW_L DECIMAL(4,2) COMMENT '左眼角膜直径 (mm)',

    -- 瞳孔直径（Pupil Diameter）
    Pupil_Diameter_R DECIMAL(4,2) COMMENT '右眼瞳孔直径 (mm)',
    Pupil_Diameter_L DECIMAL(4,2) COMMENT '左眼瞳孔直径 (mm)',

    -- 地形图参数（Topography - TR）
    TR_R DECIMAL(4,2) COMMENT '右眼地形图参数',
    TR_L DECIMAL(4,2) COMMENT '左眼地形图参数',

    -- 多区域角膜厚度数据（Ac-T1 到 Ac-T8）- 用于详细报告
    Ac_T1 DECIMAL(5,1) COMMENT '角膜厚度区域1',
    Ac_T2 DECIMAL(5,1) COMMENT '角膜厚度区域2',
    Ac_T3 DECIMAL(5,1) COMMENT '角膜厚度区域3',
    Ac_T4 DECIMAL(5,1) COMMENT '角膜厚度区域4',
    Ac_T5 DECIMAL(5,1) COMMENT '角膜厚度区域5',
    Ac_T6 DECIMAL(5,1) COMMENT '角膜厚度区域6',
    Ac_T7 DECIMAL(5,1) COMMENT '角膜厚度区域7',
    Ac_T8 DECIMAL(5,1) COMMENT '角膜厚度区域8',

    -- 角膜屈光力数据（P-T1 到 P-T8）- 用于详细报告
    P_T1 DECIMAL(5,2) COMMENT '角膜屈光力区域1',
    P_T2 DECIMAL(5,2) COMMENT '角膜屈光力区域2',
    P_T3 DECIMAL(5,2) COMMENT '角膜屈光力区域3',
    P_T4 DECIMAL(5,2) COMMENT '角膜屈光力区域4',
    P_T5 DECIMAL(5,2) COMMENT '角膜屈光力区域5',
    P_T6 DECIMAL(5,2) COMMENT '角膜屈光力区域6',
    P_T7 DECIMAL(5,2) COMMENT '角膜屈光力区域7',
    P_T8 DECIMAL(5,2) COMMENT '角膜屈光力区域8',

    -- 生物力学参数I系列（I1-T1 到 I5-T8）- 用于详细报告
    I1_T1 DECIMAL(6,2) COMMENT '生物力学参数I1-T1',
    I1_T2 DECIMAL(6,2) COMMENT '生物力学参数I1-T2',
    I1_T3 DECIMAL(6,2) COMMENT '生物力学参数I1-T3',
    I1_T4 DECIMAL(6,2) COMMENT '生物力学参数I1-T4',
    I1_T5 DECIMAL(6,2) COMMENT '生物力学参数I1-T5',
    I1_T6 DECIMAL(6,2) COMMENT '生物力学参数I1-T6',
    I1_T7 DECIMAL(6,2) COMMENT '生物力学参数I1-T7',
    I1_T8 DECIMAL(6,2) COMMENT '生物力学参数I1-T8',

    I2_T1 DECIMAL(6,2) COMMENT '生物力学参数I2-T1',
    I2_T2 DECIMAL(6,2) COMMENT '生物力学参数I2-T2',
    I2_T3 DECIMAL(6,2) COMMENT '生物力学参数I2-T3',
    I2_T4 DECIMAL(6,2) COMMENT '生物力学参数I2-T4',
    I2_T5 DECIMAL(6,2) COMMENT '生物力学参数I2-T5',
    I2_T6 DECIMAL(6,2) COMMENT '生物力学参数I2-T6',
    I2_T7 DECIMAL(6,2) COMMENT '生物力学参数I2-T7',
    I2_T8 DECIMAL(6,2) COMMENT '生物力学参数I2-T8',

    I3_T1 DECIMAL(6,2) COMMENT '生物力学参数I3-T1',
    I3_T2 DECIMAL(6,2) COMMENT '生物力学参数I3-T2',
    I3_T3 DECIMAL(6,2) COMMENT '生物力学参数I3-T3',
    I3_T4 DECIMAL(6,2) COMMENT '生物力学参数I3-T4',
    I3_T5 DECIMAL(6,2) COMMENT '生物力学参数I3-T5',
    I3_T6 DECIMAL(6,2) COMMENT '生物力学参数I3-T6',
    I3_T7 DECIMAL(6,2) COMMENT '生物力学参数I3-T7',
    I3_T8 DECIMAL(6,2) COMMENT '生物力学参数I3-T8',

    I4_T1 DECIMAL(6,2) COMMENT '生物力学参数I4-T1',
    I4_T2 DECIMAL(6,2) COMMENT '生物力学参数I4-T2',
    I4_T3 DECIMAL(6,2) COMMENT '生物力学参数I4-T3',
    I4_T4 DECIMAL(6,2) COMMENT '生物力学参数I4-T4',
    I4_T5 DECIMAL(6,2) COMMENT '生物力学参数I4-T5',
    I4_T6 DECIMAL(6,2) COMMENT '生物力学参数I4-T6',
    I4_T7 DECIMAL(6,2) COMMENT '生物力学参数I4-T7',
    I4_T8 DECIMAL(6,2) COMMENT '生物力学参数I4-T8',

    I5_T1 DECIMAL(6,2) COMMENT '生物力学参数I5-T1',
    I5_T2 DECIMAL(6,2) COMMENT '生物力学参数I5-T2',
    I5_T3 DECIMAL(6,2) COMMENT '生物力学参数I5-T3',
    I5_T4 DECIMAL(6,2) COMMENT '生物力学参数I5-T4',
    I5_T5 DECIMAL(6,2) COMMENT '生物力学参数I5-T5',
    I5_T6 DECIMAL(6,2) COMMENT '生物力学参数I5-T6',
    I5_T7 DECIMAL(6,2) COMMENT '生物力学参数I5-T7',
    I5_T8 DECIMAL(6,2) COMMENT '生物力学参数I5-T8',

    -- 生物力学参数R系列（R1-T1 到 R5-T8）- 用于详细报告
    R1_T1 DECIMAL(6,2) COMMENT '生物力学参数R1-T1',
    R1_T2 DECIMAL(6,2) COMMENT '生物力学参数R1-T2',
    R1_T3 DECIMAL(6,2) COMMENT '生物力学参数R1-T3',
    R1_T4 DECIMAL(6,2) COMMENT '生物力学参数R1-T4',
    R1_T5 DECIMAL(6,2) COMMENT '生物力学参数R1-T5',
    R1_T6 DECIMAL(6,2) COMMENT '生物力学参数R1-T6',
    R1_T7 DECIMAL(6,2) COMMENT '生物力学参数R1-T7',
    R1_T8 DECIMAL(6,2) COMMENT '生物力学参数R1-T8',

    R2_T1 DECIMAL(6,2) COMMENT '生物力学参数R2-T1',
    R2_T2 DECIMAL(6,2) COMMENT '生物力学参数R2-T2',
    R2_T3 DECIMAL(6,2) COMMENT '生物力学参数R2-T3',
    R2_T4 DECIMAL(6,2) COMMENT '生物力学参数R2-T4',
    R2_T5 DECIMAL(6,2) COMMENT '生物力学参数R2-T5',
    R2_T6 DECIMAL(6,2) COMMENT '生物力学参数R2-T6',
    R2_T7 DECIMAL(6,2) COMMENT '生物力学参数R2-T7',
    R2_T8 DECIMAL(6,2) COMMENT '生物力学参数R2-T8',

    R3_T1 DECIMAL(6,2) COMMENT '生物力学参数R3-T1',
    R3_T2 DECIMAL(6,2) COMMENT '生物力学参数R3-T2',
    R3_T3 DECIMAL(6,2) COMMENT '生物力学参数R3-T3',
    R3_T4 DECIMAL(6,2) COMMENT '生物力学参数R3-T4',
    R3_T5 DECIMAL(6,2) COMMENT '生物力学参数R3-T5',
    R3_T6 DECIMAL(6,2) COMMENT '生物力学参数R3-T6',
    R3_T7 DECIMAL(6,2) COMMENT '生物力学参数R3-T7',
    R3_T8 DECIMAL(6,2) COMMENT '生物力学参数R3-T8',

    R4_T1 DECIMAL(6,2) COMMENT '生物力学参数R4-T1',
    R4_T2 DECIMAL(6,2) COMMENT '生物力学参数R4-T2',
    R4_T3 DECIMAL(6,2) COMMENT '生物力学参数R4-T3',
    R4_T4 DECIMAL(6,2) COMMENT '生物力学参数R4-T4',
    R4_T5 DECIMAL(6,2) COMMENT '生物力学参数R4-T5',
    R4_T6 DECIMAL(6,2) COMMENT '生物力学参数R4-T6',
    R4_T7 DECIMAL(6,2) COMMENT '生物力学参数R4-T7',
    R4_T8 DECIMAL(6,2) COMMENT '生物力学参数R4-T8',

    R5_T1 DECIMAL(6,2) COMMENT '生物力学参数R5-T1',
    R5_T2 DECIMAL(6,2) COMMENT '生物力学参数R5-T2',
    R5_T3 DECIMAL(6,2) COMMENT '生物力学参数R5-T3',
    R5_T4 DECIMAL(6,2) COMMENT '生物力学参数R5-T4',
    R5_T5 DECIMAL(6,2) COMMENT '生物力学参数R5-T5',
    R5_T6 DECIMAL(6,2) COMMENT '生物力学参数R5-T6',
    R5_T7 DECIMAL(6,2) COMMENT '生物力学参数R5-T7',
    R5_T8 DECIMAL(6,2) COMMENT '生物力学参数R5-T8',

    -- 备注和状态字段
    Notes TEXT COMMENT '备注说明',
    Report_Status ENUM('待生成', '已生成', '已归档') DEFAULT '待生成' COMMENT '报告状态',
    Report_Type VARCHAR(20) COMMENT '生成的报告类型（basic/detailed）',
    Report_Path VARCHAR(255) COMMENT '生成的报告文件路径',

    -- 审核字段
    Reviewed_By VARCHAR(50) COMMENT '审核医生',
    Reviewed_At DATETIME COMMENT '审核时间',

    -- 时间戳
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    -- 外键约束
    FOREIGN KEY (Patient_ID) REFERENCES patient(Patient_ID) ON DELETE CASCADE,
    FOREIGN KEY (Medical_Record_ID) REFERENCES medical_record(Medical_Record_ID) ON DELETE SET NULL,

    -- 索引
    INDEX idx_patient (Patient_ID),
    INDEX idx_medical_record (Medical_Record_ID),
    INDEX idx_scan_date (Scan_Date),
    INDEX idx_operator (Operator),
    INDEX idx_report_status (Report_Status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='眼科生物力学检查数据表';

-- 插入演示数据

-- 演示数据1：张三的基础生物力学检查（Patient_ID=1）
INSERT INTO biomechanics_scan (
    Patient_ID, Medical_Record_ID, Patient_Name, Gender, Birth_Date, Age,
    Scan_Date, Scan_Time, Operator,
    -- 基础测量数据
    AXL_R, AXL_L, CCT_R, CCT_L, ACD_R, ACD_L, LT_R, LT_L, VT_R, VT_L,
    -- K1曲率
    K1_D_R, K1_mm_R, K1_Axis_R, K1_D_L, K1_mm_L, K1_Axis_L,
    -- K2曲率
    K2_D_R, K2_mm_R, K2_Axis_R, K2_D_L, K2_mm_L, K2_Axis_L,
    -- 散光和其他
    Astigmatism_R, Astigmatism_L, WTW_R, WTW_L, Pupil_Diameter_R, Pupil_Diameter_L,
    Notes, Report_Status
)
VALUES (
    1, 1, '张三', '男', '1990-01-01', 35,
    '2025-11-10', '2025-11-10 09:30:00', '张医生',
    -- 基础测量
    24.89, 24.73, 540.1, 542.2, 3.66, 3.51, 4.28, 4.30, 16.95, 16.94,
    -- K1
    47.47, 7.11, 178, 47.27, 7.14, 14,
    -- K2
    48.31, 6.99, 88, 48.09, 7.02, 104,
    -- 其他
    -0.84, -0.81, 11.80, 12.00, 3.86, 3.80,
    '患者配合良好，数据准确', '已生成'
);

-- 演示数据2：李四的详细生物力学检查（Patient_ID=2）
INSERT INTO biomechanics_scan (
    Patient_ID, Medical_Record_ID, Patient_Name, Gender, Birth_Date, Age,
    Scan_Date, Scan_Time, Operator,
    -- 基础测量数据
    AXL_R, AXL_L, CCT_R, CCT_L, ACD_R, ACD_L, LT_R, LT_L, VT_R, VT_L,
    -- K1曲率
    K1_D_R, K1_mm_R, K1_Axis_R, K1_D_L, K1_mm_L, K1_Axis_L,
    -- K2曲率
    K2_D_R, K2_mm_R, K2_Axis_R, K2_D_L, K2_mm_L, K2_Axis_L,
    -- 散光和其他
    Astigmatism_R, Astigmatism_L, WTW_R, WTW_L, Pupil_Diameter_R, Pupil_Diameter_L,
    TR_R, TR_L,
    -- 多区域角膜厚度（Ac）
    Ac_T1, Ac_T2, Ac_T3, Ac_T4, Ac_T5, Ac_T6, Ac_T7, Ac_T8,
    -- 角膜屈光力（P）
    P_T1, P_T2, P_T3, P_T4, P_T5, P_T6, P_T7, P_T8,
    -- 生物力学参数I1
    I1_T1, I1_T2, I1_T3, I1_T4, I1_T5, I1_T6, I1_T7, I1_T8,
    -- 生物力学参数I2
    I2_T1, I2_T2, I2_T3, I2_T4, I2_T5, I2_T6, I2_T7, I2_T8,
    -- 生物力学参数I3
    I3_T1, I3_T2, I3_T3, I3_T4, I3_T5, I3_T6, I3_T7, I3_T8,
    -- 生物力学参数R1
    R1_T1, R1_T2, R1_T3, R1_T4, R1_T5, R1_T6, R1_T7, R1_T8,
    -- 生物力学参数R2
    R2_T1, R2_T2, R2_T3, R2_T4, R2_T5, R2_T6, R2_T7, R2_T8,
    Notes, Report_Status, Report_Type
)
VALUES (
    2, 3, '李四', '女', '1997-05-15', 28,
    '2025-11-12', '2025-11-12 10:45:00', '李医生',
    -- 基础测量
    23.45, 23.52, 535.5, 538.0, 3.55, 3.60, 4.15, 4.18, 15.75, 15.74,
    -- K1
    46.80, 7.21, 165, 46.95, 7.19, 10,
    -- K2
    47.65, 7.09, 75, 47.80, 7.06, 100,
    -- 其他
    -0.85, -0.85, 11.95, 12.05, 4.10, 4.05,
    -0.5, -0.5,
    -- Ac多区域厚度
    535.5, 538.2, 540.1, 542.3, 544.5, 546.2, 548.0, 550.1,
    -- P角膜屈光力
    46.80, 46.85, 46.90, 46.95, 47.00, 47.05, 47.10, 47.15,
    -- I1生物力学
    1.25, 1.28, 1.30, 1.32, 1.35, 1.38, 1.40, 1.42,
    -- I2生物力学
    2.10, 2.12, 2.15, 2.18, 2.20, 2.22, 2.25, 2.28,
    -- I3生物力学
    3.05, 3.08, 3.10, 3.12, 3.15, 3.18, 3.20, 3.22,
    -- R1生物力学
    5.50, 5.52, 5.55, 5.58, 5.60, 5.62, 5.65, 5.68,
    -- R2生物力学
    6.20, 6.22, 6.25, 6.28, 6.30, 6.32, 6.35, 6.38,
    '详细检查数据完整，建议生成详细报告', '已生成', 'detailed'
);

-- 演示数据3：王五的最新检查（Patient_ID=3）
INSERT INTO biomechanics_scan (
    Patient_ID, Medical_Record_ID, Patient_Name, Gender, Birth_Date, Age,
    Scan_Date, Scan_Time, Operator,
    -- 基础测量数据
    AXL_R, AXL_L, CCT_R, CCT_L, ACD_R, ACD_L, LT_R, LT_L, VT_R, VT_L,
    -- K1曲率
    K1_D_R, K1_mm_R, K1_Axis_R, K1_D_L, K1_mm_L, K1_Axis_L,
    -- K2曲率
    K2_D_R, K2_mm_R, K2_Axis_R, K2_D_L, K2_mm_L, K2_Axis_L,
    -- 散光和其他
    Astigmatism_R, Astigmatism_L, WTW_R, WTW_L, Pupil_Diameter_R, Pupil_Diameter_L,
    Notes, Report_Status, Reviewed_By, Reviewed_At
)
VALUES (
    3, NULL, '王五', '男', '1980-08-20', 45,
    '2025-11-18', '2025-11-18 14:20:00', '王医生',
    -- 基础测量
    25.12, 25.08, 545.0, 548.5, 3.75, 3.72, 4.35, 4.38, 17.02, 16.98,
    -- K1
    48.20, 7.00, 170, 48.05, 7.02, 8,
    -- K2
    49.15, 6.87, 80, 49.00, 6.89, 98,
    -- 其他
    -0.95, -0.95, 11.70, 11.85, 3.75, 3.70,
    '患者为术前检查，数据已审核', '待生成', '赵医生', '2025-11-18 15:00:00'
);

-- 演示数据4：张三的复查数据（Patient_ID=1）
INSERT INTO biomechanics_scan (
    Patient_ID, Medical_Record_ID, Patient_Name, Gender, Birth_Date, Age,
    Scan_Date, Scan_Time, Operator,
    -- 基础测量数据
    AXL_R, AXL_L, CCT_R, CCT_L, ACD_R, ACD_L, LT_R, LT_L, VT_R, VT_L,
    -- K1曲率
    K1_D_R, K1_mm_R, K1_Axis_R, K1_D_L, K1_mm_L, K1_Axis_L,
    -- K2曲率
    K2_D_R, K2_mm_R, K2_Axis_R, K2_D_L, K2_mm_L, K2_Axis_L,
    -- 散光和其他
    Astigmatism_R, Astigmatism_L, WTW_R, WTW_L, Pupil_Diameter_R, Pupil_Diameter_L,
    Notes, Report_Status
)
VALUES (
    1, 2, '张三', '男', '1990-01-01', 35,
    '2025-11-15', '2025-11-15 11:00:00', '张医生',
    -- 基础测量
    24.91, 24.75, 541.0, 543.0, 3.67, 3.52, 4.29, 4.31, 16.95, 16.92,
    -- K1
    47.50, 7.10, 177, 47.30, 7.13, 15,
    -- K2
    48.35, 6.98, 87, 48.12, 7.01, 105,
    -- 其他
    -0.85, -0.82, 11.82, 12.02, 3.88, 3.82,
    '复查数据与上次基本一致，眼轴稍有变化', '已生成'
);

-- 查看插入结果
SELECT '生物力学检查表创建成功！' AS message;
SELECT CONCAT('已插入 ', COUNT(*), ' 条演示数据') AS scan_count FROM biomechanics_scan;

-- 查看演示数据详情
SELECT
    Scan_ID,
    Patient_Name,
    Gender,
    Age,
    Scan_Date,
    Operator,
    AXL_R,
    AXL_L,
    CCT_R,
    CCT_L,
    Report_Status,
    Report_Type
FROM biomechanics_scan
ORDER BY Scan_Date DESC;

-- ========================================
-- 处方表查询示例 SQL
-- ========================================
-- 本文件包含处方表的常用查询示例

USE medical_db;

-- ========================================
-- 1. 基础查询
-- ========================================

-- 1.1 查询所有处方
SELECT * FROM prescription;

-- 1.2 查询某个患者的所有处方
SELECT 
    p.Prescription_Number AS '处方编号',
    p.Prescription_Date AS '开方日期',
    p.Diagnosis_Description AS '诊断',
    p.Total_Amount AS '总金额',
    p.Prescription_Status AS '状态',
    p.Prescriber_Name AS '开方医生'
FROM prescription p
WHERE p.Patient_ID = 1
ORDER BY p.Prescription_Date DESC;

-- 1.3 查询某个医生开具的所有处方
SELECT 
    p.Prescription_Number AS '处方编号',
    pat.Name AS '患者姓名',
    p.Diagnosis_Description AS '诊断',
    p.Total_Amount AS '总金额',
    p.Prescription_Date AS '开方日期'
FROM prescription p
JOIN patient pat ON p.Patient_ID = pat.Patient_ID
WHERE p.Doctor_ID = 1
ORDER BY p.Prescription_Date DESC;

-- ========================================
-- 2. 关联查询
-- ========================================

-- 2.1 查询处方详细信息（包含患者、医生、病例信息）
SELECT 
    p.Prescription_Number AS '处方编号',
    pat.Name AS '患者姓名',
    pat.Phone_Number AS '联系电话',
    d.Name AS '医生姓名',
    d.Title AS '医生职称',
    mr.Visit_Date AS '就诊日期',
    mr.Diagnosis AS '病例诊断',
    p.Diagnosis_Description AS '处方诊断',
    p.Total_Amount AS '处方金额',
    p.Prescription_Status AS '处方状态'
FROM prescription p
JOIN patient pat ON p.Patient_ID = pat.Patient_ID
JOIN doctor d ON p.Doctor_ID = d.Doctor_ID
JOIN medical_record mr ON p.Medical_Record_ID = mr.Medical_Record_ID
ORDER BY p.Prescription_Date DESC;

-- 2.2 查询处方及其所有药物明细
SELECT 
    p.Prescription_Number AS '处方编号',
    pat.Name AS '患者姓名',
    pd.Drug_Name AS '药物名称',
    pd.Drug_Specification AS '规格',
    pd.Quantity AS '数量',
    pd.Unit AS '单位',
    pd.Dosage AS '用法用量',
    pd.Frequency AS '用药频率',
    pd.Duration AS '疗程',
    pd.Unit_Price AS '单价',
    pd.Subtotal AS '小计'
FROM prescription p
JOIN patient pat ON p.Patient_ID = pat.Patient_ID
JOIN prescription_detail pd ON p.Prescription_ID = pd.Prescription_ID
WHERE p.Prescription_ID = 1;

-- 2.3 查询完整的处方单（包含所有相关信息）
SELECT 
    p.Prescription_Number AS '处方编号',
    p.Prescription_Date AS '开方日期',
    pat.Name AS '患者姓名',
    pat.Gender AS '性别',
    pat.Age AS '年龄',
    d.Name AS '医生姓名',
    d.Title AS '职称',
    mr.Chief_Complaint AS '主诉',
    mr.Diagnosis AS '诊断',
    pd.Drug_Name AS '药物名称',
    pd.Drug_Specification AS '规格',
    pd.Quantity AS '数量',
    pd.Dosage AS '用法用量',
    pd.Frequency AS '频率',
    pd.Duration AS '疗程',
    pd.Administration_Route AS '给药途径',
    pd.Special_Instructions AS '特殊说明',
    p.Usage_Instruction AS '用药指导',
    p.Total_Amount AS '总金额'
FROM prescription p
JOIN patient pat ON p.Patient_ID = pat.Patient_ID
JOIN doctor d ON p.Doctor_ID = d.Doctor_ID
JOIN medical_record mr ON p.Medical_Record_ID = mr.Medical_Record_ID
JOIN prescription_detail pd ON p.Prescription_ID = pd.Prescription_ID
WHERE p.Prescription_Number = 'RX20251117001';

-- ========================================
-- 3. 统计查询
-- ========================================

-- 3.1 统计每个医生开具的处方数量
SELECT 
    d.Name AS '医生姓名',
    d.Title AS '职称',
    COUNT(p.Prescription_ID) AS '处方数量',
    SUM(p.Total_Amount) AS '总金额'
FROM doctor d
LEFT JOIN prescription p ON d.Doctor_ID = p.Doctor_ID
GROUP BY d.Doctor_ID, d.Name, d.Title
ORDER BY COUNT(p.Prescription_ID) DESC;

-- 3.2 统计某段时间内的处方金额
SELECT 
    DATE(Prescription_Date) AS '日期',
    COUNT(Prescription_ID) AS '处方数量',
    SUM(Total_Amount) AS '总金额',
    AVG(Total_Amount) AS '平均金额'
FROM prescription
WHERE Prescription_Date >= '2025-11-01' AND Prescription_Date < '2025-12-01'
GROUP BY DATE(Prescription_Date)
ORDER BY DATE(Prescription_Date);

-- 3.3 统计最常用的药物
SELECT 
    d.drug_name AS '药物名称',
    d.drug_category AS '药物类别',
    COUNT(pd.Detail_ID) AS '使用次数',
    SUM(pd.Quantity) AS '总数量'
FROM prescription_detail pd
JOIN drugs d ON pd.Drug_ID = d.drug_id
GROUP BY d.drug_id, d.drug_name, d.drug_category
ORDER BY COUNT(pd.Detail_ID) DESC
LIMIT 10;

-- 3.4 按处方状态统计
SELECT 
    Prescription_Status AS '处方状态',
    COUNT(*) AS '数量',
    SUM(Total_Amount) AS '总金额'
FROM prescription
GROUP BY Prescription_Status;

-- ========================================
-- 4. 复杂查询
-- ========================================

-- 4.1 查询包含某类药物的所有处方
SELECT DISTINCT
    p.Prescription_Number AS '处方编号',
    pat.Name AS '患者姓名',
    d.Name AS '医生姓名',
    p.Prescription_Date AS '开方日期',
    drug.drug_category AS '药物类别'
FROM prescription p
JOIN patient pat ON p.Patient_ID = pat.Patient_ID
JOIN doctor d ON p.Doctor_ID = d.Doctor_ID
JOIN prescription_detail pd ON p.Prescription_ID = pd.Prescription_ID
JOIN drugs drug ON pd.Drug_ID = drug.drug_id
WHERE drug.drug_category = '抗生素';

-- 4.2 查询处方药物与患者过敏史的对照
SELECT 
    p.Prescription_Number AS '处方编号',
    pat.Name AS '患者姓名',
    pat.Allergy_History AS '过敏史',
    pd.Drug_Name AS '处方药物',
    drug.warning_info AS '警示信息'
FROM prescription p
JOIN patient pat ON p.Patient_ID = pat.Patient_ID
JOIN prescription_detail pd ON p.Prescription_ID = pd.Prescription_ID
JOIN drugs drug ON pd.Drug_ID = drug.drug_id
WHERE pat.Allergy_History IS NOT NULL AND pat.Allergy_History != '';

-- 4.3 查询某个病例的完整治疗记录（包括处方）
SELECT 
    mr.Visit_Card_Number AS '就诊卡号',
    mr.Visit_Date AS '就诊日期',
    mr.Chief_Complaint AS '主诉',
    mr.Diagnosis AS '诊断',
    p.Prescription_Number AS '处方编号',
    pd.Drug_Name AS '药物',
    pd.Dosage AS '用法',
    pd.Duration AS '疗程'
FROM medical_record mr
LEFT JOIN prescription p ON mr.Medical_Record_ID = p.Medical_Record_ID
LEFT JOIN prescription_detail pd ON p.Prescription_ID = pd.Prescription_ID
WHERE mr.Medical_Record_ID = 1
ORDER BY p.Prescription_Date, pd.Detail_ID;

-- 4.4 查询需要复查的患者处方
SELECT 
    pat.Name AS '患者姓名',
    pat.Phone_Number AS '联系电话',
    mr.Follow_Up_Date AS '复诊日期',
    p.Prescription_Number AS '处方编号',
    p.Diagnosis_Description AS '诊断',
    p.Prescription_Date AS '开方日期'
FROM patient pat
JOIN medical_record mr ON pat.Patient_ID = mr.Patient_ID
JOIN prescription p ON mr.Medical_Record_ID = p.Medical_Record_ID
WHERE mr.Follow_Up_Date IS NOT NULL
ORDER BY mr.Follow_Up_Date;

-- ========================================
-- 5. 更新操作示例
-- ========================================

-- 5.1 更新处方状态
UPDATE prescription 
SET Prescription_Status = '已配药',
    Pharmacist_Name = '王药师',
    Dispensed_Date = NOW()
WHERE Prescription_Number = 'RX20251117001';

-- 5.2 批量更新过期未配药的处方状态
UPDATE prescription 
SET Prescription_Status = '已作废',
    Notes = CONCAT(IFNULL(Notes, ''), ' [系统自动：超过48小时未配药]')
WHERE Prescription_Status = '待审核' 
AND Prescription_Date < DATE_SUB(NOW(), INTERVAL 48 HOUR);

-- ========================================
-- 6. 视图创建（便于常用查询）
-- ========================================

-- 6.1 创建处方详情视图
CREATE OR REPLACE VIEW v_prescription_detail AS
SELECT 
    p.Prescription_ID,
    p.Prescription_Number AS '处方编号',
    p.Prescription_Date AS '开方日期',
    pat.Name AS '患者姓名',
    pat.Phone_Number AS '患者电话',
    d.Name AS '医生姓名',
    d.Title AS '医生职称',
    p.Diagnosis_Description AS '诊断',
    p.Total_Amount AS '总金额',
    p.Prescription_Status AS '状态',
    mr.Visit_Date AS '就诊日期'
FROM prescription p
JOIN patient pat ON p.Patient_ID = pat.Patient_ID
JOIN doctor d ON p.Doctor_ID = d.Doctor_ID
JOIN medical_record mr ON p.Medical_Record_ID = mr.Medical_Record_ID;

-- 使用视图查询
SELECT * FROM v_prescription_detail WHERE `患者姓名` = '张三';

-- 6.2 创建药物使用统计视图
CREATE OR REPLACE VIEW v_drug_usage_stats AS
SELECT 
    d.drug_id AS '药物编号',
    d.drug_name AS '药物名称',
    d.drug_category AS '药物类别',
    COUNT(pd.Detail_ID) AS '处方次数',
    SUM(pd.Quantity) AS '总数量',
    SUM(pd.Subtotal) AS '总金额',
    d.stock_quantity AS '当前库存'
FROM drugs d
LEFT JOIN prescription_detail pd ON d.drug_id = pd.Drug_ID
GROUP BY d.drug_id, d.drug_name, d.drug_category, d.stock_quantity;

-- 使用视图查询
SELECT * FROM v_drug_usage_stats ORDER BY `处方次数` DESC;

-- ========================================
-- 7. 数据完整性检查
-- ========================================

-- 7.1 检查处方金额是否匹配明细小计
SELECT 
    p.Prescription_Number AS '处方编号',
    p.Total_Amount AS '处方总金额',
    SUM(pd.Subtotal) AS '明细小计',
    (p.Total_Amount - SUM(pd.Subtotal)) AS '差额'
FROM prescription p
JOIN prescription_detail pd ON p.Prescription_ID = pd.Prescription_ID
GROUP BY p.Prescription_ID, p.Prescription_Number, p.Total_Amount
HAVING ABS(p.Total_Amount - SUM(pd.Subtotal)) > 0.01;

-- 7.2 检查是否有处方没有药物明细
SELECT 
    p.Prescription_Number AS '处方编号',
    p.Prescription_Date AS '开方日期',
    pat.Name AS '患者姓名'
FROM prescription p
JOIN patient pat ON p.Patient_ID = pat.Patient_ID
LEFT JOIN prescription_detail pd ON p.Prescription_ID = pd.Prescription_ID
WHERE pd.Detail_ID IS NULL;

-- ========================================
-- 说明
-- ========================================
-- 以上示例展示了处方表的常见使用场景
-- 可根据实际业务需求进行调整和扩展


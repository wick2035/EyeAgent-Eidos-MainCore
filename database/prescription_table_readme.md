# 处方表设计说明

## 概述

处方表系统由两个核心表组成，用于管理医疗处方信息及其药物明细。该设计支持完整的处方管理流程，包括开方、审核、配药和完成等各个环节。

## 数据表结构

### 1. 处方主表 (prescription)

处方主表存储处方的基本信息，关联患者、医生和病例。

#### 主要字段

| 字段名 | 类型 | 说明 |
|--------|------|------|
| Prescription_ID | INT | 处方ID（主键，自增） |
| Patient_ID | INT | 患者ID（外键 → patient表） |
| Doctor_ID | INT | 医生ID（外键 → doctor表） |
| Medical_Record_ID | INT | 病例ID（外键 → medical_record表） |
| Prescription_Number | VARCHAR(50) | 处方编号（唯一） |
| Prescription_Date | DATETIME | 开方日期 |
| Prescription_Type | VARCHAR(20) | 处方类型（普通/急诊/儿科等） |
| Diagnosis_Description | TEXT | 诊断说明 |
| Usage_Instruction | TEXT | 用药说明 |
| Prescription_Status | ENUM | 处方状态（待审核/已审核/已配药/已完成/已作废） |
| Total_Amount | DECIMAL(10,2) | 处方总金额 |
| Notes | TEXT | 备注 |
| Prescriber_Name | VARCHAR(50) | 开方医生姓名 |
| Prescriber_Signature | VARCHAR(100) | 医生签名 |
| Pharmacist_Name | VARCHAR(50) | 配药药师姓名 |
| Pharmacist_Signature | VARCHAR(100) | 药师签名 |
| Dispensed_Date | DATETIME | 配药日期 |

#### 索引

- 主键索引：`Prescription_ID`
- 唯一索引：`Prescription_Number`
- 外键索引：`Patient_ID`, `Doctor_ID`, `Medical_Record_ID`
- 查询索引：`Prescription_Date`, `Prescription_Status`

### 2. 处方详情表 (prescription_detail)

处方详情表存储每个处方中的具体药物信息，通过药物ID关联药物表。

#### 主要字段

| 字段名 | 类型 | 说明 |
|--------|------|------|
| Detail_ID | INT | 详情ID（主键，自增） |
| Prescription_ID | INT | 处方ID（外键 → prescription表） |
| Drug_ID | VARCHAR(20) | 药物ID（外键 → drugs表） |
| Drug_Name | VARCHAR(255) | 药物名称（冗余字段，便于查询） |
| Drug_Specification | VARCHAR(100) | 药物规格（冗余字段） |
| Quantity | INT | 数量 |
| Unit | VARCHAR(20) | 单位（盒/支/瓶等） |
| Dosage | VARCHAR(100) | 用法用量 |
| Frequency | VARCHAR(50) | 用药频率（如：一日三次） |
| Duration | VARCHAR(50) | 用药疗程（如：7天） |
| Administration_Route | VARCHAR(50) | 给药途径（口服/外用/滴眼等） |
| Unit_Price | DECIMAL(10,2) | 单价 |
| Subtotal | DECIMAL(10,2) | 小计金额 |
| Special_Instructions | TEXT | 特殊说明 |

#### 索引

- 主键索引：`Detail_ID`
- 外键索引：`Prescription_ID`, `Drug_ID`

## 表关系图

```
┌─────────────┐          ┌──────────────────┐         ┌─────────────┐
│   patient   │──────────│   prescription   │─────────│   doctor    │
│  (患者表)   │          │    (处方主表)    │         │  (医生表)   │
└─────────────┘          └──────────────────┘         └─────────────┘
                                  │
                                  │
                         ┌────────┴─────────┐
                         │                  │
                ┌────────▼────────┐   ┌────▼──────────┐
                │ medical_record  │   │ prescription_ │
                │   (病例表)      │   │    detail     │
                └─────────────────┘   │  (处方详情表) │
                                      └────────┬──────┘
                                               │
                                      ┌────────▼──────┐
                                      │     drugs     │
                                      │   (药物表)    │
                                      └───────────────┘
```

## 数据关系说明

1. **患者 → 病例 → 处方**
   - 一个患者可以有多个病例记录
   - 一个病例可以对应多个处方

2. **处方 → 处方详情 → 药物**
   - 一个处方包含多条处方详情
   - 每条处方详情对应一种药物

3. **医生 → 处方**
   - 一个医生可以开具多个处方

## 处方状态流转

```
待审核 → 已审核 → 已配药 → 已完成
   ↓
已作废
```

- **待审核**：处方刚创建，等待审核
- **已审核**：处方已通过审核，可以配药
- **已配药**：药师已配药，等待患者取药
- **已完成**：患者已取药，流程结束
- **已作废**：处方因各种原因作废

## 使用示例

### 1. 创建新处方

```sql
-- 第一步：插入处方主表
INSERT INTO prescription (
    Patient_ID, Doctor_ID, Medical_Record_ID, 
    Prescription_Number, Prescription_Type, 
    Diagnosis_Description, Usage_Instruction, 
    Prescriber_Name
)
VALUES (
    1, 1, 1, 
    'RX20251117001', '普通', 
    '干眼症', '按时用药，注意用眼卫生', 
    '张医生'
);

-- 第二步：插入处方详情
INSERT INTO prescription_detail (
    Prescription_ID, Drug_ID, Drug_Name, Drug_Specification,
    Quantity, Unit, Dosage, Frequency, Duration,
    Administration_Route, Unit_Price, Subtotal
)
VALUES (
    1, 'EYD0001', '玻璃酸钠滴眼液', '10ml:5mg',
    2, '盒', '每次1-2滴', '每日4-6次', '2周',
    '滴眼', 38.50, 77.00
);

-- 第三步：更新处方总金额
UPDATE prescription 
SET Total_Amount = (
    SELECT SUM(Subtotal) 
    FROM prescription_detail 
    WHERE Prescription_ID = 1
)
WHERE Prescription_ID = 1;
```

### 2. 查询患者的处方历史

```sql
SELECT 
    p.Prescription_Number AS '处方编号',
    p.Prescription_Date AS '开方日期',
    p.Diagnosis_Description AS '诊断',
    p.Total_Amount AS '金额',
    p.Prescription_Status AS '状态',
    d.Name AS '医生'
FROM prescription p
JOIN doctor d ON p.Doctor_ID = d.Doctor_ID
WHERE p.Patient_ID = 1
ORDER BY p.Prescription_Date DESC;
```

### 3. 查询处方详细信息

```sql
SELECT 
    p.Prescription_Number AS '处方编号',
    pat.Name AS '患者',
    pd.Drug_Name AS '药物',
    pd.Quantity AS '数量',
    pd.Dosage AS '用法',
    pd.Frequency AS '频率',
    pd.Duration AS '疗程'
FROM prescription p
JOIN patient pat ON p.Patient_ID = pat.Patient_ID
JOIN prescription_detail pd ON p.Prescription_ID = pd.Prescription_ID
WHERE p.Prescription_Number = 'RX20251117001';
```

## 设计特点

### 1. 关联完整性
- 通过外键约束确保数据的引用完整性
- 级联删除确保数据一致性

### 2. 冗余字段
- 在处方详情表中冗余药物名称和规格
- 便于快速查询，减少关联查询次数

### 3. 状态管理
- 使用枚举类型管理处方状态
- 确保状态值的规范性

### 4. 时间戳
- 自动记录创建和更新时间
- 便于追踪数据变更历史

### 5. 审计字段
- 记录开方医生和配药药师信息
- 支持电子签名功能

## 注意事项

1. **金额计算**
   - 处方总金额 = 所有明细的小计之和
   - 建议使用触发器或应用层逻辑自动计算

2. **库存管理**
   - 配药时需要检查药物库存
   - 建议在配药时更新药物表的库存量

3. **过敏检查**
   - 开方时应检查患者过敏史
   - 避免开具患者过敏的药物

4. **处方有效期**
   - 建议设置处方有效期（如48小时）
   - 过期未配药的处方应自动作废

5. **数据备份**
   - 处方数据属于重要医疗数据
   - 建议定期备份

## 扩展建议

如果需要更完善的功能，可以考虑：

1. **处方审核表**：记录处方审核历史
2. **处方退药表**：处理退药业务
3. **处方模板表**：常用处方模板
4. **用药指导表**：详细的用药指导信息
5. **处方打印记录表**：记录处方打印历史

## 参考查询

更多查询示例请参考：`prescription_queries_example.sql`


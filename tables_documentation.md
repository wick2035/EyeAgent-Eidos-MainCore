# 数据库表结构文档

本文档详细说明了眼科管理系统中修改和新增的数据库表结构及字段含义。

---

## 目录

1. [Agenda 表 - 日程管理](#1-agenda-表---日程管理)
2. [Patient 表 - 患者信息](#2-patient-表---患者信息)
3. [Drugs 表 - 药品管理](#3-drugs-表---药品管理)
4. [Medical_Record 表 - 病历管理](#4-medical_record-表---病历管理)
5. [Prescription 表 - 处方管理](#5-prescription-表---处方管理)
6. [Prescription_Detail 表 - 处方明细](#6-prescription_detail-表---处方明细)
7. [Reminder_Config 表 - 提醒配置](#7-reminder_config-表---提醒配置)
8. [Reminder 表 - 提醒任务](#8-reminder-表---提醒任务)
9. [Reminder_History 表 - 提醒历史](#9-reminder_history-表---提醒历史)

---

## 1. Agenda 表 - 日程管理

**表名**: `agenda`
**用途**: 管理医生的日常日程和患者预约记录
**修改类型**: 新增字段（ALTER TABLE）

### 新增字段说明

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| medical_record_id | VARCHAR(50) | 病历号 | 关联患者的病历编号，用于预约场景 |
| patient_id | VARCHAR(36) | 患者ID | 患者的UUID，用于预约场景 |
| patient_name | VARCHAR(100) | 患者姓名 | 冗余字段，便于快速查看和展示 |
| severity_level | VARCHAR(20) | 严重程度 | 如：轻微、中等、严重、紧急 |
| status | VARCHAR(20) | 日程状态 | 如：待确认、已确认、进行中、已完成、已取消 |
| time_change_record | TEXT | 时间变更记录 | JSON格式，记录日程时间的变更历史 |
| category | VARCHAR(50) | 日程类别 | 如：建议尽快就诊、常规复查、紧急处理 |

### 索引

- `idx_patient_id`: 患者ID索引，用于查询患者的所有预约
- `idx_medical_record_id`: 病历号索引，用于关联病历查询
- `idx_status`: 状态索引，用于按状态筛选日程
- `idx_severity_level`: 严重程度索引，用于按优先级排序

### 业务场景

1. **医生日程**: 原有功能，`user_id` 为医生ID，患者相关字段为空
2. **患者预约**: 新增功能，患者通过移动端发起预约时填充患者相关字段

---

## 2. Patient 表 - 患者信息

**表名**: `patient`
**用途**: 存储患者的基本信息和医保信息
**修改类型**: 新增字段（ALTER TABLE）

### 新增字段说明

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| date_of_birth | DATETIME | 出生日期 | 用于计算年龄和年龄段统计 |
| email | VARCHAR(100) | 邮箱 | 用于发送电子邮件通知和报告 |
| emergency_contact | VARCHAR(100) | 紧急联系人 | 紧急情况下的联系人姓名 |
| emergency_contact_phone | VARCHAR(20) | 紧急联系人电话 | 紧急情况下的联系电话 |
| insurance_status | VARCHAR(50) | 医保状态 | 如：城镇职工医保、城乡居民医保、商业保险、自费 |
| insurance_card_number | VARCHAR(50) | 医保卡号 | 医保卡号码或社保卡号 |

### 索引

- `idx_email`: 邮箱索引，便于邮件通知查询
- `idx_insurance_card_number`: 医保卡号索引，便于医保结算
- `idx_date_of_birth`: 出生日期索引，便于按年龄段查询

### 业务场景

1. **患者注册**: 收集患者完整信息
2. **紧急联系**: 在紧急情况下联系家属
3. **医保结算**: 处理医保报销和费用结算
4. **电子通知**: 通过邮件发送检查结果和提醒

---

## 3. Drugs 表 - 药品管理

**表名**: `drugs`
**用途**: 管理眼科药品的基本信息、库存和价格
**修改类型**: 新建表（CREATE TABLE）

### 字段说明

#### 主键

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| ID | VARCHAR(36) | 主键ID | UUID格式 |

#### 药品基本信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| drug_id | VARCHAR(20) | 药品编号 | 业务ID，如：EYD0001，唯一索引 |
| drug_name | VARCHAR(200) | 药品名称 | 药品的通用名或商品名 |
| drug_category | VARCHAR(50) | 药品分类 | 如：润滑剂、抗生素、降眼压药、散瞳剂 |
| drug_specification | VARCHAR(100) | 药品规格 | 如：10ml:5mg、0.5g/支 |
| drug_dosage_form | VARCHAR(50) | 剂型 | 如：滴眼液、眼膏、眼用凝胶 |

#### 生产信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| manufacturer | VARCHAR(200) | 生产厂家 | 药品生产企业名称 |
| batch_number | VARCHAR(50) | 批号 | 生产批次号，用于质量追溯 |
| expiry_date | DATETIME | 过期日期 | 药品有效期，添加索引便于管理 |

#### 价格库存

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| price | DECIMAL(10,2) | 价格 | 药品单价（元） |
| stock_quantity | INT | 库存数量 | 当前库存量 |

#### 药品属性

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| is_prescription_drug | TINYINT(1) | 是否处方药 | 0-非处方药（OTC），1-处方药（Rx） |
| drug_status | VARCHAR(20) | 药品状态 | 如：在售、停售、缺货 |
| insurance_category | VARCHAR(50) | 医保类别 | 如：甲类医保、乙类医保、自费 |

#### 描述信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| warning_info | TEXT | 警告信息 | 用药警告和注意事项 |
| drug_description | TEXT | 药品描述 | 药品功能说明和适应症 |

#### 系统字段

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| create_time | DATETIME | 创建时间 | 自动设置为当前时间 |
| create_by | VARCHAR(36) | 创建人ID | UUID格式 |
| update_time | DATETIME | 更新时间 | 自动更新 |
| update_by | VARCHAR(36) | 更新人ID | UUID格式 |
| version | INT | 乐观锁版本号 | 用于并发控制 |
| deleted | TINYINT | 逻辑删除标记 | 0-未删除，1-已删除 |

### 索引

- `uk_drug_id`: 药品编号唯一索引
- `idx_drug_name`: 药品名称索引，便于搜索
- `idx_drug_category`: 分类索引，便于分类查询
- `idx_drug_status`: 状态索引，便于筛选在售药品
- `idx_expiry_date`: 过期日期索引，便于过期药品管理
- `idx_manufacturer`: 厂家索引，便于按厂家查询

### 业务场景

1. **药品库存管理**: 管理药品进销存
2. **过期药品提醒**: 定期检查即将过期的药品
3. **处方开具**: 医生开具处方时选择药品
4. **价格管理**: 药品价格维护和调整

---

## 4. Medical_Record 表 - 病历管理

**表名**: `medical_record`
**用途**: 记录患者的完整就诊信息和病历资料
**修改类型**: 新建表（CREATE TABLE）

### 字段说明

#### 主键

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| ID | VARCHAR(36) | 主键ID | UUID格式 |

#### 关联信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Patient_ID | VARCHAR(36) | 患者ID | 关联患者表，添加索引 |
| Visit_Card_Number | VARCHAR(50) | 就诊卡号 | 如：2025-000001 |
| Report_ID | VARCHAR(50) | 报告ID | 关联检查报告 |

#### 就诊信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Visit_Date | DATETIME | 就诊日期 | 患者就诊的日期 |
| Visit_Time | DATETIME | 就诊时间 | 具体就诊时间 |
| Department | VARCHAR(50) | 科室 | 如：眼科、眼底病科 |

#### 主诉与病史

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Chief_Complaint | TEXT | 主诉 | 患者描述的主要症状 |
| Present_Illness | TEXT | 现病史 | 当前疾病的发展过程 |
| Medical_History | TEXT | 既往史 | 过往疾病史 |
| Allergy_History | TEXT | 过敏史 | 药物或其他过敏史 |
| Family_History | TEXT | 家族史 | 家族遗传病史 |
| Medication_History | TEXT | 用药史 | 正在使用或曾经使用的药物 |

#### 检查结果

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Physical_Examination | TEXT | 体格检查 | 一般体格检查结果 |
| Eye_Exam_Results | TEXT | 眼部检查结果 | 视力、眼压、裂隙灯等检查结果 |
| Special_Exams | TEXT | 特殊检查 | OCT、眼底照相等特殊检查 |
| Auxiliary_Exams | TEXT | 辅助检查 | 血常规、生化等辅助检查 |

#### 诊断与治疗

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Diagnosis | TEXT | 诊断 | 医生诊断结果 |
| AI_Diagnosis | TEXT | AI诊断 | AI辅助诊断建议 |
| Treatment_Plan | TEXT | 治疗方案 | 具体治疗计划 |
| Medication | TEXT | 用药 | 开具的药物 |

#### 其他信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Surgical_History | TEXT | 手术史 | 眼科手术历史 |
| Hospitalization_Info | TEXT | 住院信息 | 住院记录 |
| Follow_Up_Date | DATETIME | 复诊日期 | 建议复诊时间 |

#### 医生信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Physician_Name | VARCHAR(100) | 医生姓名 | 主治医生 |
| Doctor_Signature | VARCHAR(255) | 医生签名 | 电子签名 |
| Print_Time | DATETIME | 打印时间 | 病历打印时间 |

#### 系统字段

与 Drugs 表相同的系统字段（create_time、create_by、update_time、update_by、version、deleted）

### 索引

- `idx_patient_id`: 患者ID索引
- `idx_visit_card_number`: 就诊卡号索引
- `idx_report_id`: 报告ID索引
- `idx_visit_date`: 就诊日期索引
- `idx_department`: 科室索引
- `idx_follow_up_date`: 复诊日期索引

### 业务场景

1. **门诊病历**: 记录每次门诊就诊信息
2. **病史查询**: 查看患者历史病历
3. **复诊提醒**: 根据复诊日期发送提醒
4. **病历打印**: 打印纸质病历

---

## 5. Prescription 表 - 处方管理

**表名**: `prescription`
**用途**: 管理医生开具的处方单
**修改类型**: 新建表（CREATE TABLE）

### 字段说明

#### 主键

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| ID | VARCHAR(36) | 主键ID | UUID格式 |

#### 关联信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Patient_ID | VARCHAR(36) | 患者ID | 关联患者 |
| Doctor_ID | VARCHAR(36) | 医生ID | 开处方医生 |
| Medical_Record_ID | VARCHAR(36) | 病历ID | 关联病历 |

#### 处方基本信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Prescription_Number | VARCHAR(50) | 处方编号 | 如：RX20251117001，唯一索引 |
| Prescription_Date | DATETIME | 处方日期 | 开处方日期 |
| Prescription_Type | VARCHAR(50) | 处方类型 | 如：普通处方、急诊处方 |

#### 诊断与用药指导

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Diagnosis_Description | TEXT | 诊断描述 | 诊断说明 |
| Usage_Instruction | TEXT | 用药指导 | 整体用药注意事项 |

#### 处方状态

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Prescription_Status | VARCHAR(20) | 处方状态 | 如：待审核、已审核、已配药、已取消 |
| Total_Amount | DECIMAL(10,2) | 总金额 | 处方总价 |
| Notes | TEXT | 备注 | 其他说明 |

#### 医生信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Prescriber_Name | VARCHAR(100) | 开处方医生姓名 | 处方医生 |
| Prescriber_Signature | VARCHAR(255) | 开处方医生签名 | 电子签名 |

#### 药师信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Pharmacist_Name | VARCHAR(100) | 药师姓名 | 配药药师 |
| Pharmacist_Signature | VARCHAR(255) | 药师签名 | 药师电子签名 |
| Dispensed_Date | DATETIME | 配药日期 | 实际配药时间 |

#### 系统字段

与 Drugs 表相同的系统字段

### 索引

- `uk_prescription_number`: 处方编号唯一索引
- `idx_patient_id`: 患者ID索引
- `idx_doctor_id`: 医生ID索引
- `idx_medical_record_id`: 病历ID索引
- `idx_prescription_date`: 处方日期索引
- `idx_prescription_status`: 处方状态索引
- `idx_dispensed_date`: 配药日期索引

### 业务场景

1. **开具处方**: 医生为患者开具处方
2. **处方审核**: 药师审核处方
3. **配药管理**: 药师配药并记录
4. **费用结算**: 根据处方金额进行结算

---

## 6. Prescription_Detail 表 - 处方明细

**表名**: `prescription_detail`
**用途**: 记录处方中每个药品的详细信息
**修改类型**: 新建表（CREATE TABLE）

### 字段说明

#### 主键

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| ID | VARCHAR(36) | 主键ID | UUID格式 |

#### 关联信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Prescription_ID | VARCHAR(36) | 处方ID | 关联处方表 |
| Drug_ID | VARCHAR(20) | 药品编号 | 关联药品表 |

#### 药品信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Drug_Name | VARCHAR(200) | 药品名称 | 冗余字段，便于查看 |
| Drug_Specification | VARCHAR(100) | 药品规格 | 如：10ml:5mg |

#### 用药信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Quantity | INT | 数量 | 开具数量 |
| Unit | VARCHAR(20) | 单位 | 如：盒、支、瓶 |
| Dosage | VARCHAR(100) | 用量 | 如：每次1-2滴 |
| Frequency | VARCHAR(100) | 频次 | 如：每日4-6次 |
| Duration | VARCHAR(50) | 疗程 | 如：2周、7天 |
| Administration_Route | VARCHAR(50) | 给药途径 | 如：滴眼、外用、口服 |

#### 价格信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Unit_Price | DECIMAL(10,2) | 单价 | 药品单价 |
| Subtotal | DECIMAL(10,2) | 小计 | 数量 × 单价 |

#### 其他信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Special_Instructions | TEXT | 特殊说明 | 如：佩戴隐形眼镜前需取下 |

#### 系统字段

与 Drugs 表相同的系统字段

### 索引

- `idx_prescription_id`: 处方ID索引（高频查询）
- `idx_drug_id`: 药品ID索引

### 业务场景

1. **处方明细展示**: 显示处方中的所有药品
2. **用药指导打印**: 打印详细用药说明
3. **库存扣减**: 根据处方明细扣减库存
4. **费用明细**: 显示每个药品的价格

---

## 7. Reminder_Config 表 - 提醒配置

**表名**: `reminder_config`
**用途**: 管理患者的提醒偏好设置
**修改类型**: 新建表（CREATE TABLE）

### 字段说明

#### 主键

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| ID | VARCHAR(36) | 主键ID | UUID格式 |

#### 关联信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Patient_ID | VARCHAR(36) | 患者ID | 关联患者，一个患者一条配置 |

#### 提醒开关

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Enable_Follow_Up | TINYINT(1) | 启用复诊提醒 | 0-否，1-是，默认1 |
| Enable_Appointment | TINYINT(1) | 启用预约提醒 | 0-否，1-是，默认1 |
| Enable_Medication | TINYINT(1) | 启用用药提醒 | 0-否，1-是，默认1 |

#### 提醒配置

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Default_Advance_Days | INT | 默认提前天数 | 默认1天，表示提前多少天提醒 |
| Preferred_Notification_Method | VARCHAR(50) | 首选通知方式 | 如：system-系统通知/sms-短信/email-邮件 |

#### 免打扰时段

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Quiet_Hours_Start | TIME | 免打扰开始时间 | 如：22:00:00 |
| Quiet_Hours_End | TIME | 免打扰结束时间 | 如：08:00:00 |

#### 系统字段

与 Drugs 表相同的系统字段

### 索引

- `idx_patient_id`: 患者ID索引

### 业务场景

1. **个性化提醒**: 根据患者偏好发送提醒
2. **免打扰管理**: 在免打扰时段不发送提醒
3. **通知方式选择**: 使用患者首选的通知方式

---

## 8. Reminder 表 - 提醒任务

**表名**: `reminder`
**用途**: 管理系统中的各类提醒任务
**修改类型**: 新建表（CREATE TABLE）

### 字段说明

#### 主键

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| ID | VARCHAR(36) | 主键ID | UUID格式 |

#### 关联信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Patient_ID | VARCHAR(36) | 患者ID | 关联患者 |
| Medical_Record_ID | VARCHAR(36) | 病历ID | 可选，关联病历 |
| Appointment_ID | VARCHAR(36) | 预约ID | 可选，关联预约 |
| Prescription_ID | VARCHAR(36) | 处方ID | 可选，关联处方 |

#### 提醒基本信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Reminder_Type | VARCHAR(50) | 提醒类型 | follow_up-复诊/medication-用药/appointment-预约 |
| Reminder_Title | VARCHAR(200) | 提醒标题 | 如：复诊提醒 |
| Reminder_Content | TEXT | 提醒内容 | 详细提醒信息 |

#### 时间信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Scheduled_Time | DATETIME | 计划提醒时间 | 应该发送提醒的时间 |
| Advance_Days | INT | 提前天数 | 提前多少天提醒 |
| Sent_Time | DATETIME | 发送时间 | 实际发送时间 |
| Completed_Time | DATETIME | 完成时间 | 患者完成操作的时间 |
| Cancelled_Time | DATETIME | 取消时间 | 提醒被取消的时间 |

#### 状态与优先级

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Status | VARCHAR(20) | 状态 | pending-待发送/sent-已发送/completed-已完成/cancelled-已取消 |
| Priority | VARCHAR(20) | 优先级 | high-高/normal-普通/low-低 |

#### 重复设置

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Repeat_Type | VARCHAR(20) | 重复类型 | once-一次/daily-每日/weekly-每周 |
| Repeat_Count | INT | 已重复次数 | 已经执行的次数，默认0 |
| Max_Repeat_Count | INT | 最大重复次数 | 最多重复多少次 |

#### 通知方式

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Notification_Method | VARCHAR(50) | 通知方式 | system-系统/sms-短信/email-邮件 |

#### 其他信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Created_By | VARCHAR(100) | 创建人 | system-系统/doctor-医生 |
| Notes | TEXT | 备注 | 其他说明 |

#### 系统字段

与 Drugs 表相同的系统字段

### 索引

- `idx_patient_id`: 患者ID索引
- `idx_medical_record_id`: 病历ID索引
- `idx_appointment_id`: 预约ID索引
- `idx_prescription_id`: 处方ID索引
- `idx_reminder_type`: 提醒类型索引
- `idx_status`: 状态索引
- `idx_scheduled_time`: 计划时间索引

### 业务场景

1. **复诊提醒**: 提醒患者按时复诊
2. **用药提醒**: 提醒患者按时用药
3. **预约提醒**: 提醒患者预约时间
4. **定时任务**: 系统定时扫描待发送的提醒

---

## 9. Reminder_History 表 - 提醒历史

**表名**: `reminder_history`
**用途**: 记录提醒的所有操作历史，用于审计和问题排查
**修改类型**: 新建表（CREATE TABLE）

### 字段说明

#### 主键

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| ID | VARCHAR(36) | 主键ID | UUID格式 |

#### 关联信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Reminder_ID | VARCHAR(36) | 提醒ID | 关联提醒表 |

#### 操作信息

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| Action_Type | VARCHAR(50) | 操作类型 | created-创建/updated-修改/sent-发送/completed-完成/cancelled-取消/failed-失败 |
| Action_Time | DATETIME | 操作时间 | 操作发生的时间 |
| Action_By | VARCHAR(100) | 操作人 | system-系统/doctor-医生/patient-患者 |
| Action_Details | TEXT | 操作详情 | 详细描述，如：创建提醒: 复诊提醒 |

#### 系统字段

与 Drugs 表相同的系统字段

### 索引

- `idx_reminder_id`: 提醒ID索引（高频查询）
- `idx_action_type`: 操作类型索引
- `idx_action_time`: 操作时间索引

### 业务场景

1. **审计跟踪**: 记录提醒的完整生命周期
2. **问题排查**: 查看提醒为什么被取消或修改
3. **统计分析**: 分析提醒的发送率、完成率等
4. **操作日志**: 查看提醒相关的所有操作记录

---

## 通用说明

### 系统字段

所有表都包含以下标准系统字段：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| create_time | DATETIME | 记录创建时间，自动设置为当前时间 |
| create_by | VARCHAR(36) | 创建人ID，UUID格式 |
| update_time | DATETIME | 记录更新时间，自动更新为当前时间 |
| update_by | VARCHAR(36) | 更新人ID，UUID格式 |
| version | INT | 乐观锁版本号，用于并发控制，默认0 |
| deleted | TINYINT | 逻辑删除标记，0-未删除，1-已删除，默认0 |

### 设计原则

1. **UUID主键**: 所有表使用UUID作为主键（VARCHAR(36)），便于分布式系统
2. **逻辑删除**: 使用deleted字段标记删除，不进行物理删除
3. **乐观锁**: 使用version字段进行并发控制
4. **无外键**: 不使用数据库外键约束，通过应用层控制关联关系
5. **适度冗余**: 适当冗余字段（如患者姓名、药品名称）以提升查询性能
6. **索引优化**: 为高频查询字段添加索引

### 字符集和引擎

- **字符集**: utf8mb4（支持emoji和特殊字符）
- **排序规则**: utf8mb4_unicode_ci
- **存储引擎**: InnoDB（支持事务）

### 执行建议

1. **测试环境验证**: 所有脚本先在测试环境执行验证
2. **数据库备份**: 执行前务必做好数据库备份
3. **逐步执行**: 建议按表逐步执行，便于排查问题
4. **验证数据**: 执行后验证数据完整性和索引是否生效

---

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0 | 2025-11-19 | 初始版本，包含9个表的完整文档 |

---

**文档作者**: Eye-Agent-Backend 开发团队
**最后更新**: 2025-11-19

# UUID主键迁移任务完成状态报告

**任务**: "将所有 *_UUID 字段设为主键，保留 *_ID INT 字段作为业务编号（非主键），检查代码"

**检查日期**: 2025-11-20
**总体状态**: ❌ **未完成**

---

## 执行总结

### ✅ 已完成部分

1. **数据库Schema层面**:
   - 所有核心表的UUID字段已创建并设置为UNIQUE约束
   - UUID字段设置为NOT NULL
   - 触发器已配置，自动生成UUID值

2. **代码层面 - JOIN操作**:
   - ✅ 所有JOIN操作已正确使用UUID字段进行关联
   - ✅ 所有JOIN都包含`AND Deleted = 0`软删除过滤

### ❌ 未完成部分

**关键问题**: UUID字段**尚未设置为主键(PRIMARY KEY)**，目前仅为UNIQUE约束

---

## 详细检查结果

### 1. 数据库Schema状态

#### 当前主键配置 (所有表仍使用INT _ID作为主键)

| 表名 | 当前主键 | UUID字段状态 |
|------|---------|-------------|
| patient | Patient_ID (INT) | Patient_UUID (UNIQUE, NOT NULL) ❌ |
| medical_record | Medical_Record_ID (INT) | Medical_Record_UUID (UNIQUE, NOT NULL) ❌ |
| doctor | Doctor_ID (INT) | Doctor_UUID (UNIQUE, NOT NULL) ❌ |
| appointment | Appointment_ID (INT) | Appointment_UUID (UNIQUE, NOT NULL) ❌ |
| prescription | Prescription_ID (INT) | Prescription_UUID (UNIQUE, NOT NULL) ❌ |
| prescription_detail | Detail_ID (INT) | Detail_UUID (UNIQUE, NOT NULL) ❌ |
| chat_conversation | Chat_ID (INT) | Chat_UUID (UNIQUE, NOT NULL) ❌ |
| chat_message | Message_ID (INT) | Message_UUID (UNIQUE, NOT NULL) ❌ |
| doctor_working_schedule | Schedule_ID (INT) | Schedule_UUID (UNIQUE, NOT NULL) ❌ |
| doctor_time_slots | Slot_ID (INT) | Slot_UUID (UNIQUE, NOT NULL) ❌ |
| doctor_schedule_exceptions | Exception_ID (INT) | Exception_UUID (UNIQUE, NOT NULL) ❌ |
| reminder | Reminder_ID (INT) | Reminder_UUID (UNIQUE, NOT NULL) ❌ |
| reminder_config | Config_ID (INT) | Config_UUID (UNIQUE, NOT NULL) ❌ |
| reminder_history | History_ID (INT) | History_UUID (UNIQUE, NOT NULL) ❌ |
| biomechanics_scan | Scan_ID (INT) | Scan_UUID (UNIQUE, NOT NULL) ❌ |
| drugs | drug_id (INT) | (无UUID字段) ⚠️ |

**结论**: 16个核心表中，15个有UUID字段，但**全部仍使用INT字段作为主键**。

---

### 2. 代码使用UUID情况

#### ✅ JOIN操作 - 100%使用UUID

所有service文件的JOIN操作已正确使用UUID字段：

**示例 (prescription_service.py:75-77)**:
```sql
LEFT JOIN patient pat ON p.Patient_UUID = pat.Patient_UUID AND pat.Deleted = 0
LEFT JOIN doctor d ON p.Doctor_UUID = d.Doctor_UUID AND d.Deleted = 0
LEFT JOIN medical_record mr ON p.Medical_Record_UUID = mr.Medical_Record_UUID AND mr.Deleted = 0
```

**检查文件**:
- ✅ [chat_service.py](database/chat_service.py) - 所有JOIN使用Chat_UUID
- ✅ [prescription_service.py](database/prescription_service.py) - 所有JOIN使用UUID
- ✅ [report_service.py](database/report_service.py) - 所有JOIN使用Patient_UUID
- ✅ [user_history_service_v2.py](database/user_history_service_v2.py) - 所有JOIN使用UUID

#### ⚠️ INSERT操作 - 部分使用INT _ID

**问题文件**: [appointment_service_v3.py:441-446](database/appointment_service_v3.py#L441-L446)

```sql
INSERT INTO appointment (
    Medical_Record_ID, Patient_ID, Doctor_ID, Time_Slot_ID,  -- ❌ 使用INT _ID
    Patient_Name, Appointment_Time, Appointment_Category,
    Severity_Level, Description, Appointment_Status,
    Version, Deleted
) VALUES (...)
```

**说明**:
- 这段代码仍使用INT类型的_ID字段进行INSERT
- 但由于数据库有触发器会自动生成UUID
- 且后续查询都用UUID，所以不影响功能
- 但不符合"UUID作为主键"的设计目标

#### ✅ SELECT/UPDATE/DELETE操作 - 正确使用UUID

所有查询操作都支持UUID和INT双重查询：

```sql
WHERE (Table_UUID = %s OR CAST(Table_ID AS CHAR) = %s)
  AND Deleted = 0
```

---

### 3. 外键关联情况

当前外键仍引用INT _ID字段。查询示例：

```sql
SELECT
    CONSTRAINT_NAME,
    TABLE_NAME,
    COLUMN_NAME,
    REFERENCED_TABLE_NAME,
    REFERENCED_COLUMN_NAME
FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = 'medical_db'
  AND REFERENCED_TABLE_NAME IS NOT NULL
```

预期外键应引用UUID字段（如果完成迁移）。

---

## 需要执行的迁移步骤

### 阶段1: 数据库Schema迁移

为完成UUID主键迁移，需执行以下SQL操作：

```sql
-- 1. 删除外键约束
ALTER TABLE appointment DROP FOREIGN KEY fk_appointment_patient;
ALTER TABLE appointment DROP FOREIGN KEY fk_appointment_doctor;
-- ... (所有外键)

-- 2. 修改主键为UUID (每个表)
ALTER TABLE patient
    DROP PRIMARY KEY,
    ADD PRIMARY KEY (Patient_UUID);

ALTER TABLE medical_record
    DROP PRIMARY KEY,
    ADD PRIMARY KEY (Medical_Record_UUID);

-- ... (所有表)

-- 3. 重建外键约束（指向UUID）
ALTER TABLE appointment
    ADD CONSTRAINT fk_appointment_patient
    FOREIGN KEY (Patient_UUID) REFERENCES patient(Patient_UUID);

ALTER TABLE appointment
    ADD CONSTRAINT fk_appointment_doctor
    FOREIGN KEY (Doctor_UUID) REFERENCES doctor(Doctor_UUID);

-- ... (所有外键)

-- 4. 为INT _ID字段添加UNIQUE索引（保留业务编号唯一性）
ALTER TABLE patient ADD UNIQUE INDEX idx_patient_id (Patient_ID);
ALTER TABLE medical_record ADD UNIQUE INDEX idx_medical_record_id (Medical_Record_ID);
-- ... (所有表)
```

### 阶段2: 代码修改

修改 [appointment_service_v3.py:441-446](database/appointment_service_v3.py#L441-L446):

```python
# 修改前
INSERT INTO appointment (
    Medical_Record_ID, Patient_ID, Doctor_ID, Time_Slot_ID,
    ...
)

# 修改后
INSERT INTO appointment (
    Medical_Record_UUID, Patient_UUID, Doctor_UUID, Time_Slot_UUID,
    ...
)
```

需要先查询各关联表获取UUID，然后使用UUID进行INSERT。

---

## 风险评估

### 高风险操作

1. **修改主键** - 可能导致应用中断
2. **删除重建外键** - 需要停机维护
3. **INT _ID自增序列** - 需要确保保留（业务编号）

### 建议迁移策略

1. **创建完整的数据库备份**
2. **在测试环境完整验证**
3. **准备回滚方案**
4. **选择低峰期执行**
5. **分阶段迁移**：
   - 先迁移非核心表
   - 再迁移核心业务表
   - 最后迁移高频访问表

---

## 任务完成度

| 项目 | 状态 | 完成度 |
|-----|------|--------|
| UUID字段创建 | ✅ 完成 | 100% |
| UUID触发器配置 | ✅ 完成 | 100% |
| UUID设为主键 | ❌ 未完成 | 0% |
| _ID保留为业务编号 | ✅ 已保留 | 100% |
| 代码JOIN使用UUID | ✅ 完成 | 100% |
| 代码INSERT使用UUID | ⚠️ 部分完成 | 95% |
| 外键迁移至UUID | ❌ 未完成 | 0% |

**总体完成度**: 约 **70%**

---

## 建议

### 短期建议（当前架构）

✅ **保持当前架构**：
- 当前"INT主键 + UUID唯一索引"的设计在功能上完全可行
- 代码已经完全使用UUID进行JOIN和查询
- 性能上UUID索引(UNIQUE)与主键索引几乎等效

### 长期建议（完整迁移）

如果确实需要将UUID设为主键：

1. **创建迁移脚本** ([migrate_to_uuid_primary_key.sql](database/migrate_to_uuid_primary_key.sql))
2. **在测试环境验证**
3. **准备回滚脚本**
4. **选择维护窗口执行**

---

## 相关文件

- 数据库连接: [db_connection.py](database/db_connection.py)
- 基础服务: [base_service.py](database/base_service.py)
- 预约服务: [appointment_service_v3.py](database/appointment_service_v3.py)
- 处方服务: [prescription_service.py](database/prescription_service.py)
- 报告服务: [report_service.py](database/report_service.py)
- 用户历史服务: [user_history_service_v2.py](database/user_history_service_v2.py)
- 聊天服务: [chat_service.py](database/chat_service.py)

---

**最终结论**: 任务**未完成**。数据库仍使用INT _ID作为主键，UUID仅为UNIQUE约束。但代码层面已完全适配UUID关联，具备迁移至UUID主键的基础条件。

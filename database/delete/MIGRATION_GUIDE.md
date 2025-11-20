# 数据库完整迁移指南

## 📋 概述

本指南说明如何将眼科管理系统数据库从当前状态迁移到符合 `tables_documentation.md` 要求的完整UUID架构。

### 迁移目标

1. ✅ 为所有表添加系统管理字段（`Create_By`, `Update_By`, `Version`, `Deleted`）
2. ✅ 扩展 `appointment` 表支持通用日程功能
3. ✅ 完整UUID主键迁移（可选，根据需求）

---

## ⚠️ 重要提示

- **执行前必须备份数据库！**
- **建议先在测试环境执行**
- **预计总耗时：30-40分钟**
- **需要停止应用服务避免并发写入**

---

## 🔍 当前数据库状态分析

### 已有内容
- ✅ 核心表：`patient`, `medical_record`, `doctor`
- ✅ 业务表：`appointment`, `prescription`, `prescription_detail`
- ✅ 辅助表：`reminder`, `reminder_config`, `reminder_history`, `drugs`
- ✅ 时间段管理：`doctor_working_schedule`, `doctor_time_slots`
- ✅ 基本字段：`Created_At`, `Updated_At`

### 缺失内容（与文档对比）
- ❌ 系统管理字段：`Create_By`, `Update_By`, `Version`, `Deleted`
- ❌ `appointment` 表的通用日程字段
- ❌ 完整的 `Agenda` 表功能（使用扩展 `appointment` 表代替）
- ⚠️  UUID主键（部分表已有UUID字段，但仍使用INT主键）

---

## 📝 迁移策略

根据你的需求，我们采用以下策略：

### 1. 主键策略：双字段方案（推荐）
- **保留**：INT AUTO_INCREMENT 主键（`Patient_ID`, `Doctor_ID`等）
- **添加**：UUID字段（`Patient_UUID`, `Doctor_UUID`等）
- **优点**：向后兼容，性能优秀，支持分布式
- **缺点**：需要维护两套ID

### 2. Agenda表策略：扩展appointment表
- 不创建独立的 `agenda` 表
- 在 `appointment` 表中添加字段支持通用日程
- 100% 字段重叠，最小化代码改动

---

## 🚀 执行步骤

### 准备阶段

#### 1. 备份数据库

```bash
# 方法1: 使用mysqldump（推荐）
mysqldump -h localhost -u root -p medical_db > backup_$(date +%Y%m%d_%H%M%S).sql

# 方法2: 使用MySQL Workbench
# Data Export -> Export to Self-Contained File
```

#### 2. 停止应用服务

```bash
# 停止FastAPI应用
# 方法取决于你的部署方式（Ctrl+C / systemctl stop / docker stop等）
```

#### 3. 验证数据库连接

```bash
mysql -h localhost -u root -p medical_db -e "SELECT COUNT(*) FROM patient;"
```

---

### 迁移阶段

#### 方案 A：使用Python自动化脚本（推荐）

```bash
cd d:\Agent\pythonProject1\database
python execute_complete_migration.py
```

**脚本功能**：
- 自动备份数据库
- 按顺序执行所有迁移SQL
- 验证迁移结果
- 生成详细日志

**执行流程**：
1. 添加系统管理字段 + 扩展appointment表
2. Phase 1: UUID迁移 - 核心表（patient, medical_record, doctor）
3. Phase 2: UUID迁移 - 业务表（appointment, prescription等）
4. Phase 3: UUID迁移 - 辅助表（reminder, time_slots等）

---

#### 方案 B：手动执行SQL脚本

如果Python脚本遇到问题，可以手动执行：

**步骤 1：添加系统管理字段**

```sql
source d:/Agent/pythonProject1/database/migrations/add_system_fields_and_extend_appointment.sql
```

**预计时间**：5-10分钟

**执行内容**：
- 为所有15个表添加 `Create_By`, `Update_By`, `Version`, `Deleted` 字段
- 为 `appointment` 表添加 `Is_Generic_Event`, `Event_Type`, `Notes` 字段
- 添加所有必要索引

---

**步骤 2-4：UUID迁移（可选）**

如果需要UUID主键支持，继续执行：

```sql
-- Phase 1: 核心表
source d:/Agent/pythonProject1/database/migrations/phase1_uuid_migration_core_tables.sql

-- Phase 2: 业务表
source d:/Agent/pythonProject1/database/migrations/phase2_uuid_migration_business_tables.sql

-- Phase 3: 辅助表
source d:/Agent/pythonProject1/database/migrations/phase3_uuid_migration_auxiliary_tables.sql
```

**预计时间**：每个阶段 10-15分钟

**执行内容**：
- 为所有表添加 `*_UUID` 字段
- 为现有数据生成UUID
- 同步UUID外键关联
- 添加UUID索引和触发器

---

### 验证阶段

#### 1. 检查系统管理字段

```sql
USE medical_db;

-- 检查所有表的系统字段
SELECT TABLE_NAME, COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'medical_db'
AND COLUMN_NAME IN ('Create_By', 'Update_By', 'Version', 'Deleted')
ORDER BY TABLE_NAME, COLUMN_NAME;

-- 预期结果：每个表都应该有4个字段
```

#### 2. 检查appointment表扩展

```sql
SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_DEFAULT, COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'medical_db'
AND TABLE_NAME = 'appointment'
AND COLUMN_NAME IN ('Is_Generic_Event', 'Event_Type', 'Notes', 'Create_By', 'Update_By', 'Version', 'Deleted');

-- 预期结果：7个字段
```

#### 3. 检查UUID字段（如果执行了UUID迁移）

```sql
SELECT TABLE_NAME, COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'medical_db'
AND COLUMN_NAME LIKE '%_UUID'
ORDER BY TABLE_NAME;

-- 预期结果：每个表都有对应的UUID字段
```

#### 4. 检查数据完整性

```sql
-- 检查patient表
SELECT COUNT(*) AS total_patients,
       SUM(CASE WHEN Patient_UUID IS NOT NULL THEN 1 ELSE 0 END) AS with_uuid,
       SUM(CASE WHEN Deleted = 0 THEN 1 ELSE 0 END) AS active
FROM patient;

-- 检查appointment表
SELECT COUNT(*) AS total_appointments,
       SUM(CASE WHEN Is_Generic_Event = 0 THEN 1 ELSE 0 END) AS patient_appointments,
       SUM(CASE WHEN Is_Generic_Event = 1 THEN 1 ELSE 0 END) AS generic_events
FROM appointment;
```

---

## 🔧 代码适配指南

迁移完成后，需要更新应用代码以使用新字段。

### 1. 系统管理字段使用

#### 数据插入（INSERT）

```python
# 旧代码
cursor.execute("""
    INSERT INTO patient (Name, Phone_Number, Age)
    VALUES (%s, %s, %s)
""", (name, phone, age))

# 新代码
import uuid

current_user_uuid = "user-uuid-here"  # 从session获取

cursor.execute("""
    INSERT INTO patient (Name, Phone_Number, Age, Create_By, Version, Deleted)
    VALUES (%s, %s, %s, %s, 0, 0)
""", (name, phone, age, current_user_uuid))
```

#### 数据更新（UPDATE）

```python
# 旧代码
cursor.execute("""
    UPDATE patient SET Name = %s WHERE Patient_ID = %s
""", (new_name, patient_id))

# 新代码
cursor.execute("""
    UPDATE patient
    SET Name = %s,
        Update_By = %s,
        Version = Version + 1
    WHERE Patient_ID = %s
      AND Deleted = 0
      AND Version = %s  -- 乐观锁检查
""", (new_name, current_user_uuid, patient_id, old_version))

# 检查affected_rows判断是否并发冲突
if cursor.rowcount == 0:
    raise ConcurrencyError("数据已被其他用户修改")
```

#### 数据删除（DELETE）

```python
# 旧代码
cursor.execute("DELETE FROM patient WHERE Patient_ID = %s", (patient_id,))

# 新代码 - 逻辑删除
cursor.execute("""
    UPDATE patient
    SET Deleted = 1,
        Update_By = %s
    WHERE Patient_ID = %s
      AND Deleted = 0
""", (current_user_uuid, patient_id))
```

#### 数据查询（SELECT）

```python
# 旧代码
cursor.execute("SELECT * FROM patient WHERE Patient_ID = %s", (patient_id,))

# 新代码 - 添加Deleted过滤
cursor.execute("""
    SELECT * FROM patient
    WHERE Patient_ID = %s
      AND Deleted = 0
""", (patient_id,))
```

---

### 2. UUID字段使用（如果执行了UUID迁移）

#### 创建新记录时使用UUID

```python
import uuid

# 生成UUID
patient_uuid = str(uuid.uuid4())

cursor.execute("""
    INSERT INTO patient (Patient_UUID, Name, Phone_Number, Create_By, Deleted)
    VALUES (%s, %s, %s, %s, 0)
""", (patient_uuid, name, phone, current_user_uuid))

# 注意：INT主键会自动生成，UUID主键需要手动生成
```

#### 支持双主键查询

```python
def get_patient(patient_id=None, patient_uuid=None):
    """根据INT ID或UUID查询患者"""
    if patient_uuid:
        cursor.execute("""
            SELECT * FROM patient
            WHERE Patient_UUID = %s AND Deleted = 0
        """, (patient_uuid,))
    elif patient_id:
        cursor.execute("""
            SELECT * FROM patient
            WHERE Patient_ID = %s AND Deleted = 0
        """, (patient_id,))
    else:
        raise ValueError("Must provide patient_id or patient_uuid")

    return cursor.fetchone()
```

---

### 3. appointment表通用日程功能

#### 创建患者预约

```python
cursor.execute("""
    INSERT INTO appointment (
        Patient_ID, Doctor_ID, Medical_Record_ID,
        Appointment_Time, Description,
        Is_Generic_Event, Event_Type,
        Create_By, Version, Deleted
    ) VALUES (%s, %s, %s, %s, %s, FALSE, 'appointment', %s, 0, 0)
""", (patient_id, doctor_id, record_id, appointment_time, desc, current_user_uuid))
```

#### 创建医生个人日程

```python
cursor.execute("""
    INSERT INTO appointment (
        Doctor_ID, Appointment_Time, Description,
        Is_Generic_Event, Event_Type, Notes,
        Create_By, Version, Deleted
    ) VALUES (%s, %s, %s, TRUE, 'meeting', %s, %s, 0, 0)
""", (doctor_id, event_time, title, notes, current_user_uuid))

# 注意：通用日程事件不需要Patient_ID和Medical_Record_ID
```

#### 查询医生所有日程（包括预约和个人日程）

```python
cursor.execute("""
    SELECT *
    FROM appointment
    WHERE Doctor_ID = %s
      AND Deleted = 0
      AND Appointment_Time >= %s
    ORDER BY Appointment_Time ASC
""", (doctor_id, start_date))

# 结果包含患者预约（Is_Generic_Event=0）和个人日程（Is_Generic_Event=1）
```

---

## 🔙 回滚方案

如果迁移出现问题，可以回滚：

### 方案 A：恢复数据库备份（推荐）

```bash
mysql -h localhost -u root -p medical_db < backup_YYYYMMDD_HHMMSS.sql
```

### 方案 B：执行回滚脚本

```sql
-- 回滚系统管理字段和appointment扩展
source d:/Agent/pythonProject1/database/migrations/rollback_system_fields_and_appointment.sql

-- 回滚UUID迁移
source d:/Agent/pythonProject1/database/migrations/rollback_uuid_migration.sql
```

---

## 📊 迁移检查清单

### 迁移前
- [ ] 已备份数据库
- [ ] 已停止应用服务
- [ ] 已在测试环境验证
- [ ] 已通知相关人员
- [ ] 已准备回滚方案

### 迁移后
- [ ] 系统管理字段已添加到所有表
- [ ] appointment表通用日程字段已添加
- [ ] UUID字段已添加（如果需要）
- [ ] 所有索引已创建
- [ ] 数据完整性验证通过
- [ ] 应用代码已更新
- [ ] 功能测试通过
- [ ] 性能测试通过

---

## 🛠️ 常见问题

### Q1: 迁移过程中断怎么办？

**答**：每个阶段的脚本都是独立的，可以重复执行。脚本会检查字段/索引是否已存在，避免重复添加。

### Q2: 如何确定是否需要UUID迁移？

**答**：
- 如果系统仅单机部署，不需要分布式ID，可以跳过UUID迁移
- 如果需要对外提供API，建议执行UUID迁移（UUID更安全，不暴露业务量）
- 如果需要微服务化或分库分表，必须执行UUID迁移

### Q3: Version字段如何使用？

**答**：乐观锁机制，防止并发更新冲突：
```sql
-- UPDATE时检查版本号
UPDATE patient
SET Name = 'new_name', Version = Version + 1
WHERE Patient_ID = 123 AND Version = 5;

-- 如果Version不匹配（被其他事务修改），affected_rows=0
```

### Q4: Deleted字段能否使用其他值？

**答**：可以扩展为多状态：
- `0` = 正常
- `1` = 已删除
- `2` = 归档（可选）

但需要更新所有SQL的WHERE条件。

### Q5: 是否需要外键约束？

**答**：文档要求"不使用数据库外键约束"，改为应用层控制。理由：
- 提升性能（减少锁等待）
- 简化分库分表
- 灵活处理级联删除

当前数据库有外键，建议保留（除非遇到性能问题）。

---

## 📚 相关文档

- [tables_documentation.md](../tables_documentation.md) - 数据库表结构详细说明
- [CLAUDE.md](../CLAUDE.md) - 项目架构和开发指南
- [database_init_complete.sql](../database/database_init_complete.sql) - 当前数据库结构

---

## 📞 支持

如遇到问题，请：
1. 查看迁移日志：`logs/migration_YYYYMMDD_HHMMSS.log`
2. 检查MySQL错误日志
3. 联系开发团队

---

**最后更新**: 2025-11-20
**版本**: 1.0
**状态**: Ready for Production

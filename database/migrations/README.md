# 数据库迁移脚本集合

## 📁 文件列表

### 主要迁移脚本

| 文件名 | 说明 | 执行时间 | 前置条件 |
|--------|------|---------|---------|
| `add_system_fields_and_extend_appointment.sql` | **核心迁移脚本**<br>- 添加系统管理字段<br>- 扩展appointment表 | 5-10分钟 | 无 |
| `phase1_uuid_migration_core_tables.sql` | UUID迁移-核心表<br>(patient, medical_record, doctor) | 10-15分钟 | 无 |
| `phase2_uuid_migration_business_tables.sql` | UUID迁移-业务表<br>(appointment, prescription等) | 15-20分钟 | Phase 1完成 |
| `phase3_uuid_migration_auxiliary_tables.sql` | UUID迁移-辅助表<br>(reminder, time_slots等) | 10-15分钟 | Phase 1-2完成 |

### 回滚脚本

| 文件名 | 说明 | 用途 |
|--------|------|------|
| `rollback_system_fields_and_appointment.sql` | 回滚系统字段和appointment扩展 | 撤销主迁移 |
| `rollback_uuid_migration.sql` | 回滚UUID迁移 | 撤销UUID迁移 |

### 已弃用/存档

| 文件名 | 状态 | 说明 |
|--------|------|------|
| `complete_uuid_only_migration.sql` | ⚠️ 草稿 | 初期设计，已被分阶段脚本替代 |

---

## 🚀 快速开始

### 场景1：只需要系统管理字段（推荐大多数用户）

```bash
# 1. 备份数据库
mysqldump -h localhost -u root -p medical_db > backup.sql

# 2. 执行核心迁移
mysql -h localhost -u root -p medical_db < add_system_fields_and_extend_appointment.sql

# 3. 验证
cd ..
python verify_migration.py
```

**结果**：
- ✅ 所有表添加：Create_By, Update_By, Version, Deleted
- ✅ appointment表扩展：Is_Generic_Event, Event_Type, Notes
- ✅ 所有必要索引

---

### 场景2：需要完整UUID支持

```bash
# 使用自动化脚本
cd ..
python execute_complete_migration.py
```

或手动执行：

```bash
# 1. 备份
mysqldump -h localhost -u root -p medical_db > backup.sql

# 2. 按顺序执行
mysql -h localhost -u root -p medical_db < add_system_fields_and_extend_appointment.sql
mysql -h localhost -u root -p medical_db < phase1_uuid_migration_core_tables.sql
mysql -h localhost -u root -p medical_db < phase2_uuid_migration_business_tables.sql
mysql -h localhost -u root -p medical_db < phase3_uuid_migration_auxiliary_tables.sql

# 3. 验证
cd ..
python verify_migration.py
```

---

## 📋 迁移内容详解

### add_system_fields_and_extend_appointment.sql

#### 添加的系统管理字段

所有以下表都会添加4个字段（reminder表只添加3个）：

```sql
Create_By    VARCHAR(36)  -- 创建人UUID
Update_By    VARCHAR(36)  -- 更新人UUID
Version      INT          -- 乐观锁版本号
Deleted      TINYINT      -- 逻辑删除标记 (0=正常, 1=已删除)
```

**受影响的表**（16个）：
- patient
- medical_record
- doctor
- drugs
- prescription
- prescription_detail
- appointment
- reminder (只有Update_By, Version, Deleted)
- reminder_config
- reminder_history (额外添加Create_Time, Update_Time)
- doctor_working_schedule
- doctor_time_slots
- doctor_schedule_exceptions
- biomechanics_scan
- chat_conversation
- chat_message

#### appointment表通用日程扩展

新增3个字段支持通用日程功能：

```sql
Is_Generic_Event  BOOLEAN      DEFAULT FALSE  -- 是否为通用事件
Event_Type        VARCHAR(50)  DEFAULT 'appointment'  -- 事件类型
Notes             TEXT                        -- 备注
```

**用途**：
- `Is_Generic_Event = FALSE`: 患者预约（原有功能）
- `Is_Generic_Event = TRUE`: 医生个人日程（新功能）

---

### UUID迁移脚本（Phase 1-3）

#### 迁移策略：双字段方案

- **保留**：INT AUTO_INCREMENT 主键（Patient_ID, Doctor_ID等）
- **添加**：UUID字段（Patient_UUID, Doctor_UUID等）
- **优势**：
  - 向后兼容（现有代码继续工作）
  - 高性能（INT JOIN优于VARCHAR JOIN）
  - 支持分布式（UUID可用于对外API）

#### Phase 1: 核心表

| 表名 | 添加的UUID字段 |
|------|---------------|
| patient | Patient_UUID |
| medical_record | Medical_Record_UUID, Patient_UUID |
| doctor | Doctor_UUID |

#### Phase 2: 业务表

| 表名 | 添加的UUID字段 |
|------|---------------|
| appointment | Appointment_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID |
| prescription | Prescription_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID |
| prescription_detail | Detail_UUID, Prescription_UUID |
| chat_conversation | Chat_UUID, Patient_UUID, Doctor_UUID |
| chat_message | Message_UUID, Chat_UUID |

#### Phase 3: 辅助表

| 表名 | 添加的UUID字段 |
|------|---------------|
| doctor_working_schedule | Schedule_UUID, Doctor_UUID |
| doctor_time_slots | Slot_UUID, Doctor_UUID |
| doctor_schedule_exceptions | Exception_UUID, Doctor_UUID |
| reminder | Reminder_UUID, Patient_UUID, Medical_Record_UUID, Appointment_UUID, Prescription_UUID |
| reminder_history | History_UUID, Reminder_UUID |
| reminder_config | Config_UUID, Patient_UUID |
| biomechanics_scan | Scan_UUID, Patient_UUID, Medical_Record_UUID |

---

## 🔒 安全特性

### 1. 可重复执行

所有脚本使用存储过程检查列/索引是否存在，可安全重复执行：

```sql
CALL add_column_if_not_exists('patient', 'Create_By', 'VARCHAR(36)');
```

### 2. 事务保护

脚本禁用外键检查，但每个操作都会提交：

```sql
SET FOREIGN_KEY_CHECKS = 0;
-- ... 迁移操作 ...
SET FOREIGN_KEY_CHECKS = 1;
```

### 3. 数据验证

每个阶段都包含验证查询：

```sql
SELECT COUNT(*) FROM patient WHERE Patient_UUID IS NOT NULL;
```

---

## 📊 性能影响

### 执行时间估算

| 数据量 | add_system_fields | UUID Phase 1-3 | 总计 |
|--------|------------------|----------------|------|
| 小（<1万条） | 2-3分钟 | 10-15分钟 | 15-20分钟 |
| 中（1-10万条） | 5-8分钟 | 20-30分钟 | 30-40分钟 |
| 大（>10万条） | 10-15分钟 | 40-60分钟 | 60-80分钟 |

### 存储空间增加

| 项目 | 每表增加 | 总增加（16表） |
|------|---------|---------------|
| 系统字段 | ~50 bytes/row | ~800 bytes/row |
| UUID字段 | ~36 bytes/UUID | ~200 bytes/row |
| 索引 | ~15% table size | ~25% table size |

---

## 🔙 回滚方案

### 完整回滚

```bash
# 方法1：恢复备份（推荐）
mysql -h localhost -u root -p medical_db < backup.sql

# 方法2：执行回滚脚本
mysql -h localhost -u root -p medical_db < rollback_system_fields_and_appointment.sql
mysql -h localhost -u root -p medical_db < rollback_uuid_migration.sql
```

### 部分回滚

如果只想回滚UUID迁移，保留系统字段：

```bash
mysql -h localhost -u root -p medical_db < rollback_uuid_migration.sql
```

---

## ❗ 注意事项

### 执行前

- ✅ **必须**备份数据库
- ✅ **建议**在测试环境先执行
- ✅ **应该**停止应用服务（避免并发写入）
- ✅ **确保**数据库连接配置正确

### 执行中

- ⏸️  不要中断脚本执行
- 👀 观察输出信息（SELECT语句的结果）
- 📝 保存执行日志

### 执行后

- ✅ 运行验证脚本：`python verify_migration.py`
- ✅ 检查应用日志
- ✅ 进行功能测试
- ✅ 监控数据库性能

---

## 📚 相关文档

- [QUICK_START.md](../QUICK_START.md) - 快速开始指南
- [MIGRATION_GUIDE.md](../MIGRATION_GUIDE.md) - 完整迁移文档
- [tables_documentation.md](../../tables_documentation.md) - 表结构文档

---

## 🆘 故障排查

### 问题1：列已存在错误

**现象**：
```
ERROR 1060: Duplicate column name 'Create_By'
```

**解决**：
- 脚本已包含检查逻辑，应该不会出现
- 如果出现，说明部分迁移已完成，可继续执行

### 问题2：内存不足

**现象**：
```
ERROR 1041: Out of memory
```

**解决**：
```sql
-- 分批执行UUID生成
UPDATE patient SET Patient_UUID = UUID() WHERE Patient_UUID IS NULL LIMIT 1000;
-- 重复执行直到全部完成
```

### 问题3：执行超时

**现象**：
```
ERROR 2013: Lost connection to MySQL server during query
```

**解决**：
```sql
-- 增加超时时间
SET SESSION wait_timeout = 28800;
SET SESSION interactive_timeout = 28800;
```

---

**版本**: 1.0
**最后更新**: 2025-11-20
**维护者**: Eye-Agent-Backend 开发团队

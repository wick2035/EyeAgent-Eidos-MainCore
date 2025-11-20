# UUID迁移完整指南

> **创建日期**: 2025-11-20
> **版本**: 1.0
> **迁移策略**: 零停机时间 + 分阶段执行

---

## 📋 目录

1. [迁移概述](#迁移概述)
2. [迁移策略](#迁移策略)
3. [已创建的文件](#已创建的文件)
4. [执行步骤](#执行步骤)
5. [代码更新指南](#代码更新指南)
6. [测试验证](#测试验证)
7. [回滚方案](#回滚方案)
8. [常见问题](#常见问题)

---

## 迁移概述

### 背景

当前medical_db数据库中的所有表都使用 `INT AUTO_INCREMENT` 作为主键。为了实现更好的扩展性、分布式支持和跨系统兼容性,需要将主键迁移为UUID格式。

### 迁移范围

**总计15个表需要迁移:**

**第一阶段 - 核心表(3个):**
- `patient`: Patient_ID → Patient_UUID
- `medical_record`: Medical_Record_ID → Medical_Record_UUID
- `doctor`: Doctor_ID → Doctor_UUID

**第二阶段 - 业务表(5个):**
- `appointment`: Appointment_ID → Appointment_UUID
- `prescription`: Prescription_ID → Prescription_UUID
- `prescription_detail`: Detail_ID → Detail_UUID
- `chat_conversation`: Chat_ID → Chat_UUID
- `chat_message`: Message_ID → Message_UUID

**第三阶段 - 辅助表(7个):**
- `doctor_working_schedule`: Schedule_ID → Schedule_UUID
- `doctor_time_slots`: Slot_ID → Slot_UUID
- `doctor_schedule_exceptions`: Exception_ID → Exception_UUID
- `reminder`: Reminder_ID → Reminder_UUID
- `reminder_history`: History_ID → History_UUID
- `reminder_config`: Config_ID → Config_UUID
- `biomechanics_scan`: Scan_ID → Scan_UUID

### UUID格式

- **存储格式**: `CHAR(36)`
- **示例**: `550e8400-e29b-41d4-a716-446655440000`
- **生成方法**: MySQL `UUID()` 函数 / Python `uuid.uuid4()`

### 保留的自定义ID格式

以下字段**不迁移为UUID**,保持人类可读格式:
- `drugs.drug_id` (格式: `EYD0001`)
- `Prescription_Number` (格式: `RX20251117001`)
- `Visit_Card_Number` (格式: `2025-000001`)
- `Report_ID` (格式: `FILE-2025-00005`)

---

## 迁移策略

### 核心原则

✅ **零停机时间** - 添加UUID列而不删除旧INT列
✅ **分阶段执行** - 三个阶段独立可回滚
✅ **向后兼容** - 保留INT列30天作为过渡期
✅ **触发器支持** - 自动为新记录生成UUID
✅ **外键同步** - 自动维护UUID外键关联

### 迁移流程

```
┌─────────────────┐
│ 第一阶段:核心表  │ → patient, medical_record, doctor
└────────┬────────┘
         ↓
┌─────────────────┐
│ 第二阶段:业务表  │ → appointment, prescription, chat
└────────┬────────┘
         ↓
┌─────────────────┐
│ 第三阶段:辅助表  │ → reminders, time_slots, biomechanics
└────────┬────────┘
         ↓
┌─────────────────┐
│  验证&监控30天  │
└────────┬────────┘
         ↓
┌─────────────────┐
│ 最终切换(可选)  │ → 删除旧INT列,UUID成为唯一主键
└─────────────────┘
```

---

## 已创建的文件

### 1. SQL迁移脚本

| 文件 | 位置 | 用途 |
|------|------|------|
| `phase1_uuid_migration_core_tables.sql` | `database/migrations/` | 迁移核心表(patient, medical_record, doctor) |
| `phase2_uuid_migration_business_tables.sql` | `database/migrations/` | 迁移业务表(appointment, prescription, chat等) |
| `phase3_uuid_migration_auxiliary_tables.sql` | `database/migrations/` | 迁移辅助表(reminders, time_slots等) |
| `rollback_uuid_migration.sql` | `database/migrations/` | 回滚所有UUID更改 |

### 2. Python工具

| 文件 | 位置 | 用途 |
|------|------|------|
| `base_service.py` | `database/` | UUID生成、验证和兼容性工具类 |
| `execute_uuid_migration.py` | `database/` | 自动执行迁移的Python脚本 |

### 3. 文档

| 文件 | 位置 | 用途 |
|------|------|------|
| `UUID_MIGRATION_GUIDE.md` | `Instruction Manual/` | 完整迁移指南(本文档) |

---

## 执行步骤

### 方式一: 使用Python自动脚本(推荐)

```bash
# 1. 执行所有阶段迁移
python database/execute_uuid_migration.py --phase all

# 2. 或分阶段执行
python database/execute_uuid_migration.py --phase 1  # 核心表
python database/execute_uuid_migration.py --phase 2  # 业务表
python database/execute_uuid_migration.py --phase 3  # 辅助表

# 3. 验证迁移状态
python database/execute_uuid_migration.py --verify

# 4. 如需回滚
python database/execute_uuid_migration.py --rollback
```

### 方式二: 手动执行SQL

```bash
# Windows (MySQL命令行)
cd d:\Agent\pythonProject1\database\migrations

# 执行第一阶段
mysql -u root -p medical_db < phase1_uuid_migration_core_tables.sql

# 执行第二阶段
mysql -u root -p medical_db < phase2_uuid_migration_business_tables.sql

# 执行第三阶段
mysql -u root -p medical_db < phase3_uuid_migration_auxiliary_tables.sql

# 如需回滚
mysql -u root -p medical_db < rollback_uuid_migration.sql
```

### 迁移后验证

```sql
-- 连接到数据库
mysql -u root -p medical_db

-- 查看迁移日志
SELECT phase, table_name, records_migrated, status, completed_at
FROM _uuid_migration_log
WHERE status = 'completed'
ORDER BY completed_at;

-- 检查UUID列是否存在
SHOW COLUMNS FROM patient LIKE '%UUID%';
SHOW COLUMNS FROM appointment LIKE '%UUID%';

-- 验证数据完整性
SELECT
    COUNT(*) as total_patients,
    SUM(CASE WHEN Patient_UUID IS NOT NULL THEN 1 ELSE 0 END) as with_uuid
FROM patient;

-- 验证外键关联
SELECT
    COUNT(*) as total_records,
    SUM(CASE WHEN mr.Patient_UUID = p.Patient_UUID THEN 1 ELSE 0 END) as matched_uuids
FROM medical_record mr
INNER JOIN patient p ON mr.Patient_ID = p.Patient_ID;
```

---

## 代码更新指南

### 数据库服务层更新

所有数据库服务类都需要更新以支持UUID参数。以下是需要修改的文件清单:

#### 核心服务(高优先级)

1. **database/user_history_service_v2.py**
   - 修改方法签名接受UUID参数
   - 示例:
     ```python
     from database.base_service import BaseServiceWithUUID, normalize_id

     class UserHistoryServiceV2(BaseServiceWithUUID):
         def get_user_by_id(self, patient_id: Union[str, int]) -> Optional[Dict[str, Any]]:
             # 规范化ID(兼容INT和UUID)
             patient_id = normalize_id(patient_id)

             # 优先使用UUID查询
             query = """
                 SELECT * FROM patient
                 WHERE Patient_UUID = %s OR Patient_ID = %s
             """
             return self.db.execute_one(query, (patient_id, patient_id))
     ```

2. **database/appointment_service_v3.py**
   - 更新 `create_or_get_patient()` 返回UUID
   - 更新 `create_appointment()` 接受UUID参数
   - 示例:
     ```python
     def create_or_get_patient(self, patient_info: Dict) -> str:  # 返回UUID
         # ... 原有逻辑 ...
         # 返回Patient_UUID而非Patient_ID
         return existing_user['Patient_UUID']
     ```

3. **database/prescription_service.py**
   - 更新 `get_prescription_full()` 接受UUID
   - 返回数据包含UUID字段

4. **database/chat_service.py**
   - 更新 `create_chat_for_patient()` 接受UUID
   - 更新 `save_message()` 使用Chat_UUID

#### 辅助服务

5. **database/report_service.py**
6. **database/reminder_service.py**
7. **database/time_slot_service.py**
8. **database/doctor_schedule_service.py**
9. **database/biomechanics_service.py**

### Agent层更新

#### agents/agent_1.py (HealthAgent)

```python
from database.base_service import generate_uuid

class HealthAgent:
    def __init__(self, user_id=None, phone_number=None, role="patient"):
        # user_id现在可以是INT或UUID
        self.user_id = user_id  # 可以是UUID字符串
        # ... 原有代码 ...
```

#### agents/agent_2.py (ReportAgent)

```python
# 更新所有patient_id、medical_record_id参数为UUID兼容
```

#### agents/agent_manager.py

```python
# 更新agent实例化时传递的ID参数
```

### API路由层更新 (main.py)

```python
from database.base_service import is_valid_uuid, normalize_id
from fastapi import HTTPException

@app.post("/api/chat")
async def chat_endpoint(request: dict):
    # 获取patient_id(可能是INT或UUID)
    patient_id = request.get("patient_id")

    # 如果提供了ID,验证格式
    if patient_id:
        try:
            patient_id = normalize_id(patient_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # 使用phone_number作为主要标识(推荐)
    phone = request.get("phone_number")
    user = user_service.get_user_by_phone(phone)

    # 使用UUID
    agent = HealthAgent(
        user_id=user['Patient_UUID'],  # 使用UUID
        phone_number=phone,
        role="patient"
    )
```

### 文档生成器更新

#### utils/report_generator.py

```python
from database.base_service import normalize_id

def generate_medical_report(medical_record_id: Union[str, int]) -> str:
    # 规范化ID
    medical_record_id = normalize_id(medical_record_id)

    # 查询时同时支持INT和UUID
    query = """
        SELECT * FROM medical_record
        WHERE Medical_Record_UUID = %s OR Medical_Record_ID = %s
    """
```

#### utils/prescription_generator.py

```python
def generate_prescription_pdf(prescription_id: Union[str, int]) -> str:
    prescription_id = normalize_id(prescription_id)
    # ... 原有逻辑 ...
```

### 代码更新优先级

| 优先级 | 文件 | 原因 |
|--------|------|------|
| **P0** | base_service.py | 已完成 - 提供UUID工具 |
| **P1** | user_history_service_v2.py | 核心用户查询 |
| **P1** | appointment_service_v3.py | 核心预约功能 |
| **P1** | chat_service.py | 聊天历史记录 |
| **P2** | prescription_service.py | 处方查询 |
| **P2** | agent_1.py, agent_2.py | Agent兼容性 |
| **P3** | main.py | API层兼容性 |
| **P3** | 其他服务文件 | 辅助功能 |

---

## 测试验证

### 单元测试脚本

创建 `test/test_uuid_migration.py`:

```python
import pytest
from database.base_service import generate_uuid, is_valid_uuid, normalize_id
from database.user_history_service_v2 import UserHistoryServiceV2

class TestUUIDMigration:
    """UUID迁移测试"""

    def test_uuid_generation(self):
        """测试UUID生成"""
        uuid1 = generate_uuid()
        uuid2 = generate_uuid()

        assert is_valid_uuid(uuid1)
        assert is_valid_uuid(uuid2)
        assert uuid1 != uuid2

    def test_uuid_validation(self):
        """测试UUID验证"""
        assert is_valid_uuid("550e8400-e29b-41d4-a716-446655440000") == True
        assert is_valid_uuid("invalid-uuid") == False
        assert is_valid_uuid("123") == False

    def test_id_normalization(self):
        """测试ID规范化"""
        # INT ID
        assert normalize_id(123) == "123"

        # UUID
        uuid = "550e8400-e29b-41d4-a716-446655440000"
        assert normalize_id(uuid) == uuid.lower()

        # 数字字符串
        assert normalize_id("456") == "456"

    def test_user_query_with_uuid(self):
        """测试使用UUID查询用户"""
        service = UserHistoryServiceV2()

        # 假设数据库中已有UUID
        user = service.get_user_by_phone("13800138000")
        if user and user.get('Patient_UUID'):
            # 使用UUID查询
            user_by_uuid = service.get_user_by_id(user['Patient_UUID'])
            assert user_by_uuid is not None
            assert user_by_uuid['Patient_UUID'] == user['Patient_UUID']

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

### 集成测试清单

- [ ] 用户创建 (patient表UUID生成)
- [ ] 病例创建 (medical_record表UUID + 外键同步)
- [ ] 预约创建 (appointment表UUID + 多外键同步)
- [ ] 处方生成 (prescription表UUID)
- [ ] 聊天记录 (chat_conversation + chat_message UUID)
- [ ] 文档生成 (report/prescription使用UUID查询)
- [ ] API端点 (所有/api/*路由兼容UUID参数)

### 性能测试

```sql
-- 测试UUID索引性能
EXPLAIN SELECT * FROM patient WHERE Patient_UUID = '550e8400-e29b-41d4-a716-446655440000';

-- 对比INT索引性能
EXPLAIN SELECT * FROM patient WHERE Patient_ID = 1;

-- 外键JOIN性能
EXPLAIN SELECT mr.*, p.Name
FROM medical_record mr
INNER JOIN patient p ON mr.Patient_UUID = p.Patient_UUID
WHERE mr.Patient_UUID = '550e8400-e29b-41d4-a716-446655440000';
```

---

## 回滚方案

### 何时需要回滚

- 迁移过程中遇到数据完整性问题
- 应用程序兼容性问题严重
- UUID性能不符合预期
- 需要回退到稳定版本

### 回滚步骤

```bash
# 方式一: Python脚本
python database/execute_uuid_migration.py --rollback

# 方式二: 手动SQL
mysql -u root -p medical_db < database/migrations/rollback_uuid_migration.sql
```

### 回滚验证

```sql
-- 检查UUID列是否已删除
SELECT COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'medical_db'
  AND COLUMN_NAME LIKE '%UUID%';
-- 应返回0行

-- 检查迁移日志表是否已删除
SHOW TABLES LIKE '_uuid_migration_log';
-- 应返回0行

-- 验证INT主键正常
SELECT Patient_ID, Name FROM patient LIMIT 5;
```

### 回滚后注意事项

⚠️ 回滚后,在迁移期间创建的新记录的INT ID会保留
⚠️ 确保应用程序代码已恢复为使用INT ID的版本
⚠️ 重新迁移前需要解决导致回滚的原因

---

## 常见问题

### Q1: 迁移会导致停机吗?

**A:** 不会。我们采用的是"添加列"策略,不删除旧INT主键,零停机时间。

### Q2: 旧的INT ID还能继续使用吗?

**A:** 可以。在过渡期(建议30天)内,INT和UUID都有效。代码可以同时支持两种ID格式。

### Q3: UUID会影响性能吗?

**A:**
- **存储**: UUID(36字节) vs INT(4字节),增加约8倍空间
- **索引**: CHAR(36)索引稍慢于INT,但可接受
- **查询**: 建议使用BINARY(16)存储UUID可优化性能,但本方案选择CHAR(36)以保持可读性

### Q4: 如何处理外键关联?

**A:** 迁移脚本已自动处理所有外键UUID同步。每个外键都有对应的UUID列(如Patient_UUID, Doctor_UUID)。

### Q5: 什么时候可以删除旧INT列?

**A:** 建议在以下条件满足后:
1. 所有代码已更新为使用UUID
2. 生产环境运行30天无问题
3. 确认无外部系统依赖INT ID
4. 完成充分测试和备份

### Q6: 如何处理已有的自定义ID格式(如drug_id)?

**A:** 保留不变。以下字段保持人类可读格式:
- `drugs.drug_id` = 'EYD0001'
- `Prescription_Number` = 'RX20251117001'
- `Visit_Card_Number` = '2025-000001'

### Q7: 触发器会自动生成UUID吗?

**A:** 是的。所有表都有BEFORE INSERT触发器,自动为新记录生成UUID并同步外键UUID。

### Q8: 如何在Python代码中生成UUID?

**A:**
```python
from database.base_service import generate_uuid

# 生成新UUID
new_uuid = generate_uuid()

# 验证UUID
from database.base_service import is_valid_uuid
if is_valid_uuid(user_input):
    # ... 使用UUID ...

# 兼容INT和UUID
from database.base_service import normalize_id
normalized_id = normalize_id(user_input)  # 自动处理INT/UUID
```

### Q9: 迁移日志在哪里查看?

**A:**
```sql
-- 查看所有迁移记录
SELECT * FROM _uuid_migration_log ORDER BY completed_at DESC;

-- 查看各阶段统计
SELECT phase, COUNT(*) as tables, SUM(records_migrated) as records
FROM _uuid_migration_log
WHERE status = 'completed'
GROUP BY phase;
```

### Q10: 如何测试迁移成功?

**A:**
```bash
# 使用验证脚本
python database/execute_uuid_migration.py --verify

# 手动验证
mysql -u root -p medical_db -e "
SELECT table_name, records_migrated, status
FROM _uuid_migration_log
WHERE status = 'completed';
"
```

---

## 迁移时间表(建议)

### 第1周: 准备阶段
- ✅ 创建迁移脚本 (已完成)
- ✅ 创建工具类 (已完成)
- ⏳ 代码审查
- ⏳ 测试环境验证

### 第2周: 数据库迁移
- ⏳ 执行第一阶段(核心表)
- ⏳ 验证数据完整性
- ⏳ 执行第二阶段(业务表)
- ⏳ 执行第三阶段(辅助表)

### 第3-4周: 代码更新
- ⏳ 更新数据库服务层
- ⏳ 更新Agent层
- ⏳ 更新API层
- ⏳ 单元测试

### 第5周: 集成测试
- ⏳ 功能测试
- ⏳ 性能测试
- ⏳ 用户验收测试

### 第6-10周: 监控期
- ⏳ 生产环境监控
- ⏳ 收集反馈
- ⏳ 性能优化

### 第11周: 清理(可选)
- ⏳ 删除旧INT列
- ⏳ 清理_migration_flag
- ⏳ 更新文档

---

## 技术支持

### 日志查看

```bash
# Python应用日志
tail -f logs/application.log

# MySQL慢查询日志
tail -f /var/log/mysql/mysql-slow.log
```

### 联系方式

如遇到问题,请:
1. 查看本文档的[常见问题](#常见问题)章节
2. 检查迁移日志表: `SELECT * FROM _uuid_migration_log`
3. 查看MySQL错误日志: `/var/log/mysql/error.log`

---

## 附录

### A. 文件清单

```
database/
├── migrations/
│   ├── phase1_uuid_migration_core_tables.sql
│   ├── phase2_uuid_migration_business_tables.sql
│   ├── phase3_uuid_migration_auxiliary_tables.sql
│   └── rollback_uuid_migration.sql
├── base_service.py
└── execute_uuid_migration.py

Instruction Manual/
└── UUID_MIGRATION_GUIDE.md
```

### B. 数据库变更总结

| 表名 | 新增UUID主键列 | 新增UUID外键列 | 索引数量 |
|------|---------------|---------------|---------|
| patient | Patient_UUID | - | 2 |
| medical_record | Medical_Record_UUID | Patient_UUID | 3 |
| doctor | Doctor_UUID | - | 2 |
| appointment | Appointment_UUID | Patient_UUID, Doctor_UUID, Medical_Record_UUID, Time_Slot_UUID | 6 |
| prescription | Prescription_UUID | Patient_UUID, Doctor_UUID, Medical_Record_UUID | 5 |
| prescription_detail | Detail_UUID | Prescription_UUID | 3 |
| chat_conversation | Chat_UUID | Patient_UUID, Doctor_UUID | 4 |
| chat_message | Message_UUID | Chat_UUID | 4 |
| doctor_working_schedule | Schedule_UUID | Doctor_UUID | 3 |
| doctor_time_slots | Slot_UUID | Doctor_UUID | 3 |
| doctor_schedule_exceptions | Exception_UUID | Doctor_UUID | 3 |
| reminder | Reminder_UUID | Patient_UUID, Medical_Record_UUID, Appointment_UUID, Prescription_UUID | 6 |
| reminder_history | History_UUID | Reminder_UUID | 3 |
| reminder_config | Config_UUID | Patient_UUID | 3 |
| biomechanics_scan | Scan_UUID | Patient_UUID, Medical_Record_UUID | 4 |

**总计:**
- **新增UUID主键列**: 15个
- **新增UUID外键列**: 26个
- **新增索引**: 57个
- **新增触发器**: 12个

### C. SQL示例库

```sql
-- 使用UUID创建患者
INSERT INTO patient (Name, Gender, Age, Phone_Number)
VALUES ('张三', '男', 30, '13800138000');
-- Patient_UUID会自动生成

-- 使用UUID查询
SELECT * FROM patient WHERE Patient_UUID = '550e8400-e29b-41d4-a716-446655440000';

-- 兼容查询(INT或UUID)
SELECT * FROM patient
WHERE Patient_UUID = ? OR Patient_ID = ?;

-- JOIN查询(UUID外键)
SELECT p.Name, mr.Diagnosis
FROM patient p
INNER JOIN medical_record mr ON p.Patient_UUID = mr.Patient_UUID
WHERE p.Patient_UUID = '550e8400-e29b-41d4-a716-446655440000';
```

---

**文档版本**: 1.0
**最后更新**: 2025-11-20
**维护者**: System Migration Team


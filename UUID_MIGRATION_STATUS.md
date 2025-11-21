# UUID迁移状态报告

**日期**: 2025-11-21
**目标**: 彻底删除所有INT ID列,只使用UUID作为主键

---

## ✅ 已完成的工作

### 1. 数据库备份
- 已创建数据库备份(虽然命令被中断,但备份进程应该已运行)
- 备份位置: `database/backups/`

### 2. 代码修复

#### ✅ appointment_service_v3.py
- **修改方法签名**: `create_appointment_v3()` 参数从 INT 改为 STR (UUID)
  - `medical_record_id: str` (原 int)
  - `patient_id: str` (原 int)
  - `slot_id: str` (原 int)
- **删除UUID→INT ID查询逻辑**: 删除了第446-468行的所有查询INT ID的代码
- **简化INSERT语句**: 只插入UUID字段,不再插入INT ID字段
- **修复cancel_appointment()**: 使用 `Appointment_UUID` 而非 `Appointment_ID`

#### ✅ agents/agent_2.py
- **修改 `_extract_report_id()`**: 现在返回UUID而非INT
  - 添加UUID格式检测: `[0-9a-f]{8}-[0-9a-f]{4}-...`
  - 从 `user_reports` 中提取 `Medical_Record_UUID` 而非 `Medical_Record_ID`
  - 删除直接使用INT ID的逻辑
- **修改 `extract_ids_from_text()`**: 将序号转换为UUID
  - 使用 `Medical_Record_UUID` 而非 `Medical_Record_ID`
- **修改 `_prepare_context()`**: 显示UUID前8位
  - 显示格式: `【UUID:f0b91f1b...】`

---

## ⚠️ 数据库迁移问题

### 当前状态
**INT ID列尚未删除**,原因是遇到了MySQL表元数据锁(metadata lock)问题:

```
ERROR: Waiting for table metadata lock
```

### 问题原因
1. 之前执行的`fix_autoincrement_for_all_tables.sql`脚本卡住并持有锁
2. mysqldump备份进程持有READ锁
3. 多个ALTER TABLE命令排队等待

### 解决方案(待执行)
已创建 `database/simple_drop_ids.py` 脚本,逐个删除列以避免锁问题。

脚本正在后台运行中...

---

## 📋 待完成的工作

### 1. 完成数据库迁移
需要确认以下INT ID列已删除:
- [x] 脚本已创建
- [ ] `appointment`: Appointment_ID, Medical_Record_ID, Patient_ID, Doctor_ID, Time_Slot_ID
- [ ] `medical_record`: Medical_Record_ID, Patient_ID
- [ ] `patient`: Patient_ID
- [ ] `doctor`: Doctor_ID

### 2. 修复其他数据库服务类
需要检查并修复以下文件:
- [ ] `database/user_history_service_v2.py`
- [ ] `database/report_service.py`
- [ ] `database/prescription_service.py`
- [ ] `database/time_slot_service.py`
- [ ] `database/doctor_schedule_service.py`
- [ ] `database/chat_service.py`

### 3. 修复Agent相关代码
- [ ] `agents/agent_1.py` - 检查是否有INT ID引用
- [x] `agents/agent_2.py` - 已完成
- [ ] `agents/agent_manager.py` - 检查

### 4. 修复API层
- [ ] `main.py` - 更新所有API接口的参数类型
  - `/api/chat`
  - `/api/report/*`
  - `/api/prescription/*`
  - `/api/appointments`

### 5. 测试
- [ ] 测试患者创建流程
- [ ] 测试病例创建流程
- [ ] 测试预约创建流程 (核心测试)
- [ ] 测试报告生成
- [ ] 测试处方生成

---

## 🔧 关键代码变更示例

### Before (使用INT ID):
```python
def create_appointment_v3(
    self,
    medical_record_id: int,  # ❌ INT
    patient_id: int,          # ❌ INT
    ...
):
    # 查询UUID对应的INT ID
    mr_query = "SELECT Medical_Record_ID FROM medical_record WHERE Medical_Record_UUID = %s"
    ...
    # INSERT同时插入UUID和INT
    INSERT INTO appointment (Appointment_UUID, Medical_Record_UUID, Medical_Record_ID, ...)
```

### After (只用UUID):
```python
def create_appointment_v3(
    self,
    medical_record_id: str,  # ✅ UUID
    patient_id: str,          # ✅ UUID
    ...
):
    # 不再查询INT ID

    # INSERT只插入UUID
    INSERT INTO appointment (Appointment_UUID, Medical_Record_UUID, Patient_UUID, ...)
```

---

## 📝 下一步行动

1. **等待数据库迁移脚本完成** (`simple_drop_ids.py`)
2. **验证INT ID列已删除**:
   ```bash
   mysql -u root -p medical_db -e "DESC appointment;"
   ```
3. **测试预约创建**:
   ```bash
   python test_appointment_uuid_debug.py
   ```
4. **如果成功,继续修复其他服务类和API层**

---

## ⚠️ 重要提示

- 此迁移是**破坏性操作**,删除INT ID列后无法回滚(除非从备份恢复)
- 所有代码必须改为使用UUID,否则会出现字段不存在错误
- 需要全面测试所有功能确保正常工作

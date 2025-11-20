# UUID迁移 - 剩余任务清单

> **更新日期**: 2025-11-20
> **当前进度**: 3/17 文件已完成 (18%)

---

## ✅ 已完成文件

1. ✅ **base_service.py** - UUID工具类
2. ✅ **user_history_service_v2.py** - 用户历史服务
3. ✅ **appointment_service_v3.py** - 预约服务(部分完成)

---

## 📝 待更新文件清单 (14个)

### P0 - 核心服务 (3个)

#### 1. chat_service.py
**位置**: `database/chat_service.py`
**优先级**: 高
**预计时间**: 20分钟

**需要修改的方法**:
```python
class ChatService(BaseServiceWithUUID):  # 继承基类

    def create_chat_for_patient(self, patient_id: Union[str, int], ...) -> str:
        # 返回Chat_UUID而非Chat_ID
        patient_id_normalized = normalize_id(patient_id)
        # 查询Patient_UUID...
        # 插入使用Patient_UUID
        # 返回Chat_UUID

    def create_chat_for_doctor(self, doctor_id: Union[str, int], ...) -> str:
        # 类似逻辑

    def save_message(self, chat_id: Union[str, int], ...) -> str:
        # 返回Message_UUID
        chat_id_normalized = normalize_id(chat_id)
        # 查询Chat_UUID...
        # 插入使用Chat_UUID
        # 返回Message_UUID

    def get_chat_by_id(self, chat_id: Union[str, int]) -> Optional[Dict]:
        chat_id_normalized = normalize_id(chat_id)
        query = """
            SELECT * FROM chat_conversation
            WHERE Chat_UUID = %s OR CAST(Chat_ID AS CHAR) = %s
        """
        return self.db.execute_one(query, (chat_id_normalized, chat_id_normalized))

    def get_chat_messages(self, chat_id: Union[str, int], ...) -> List[Dict]:
        chat_id_normalized = normalize_id(chat_id)
        query = """
            SELECT cm.*, cc.Chat_UUID
            FROM chat_message cm
            INNER JOIN chat_conversation cc ON cm.Chat_UUID = cc.Chat_UUID
            WHERE cc.Chat_UUID = %s OR CAST(cc.Chat_ID AS CHAR) = %s
            ORDER BY cm.Message_Order
        """
```

---

#### 2. prescription_service.py
**位置**: `database/prescription_service.py`
**优先级**: 高
**预计时间**: 15分钟

**需要修改的方法**:
```python
class PrescriptionService(BaseServiceWithUUID):

    def get_prescription_full(self, prescription_id: Union[str, int]) -> Optional[Dict]:
        prescription_id_normalized = normalize_id(prescription_id)

        main_query = """
            SELECT
                p.Prescription_ID,
                p.Prescription_UUID,
                p.Prescription_Number,
                ...,
                pat.Patient_UUID,
                d.Doctor_UUID,
                mr.Medical_Record_UUID
            FROM prescription p
            LEFT JOIN patient pat ON p.Patient_UUID = pat.Patient_UUID
            LEFT JOIN doctor d ON p.Doctor_UUID = d.Doctor_UUID
            LEFT JOIN medical_record mr ON p.Medical_Record_UUID = mr.Medical_Record_UUID
            WHERE p.Prescription_UUID = %s OR CAST(p.Prescription_ID AS CHAR) = %s
        """

        detail_query = """
            SELECT
                pd.Detail_ID,
                pd.Detail_UUID,
                pd.Prescription_UUID,
                ...
            FROM prescription_detail pd
            INNER JOIN prescription p ON pd.Prescription_UUID = p.Prescription_UUID
            WHERE p.Prescription_UUID = %s OR CAST(p.Prescription_ID AS CHAR) = %s
        """
```

---

#### 3. report_service.py
**位置**: `database/report_service.py`
**优先级**: 高
**预计时间**: 15分钟

**需要修改的方法**:
```python
class ReportService(BaseServiceWithUUID):

    def get_report_by_id(self, medical_record_id: Union[str, int]) -> Optional[Dict]:
        medical_record_id_normalized = normalize_id(medical_record_id)

        query = """
            SELECT mr.*, p.Patient_UUID
            FROM medical_record mr
            INNER JOIN patient p ON mr.Patient_UUID = p.Patient_UUID
            WHERE mr.Medical_Record_UUID = %s OR CAST(mr.Medical_Record_ID AS CHAR) = %s
        """
```

---

### P1 - Agent层 (3个)

#### 4. agents/agent_1.py
**位置**: `agents/agent_1.py`
**优先级**: 中高
**预计时间**: 25分钟

**需要修改**:
```python
class HealthAgent:
    def __init__(self, user_id: Union[str, int, None] = None, phone_number: str = None, role: str = "patient"):
        # user_id现在可以是UUID
        self.user_id = user_id  # Union[str, int, None]
        self.phone_number = phone_number
        self.role = role

        # 如果user_id是INT,转换为UUID
        if user_id and isinstance(user_id, int):
            from database.base_service import normalize_id
            self.user_id = normalize_id(user_id)

    def _load_user_history(self):
        if self.user_id:
            # user_id已经是UUID兼容格式
            history = user_history_service.get_user_complete_info(self.user_id)
        elif self.phone_number:
            history = user_history_service.get_user_complete_info_by_phone(self.phone_number)
            if history and history.get('patient_uuid'):
                self.user_id = history['patient_uuid']  # 更新为UUID
```

---

#### 5. agents/agent_2.py
**位置**: `agents/agent_2.py`
**优先级**: 中高
**预计时间**: 20分钟

**需要修改**:
```python
class ReportAgent:
    def __init__(self, user_id: Union[str, int, None] = None, phone_number: str = None, role: str = "doctor"):
        self.user_id = user_id  # UUID兼容
        # 类似agent_1的修改

    def generate_report(self, medical_record_id: Union[str, int]):
        # 接受UUID或INT
        from database.base_service import normalize_id
        medical_record_id = normalize_id(medical_record_id)
        # 使用report_generator生成报告
```

---

#### 6. agents/agent_manager.py
**位置**: `agents/agent_manager.py`
**优先级**: 中
**预计时间**: 10分钟

**需要修改**:
```python
class AgentManager:
    def create_agent(self, agent_type: str, user_id: Union[str, int, None] = None, ...):
        # user_id可以是UUID
        if agent_type == 'health':
            return HealthAgent(user_id=user_id, ...)
        elif agent_type == 'report':
            return ReportAgent(user_id=user_id, ...)
```

---

### P2 - API层 (1个)

#### 7. main.py
**位置**: `main.py`
**优先级**: 中
**预计时间**: 30分钟

**需要修改的端点**:
```python
from database.base_service import is_valid_uuid, normalize_id
from fastapi import HTTPException

@app.post("/api/chat")
async def chat_endpoint(request: dict):
    # 验证UUID格式
    patient_id = request.get("patient_id")
    if patient_id:
        try:
            patient_id = normalize_id(patient_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"无效的ID格式: {e}")

    # 使用phone_number获取patient_uuid
    phone = request.get("phone_number")
    if phone:
        user = user_service.get_user_by_phone(phone)
        if user:
            patient_uuid = user['Patient_UUID']
            agent = HealthAgent(user_id=patient_uuid, phone_number=phone, role="patient")

    # 响应包含UUID
    return {
        "response": response,
        "patient_uuid": patient_uuid,
        "chat_uuid": chat_uuid
    }

@app.post("/api/report/generate")
async def generate_report(request: dict):
    medical_record_id = request.get("medical_record_id")
    medical_record_id = normalize_id(medical_record_id)
    # ...

@app.post("/api/prescription/generate")
async def generate_prescription(request: dict):
    prescription_id = request.get("prescription_id")
    prescription_id = normalize_id(prescription_id)
    # ...
```

---

### P3 - 辅助服务 (5个)

#### 8. reminder_service.py
**位置**: `database/reminder_service.py`
**预计时间**: 15分钟

**修改模式**:
- 继承 `BaseServiceWithUUID`
- 所有ID参数改为 `Union[str, int]`
- 查询使用UUID外键

---

#### 9. biomechanics_service.py
**位置**: `database/biomechanics_service.py`
**预计时间**: 15分钟

**修改模式**:
- 类似上述
- 重点: `get_scan_by_id()`, `create_scan()`

---

#### 10. time_slot_service.py
**位置**: `database/time_slot_service.py`
**预计时间**: 20分钟

**修改模式**:
- `get_available_slots()` 返回Slot_UUID
- `book_slot()` 接受Slot_UUID
- 查询doctor时使用Doctor_UUID

---

#### 11. doctor_schedule_service.py
**位置**: `database/doctor_schedule_service.py`
**预计时间**: 15分钟

**修改模式**:
- `create_working_schedule(doctor_id: Union[str, int])`
- 使用Doctor_UUID插入

---

#### 12. db_connection.py (可选)
**位置**: `database/db_connection.py`
**预计时间**: 5分钟

**可能需要**:
- 检查execute_insert是否返回正确的ID
- 可能需要调整返回逻辑

---

### P4 - 文档生成器 (2个)

#### 13. utils/report_generator.py
**位置**: `utils/report_generator.py`
**预计时间**: 10分钟

**需要修改**:
```python
from database.base_service import normalize_id

def generate_medical_report(medical_record_id: Union[str, int]) -> str:
    medical_record_id = normalize_id(medical_record_id)

    # 查询medical_record
    report_service = ReportService()
    record = report_service.get_report_by_id(medical_record_id)

    if not record:
        raise ValueError(f"未找到病例: {medical_record_id}")

    # 生成报告...
```

---

#### 14. utils/prescription_generator.py
**位置**: `utils/prescription_generator.py`
**预计时间**: 10分钟

**需要修改**:
```python
from database.base_service import normalize_id

def generate_prescription_pdf(prescription_id: Union[str, int]) -> str:
    prescription_id = normalize_id(prescription_id)

    # 查询prescription
    prescription_service = PrescriptionService()
    prescription = prescription_service.get_prescription_full(prescription_id)

    # 生成PDF...
```

---

## 🔧 通用更新模板

### 1. 服务类基本模板

```python
# 1. 添加导入
from typing import Union
from .base_service import BaseServiceWithUUID, normalize_id

# 2. 继承基类
class YourService(BaseServiceWithUUID):
    def __init__(self):
        super().__init__()
        self.db = DatabaseConnection()

# 3. 更新方法签名
def your_method(self, record_id: Union[str, int]) -> Optional[Dict]:
    record_id_normalized = normalize_id(record_id)

    query = """
        SELECT * FROM your_table
        WHERE Your_UUID = %s OR CAST(Your_ID AS CHAR) = %s
    """
    return self.db.execute_one(query, (record_id_normalized, record_id_normalized))

# 4. 创建方法返回UUID
def create_record(self, ...) -> str:  # 返回UUID
    record_id = self.db.execute_insert(insert_query, params)

    # 查询生成的UUID
    query_uuid = "SELECT Your_UUID FROM your_table WHERE Your_ID = %s"
    result = self.db.execute_one(query_uuid, (record_id,))
    return result['Your_UUID'] if result else None
```

### 2. Agent类更新模板

```python
class YourAgent:
    def __init__(self, user_id: Union[str, int, None] = None, ...):
        self.user_id = user_id  # 现在支持UUID

        # 规范化ID
        if user_id:
            from database.base_service import normalize_id
            self.user_id = normalize_id(user_id)
```

### 3. API端点更新模板

```python
from database.base_service import normalize_id
from fastapi import HTTPException

@app.post("/api/your_endpoint")
async def your_endpoint(request: dict):
    # 提取并验证ID
    record_id = request.get("record_id")
    if record_id:
        try:
            record_id = normalize_id(record_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # 响应包含UUID
    return {
        "data": data,
        "record_uuid": record['Your_UUID']
    }
```

---

## 📊 预计总工作量

| 优先级 | 文件数 | 预计时间 |
|--------|--------|----------|
| P0 | 3 | 50分钟 |
| P1 | 3 | 55分钟 |
| P2 | 1 | 30分钟 |
| P3 | 5 | 70分钟 |
| P4 | 2 | 20分钟 |
| **总计** | **14** | **约4小时** |

---

## 🎯 建议执行顺序

### 第一批 (核心功能 - 1小时)
1. ✅ chat_service.py
2. ✅ prescription_service.py
3. ✅ report_service.py

### 第二批 (Agent层 - 1小时)
4. ✅ agent_1.py
5. ✅ agent_2.py
6. ✅ agent_manager.py

### 第三批 (API层 - 30分钟)
7. ✅ main.py

### 第四批 (辅助服务 - 1.5小时)
8-12. ✅ 5个辅助服务

### 第五批 (工具类 - 20分钟)
13-14. ✅ 文档生成器

---

## ✅ 验证清单

完成每个文件后验证:
- [ ] 类继承 `BaseServiceWithUUID`
- [ ] 导入了 `Union`, `normalize_id`
- [ ] 所有ID参数类型为 `Union[str, int]`
- [ ] 创建方法返回UUID字符串
- [ ] 查询使用UUID外键JOIN
- [ ] SELECT包含UUID列
- [ ] 没有硬编码INT类型假设

---

## 📝 测试建议

每完成一批后运行:
```bash
# 测试核心服务
python test/test_uuid_migration_quick.py

# 测试特定功能
python -c "
from database.chat_service import ChatService
service = ChatService()
# 测试创建和查询
"
```

---

## 🔗 相关文档

- [UUID迁移指南](UUID_MIGRATION_GUIDE.md)
- [迁移状态报告](UUID_MIGRATION_STATUS.md)
- [项目总文档](../CLAUDE.md)

---

**最后更新**: 2025-11-20
**剩余文件**: 14个
**预计完成时间**: 4小时


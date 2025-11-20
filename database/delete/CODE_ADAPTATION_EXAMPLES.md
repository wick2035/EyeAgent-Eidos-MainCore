# 代码适配示例 - 使用新增的系统管理字段

## 📋 概述

数据库迁移完成后，所有表都新增了以下字段：
- `Create_By` - 创建人UUID
- `Update_By` - 更新人UUID
- `Version` - 乐观锁版本号
- `Deleted` - 逻辑删除标记

本文档提供代码适配的具体示例。

---

## 🔧 基础适配模式

### 1. INSERT操作 - 添加Create_By

**修改前：**
```python
def create_patient(name, phone, age):
    cursor.execute("""
        INSERT INTO patient (Name, Phone_Number, Age, Created_At)
        VALUES (%s, %s, %s, NOW())
    """, (name, phone, age))
    return cursor.lastrowid
```

**修改后：**
```python
def create_patient(name, phone, age, current_user_uuid):
    cursor.execute("""
        INSERT INTO patient (
            Name, Phone_Number, Age,
            Create_By, Version, Deleted,
            Created_At
        ) VALUES (%s, %s, %s, %s, 0, 0, NOW())
    """, (name, phone, age, current_user_uuid))
    return cursor.lastrowid
```

---

### 2. UPDATE操作 - 添加Update_By和Version递增

**修改前：**
```python
def update_patient(patient_id, new_name):
    cursor.execute("""
        UPDATE patient
        SET Name = %s, Updated_At = NOW()
        WHERE Patient_ID = %s
    """, (new_name, patient_id))
    return cursor.rowcount > 0
```

**修改后（带乐观锁）：**
```python
def update_patient(patient_id, new_name, current_user_uuid, old_version):
    cursor.execute("""
        UPDATE patient
        SET Name = %s,
            Update_By = %s,
            Version = Version + 1,
            Updated_At = NOW()
        WHERE Patient_ID = %s
          AND Deleted = 0
          AND Version = %s
    """, (new_name, current_user_uuid, patient_id, old_version))

    if cursor.rowcount == 0:
        raise ConcurrencyError("数据已被其他用户修改或已删除")

    return True
```

---

### 3. DELETE操作 - 改为逻辑删除

**修改前：**
```python
def delete_patient(patient_id):
    cursor.execute("""
        DELETE FROM patient WHERE Patient_ID = %s
    """, (patient_id,))
    return cursor.rowcount > 0
```

**修改后（逻辑删除）：**
```python
def delete_patient(patient_id, current_user_uuid):
    cursor.execute("""
        UPDATE patient
        SET Deleted = 1,
            Update_By = %s,
            Updated_At = NOW()
        WHERE Patient_ID = %s
          AND Deleted = 0
    """, (current_user_uuid, patient_id))

    if cursor.rowcount == 0:
        raise ValueError("Patient not found or already deleted")

    return True
```

---

### 4. SELECT操作 - 添加Deleted过滤

**修改前：**
```python
def get_patient(patient_id):
    cursor.execute("""
        SELECT * FROM patient WHERE Patient_ID = %s
    """, (patient_id,))
    return cursor.fetchone()
```

**修改后：**
```python
def get_patient(patient_id):
    cursor.execute("""
        SELECT * FROM patient
        WHERE Patient_ID = %s
          AND Deleted = 0
    """, (patient_id,))
    return cursor.fetchone()
```

**列表查询：**
```python
def get_all_patients():
    cursor.execute("""
        SELECT * FROM patient
        WHERE Deleted = 0
        ORDER BY Created_At DESC
    """)
    return cursor.fetchall()
```

---

## 💼 实际应用场景

### 场景1：患者注册 (agents/agent_1.py)

**位置**: `d:\Agent\pythonProject1\agents\agent_1.py` 约180-200行

**修改前：**
```python
def save_patient_info(self, patient_data):
    cursor.execute("""
        INSERT INTO patient (Name, Phone_Number, Age, Gender, Address)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        patient_data['name'],
        patient_data['phone'],
        patient_data['age'],
        patient_data['gender'],
        patient_data['address']
    ))
```

**修改后：**
```python
def save_patient_info(self, patient_data):
    # 获取当前操作人UUID（从session或默认为system）
    current_user = getattr(self, 'current_user_uuid', 'system')

    cursor.execute("""
        INSERT INTO patient (
            Name, Phone_Number, Age, Gender, Address,
            Create_By, Version, Deleted, Created_At
        ) VALUES (%s, %s, %s, %s, %s, %s, 0, 0, NOW())
    """, (
        patient_data['name'],
        patient_data['phone'],
        patient_data['age'],
        patient_data['gender'],
        patient_data['address'],
        current_user
    ))
```

---

### 场景2：预约创建 (database/appointment_service_v3.py)

**位置**: `d:\Agent\pythonProject1\database\appointment_service_v3.py` 约430-450行

**修改前：**
```python
cursor.execute("""
    INSERT INTO appointment (
        Medical_Record_ID, Patient_ID, Doctor_ID, Time_Slot_ID,
        Patient_Name, Appointment_Time, Appointment_Category,
        Severity_Level, Description, Appointment_Status
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
""", (...))
```

**修改后：**
```python
cursor.execute("""
    INSERT INTO appointment (
        Medical_Record_ID, Patient_ID, Doctor_ID, Time_Slot_ID,
        Patient_Name, Appointment_Time, Appointment_Category,
        Severity_Level, Description, Appointment_Status,
        Create_By, Version, Deleted, Created_At
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0, NOW())
""", (..., current_user_uuid))
```

---

### 场景3：处方生成 (database/prescription_service.py)

**位置**: `d:\Agent\pythonProject1\database\prescription_service.py`

**修改前：**
```python
def create_prescription(patient_id, doctor_id, record_id, prescription_data):
    cursor.execute("""
        INSERT INTO prescription (
            Patient_ID, Doctor_ID, Medical_Record_ID,
            Prescription_Number, Prescription_Type,
            Diagnosis_Description, Usage_Instruction
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (...))
```

**修改后：**
```python
def create_prescription(patient_id, doctor_id, record_id, prescription_data, current_user_uuid):
    cursor.execute("""
        INSERT INTO prescription (
            Patient_ID, Doctor_ID, Medical_Record_ID,
            Prescription_Number, Prescription_Type,
            Diagnosis_Description, Usage_Instruction,
            Create_By, Version, Deleted
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, 0)
    """, (..., current_user_uuid))
```

---

## 🚀 appointment表通用日程功能

### 场景4：创建患者预约

```python
def create_patient_appointment(patient_id, doctor_id, appointment_time, description, current_user_uuid):
    cursor.execute("""
        INSERT INTO appointment (
            Patient_ID, Doctor_ID, Appointment_Time, Description,
            Is_Generic_Event, Event_Type,
            Create_By, Version, Deleted
        ) VALUES (%s, %s, %s, %s, FALSE, 'appointment', %s, 0, 0)
    """, (patient_id, doctor_id, appointment_time, description, current_user_uuid))
    return cursor.lastrowid
```

### 场景5：创建医生个人日程

```python
def create_doctor_event(doctor_id, event_time, title, event_type, notes, current_user_uuid):
    """
    创建医生个人日程（非患者预约）

    Args:
        event_type: 'meeting', 'personal_task', 'reminder' 等
    """
    cursor.execute("""
        INSERT INTO appointment (
            Doctor_ID, Appointment_Time, Description,
            Is_Generic_Event, Event_Type, Notes,
            Create_By, Version, Deleted
        ) VALUES (%s, %s, %s, TRUE, %s, %s, %s, 0, 0)
    """, (doctor_id, event_time, title, event_type, notes, current_user_uuid))
    return cursor.lastrowid
```

### 场景6：查询医生所有日程（预约+个人事件）

```python
def get_doctor_schedule(doctor_id, start_date, end_date):
    """获取医生的完整日程（包括患者预约和个人事件）"""
    cursor.execute("""
        SELECT
            a.*,
            CASE
                WHEN a.Is_Generic_Event = 0 THEN '患者预约'
                ELSE a.Event_Type
            END as event_category,
            p.Name as patient_name
        FROM appointment a
        LEFT JOIN patient p ON a.Patient_ID = p.Patient_ID AND p.Deleted = 0
        WHERE a.Doctor_ID = %s
          AND a.Deleted = 0
          AND a.Appointment_Time BETWEEN %s AND %s
        ORDER BY a.Appointment_Time ASC
    """, (doctor_id, start_date, end_date))
    return cursor.fetchall()
```

---

## 🔄 乐观锁使用示例

### 完整的更新流程

```python
def update_patient_with_optimistic_lock(patient_id, updates, current_user_uuid):
    """
    使用乐观锁更新患者信息

    Args:
        patient_id: 患者ID
        updates: dict, 要更新的字段 {'Name': 'new_name', 'Age': 30}
        current_user_uuid: 当前操作用户UUID

    Returns:
        bool: 更新是否成功

    Raises:
        ConcurrencyError: 并发冲突
        ValueError: 患者不存在或已删除
    """
    # 1. 读取当前版本号
    cursor.execute("""
        SELECT Version FROM patient
        WHERE Patient_ID = %s AND Deleted = 0
    """, (patient_id,))

    result = cursor.fetchone()
    if not result:
        raise ValueError(f"Patient {patient_id} not found or deleted")

    old_version = result['Version']

    # 2. 构建UPDATE语句
    set_clauses = []
    params = []

    for field, value in updates.items():
        set_clauses.append(f"{field} = %s")
        params.append(value)

    # 添加系统字段
    set_clauses.append("Update_By = %s")
    set_clauses.append("Version = Version + 1")
    set_clauses.append("Updated_At = NOW()")

    params.append(current_user_uuid)
    params.append(patient_id)
    params.append(old_version)

    # 3. 执行UPDATE with版本检查
    sql = f"""
        UPDATE patient
        SET {', '.join(set_clauses)}
        WHERE Patient_ID = %s
          AND Deleted = 0
          AND Version = %s
    """

    cursor.execute(sql, params)

    # 4. 检查更新结果
    if cursor.rowcount == 0:
        # 版本号不匹配，说明数据已被其他人修改
        raise ConcurrencyError(
            f"Patient {patient_id} was modified by another user. "
            f"Please refresh and try again."
        )

    return True


# 使用示例
try:
    update_patient_with_optimistic_lock(
        patient_id=123,
        updates={'Name': '张三', 'Age': 30},
        current_user_uuid='user-uuid-123'
    )
    print("Update successful")
except ConcurrencyError as e:
    print(f"Concurrency conflict: {e}")
    # 提示用户刷新页面重试
except ValueError as e:
    print(f"Patient not found: {e}")
```

---

## 🛡️ 自定义异常类

创建 `database/exceptions.py`:

```python
class ConcurrencyError(Exception):
    """并发冲突异常 - 乐观锁版本检查失败"""
    pass


class DeletedRecordError(Exception):
    """记录已被删除异常"""
    pass
```

---

## 📊 辅助工具函数

创建 `database/utils.py`:

```python
import uuid
from datetime import datetime


def get_system_user_uuid():
    """获取系统用户UUID（用于自动化操作）"""
    return "00000000-0000-0000-0000-000000000000"


def get_current_user_uuid(session=None):
    """
    从session获取当前用户UUID

    Args:
        session: Flask/FastAPI session对象

    Returns:
        str: 用户UUID，如果未登录返回系统UUID
    """
    if session and 'user_uuid' in session:
        return session['user_uuid']
    return get_system_user_uuid()


def generate_uuid():
    """生成新的UUID"""
    return str(uuid.uuid4())


def create_audit_info(user_uuid=None):
    """
    生成创建记录的审计信息

    Returns:
        dict: {'Create_By': uuid, 'Version': 0, 'Deleted': 0}
    """
    return {
        'Create_By': user_uuid or get_system_user_uuid(),
        'Version': 0,
        'Deleted': 0
    }


def update_audit_info(user_uuid=None):
    """
    生成更新记录的审计信息

    Returns:
        dict: {'Update_By': uuid}
    """
    return {
        'Update_By': user_uuid or get_system_user_uuid()
    }
```

---

## 🔧 Service层基类（推荐）

创建 `database/base_service.py`:

```python
from database.db_connection import DatabaseConnection
from database.exceptions import ConcurrencyError, DeletedRecordError


class BaseService:
    """数据库服务基类 - 封装通用的CRUD操作"""

    def __init__(self, table_name):
        self.table_name = table_name
        self.db = DatabaseConnection()
        self.connection = None
        self.cursor = None

    def __enter__(self):
        self.connection = self.db.connect()
        self.cursor = self.connection.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.connection.commit()
        else:
            self.connection.rollback()
        self.cursor.close()
        self.connection.close()

    def insert(self, data, current_user_uuid):
        """
        插入新记录

        Args:
            data: dict, 字段值
            current_user_uuid: 当前用户UUID

        Returns:
            int: 新记录ID
        """
        data['Create_By'] = current_user_uuid
        data['Version'] = 0
        data['Deleted'] = 0

        fields = ', '.join(data.keys())
        placeholders = ', '.join(['%s'] * len(data))

        sql = f"""
            INSERT INTO {self.table_name} ({fields})
            VALUES ({placeholders})
        """

        self.cursor.execute(sql, list(data.values()))
        return self.cursor.lastrowid

    def update(self, record_id, updates, current_user_uuid, check_version=True):
        """
        更新记录（带乐观锁）

        Args:
            record_id: 记录ID
            updates: dict, 要更新的字段
            current_user_uuid: 当前用户UUID
            check_version: 是否检查版本号

        Raises:
            ConcurrencyError: 并发冲突
        """
        if check_version:
            # 读取当前版本
            self.cursor.execute(f"""
                SELECT Version FROM {self.table_name}
                WHERE id = %s AND Deleted = 0
            """, (record_id,))

            result = self.cursor.fetchone()
            if not result:
                raise DeletedRecordError(f"Record {record_id} not found")

            old_version = result['Version']

        updates['Update_By'] = current_user_uuid

        set_clause = ', '.join([f"{k} = %s" for k in updates.keys()])
        set_clause += ", Version = Version + 1, Updated_At = NOW()"

        params = list(updates.values())
        params.append(record_id)

        if check_version:
            sql = f"""
                UPDATE {self.table_name}
                SET {set_clause}
                WHERE id = %s AND Version = %s AND Deleted = 0
            """
            params.append(old_version)
        else:
            sql = f"""
                UPDATE {self.table_name}
                SET {set_clause}
                WHERE id = %s AND Deleted = 0
            """

        self.cursor.execute(sql, params)

        if check_version and self.cursor.rowcount == 0:
            raise ConcurrencyError(f"Record {record_id} was modified by another user")

    def soft_delete(self, record_id, current_user_uuid):
        """逻辑删除"""
        self.cursor.execute(f"""
            UPDATE {self.table_name}
            SET Deleted = 1, Update_By = %s, Updated_At = NOW()
            WHERE id = %s AND Deleted = 0
        """, (current_user_uuid, record_id))

        if self.cursor.rowcount == 0:
            raise DeletedRecordError(f"Record {record_id} not found")

    def get_by_id(self, record_id):
        """根据ID查询（排除已删除）"""
        self.cursor.execute(f"""
            SELECT * FROM {self.table_name}
            WHERE id = %s AND Deleted = 0
        """, (record_id,))
        return self.cursor.fetchone()


# 使用示例
with BaseService('patient') as service:
    # 插入
    patient_id = service.insert({
        'Name': '张三',
        'Phone_Number': '13800138000',
        'Age': 30
    }, current_user_uuid='user-123')

    # 更新
    service.update(patient_id, {
        'Name': '李四'
    }, current_user_uuid='user-123')

    # 删除
    service.soft_delete(patient_id, current_user_uuid='user-123')
```

---

## 📝 总结

### 必须修改的地方
1. ✅ 所有INSERT语句 - 添加Create_By, Version, Deleted
2. ✅ 所有UPDATE语句 - 添加Update_By, Version递增, Deleted=0过滤
3. ✅ 所有DELETE语句 - 改为UPDATE SET Deleted=1
4. ✅ 所有SELECT语句 - 添加WHERE Deleted=0

### 可选优化
- 使用BaseService基类统一管理
- 实现乐观锁ConcurrencyError处理
- 创建辅助工具函数
- 添加审计日志记录

### 下一步
参考本文档修改以下关键文件：
1. `database/appointment_service_v3.py`
2. `database/prescription_service.py`
3. `database/user_history_service_v2.py`
4. `agents/agent_1.py`
5. `agents/agent_2.py`

---

**更新日期**: 2025-11-20
**版本**: 1.0

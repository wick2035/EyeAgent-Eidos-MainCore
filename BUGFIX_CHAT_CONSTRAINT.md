# 聊天对话约束错误修复说明

## 问题描述

在UUID迁移完成后，创建聊天对话时出现数据库约束违反错误：

```
ERROR:database.chat_service:为患者创建对话失败: (3819, "Check constraint 'chat_conversation_chk_1' is violated.")
```

## 根本原因

数据库表 `chat_conversation` 有一个约束 `chat_conversation_chk_1`：

```sql
CHECK (
    ((User_Type = 'patient') AND (Patient_ID IS NOT NULL) AND (Doctor_ID IS NULL))
    OR
    ((User_Type = 'doctor') AND (Doctor_ID IS NOT NULL) AND (Patient_ID IS NULL))
)
```

**问题**：旧代码在创建对话时只插入了UUID列（`Patient_UUID` 或 `Doctor_UUID`），但约束检查的是INT列（`Patient_ID` 或 `Doctor_ID`）。由于没有提供INT列的值，导致约束检查失败。

## 修复方案

修改了 `database/chat_service.py` 中的两个方法：

### 1. `create_chat_for_patient()`

**修改前**：
```python
# 只插入Patient_UUID
query = """
    INSERT INTO chat_conversation
    (User_Type, Patient_UUID, Title, Conversation_Type, AI_Agent)
    VALUES ('patient', %s, %s, %s, %s)
"""
chat_id = self.db.execute_insert(query, (patient_uuid, title, conversation_type, ai_agent))
```

**修改后**：
```python
# 同时查询Patient_ID和Patient_UUID
if patient_id_normalized.isdigit():
    patient_query = "SELECT Patient_ID, Patient_UUID FROM patient WHERE Patient_ID = %s"
    patient_result = self.db.execute_one(patient_query, (patient_id_normalized,))
else:
    patient_query = "SELECT Patient_ID, Patient_UUID FROM patient WHERE Patient_UUID = %s"
    patient_result = self.db.execute_one(patient_query, (patient_id_normalized,))

patient_id_int = patient_result['Patient_ID']
patient_uuid = patient_result['Patient_UUID']

# 同时插入Patient_ID和Patient_UUID
query = """
    INSERT INTO chat_conversation
    (User_Type, Patient_ID, Patient_UUID, Title, Conversation_Type, AI_Agent)
    VALUES ('patient', %s, %s, %s, %s, %s)
"""
chat_id = self.db.execute_insert(query, (patient_id_int, patient_uuid, title, conversation_type, ai_agent))
```

### 2. `create_chat_for_doctor()`

应用了相同的修复逻辑，同时插入 `Doctor_ID` 和 `Doctor_UUID`。

## 测试结果

运行 `test_chat_fix.py` 验证：

```
测试1: 使用Patient_ID创建对话
[SUCCESS] 成功创建对话: Chat_UUID=06574082-c5ee-11f0-b733-08bfb82fad24

测试2: 使用Patient_UUID创建对话
查询到Patient_UUID: f0b8e0e2-c5e5-11f0-b733-08bfb82fad24
[SUCCESS] 成功创建对话: Chat_UUID=065dbb93-c5ee-11f0-b733-08bfb82fad24

测试3: 验证数据库记录
记录: Chat_ID=17
  User_Type: patient
  Patient_ID: 1
  Patient_UUID: f0b8e0e2-c5e5-11f0-b733-08bfb82fad24
  Doctor_ID: None
  Doctor_UUID: None
  [OK] 约束满足: Patient_ID NOT NULL, Doctor_ID IS NULL

[SUCCESS] 所有测试通过!
```

## 关键要点

1. **约束检查INT列**：即使在UUID迁移期间，数据库约束仍然检查原有的INT列
2. **双列插入策略**：在过渡期必须同时插入INT和UUID列
3. **向后兼容**：修复后的代码支持接收INT或UUID作为输入参数
4. **约束逻辑**：患者对话必须有`Patient_ID`且无`Doctor_ID`，医生对话反之

## 影响范围

- ✅ 修复文件：`database/chat_service.py`
- ✅ 测试脚本：`test_chat_fix.py`
- ✅ 影响功能：所有创建聊天对话的功能（患者端和医生端）

## 日期

2025-11-20

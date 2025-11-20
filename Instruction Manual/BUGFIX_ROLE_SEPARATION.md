# Bug修复：医生和患者对话记录分离

**修复日期**: 2025-11-20
**问题严重级别**: 高 (数据完整性问题)
**状态**: ✅ 已修复并测试通过

## 问题描述

### 核心问题
医生的对话记录可能被错误地绑定到患者记录上，导致数据混乱。

### 问题根源

1. **变量命名混乱** ([main.py:176](main.py#L176))
   - 代码中使用 `patient_id` 变量同时存储患者ID和医生ID
   - 当 `role == "doctor"` 时，`patient_id` 实际包含的是医生ID

2. **只查询患者表** ([main.py:154-164](main.py#L154-L164))
   - 当通过手机号查找用户时，系统只查询 `patient` 表
   - 即使 `role == "doctor"`，也不会查询 `doctor` 表
   - 如果医生的手机号在患者表中存在，会返回患者ID

3. **缺少医生查询功能**
   - `UserHistoryServiceV2` 只有 `get_user_by_phone()` 查询患者
   - 没有对应的 `get_doctor_by_phone()` 方法

4. **数据库约束被违反**
   - `chat_conversation` 表有严格约束：
     - 医生对话必须 `Doctor_ID NOT NULL` 且 `Patient_ID IS NULL`
     - 患者对话必须 `Patient_ID NOT NULL` 且 `Doctor_ID IS NULL`
   - 但如果传入的是患者ID，就会将患者ID存入 `Doctor_ID` 字段

## 修复方案

### 1. 添加医生查询服务

**文件**: [database/user_history_service_v2.py](database/user_history_service_v2.py)

新增方法：
- `get_doctor_by_id(doctor_id)` - 根据Doctor_ID或Doctor_UUID查询医生信息
- `get_doctor_by_phone(phone_number)` - 根据手机号查询医生信息

```python
def get_doctor_by_phone(self, phone_number: str) -> Optional[Dict[str, Any]]:
    """根据手机号查询医生基本信息"""
    query = "SELECT * FROM doctor WHERE Phone_Number = %s"
    result = self.db.execute_one(query, (phone_number,))
    return result
```

### 2. 修复主聊天端点的用户查询逻辑

**文件**: [main.py](main.py) (Lines 153-210)

**修改前**:
```python
# 获取patient_id（优先使用UUID）
patient_id = user_id_normalized
if not patient_id and message.phone_number:
    user_info = user_service.get_user_by_phone(message.phone_number)  # 只查询患者表
    if user_info:
        patient_id = user_info.get('Patient_UUID') or normalize_id(user_info['Patient_ID'])

# 根据角色创建对话
if patient_id:
    if role == "patient":
        chat_id = chat_service.create_chat_for_patient(patient_id=patient_id, ...)
    elif role == "doctor":
        chat_id = chat_service.create_chat_for_doctor(doctor_id=patient_id, ...)  # ❌ 错误！
```

**修改后**:
```python
# 根据角色分别查询患者或医生信息
patient_id = None
doctor_id = None

if role == "patient":
    # 查询患者信息
    patient_id = user_id_normalized
    if not patient_id and message.phone_number:
        user_info = user_service.get_user_by_phone(message.phone_number)
        if user_info:
            patient_id = user_info.get('Patient_UUID') or normalize_id(user_info['Patient_ID'])

elif role == "doctor":
    # 查询医生信息
    doctor_id = user_id_normalized
    if not doctor_id and message.phone_number:
        doctor_info = user_service.get_doctor_by_phone(message.phone_number)  # ✅ 查询医生表
        if doctor_info:
            doctor_id = doctor_info.get('Doctor_UUID') or normalize_id(doctor_info['Doctor_ID'])

# 根据角色创建对话
if role == "patient" and patient_id:
    chat_id = chat_service.create_chat_for_patient(patient_id=patient_id, ...)
elif role == "doctor" and doctor_id:
    chat_id = chat_service.create_chat_for_doctor(doctor_id=doctor_id, ...)  # ✅ 正确！
```

### 3. 添加ID验证方法

**文件**: [database/chat_service.py](database/chat_service.py) (Lines 722-795)

新增验证方法：
- `validate_patient_id(patient_id)` - 验证患者ID是否存在于patient表
- `validate_doctor_id(doctor_id)` - 验证医生ID是否存在于doctor表
- `validate_user_id_for_role(user_id, role)` - 根据角色验证用户ID

```python
def validate_patient_id(self, patient_id: Union[str, int]) -> bool:
    """验证患者ID是否存在于patient表中"""
    query = """
        SELECT Patient_ID FROM patient
        WHERE Patient_UUID = %s OR CAST(Patient_ID AS CHAR) = %s
    """
    result = self.db.execute_one(query, (patient_id_normalized, patient_id_normalized))
    return result is not None

def validate_doctor_id(self, doctor_id: Union[str, int]) -> bool:
    """验证医生ID是否存在于doctor表中"""
    query = """
        SELECT Doctor_ID FROM doctor
        WHERE Doctor_UUID = %s OR CAST(Doctor_ID AS CHAR) = %s
    """
    result = self.db.execute_one(query, (doctor_id_normalized, doctor_id_normalized))
    return result is not None
```

## 测试验证

### 测试脚本
创建了测试脚本 [test_chat_role_separation.py](test_chat_role_separation.py) 进行全面验证。

### 测试结果

所有测试用例均通过 ✅

1. **✅ 医生信息查询功能**
   - 成功通过ID查询医生信息
   - 成功通过手机号查询医生信息

2. **✅ 患者信息查询功能**
   - 成功通过ID查询患者信息
   - 成功通过手机号查询患者信息

3. **✅ ID验证功能**
   - 医生ID验证：✓ 有效
   - 将医生ID作为患者ID验证：✓ 正确拒绝
   - 患者ID验证：✓ 有效
   - 将患者ID作为医生ID验证：✓ 正确拒绝

4. **✅ 创建医生对话并验证**
   - 对话类型：`User_Type='doctor'` ✓ 正确
   - 患者ID：`Patient_ID=NULL` ✓ 正确
   - 医生ID：`Doctor_ID NOT NULL` ✓ 正确

5. **✅ 创建患者对话并验证**
   - 对话类型：`User_Type='patient'` ✓ 正确
   - 医生ID：`Doctor_ID=NULL` ✓ 正确
   - 患者ID：`Patient_ID NOT NULL` ✓ 正确

### 运行测试
```bash
python test_chat_role_separation.py
```

## 影响范围

### 修改的文件
1. ✅ `database/user_history_service_v2.py` - 新增医生查询方法
2. ✅ `main.py` - 修复用户查询和会话创建逻辑
3. ✅ `database/chat_service.py` - 新增ID验证方法
4. ✅ `test_chat_role_separation.py` - 新增测试脚本

### 向后兼容性
- ✅ 所有修改都是新增功能或修复bug，不影响现有正常功能
- ✅ `create_chat_for_patient()` 和 `create_chat_for_doctor()` 的内部验证逻辑确保数据完整性
- ✅ 支持INT和UUID格式的ID查询

## 数据库约束验证

数据库表 `chat_conversation` 的约束确保数据完整性：

```sql
CONSTRAINT check_user_type_match CHECK (
    (User_Type = 'patient' AND Patient_ID IS NOT NULL AND Doctor_ID IS NULL) OR
    (User_Type = 'doctor' AND Doctor_ID IS NOT NULL AND Patient_ID IS NULL)
)
```

- 患者对话：必须 `Patient_ID NOT NULL` 且 `Doctor_ID IS NULL`
- 医生对话：必须 `Doctor_ID NOT NULL` 且 `Patient_ID IS NULL`

修复后的代码完全符合此约束。

## 预防措施

### 代码审查建议
1. ✅ 变量命名应明确表达其用途（如 `patient_id` vs `doctor_id`）
2. ✅ 根据 `role` 参数查询相应的用户表
3. ✅ 在创建对话前验证ID的有效性和角色匹配
4. ✅ 使用数据库约束防止跨表ID混用

### 后续改进建议
1. 考虑在注册时检查手机号是否已在 `patient` 或 `doctor` 表中存在
2. 如果业务需要，可以添加手机号唯一性约束（跨patient和doctor表）
3. 添加更多单元测试覆盖边界情况

## 总结

此修复解决了医生和患者对话记录混淆的严重bug，确保：
- ✅ 医生对话记录只绑定到医生账户
- ✅ 患者对话记录只绑定到患者账户
- ✅ 根据角色正确查询对应的用户表
- ✅ 数据库约束得到正确执行
- ✅ 所有测试用例通过验证

**修复状态**: 完成并验证 ✅

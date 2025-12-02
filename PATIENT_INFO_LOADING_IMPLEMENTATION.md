# 患者信息加载功能实现总结

## 实现目标
在Agent初始化时自动加载患者的基本信息（姓名、年龄、性别、病史等），使Agent能够回答"我是谁"等关于患者基本信息的问题。

## 实现方案
使用现有的病历数据，通过 `/agent/api/get-medical-record` 接口获取患者基本信息和病历列表。

---

## 一、后端修改（Java）

### 1. 新增响应类
**文件**: `backend-test/src/main/java/org/example/eyeagentbackend/core/dto/response/agent/PatientMedicalRecordsResponse.java`

```java
package org.example.eyeagentbackend.core.dto.response.agent;

import lombok.Data;
import org.example.eyeagentbackend.core.dao.entity.hospital.MedicalRecord;
import org.example.eyeagentbackend.core.dao.entity.patient.Patient;

import java.util.List;

/**
 * 患者病历响应（包含患者基本信息和病历列表）
 */
@Data
public class PatientMedicalRecordsResponse {
    private Patient patient;
    private List<MedicalRecord> medicalRecords;
}
```

### 2. Controller层添加接口
**文件**: `backend-test/src/main/java/org/example/eyeagentbackend/controller/AgentToolController.java`
**位置**: 第185-197行

```java
// ==================== 患者信息相关接口 ====================

/**
 * 获取患者病历列表（用于Agent加载患者历史病史信息）
 *
 * @param patientId 患者ID
 * @return {patient: Patient, medicalRecords: List<MedicalRecord>}
 */
@GetMapping("/get-medical-record")
public SaResult getMedicalRecords(@RequestParam String patientId) {
    return agentToolService.getMedicalRecords(patientId);
}
```

### 3. Service接口添加方法
**文件**: `backend-test/src/main/java/org/example/eyeagentbackend/core/service/AgentToolService.java`
**位置**: 第87-93行

```java
/**
 * 获取患者病历列表（包含患者基本信息）
 *
 * @param patientId 患者ID
 * @return {patient: Patient, medicalRecords: List<MedicalRecord>}
 */
SaResult getMedicalRecords(String patientId);
```

### 4. Service实现
**文件**: `backend-test/src/main/java/org/example/eyeagentbackend/core/service/impl/AgentToolServiceImpl.java`
**位置**: 第764-800行

```java
@Override
public SaResult getMedicalRecords(String patientId) {
    log.info("Patient {} 正在通过agent获取病历信息", patientId);
    try {
        if (!StringUtils.hasText(patientId)) {
            throw new AgentException("患者ID不能为空");
        }

        // 获取患者基本信息
        Patient patient = patientService.getById(patientId);
        if (patient == null) {
            throw new AgentException("未找到指定患者信息");
        }

        // 获取患者所有病历（按就诊日期降序）
        List<MedicalRecord> medicalRecords = medicalRecordService.lambdaQuery()
                .eq(MedicalRecord::getPatientId, patientId)
                .orderByDesc(MedicalRecord::getVisitDate)
                .list();

        if (CollectionUtils.isEmpty(medicalRecords)) {
            medicalRecords = Collections.emptyList();
        }

        // 构建响应
        PatientMedicalRecordsResponse response = new PatientMedicalRecordsResponse();
        response.setPatient(patient);
        response.setMedicalRecords(medicalRecords);

        return SaResult.ok("获取病历信息成功").setData(response);
    } catch (AgentException ex) {
        throw ex;
    } catch (Exception ex) {
        log.error("查询病历信息失败, patientId={}", patientId, ex);
        throw new AgentException("查询病历信息失败，请稍后再试");
    }
}
```

---

## 二、Python端修改

### 1. API Client层
**文件**: `infrastructure/api/backend_client.py`
**位置**: 第314-348行

新增方法：
```python
def get_medical_records(self, patient_id: str) -> Dict[str, Any]:
    """
    获取患者病历列表（包含患者基本信息）

    Args:
        patient_id: 患者UUID

    Returns:
        包含患者信息和病历列表的字典:
        {
            "patient": {...},
            "medicalRecords": [...]
        }

    Raises:
        APIError: 患者不存在或后端返回错误
        NetworkError: 网络请求失败
    """
    return self._request('GET', '/agent/api/get-medical-record',
                        params={'patientId': patient_id})
```

### 2. Repository层
**文件**: `infrastructure/repositories/patient_repository_impl.py`
**位置**: 第20-86行

完善`get_by_id()`方法：
```python
def get_by_id(self, patient_id: str) -> Optional[Patient]:
    """
    根据ID获取患者（通过后端API）

    使用 /agent/api/get-medical-record 接口获取患者信息和病历
    从病历中提取既往史、过敏史、家族史等信息
    """
    try:
        # 调用新的get_medical_records接口
        result = self.api_client.get_medical_records(patient_id)

        if not result:
            logger.warning(f"[PatientRepository] 患者不存在: {patient_id}")
            return None

        # 提取患者基本信息
        patient_data = result.get("patient", {})
        medical_records = result.get("medicalRecords", [])

        # 从最新的病历中提取病史信息（如果有）
        medical_history = None
        allergy_history = None
        family_history = None

        if medical_records:
            # 取最新的病历（已按visitDate降序排序）
            latest_record = medical_records[0]
            medical_history = latest_record.get("medicalHistory")
            allergy_history = latest_record.get("allergyHistory")
            family_history = latest_record.get("familyHistory")

        # 构建Patient对象
        # 注意：后端gender字段是枚举类型（male/female），需要转换
        gender_value = patient_data.get("gender")
        if isinstance(gender_value, str):
            gender = "男" if gender_value.lower() == "male" else "女"
        else:
            gender = "男" if str(gender_value).lower() == "male" else "女"

        return Patient(
            patient_id=patient_data.get("id", patient_id),
            name=patient_data.get("patientName", ""),
            age=patient_data.get("age", 0),
            gender=gender,
            phone=patient_data.get("phone", ""),
            id_number=patient_data.get("idNumber"),
            medical_history=medical_history,
            allergy_history=allergy_history,
            family_history=family_history,
        )

    except APIError as e:
        logger.warning(f"[PatientRepository] API错误: {e}")
        return None
    except NetworkError as e:
        logger.error(f"[PatientRepository] 网络错误: {e}")
        return None
    except Exception as e:
        logger.error(f"[PatientRepository] 未知错误: {e}", exc_info=True)
        return None
```

### 3. BaseAgent层
**文件**: `agents/base/base_agent.py`

#### 修改1：添加patient_info属性
**位置**: 第57-63行

```python
self.patient_id = patient_id
self.session_id = session_id
self.agent_type = agent_type
self.role = role

# 患者信息缓存（在初始化时加载）
self.patient_info: Optional[Any] = None

# 初始化LLM
self.llm: BaseChatModel = get_llm()
```

#### 修改2：调用加载方法
**位置**: 第83-90行

```python
# 创建对话链
self.conversation_chain: Optional[LLMChain] = None
self._create_conversation_chain()

# 加载患者信息（优雅降级）
self._load_patient_info()

logger.info(f"[{self.__class__.__name__}] 初始化完成: patient={patient_id}, session={session_id}")
```

#### 修改3：新增_load_patient_info()方法
**位置**: 第109-141行

```python
def _load_patient_info(self):
    """
    加载患者详细信息（优雅降级）

    如果加载失败，Agent仍能正常工作，只是缺少患者详细信息。
    失败原因可能是：
    1. 后端API未实现
    2. 网络错误
    3. 患者不存在
    """
    try:
        from infrastructure.repositories.patient_repository_impl import PatientRepositoryImpl

        patient_repo = PatientRepositoryImpl()
        self.patient_info = patient_repo.get_by_id(self.patient_id)

        if self.patient_info:
            logger.info(
                f"[{self.__class__.__name__}] 成功加载患者信息: "
                f"name={self.patient_info.name}, age={self.patient_info.age}"
            )
        else:
            logger.warning(
                f"[{self.__class__.__name__}] 未找到患者信息: {self.patient_id}"
            )

    except Exception as e:
        # 优雅降级：记录错误但不中断初始化
        logger.error(
            f"[{self.__class__.__name__}] 加载患者信息失败: {e}",
            exc_info=True
        )
        self.patient_info = None
```

#### 修改4：完善_build_additional_context()方法
**位置**: 第234-270行

```python
def _build_additional_context(self, extracted_info: Dict[str, Any]) -> str:
    """
    构建额外上下文（可被子类覆盖）

    Args:
        extracted_info: 提取的信息

    Returns:
        上下文字符串，包含患者基本信息
    """
    context_parts = []

    # 添加患者基本信息
    if self.patient_info:
        context_parts.append("【患者信息】")
        context_parts.append(f"姓名: {self.patient_info.name}")
        context_parts.append(f"年龄: {self.patient_info.age}岁")
        context_parts.append(f"性别: {self.patient_info.gender}")
        context_parts.append(f"联系电话: {self.patient_info.phone}")

        # 添加病史信息（如果有）
        if self.patient_info.medical_history:
            context_parts.append(f"既往病史: {self.patient_info.medical_history}")

        if self.patient_info.allergy_history:
            context_parts.append(f"过敏史: {self.patient_info.allergy_history}")

        if self.patient_info.family_history:
            context_parts.append(f"家族史: {self.patient_info.family_history}")

        context_parts.append("")  # 空行分隔
    else:
        # 如果没有患者详细信息，至少提供ID
        context_parts.append(f"【患者ID】{self.patient_id}")
        context_parts.append("")

    return "\n".join(context_parts)
```

### 4. 子类Agent调整

#### HealthAgent
**文件**: `agents/health/health_agent.py`
**位置**: 第185-198行

```python
def _build_additional_context(self, extracted_info: Dict[str, Any]) -> str:
    """构建额外上下文（覆盖父类方法）"""
    # 先调用父类方法获取患者基本信息
    context = super()._build_additional_context(extracted_info)

    # 添加HealthAgent特有的上下文
    context += "【预约状态】\n"
    context += f"需要预约: {'是' if self.needs_appointment else '否'}\n"
    context += f"预约已确认: {'是' if self.appointment_confirmed else '否'}\n"

    if extracted_info:
        context += f"\n【提取信息】\n{extracted_info}\n"

    return context
```

#### ReportAgent
**文件**: `agents/report/report_agent.py`
**位置**: 第146-162行

```python
def _build_additional_context(self, extracted_info: Dict[str, Any]) -> str:
    """构建额外上下文（覆盖父类方法）"""
    # 先调用父类方法获取患者基本信息
    context = super()._build_additional_context(extracted_info)

    # 添加ReportAgent特有的上下文
    context += f"【用户角色】{self.role}\n"

    if self.role == "patient":
        context += "权限: 只能查看报告，不能生成PDF\n"
    else:
        context += "权限: 可以查看和生成PDF报告\n"

    if extracted_info:
        context += f"\n【提取信息】{extracted_info}\n"

    return context
```

#### ReminderAgent
**文件**: `agents/reminder/reminder_agent.py`
**位置**: 第150-162行

```python
def _build_additional_context(self, extracted_info: Dict[str, Any]) -> str:
    """构建额外上下文（覆盖父类方法）"""
    # 先调用父类方法获取患者基本信息
    context = super()._build_additional_context(extracted_info)

    # 添加ReminderAgent特有的上下文
    if self.pending_reminder_data:
        context += f"【待创建提醒】{self.pending_reminder_data}\n"

    if extracted_info:
        context += f"\n【提取信息】{extracted_info}\n"

    return context
```

---

## 三、测试步骤

### 1. 编译并重启后端服务

```bash
cd backend-test
mvn clean package
# 重启Spring Boot应用
```

### 2. 测试后端API

```bash
curl "http://127.0.0.1:8081/agent/api/get-medical-record?patientId=f9bbb3d1c424c831a3b656a486661762" \
  -H "Agent-Token: REMOVED_CONFIGURE_BACKEND_API_TOKEN"
```

期望返回：
```json
{
  "code": 200,
  "msg": "获取病历信息成功",
  "data": {
    "patient": {
      "id": "f9bbb3d1c424c831a3b656a486661762",
      "patientName": "张伟",
      "gender": "MALE",
      "age": 45,
      "phone": "13812345678",
      ...
    },
    "medicalRecords": [
      {
        "id": "...",
        "medicalHistory": "...",
        "allergyHistory": "...",
        "familyHistory": "...",
        ...
      }
    ]
  }
}
```

### 3. 测试Python端

```bash
cd d:\Agent\pythonProject1
python -c "
import logging
logging.basicConfig(level=logging.INFO)

from agents.health.health_agent import HealthAgent

# 测试创建Agent
agent = HealthAgent(
    patient_id='f9bbb3d1c424c831a3b656a486661762',
    session_id='test_session'
)

print(f'Patient Info: {agent.patient_info}')

if agent.patient_info:
    print(f'姓名: {agent.patient_info.name}')
    print(f'年龄: {agent.patient_info.age}')
    print(f'性别: {agent.patient_info.gender}')
"
```

### 4. 测试对话功能

启动FastAPI服务：
```bash
python main.py
```

通过前端或API测试：
```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "f9bbb3d1c424c831a3b656a486661762",
    "agent_type": "health",
    "message": "你好，我是谁？"
  }'
```

期望响应包含患者姓名、年龄等信息。

---

## 四、关键特性

### 1. 优雅降级
如果API调用失败或患者不存在，Agent仍能正常工作，只是缺少患者详细信息。

### 2. 自动缓存
患者信息在Agent初始化时加载一次，缓存在`self.patient_info`中，整个会话期间复用。

### 3. 统一接口
所有Agent（HealthAgent、ReportAgent、ReminderAgent）都通过BaseAgent自动加载患者信息，无需重复实现。

### 4. 清晰的日志
- 成功加载：`[HealthAgent] 成功加载患者信息: name=张伟, age=45`
- 患者不存在：`[HealthAgent] 未找到患者信息: xxx`
- 加载失败：`[HealthAgent] 加载患者信息失败: ...`

---

## 五、文件修改清单

### Java文件（4个）
1. ✅ `backend-test/.../PatientMedicalRecordsResponse.java` (新建)
2. ✅ `backend-test/.../AgentToolController.java` (添加接口)
3. ✅ `backend-test/.../AgentToolService.java` (添加方法签名)
4. ✅ `backend-test/.../AgentToolServiceImpl.java` (实现方法)

### Python文件（6个）
1. ✅ `infrastructure/api/backend_client.py` (新增方法)
2. ✅ `infrastructure/repositories/patient_repository_impl.py` (完善实现)
3. ✅ `agents/base/base_agent.py` (核心逻辑)
4. ✅ `agents/health/health_agent.py` (调用父类)
5. ✅ `agents/report/report_agent.py` (调用父类)
6. ✅ `agents/reminder/reminder_agent.py` (调用父类)

---

## 六、下一步

1. ✅ 编译并重启后端服务
2. ✅ 测试API接口
3. ✅ 测试Agent初始化
4. ✅ 测试完整对话流程
5. 🔄 验证"我是谁"问题能得到正确回答

---

**实现完成日期**: 2025-12-02
**实现者**: Claude Code
**架构模式**: DDD + Repository Pattern + 优雅降级

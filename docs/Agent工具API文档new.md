# Agent 工具 API 文档

> 基础路径：`/agent/api`
>
> 本文档描述 AI Agent 调用的各类接口，用于预约管理、处方查询、扫描数据获取、提醒管理等功能。

---

## 目录

- - - 
  - [3. 提醒管理接口](#3-提醒管理接口)
    - [3.1 获取患者提醒信息](#31-获取患者提醒信息)
    - [3.2 获取患者提醒配置](#32-获取患者提醒配置)
    - [3.3 初始化患者提醒配置](#33-初始化患者提醒配置)
    - [3.4 修改患者提醒配置](#34-修改患者提醒配置)
    - [3.5 创建患者提醒](#35-创建患者提醒)
    - [3.6 创建用药提醒](#36-创建用药提醒)
  - [4. 数据模型](#4-数据模型)
    - [Patient](#patient)
    - [MedicalRecord](#medicalrecord)
    - [Prescription](#prescription)
    - [PrescriptionDetail](#prescriptiondetail)
    - [BiomechanicsScan](#biomechanicsscan)
    - [Reminder](#reminder)
    - [ReminderConfig](#reminderconfig)
  - [错误处理](#错误处理)
  - [更新日志](#更新日志)

---

> 

---

## 3. 提醒管理接口

### 3.1 获取患者提醒信息

获取指定患者最近的提醒记录。

**请求**

```
GET /agent/api/patient-reminder
```

**请求参数**

| 参数名    | 类型    | 必填 | 默认值 | 说明           |
| --------- | ------- | ---- | ------ | -------------- |
| patientId | String  | 是   | -      | 患者 ID (UUID) |
| limit     | Integer | 否   | 5      | 获取数量       |

**响应数据**

```json
{
  "code": 200,
  "msg": "获取患者提醒信息成功",
  "data": {
    "patient": {
      "id": "患者UUID",
      "patientName": "张三",
      "gender": "MALE",
      "age": 35
    },
    "reminders": [
      {
        "id": "提醒UUID",
        "patientId": "患者UUID",
        "reminderType": "FOLLOW_UP",
        "reminderTitle": "复诊提醒",
        "reminderContent": "您需要在下周进行复诊",
        "scheduledTime": "2025-12-10T09:00:00",
        "advanceDays": 3,
        "status": "PENDING",
        "priority": "NORMAL",
        "repeatType": "NONE",
        "notificationMethod": "APP"
      }
    ]
  }
}
```

---

### 3.2 获取患者提醒配置

获取指定患者的提醒偏好配置。

**请求**

```
GET /agent/api/patient-reminder-config
```

**请求参数**

| 参数名    | 类型   | 必填 | 说明           |
| --------- | ------ | ---- | -------------- |
| patientId | String | 是   | 患者 ID (UUID) |

**响应数据**

```json
{
  "code": 200,
  "msg": "获取患者提醒配置成功",
  "data": {
    "patient": {
      "id": "患者UUID",
      "patientName": "张三"
    },
    "config": {
      "id": "配置UUID",
      "patientId": "患者UUID",
      "enableFollowUp": true,
      "enableAppointment": true,
      "enableMedication": true,
      "defaultAdvanceDays": 3,
      "preferredNotificationMethod": "APP",
      "quietHoursStart": "22:00:00",
      "quietHoursEnd": "08:00:00"
    }
  }
}
```

---

### 3.3 初始化患者提醒配置

为患者首次创建提醒配置（已存在则报错）。

**请求**

```
POST /agent/api/init-patient-reminder-config
Content-Type: application/json
```

**请求体 - InitPatientReminderRequest**

```json
{
  "patientId": "患者UUID",
  "config": {
    "enableFollowUp": true,
    "enableAppointment": true,
    "enableMedication": true,
    "defaultAdvanceDays": 3,
    "preferredNotificationMethod": "APP",
    "quietHoursStart": "22:00:00",
    "quietHoursEnd": "08:00:00"
  }
}
```

**请求参数说明**

| 字段      | 类型           | 必填 | 说明           |
| --------- | -------------- | ---- | -------------- |
| patientId | String         | 是   | 患者 ID (UUID) |
| config    | ReminderConfig | 是   | 提醒配置对象   |

**ReminderConfig 字段说明**

| 字段                        | 类型      | 说明                              |
| --------------------------- | --------- | --------------------------------- |
| enableFollowUp              | Boolean   | 启用复诊提醒                      |
| enableAppointment           | Boolean   | 启用预约提醒                      |
| enableMedication            | Boolean   | 启用用药提醒                      |
| defaultAdvanceDays          | Integer   | 默认提前天数                      |
| preferredNotificationMethod | String    | 首选通知方式：`APP`/`SMS`/`EMAIL` |
| quietHoursStart             | LocalTime | 免打扰开始时间                    |
| quietHoursEnd               | LocalTime | 免打扰结束时间                    |

**响应数据**

```json
{
  "code": 200,
  "msg": "初始化患者提醒配置成功",
  "data": {
    "id": "配置UUID",
    "patientId": "患者UUID",
    "enableFollowUp": true,
    "enableAppointment": true,
    "enableMedication": true,
    "defaultAdvanceDays": 3,
    "preferredNotificationMethod": "APP",
    "quietHoursStart": "22:00:00",
    "quietHoursEnd": "08:00:00"
  }
}
```

---

### 3.4 修改患者提醒配置

修改已存在的患者提醒配置。

**请求**

```
POST /agent/api/modify-patient-reminder-config
Content-Type: application/json
```

**请求体 - ModifyPatientReminderConfigRequest**

与 [初始化患者提醒配置](#33-初始化患者提醒配置) 请求体格式相同。

**响应数据**

```json
{
  "code": 200,
  "msg": "修改患者提醒配置成功",
  "data": { ... }
}
```

---

### 3.5 创建患者提醒

为患者创建新的提醒任务。

**请求**

```
POST /agent/api/create-reminder
Content-Type: application/json
```

**请求体 - CreateReminderRequest**

```json
{
  "patientId": "患者UUID",
  "reminder": {
    "medicalRecordId": "病历UUID",
    "appointmentId": "预约UUID",
    "prescriptionId": "处方UUID",
    "reminderType": "FOLLOW_UP",
    "reminderTitle": "复诊提醒",
    "reminderContent": "您的复诊时间即将到来，请提前做好准备",
    "scheduledTime": "2025-12-10T09:00:00",
    "advanceDays": 3,
    "priority": "NORMAL",
    "repeatType": "NONE",
    "maxRepeatCount": 3,
    "notificationMethod": "APP",
    "notes": "请携带以往病历资料"
  }
}
```

**请求参数说明**

| 字段      | 类型     | 必填 | 说明           |
| --------- | -------- | ---- | -------------- |
| patientId | String   | 是   | 患者 ID (UUID) |
| reminder  | Reminder | 是   | 提醒对象       |

**Reminder 字段说明**

| 字段               | 类型          | 说明                                                               |
| ------------------ | ------------- | ------------------------------------------------------------------ |
| medicalRecordId    | String        | 关联病历 ID（可选）                                                |
| appointmentId      | String        | 关联预约 ID（可选）                                                |
| prescriptionId     | String        | 关联处方 ID（可选）                                                |
| reminderType       | String        | 提醒类型：`FOLLOW_UP`(复诊)/`APPOINTMENT`(预约)/`MEDICATION`(用药) |
| reminderTitle      | String        | 提醒标题                                                           |
| reminderContent    | String        | 提醒内容                                                           |
| scheduledTime      | LocalDateTime | 计划提醒时间                                                       |
| advanceDays        | Integer       | 提前天数                                                           |
| priority           | String        | 优先级：`LOW`/`NORMAL`/`HIGH`/`URGENT`                             |
| repeatType         | String        | 重复类型：`NONE`/`DAILY`/`WEEKLY`/`MONTHLY`                        |
| maxRepeatCount     | Integer       | 最大重复次数                                                       |
| notificationMethod | String        | 通知方式：`APP`/`SMS`/`EMAIL`                                      |
| notes              | String        | 备注                                                               |

**响应数据**

```json
{
  "code": 200,
  "msg": "创建患者提醒成功",
  "data": {
    "id": "提醒UUID",
    "patientId": "患者UUID",
    "reminderType": "FOLLOW_UP",
    "reminderTitle": "复诊提醒",
    "status": "PENDING",
    "createTime": "2025-12-02T11:00:00"
  }
}
```

---

### 3.6 创建用药提醒

为患者批量创建用药提醒（含关联日程）。根据指定的用药时间和持续天数，自动生成多天的 Reminder 和对应的 Agenda。

**请求**

```
POST /agent/api/create-medical-reminder
Content-Type: application/json
```

**请求体 - CreateMedicalReminderRequest**

```json
{
  "patientId": "患者UUID",
  "title": "玻璃酸钠滴眼液",
  "content": "每次1-2滴，滴入眼睑内",
  "medicalType": "DROP",
  "time": "08:30:00",
  "duration": 7
}
```

**请求参数说明**

| 字段        | 类型        | 必填 | 说明                                                     |
| ----------- | ----------- | ---- | -------------------------------------------------------- |
| patientId   | String      | 是   | 患者 ID (UUID)                                           |
| title       | String      | 是   | 提醒标题（通常为药品名称）                               |
| content     | String      | 否   | 提醒内容（用药说明）                                     |
| medicalType | MedicalType | 是   | 药品类型枚举，见下方说明                                 |
| time        | LocalTime   | 是   | 每日用药时间，格式：`HH:mm:ss`                           |
| duration    | Integer     | 是   | 持续天数（从今天起连续 N 天生成提醒）                    |

**MedicalType 枚举**

| 枚举值    | 中文描述 |
| --------- | -------- |
| `DROP`    | 滴剂     |
| `PILL`    | 药片     |
| `CAPSULE` | 胶囊     |
| `INJECT`  | 注射     |

**响应数据**

```json
{
  "code": 200,
  "msg": "已成功添加 7 个用药提醒",
  "data": null
}
```

| 字段 | 类型   | 说明                           |
| ---- | ------ | ------------------------------ |
| msg  | String | 包含实际创建的提醒数量         |
| data | null   | 无返回数据                     |

**业务规则**

- 如果当天指定的 `time` 已过（早于当前时间），则从明天开始生成提醒，持续天数顺延一天
- 每个 Reminder 自动关联创建一个 Agenda（日程），分类为 `MEDICAL`
- Reminder 的 `reminderType` 固定为 `MEDICATION`，`status` 固定为 `SCHEDULED`
- Agenda 的 `userId` 设为 `patientId`，`status` 为 `PENDING`
- Agenda 的 `category` 取自 MedicalType 的中文描述（如"滴剂"、"药片"等）

**请求示例 — 创建 7 天滴眼液提醒**

```json
{
  "patientId": "abc123-def456-ghi789",
  "title": "玻璃酸钠滴眼液",
  "content": "每次1-2滴，滴入结膜囊内，每日4次",
  "medicalType": "DROP",
  "time": "08:00:00",
  "duration": 7
}
```

**响应**

```json
{
  "code": 200,
  "msg": "已成功添加 7 个用药提醒",
  "data": null
}
```

**错误响应**

```json
{
  "code": 500,
  "msg": "未找到指定患者信息",
  "data": null
}
```

```json
{
  "code": 500,
  "msg": "创建用药提醒失败，请稍后再试",
  "data": null
}
```

---

## 4. 数据模型

### Patient

患者信息表

| 字段                  | 类型          | 说明                      |
| --------------------- | ------------- | ------------------------- |
| id                    | String        | 患者 ID (UUID)            |
| patientName           | String        | 患者姓名                  |
| gender                | Gender        | 性别枚举：`MALE`/`FEMALE` |
| age                   | Integer       | 年龄                      |
| phone                 | String        | 联系电话                  |
| idNumber              | String        | 身份证号                  |
| address               | String        | 联系地址                  |
| dateOfBirth           | LocalDateTime | 出生日期                  |
| email                 | String        | 邮箱                      |
| emergencyContact      | String        | 紧急联系人                |
| emergencyContactPhone | String        | 紧急联系人电话            |
| insuranceStatus       | String        | 医保状态                  |
| insuranceCardNumber   | String        | 医保卡号                  |

---

### MedicalRecord

病历管理表

| 字段                | 类型          | 说明                                          |
| ------------------- | ------------- | --------------------------------------------- |
| id                  | String        | 病历 ID (UUID)                                |
| patientId           | String        | 患者 ID                                       |
| visitCardNumber     | String        | 就诊卡号（格式：日期+序号，如 2025120100001） |
| reportId            | String        | 报告 ID                                       |
| visitDate           | LocalDateTime | 就诊日期                                      |
| visitTime           | LocalDateTime | 就诊时间                                      |
| department          | String        | 科室                                          |
| chiefComplaint      | String        | 主诉                                          |
| presentIllness      | String        | 现病史                                        |
| medicalHistory      | String        | 既往史                                        |
| allergyHistory      | String        | 过敏史                                        |
| familyHistory       | String        | 家族史                                        |
| medicationHistory   | String        | 用药史                                        |
| physicalExamination | String        | 体格检查                                      |
| eyeExamResults      | String        | 眼部检查结果                                  |
| specialExams        | String        | 特殊检查                                      |
| auxiliaryExams      | String        | 辅助检查                                      |
| diagnosis           | String        | 诊断                                          |
| aiDiagnosis         | String        | AI 诊断                                       |
| treatmentPlan       | String        | 治疗方案                                      |
| medication          | String        | 用药                                          |
| surgicalHistory     | String        | 手术史                                        |
| hospitalizationInfo | String        | 住院信息                                      |
| followUpDate        | LocalDateTime | 复诊日期                                      |
| physicianName       | String        | 医生姓名                                      |
| doctorSignature     | String        | 医生签名                                      |
| printTime           | LocalDateTime | 打印时间                                      |

---

### Prescription

处方管理表

| 字段                 | 类型          | 说明                                          |
| -------------------- | ------------- | --------------------------------------------- |
| id                   | String        | 处方 ID (UUID)                                |
| patientId            | String        | 患者 ID                                       |
| doctorId             | String        | 医生 ID                                       |
| medicalRecordId      | String        | 病历 ID                                       |
| prescriptionNumber   | String        | 处方编号                                      |
| prescriptionDate     | LocalDateTime | 处方日期                                      |
| prescriptionType     | String        | 处方类型                                      |
| diagnosisDescription | String        | 诊断描述                                      |
| usageInstruction     | String        | 用药指导                                      |
| prescriptionStatus   | String        | 处方状态：`待审核`/`已审核`/`已配药`/`已取药` |
| totalAmount          | BigDecimal    | 总金额                                        |
| notes                | String        | 备注                                          |
| prescriberName       | String        | 开处方医生姓名                                |
| prescriberSignature  | String        | 医生签名                                      |
| pharmacistName       | String        | 药师姓名                                      |
| pharmacistSignature  | String        | 药师签名                                      |
| dispensedDate        | LocalDateTime | 配药日期                                      |

---

### PrescriptionDetail

处方明细表

| 字段                | 类型       | 说明                    |
| ------------------- | ---------- | ----------------------- |
| id                  | String     | 明细 ID (UUID)          |
| prescriptionId      | String     | 处方 ID                 |
| drugId              | String     | 药品编号                |
| drugName            | String     | 药品名称                |
| drugSpecification   | String     | 药品规格                |
| quantity            | Integer    | 数量                    |
| unit                | String     | 单位                    |
| dosage              | String     | 用量（如：每次 1-2 滴） |
| frequency           | String     | 频次（如：每日 2-4 次） |
| duration            | String     | 疗程（如：1-2 周）      |
| administrationRoute | String     | 给药途径（如：滴眼）    |
| unitPrice           | BigDecimal | 单价                    |
| subtotal            | BigDecimal | 小计                    |
| specialInstructions | String     | 特殊说明                |

---

### BiomechanicsScan

生物力学扫描数据表（完整字段列表）

**基本信息**

| 字段            | 类型          | 说明                      |
| --------------- | ------------- | ------------------------- |
| id              | String        | 扫描 ID (UUID)            |
| patientId       | String        | 患者 ID                   |
| medicalRecordId | String        | 病历 ID                   |
| patientName     | String        | 患者姓名                  |
| gender          | Boolean       | 性别（true=男，false=女） |
| birthDate       | LocalDateTime | 出生日期                  |
| age             | Integer       | 年龄                      |
| scanDate        | LocalDateTime | 扫描日期                  |
| scanTime        | LocalDateTime | 扫描时间                  |
| operator        | String        | 操作员                    |

**眼轴/厚度测量**

| 字段      | 类型       | 说明         | 正常范围     |
| --------- | ---------- | ------------ | ------------ |
| axlR/axlL | BigDecimal | 眼轴长度     | 22.0-24.5 mm |
| cctR/cctL | BigDecimal | 角膜中央厚度 | 500-560 μm   |
| acdR/acdL | BigDecimal | 前房深度     | 2.5-3.5 mm   |
| ltR/ltL   | BigDecimal | 晶状体厚度   | 4.0-5.0 mm   |
| vtR/vtL   | BigDecimal | 玻璃体厚度   | -            |

**角膜曲率**

| 字段            | 类型       | 说明        | 正常范围    |
| --------------- | ---------- | ----------- | ----------- |
| k1DR/k1DL       | BigDecimal | K1 屈光度   | 42.0-46.0 D |
| k1MmR/k1MmL     | BigDecimal | K1 曲率半径 | 7.5-8.2 mm  |
| k1AxisR/k1AxisL | BigDecimal | K1 轴位     | 0-180°      |
| k2DR/k2DL       | BigDecimal | K2 屈光度   | 42.0-46.0 D |
| k2MmR/k2MmL     | BigDecimal | K2 曲率半径 | 7.5-8.2 mm  |
| k2AxisR/k2AxisL | BigDecimal | K2 轴位     | 0-180°      |

**其他测量**

| 字段                          | 类型       | 说明       | 正常范围     |
| ----------------------------- | ---------- | ---------- | ------------ |
| astigmatismR/astigmatismL     | BigDecimal | 散光度     | -            |
| wtwR/wtwL                     | BigDecimal | 白到白距离 | 11.0-12.5 mm |
| pupilDiameterR/pupilDiameterL | BigDecimal | 瞳孔直径   | 3.0-6.0 mm   |
| trR/trL                       | BigDecimal | TR 参数    | -            |

**时间序列数据**

扫描包含多组时间序列测量点（T1-T8）：

- `acT1` ~ `acT8`: Ac 测量点
- `pT1` ~ `pT8`: P 测量点
- `i1T1` ~ `i5T8`: I1-I5 测量点
- `r1T1` ~ `r5T8`: R1-R5 测量点

**报告信息**

| 字段         | 类型          | 说明         |
| ------------ | ------------- | ------------ |
| notes        | String        | 备注信息     |
| reportStatus | String        | 报告状态     |
| reportType   | String        | 报告类型     |
| reportPath   | String        | 报告文件路径 |
| reviewedBy   | String        | 审核人       |
| reviewedAt   | LocalDateTime | 审核时间     |

---

### Reminder

提醒任务管理表

| 字段               | 类型          | 说明                                           |
| ------------------ | ------------- | ---------------------------------------------- |
| id                 | String        | 提醒 ID (UUID)                                 |
| patientId          | String        | 患者 ID                                        |
| medicalRecordId    | String        | 病历 ID                                        |
| appointmentId      | String        | 预约 ID                                        |
| prescriptionId     | String        | 处方 ID                                        |
| reminderType       | String        | 提醒类型                                       |
| reminderTitle      | String        | 提醒标题                                       |
| reminderContent    | String        | 提醒内容                                       |
| scheduledTime      | LocalDateTime | 计划提醒时间                                   |
| advanceDays        | Integer       | 提前天数                                       |
| sentTime           | LocalDateTime | 发送时间                                       |
| completedTime      | LocalDateTime | 完成时间                                       |
| cancelledTime      | LocalDateTime | 取消时间                                       |
| status             | String        | 状态：`PENDING`/`SENT`/`COMPLETED`/`CANCELLED` |
| priority           | String        | 优先级：`LOW`/`NORMAL`/`HIGH`/`URGENT`         |
| repeatType         | String        | 重复类型：`NONE`/`DAILY`/`WEEKLY`/`MONTHLY`    |
| repeatCount        | Integer       | 已重复次数                                     |
| maxRepeatCount     | Integer       | 最大重复次数                                   |
| notificationMethod | String        | 通知方式：`APP`/`SMS`/`EMAIL`                  |
| notes              | String        | 备注                                           |

---

### ReminderConfig

患者提醒偏好配置表

| 字段                        | 类型      | 说明           |
| --------------------------- | --------- | -------------- |
| id                          | String    | 配置 ID (UUID) |
| patientId                   | String    | 患者 ID        |
| enableFollowUp              | Boolean   | 启用复诊提醒   |
| enableAppointment           | Boolean   | 启用预约提醒   |
| enableMedication            | Boolean   | 启用用药提醒   |
| defaultAdvanceDays          | Integer   | 默认提前天数   |
| preferredNotificationMethod | String    | 首选通知方式   |
| quietHoursStart             | LocalTime | 免打扰开始时间 |
| quietHoursEnd               | LocalTime | 免打扰结束时间 |

---

## 错误处理

所有接口在发生错误时会抛出 `AgentException`，返回格式：

```json
{
  "code": 500,
  "msg": "错误信息描述",
  "data": null
}
```

**常见错误信息**

| 错误信息                             | 说明                     |
| ------------------------------------ | ------------------------ |
| 患者 ID 不能为空                     | 未提供必要的患者 ID 参数 |
| 未找到指定患者信息                   | 患者 ID 不存在           |
| 获取数量必须大于 0                   | limit 参数无效           |
| 病历 ID 不能为空                     | 未提供必要的病历 ID 参数 |
| 未找到该病历对应的扫描数据           | 病历没有关联的扫描数据   |
| 该患者已存在提醒配置，无法重复初始化 | 重复初始化配置           |
| 该患者不存在提醒配置，请先初始化     | 修改不存在的配置         |
| 未找到医院信息                       | 医院关键字无法匹配       |
| 该日期没有医生工作                   | 查询日期医生不上班       |
| 预约时间不能早于当前时间             | 预约时间无效             |
| 该时段已无剩余名额                   | 预约时段已满             |

---

## 

|      |      |      |
| ---- | ---- | ---- |
|      |      |      |
|      |      |      |

# AgentToolController 患者综合画像与药品接口 API 文档

## 概述

本文档描述 `AgentToolController` 中以下 3 个接口：

1. 获取患者综合画像：`GET /agent/api/patient-comprehensive-profile`
2. 获取药品分页列表：`GET /agent/api/medicine-page`
3. 创建处方药订单：`POST /agent/api/create-prescription-order`

这些接口面向平台侧 AI Agent 工具调用，分别用于：

- 汇总患者核心医疗信息，供 AI 进行上下文分析
- 检索可购买药品列表
- 根据处方创建药品订单

**控制器**：`AgentToolController`

**基础路径**：`/agent/api`

**版本**：1.0

**最后更新**：2026-04-06

---

## 通用说明

### 认证说明

从当前控制器代码看，这 3 个接口**没有直接声明** `@SaCheckLogin` 或 `@SaCheckPermission` 注解。

但需要注意：

- `POST /create-prescription-order` 在服务层内部会通过 `StpUtil.getLoginIdAsString()` 读取当前登录医生 ID
- 因此，该接口在实际调用时应运行于**有效登录态上下文**中

建议调用方统一携带：

```http
satoken: <your-token>
```

### 通用响应格式

接口统一返回 `SaResult` 结构。

#### 成功响应

```json
{
  "code": 200,
  "msg": "success 或业务成功信息",
  "data": {}
}
```

#### 失败响应

```json
{
  "code": 500,
  "msg": "错误信息",
  "data": null
}
```

> 说明：部分接口还会在顶层附加额外字段，例如分页接口会额外返回 `total`、`pageNum`、`pageSize`、`pages`。

---

## 接口总览

| 接口名称     | 方法   | 路径                                         | 说明                    |
|----------|------|--------------------------------------------|-----------------------|
| 获取患者综合画像 | GET  | `/agent/api/patient-comprehensive-profile` | 返回患者基础信息、病历、检查历史、处方明细 |
| 获取药品分页列表 | GET  | `/agent/api/medicine-page`                 | 按药品名称关键字模糊搜索并分页返回药品列表 |
| 创建处方药订单  | POST | `/agent/api/create-prescription-order`     | 根据处方 ID 创建订单          |

---

## 1. 获取患者综合画像

### 接口信息

**接口**：`GET /agent/api/patient-comprehensive-profile`

**描述**：根据患者 ID 返回综合画像信息，供 AI Agent 做患者整体分析。

### 请求参数

| 参数名         | 位置    | 类型     | 必填 | 说明    |
|-------------|-------|--------|----|-------|
| `patientId` | Query | String | 是  | 患者 ID |

### 请求示例

```bash
curl -X GET "http://localhost:8081/agent/api/patient-comprehensive-profile?patientId=patient123" \
  -H "satoken: your-token"
```

### 响应说明

该接口返回 `PatientComprehensiveProfileResponse`，结构如下：

```json
{
  "code": 200,
  "msg": "获取患者综合画像成功",
  "data": {
    "patient": {
      "id": "patient123",
      "patientName": "张三",
      "gender": "MALE",
      "age": 35,
      "phone": "13800138000",
      "idNumber": "110101199001011234",
      "address": "北京市朝阳区",
      "allergyHistory": "青霉素过敏"
    },
    "medicalRecords": [
      {
        "id": "mr001",
        "patientId": "patient123",
        "visitDate": "2026-03-20T00:00:00",
        "visitTime": "2026-03-20T09:30:00",
        "department": "眼科",
        "diagnosis": "双眼近视",
        "aiDiagnosis": "轻度近视，建议定期复查",
        "hospitalName": "北京人民医院",
        "doctorName": "李医生"
      }
    ],
    "checkHistory": [
      {
        "id": "check001",
        "medicalRecordId": "mr001",
        "patientId": "patient123",
        "doctorId": "doctor001",
        "reportNumber": "CR20260320001",
        "vaOd": 0.8,
        "vaOs": 0.7,
        "myopiaRisk": 62.5,
        "fundusDiseaseRisk": 15.0,
        "department": "眼科",
        "doctorName": "李医生",
        "aiDiagnosis": "近视风险中高，建议控制用眼"
      }
    ],
    "prescriptions": [
      {
        "prescription": {
          "id": "pres001",
          "patientId": "patient123",
          "doctorId": "doctor001",
          "medicalRecordId": "mr001",
          "prescriptionNumber": "RP20260320001",
          "prescriptionStatus": "PENDING",
          "totalAmount": 128.00
        },
        "details": [
          {
            "id": "detail001",
            "prescriptionId": "pres001",
            "drugId": "drug001",
            "drugName": "玻璃酸钠滴眼液",
            "quantity": 2,
            "unitPrice": 64.00,
            "subtotal": 128.00
          }
        ],
        "hospitalName": null
      }
    ]
  }
}
```

### 顶层字段说明

| 字段名              | 类型                              | 说明                |
|------------------|---------------------------------|-------------------|
| `patient`        | `PatientInfoResponse`           | 患者基础信息，含最近病历中的过敏史 |
| `medicalRecords` | `List<AppMedicalRecordResp>`    | 患者病历列表            |
| `checkHistory`   | `List<GetCheckHistoryResponse>` | 患者检查历史            |
| `prescriptions`  | `List<PrescriptionWithDetail>`  | 最近处方及处方明细         |

### 嵌套对象说明

#### patient（PatientInfoResponse）

基于 `Patient` 扩展，额外包含：

| 字段名              | 类型      | 说明        |
|------------------|---------|-----------|
| `id`             | String  | 患者主键 ID   |
| `patientName`    | String  | 患者姓名      |
| `gender`         | String  | 性别        |
| `age`            | Integer | 年龄        |
| `phone`          | String  | 联系电话      |
| `idNumber`       | String  | 身份证号      |
| `address`        | String  | 地址        |
| `allergyHistory` | String  | 最近病历中的过敏史 |

#### medicalRecords（AppMedicalRecordResp）

病历响应继承 `MedicalRecord`，并额外包含：

| 字段名              | 类型            | 说明    |
|------------------|---------------|-------|
| `id`             | String        | 病历 ID |
| `patientId`      | String        | 患者 ID |
| `visitDate`      | LocalDateTime | 就诊日期  |
| `visitTime`      | LocalDateTime | 就诊时间  |
| `department`     | String        | 科室    |
| `chiefComplaint` | String        | 主诉    |
| `presentIllness` | String        | 现病史   |
| `medicalHistory` | String        | 既往史   |
| `allergyHistory` | String        | 过敏史   |
| `diagnosis`      | String        | 诊断    |
| `aiDiagnosis`    | String        | AI 诊断 |
| `treatmentPlan`  | String        | 治疗方案  |
| `hospitalName`   | String        | 医院名称  |
| `doctorName`     | String        | 医生姓名  |

#### checkHistory（GetCheckHistoryResponse）

基于 `CheckResult` 扩展，额外包含科室、医生、AI 诊断：

| 字段名                 | 类型         | 说明      |
|---------------------|------------|---------|
| `id`                | String     | 检查记录 ID |
| `medicalRecordId`   | String     | 病历 ID   |
| `patientId`         | String     | 患者 ID   |
| `doctorId`          | String     | 医生 ID   |
| `reportNumber`      | String     | 报告编号    |
| `vaOd`              | BigDecimal | 右眼视力    |
| `vaOs`              | BigDecimal | 左眼视力    |
| `myopiaRisk`        | BigDecimal | 近视风险    |
| `fundusDiseaseRisk` | BigDecimal | 眼底病风险   |
| `resultContent`     | String     | 检查结果内容  |
| `funduscopy`        | String     | 眼底检查    |
| `department`        | String     | 科室      |
| `doctorName`        | String     | 医生姓名    |
| `aiDiagnosis`       | String     | AI 诊断   |

#### prescriptions（PrescriptionWithDetail）

| 字段名            | 类型                         | 说明             |
|----------------|----------------------------|----------------|
| `prescription` | `Prescription`             | 处方基本信息         |
| `details`      | `List<PrescriptionDetail>` | 药品明细列表         |
| `hospitalName` | String                     | 医院名称（当前实现可能为空） |

### 当前实现约束

1. `patient.allergyHistory` 取自**最近一条病历**
2. `prescriptions` 当前最多返回**最近 20 条处方**
3. 当前接口**不包含**：
    - 提醒信息 / 提醒配置
    - 生物力学扫描数据
    - 预约/日程信息
4. 如需提醒或扫描数据，请分别调用已有专用接口：
    - `/agent/api/patient-reminder`
    - `/agent/api/patient-reminder-config`
    - `/agent/api/patient-scan-data`

### 常见错误

| 场景           | msg                |
|--------------|--------------------|
| patientId 为空 | `患者ID不能为空`         |
| 患者不存在        | `未找到指定患者信息`        |
| 聚合查询异常       | `获取患者综合画像失败，请稍后再试` |

---

## 2. 获取药品分页列表

### 接口信息

**接口**：`GET /agent/api/medicine-page`

**描述**：分页查询药品信息，支持按药品名称关键字模糊搜索。

### 请求参数

| 参数名        | 位置    | 类型      | 必填 | 默认值  | 说明                      |
|------------|-------|---------|----|------|-------------------------|
| `pageNum`  | Query | Integer | 否  | `1`  | 页码，从 1 开始               |
| `pageSize` | Query | Integer | 否  | `10` | 每页数量                    |
| `keyword`  | Query | String  | 否  | -    | 药品名称关键字，模糊匹配 `drugName` |

### 请求示例

```bash
curl -X GET "http://localhost:8081/agent/api/medicine-page?pageNum=1&pageSize=10&keyword=滴眼液" \
  -H "satoken: your-token"
```

### 响应示例

```json
{
  "code": 200,
  "msg": "查询成功",
  "data": [
    {
      "id": "drug-uuid-001",
      "drugId": "D2026001",
      "drugName": "玻璃酸钠滴眼液",
      "drugCategory": "眼科用药",
      "drugSpecification": "0.1%*10ml",
      "drugDosageForm": "滴眼液",
      "manufacturer": "某制药公司",
      "batchNumber": "BN20260301",
      "expiryDate": "2027-03-01T00:00:00",
      "price": 64.00,
      "stockQuantity": 126,
      "isPrescriptionDrug": true,
      "drugStatus": "ENABLE",
      "insuranceCategory": "甲类",
      "warningInfo": "开封后请尽快使用",
      "drugDescription": "用于缓解干眼症状",
      "createTime": "2026-03-01T10:00:00",
      "updateTime": "2026-03-10T10:00:00"
    }
  ],
  "total": 23,
  "pageNum": 1,
  "pageSize": 10,
  "pages": 3
}
```

### 响应字段说明

#### 顶层字段

| 字段名        | 类型            | 说明      |
|------------|---------------|---------|
| `code`     | Integer       | 状态码     |
| `msg`      | String        | 返回消息    |
| `data`     | `List<Drugs>` | 当前页药品列表 |
| `total`    | Long          | 总记录数    |
| `pageNum`  | Long          | 当前页码    |
| `pageSize` | Long          | 每页大小    |
| `pages`    | Long          | 总页数     |

#### 药品对象字段（Drugs）

| 字段名                  | 类型            | 说明     |
|----------------------|---------------|--------|
| `id`                 | String        | 主键 ID  |
| `drugId`             | String        | 药品业务编号 |
| `drugName`           | String        | 药品名称   |
| `drugCategory`       | String        | 药品分类   |
| `drugSpecification`  | String        | 药品规格   |
| `drugDosageForm`     | String        | 剂型     |
| `manufacturer`       | String        | 生产厂家   |
| `batchNumber`        | String        | 批号     |
| `expiryDate`         | LocalDateTime | 过期日期   |
| `price`              | BigDecimal    | 价格     |
| `stockQuantity`      | Integer       | 库存数量   |
| `isPrescriptionDrug` | Boolean       | 是否处方药  |
| `drugStatus`         | String        | 药品状态   |
| `insuranceCategory`  | String        | 医保类别   |
| `warningInfo`        | String        | 警告信息   |
| `drugDescription`    | String        | 药品描述   |
| `createTime`         | LocalDateTime | 创建时间   |
| `updateTime`         | LocalDateTime | 更新时间   |

### 查询规则

当前实现内部固定为：

- `keyword` → 模糊匹配 `drugName`
- 不按 `manufacturer` 过滤
- 不按 `isPrescriptionDrug` 过滤
- 不按 `insuranceCategory` 过滤
- 按 `drugName` 升序排序

### 常见错误

| 场景     | msg               |
|--------|-------------------|
| 分页查询异常 | `分页查询药品信息失败: ...` |

---

## 3. 创建处方药订单

### 接口信息

**接口**：`POST /agent/api/create-prescription-order`

**描述**：根据处方 ID 创建处方药订单。

### 业务约束

1. 该接口底层会读取当前登录用户作为 `doctorId`
2. 因此调用方应处于**平台医生登录态**
3. 同一处方如果已有未失效订单，重复创建会失败
4. 订单创建成功后返回 `DrugOrder` 主表对象，不包含订单项列表

### 请求参数（Body）

| 字段名              | 类型     | 必填 | 说明    |
|------------------|--------|----|-------|
| `prescriptionId` | String | 是  | 处方 ID |
| `remark`         | String | 否  | 订单备注  |

### 请求示例

```bash
curl -X POST "http://localhost:8081/agent/api/create-prescription-order" \
  -H "Content-Type: application/json" \
  -H "satoken: your-token" \
  -d '{
    "prescriptionId": "pres001",
    "remark": "AI工具代医生创建处方订单"
  }'
```

### 响应示例

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": "order-uuid-001",
    "orderNo": "2026040613050100001",
    "patientId": "patient123",
    "orderType": "PRESCRIPTION",
    "prescriptionId": "pres001",
    "doctorId": "doctor001",
    "totalAmount": 128.00,
    "orderStatus": "PENDING_PAYMENT",
    "paymentMethod": null,
    "paidTime": null,
    "expireTime": "2026-04-07T13:05:00",
    "remark": "AI工具代医生创建处方订单",
    "createTime": "2026-04-06T13:05:00",
    "updateTime": "2026-04-06T13:05:00"
  }
}
```

### 响应字段说明（DrugOrder）

| 字段名              | 类型            | 说明                      |
|------------------|---------------|-------------------------|
| `id`             | String        | 订单主键 ID                 |
| `orderNo`        | String        | 订单编号                    |
| `patientId`      | String        | 患者 ID                   |
| `orderType`      | String        | 订单类型，当前为 `PRESCRIPTION` |
| `prescriptionId` | String        | 处方 ID                   |
| `doctorId`       | String        | 医生 ID                   |
| `totalAmount`    | BigDecimal    | 订单总金额                   |
| `orderStatus`    | String        | 订单状态                    |
| `paymentMethod`  | String        | 支付方式，未支付时可能为 `null`     |
| `paidTime`       | LocalDateTime | 支付时间                    |
| `expireTime`     | LocalDateTime | 过期时间                    |
| `remark`         | String        | 备注                      |
| `createTime`     | LocalDateTime | 创建时间                    |
| `updateTime`     | LocalDateTime | 更新时间                    |

### 订单状态说明

| 枚举值               | 说明  |
|-------------------|-----|
| `PENDING_PAYMENT` | 待支付 |
| `PAID`            | 已支付 |
| `COMPLETED`       | 已完成 |
| `CANCELLED`       | 已取消 |
| `EXPIRED`         | 已过期 |

### 常见错误

| 场景                  | msg                          |
|---------------------|------------------------------|
| `prescriptionId` 为空 | `处方ID不能为空`                   |
| 处方不存在               | 例如：`处方不存在: pres001`          |
| 该处方已创建订单            | 例如：`该处方已创建订单: pres001`       |
| 当前无有效登录态            | 依赖 Sa-Token 登录上下文，可能出现登录相关异常 |
| 服务异常                | `创建处方订单失败，请稍后再试`             |

---

## 调用建议

### 推荐调用顺序

1. 若需分析患者背景：先调 `patient-comprehensive-profile`
2. 若需展示药品：调 `medicine-page`
3. 若已确认处方：调 `create-prescription-order`

### AI Agent 使用建议

- `patient-comprehensive-profile` 适合做病情上下文分析
- `medicine-page` 适合做药品检索、候选药品说明
- `create-prescription-order` 适合在医生确认处方后执行，不建议让 AI 在无登录态、无医生确认时直接调用

---

## 版本记录

| 版本  | 日期         | 说明                               |
|-----|------------|----------------------------------|
| 1.0 | 2026-04-06 | 新增 AgentToolController 中 3 个接口文档 |

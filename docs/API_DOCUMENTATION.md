# 智能医疗咨询系统 - API 接口文档

**版本**: 3.0.0
**基础URL**: `http://{host}:{port}`
**更新时间**: 2026-02-27

---

## 目录

1. [概述](#概述)
2. [通用说明](#通用说明)
3. [安全机制](#安全机制)
4. [核心接口 — 聊天对话](#核心接口--聊天对话)
5. [科研Agent接口](#科研agent接口)
6. [合规审查Agent接口](#合规审查agent接口)
7. [产品推荐Agent接口](#产品推荐agent接口)
8. [会话管理接口](#会话管理接口)
9. [辅助接口](#辅助接口)
10. [数据模型](#数据模型)
11. [错误处理](#错误处理)
12. [使用流程](#使用流程)

---

## 概述

本系统是基于 LangGraph 的多 Agent 智能医疗咨询平台，提供眼科健康咨询、报告分析、提醒管理、科研辅助、合规审查和产品推荐功能。系统具备多层安全防护（输入注入检测、角色校验、输出安全校验），支持同步和 SSE 流式两种对话模式。

### Agent 类型

| 类型 | 标识 | 说明 | 访问权限 |
|-----|-----|-----|---------|
| 健康咨询 | `health` | 默认 Agent，症状评估、智能分诊、预约推荐 | 患者 + 医生 |
| 报告分析 | `report` | 检查报告解读、处方查询、PDF 生成 | 患者 + 医生 |
| 提醒管理 | `reminder` | 用药提醒、复诊提醒、预约提醒 | 患者 + 医生 |
| 科研辅助 | `research` | 文献检索、数据分析、论文辅助 | 仅医生 |
| 合规审查 | `compliance` | 处方/诊断/病历/检查合规性审查 | 仅医生 |
| 产品推荐 | `recommendation` | 药品/器械推荐、购物车、处方开具 | 患者 + 医生 |

### 系统路由

系统采用两层路由机制自动识别用户意图并分配到对应 Agent：
1. **规则引擎**：基于关键词和正则匹配，零延迟
2. **LLM 路由**：对模糊意图使用轻量 LLM 判断

---

## 通用说明

### 请求格式
- Content-Type: `application/json`
- 字符编码: `UTF-8`

### UUID 格式要求
`patient_id`、`doctor_id`、`conversation_id` 等 ID 字段必须是有效的 UUID 格式：
- 带连字符: `550e8400-e29b-41d4-a716-446655440000`
- 不带连字符: `550e8400e29b41d4a716446655440000`

### 角色说明

| 角色 | `role` | `patient_id` | `doctor_id` | 说明 |
|-----|--------|-------------|-------------|------|
| 患者 | `patient` | 自己的 UUID | 不需要 | 可访问 health、report、reminder、recommendation |
| 医生 | `doctor` | 目标患者 UUID | **自己的 UUID** | 可访问全部 6 个 Agent |

---

## 安全机制

### 输入安全防护

所有对话接口在处理消息前会经过多层安全检测，防止提示词注入、越狱攻击和越权操作。

#### 检测层级

| 层级 | 位置 | 作用 |
|------|------|------|
| 1 - 输入防护 | GraphManager 入口 | 规则引擎 + LLM 双层检测，分级拦截 |
| 2 - 路由防护 | Router Node | 二次高风险检测（纵深防御） |
| 3 - 提示词加固 | Agent 系统提示词 | 指令级防御，拒绝角色篡改/提示泄露 |
| 4 - 上下文消毒 | 提示词构建 | 清理注入标记后再插入上下文 |
| 5 - 输出校验 | Response Node | 检测并阻止系统提示泄露 |

#### 分级响应

**高风险**（明确的注入攻击）：立即中断对话，返回警告：
```json
{
  "response": "检测到您的输入包含不安全内容。为了保障系统安全和您的隐私，本次对话已被中断。如果您有正常的医疗咨询需求，请重新描述您的问题。\n\n如有疑问，请联系客服。",
  "stage": "security_blocked",
  "is_completed": true
}
```

**低风险**（模糊的越权尝试）：返回引导回复，对话可继续：
```json
{
  "response": "抱歉，我无法处理您的请求。我是一个专业的医疗咨询助手，只能为您提供眼科健康咨询、预约、报告查看等医疗服务。\n\n请问您有什么健康方面的问题需要咨询吗？",
  "stage": "security_blocked",
  "is_completed": false
}
```

流式接口的安全拦截以 SSE 事件返回：
```
data: {"type": "token", "content": "拦截回复文本...", "metadata": {"security_blocked": true, "risk": "high"}}

data: {"type": "done", "content": "", "metadata": {"security_blocked": true}}
```

### 角色校验

系统在服务端对角色进行校验，不信任客户端提交的 `role` 字段：

| 场景 | 处理 |
|------|------|
| `role=doctor` 但未提供 `doctor_id` | 降级为 `patient` |
| `doctor_id` UUID 格式无效 | 降级为 `patient` |
| `doctor_id` 与 `patient_id` 相同 | 降级为 `patient`（防自我提权） |
| 降级后 `agent_type` 为 doctor-only Agent | 自动回退到 `health` |

---

## 核心接口 — 聊天对话

### 1.1 发送消息（同步）

**请求**
```
POST /api/chat
```

**请求体**
```json
{
  "message": "我眼睛最近很干涩，想预约医生",
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "doctor_id": null,
  "session_id": null,
  "agent_type": "health",
  "role": "patient",
  "conversation_id": null
}
```

| 字段 | 类型 | 必需 | 说明 |
|-----|-----|-----|-----|
| `message` | string | 是 | 用户消息内容 |
| `patient_id` | string | 是 | 患者 UUID |
| `doctor_id` | string | 医生端必需 | 医生 UUID |
| `session_id` | string | 否 | 会话 ID，为空则自动生成 |
| `agent_type` | string | 否 | Agent 类型，默认 `health`。可选：`report`、`reminder`、`research`、`compliance`、`recommendation` |
| `role` | string | 否 | 用户角色，默认 `patient`，可选 `doctor` |
| `conversation_id` | string | 否 | 数据库会话 ID。为空=新建对话，有值=继续对话 |

**响应**
```json
{
  "response": "您好！我是小Eye，很高兴为您服务。您提到眼睛干涩，请问持续多长时间了？",
  "session_id": "sess-abc123",
  "conversation_id": "660e8400-e29b-41d4-a716-446655440099",
  "is_completed": false,
  "stage": "health_consultation",
  "agent_type": "health",
  "metadata": {
    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
    "message_count": 2,
    "role": "patient",
    "thread_id": "...",
    "version": "3.0.0"
  }
}
```

| 字段 | 类型 | 说明 |
|-----|-----|-----|
| `response` | string | AI 响应内容 |
| `session_id` | string | 会话 ID |
| `conversation_id` | string | 数据库会话 ID（**后续请求需带上此值以继续对话**） |
| `is_completed` | boolean | 当前对话流程是否完成 |
| `stage` | string | 当前对话阶段 |
| `agent_type` | string | 当前 Agent 类型 |
| `metadata` | object | 附加元数据 |

---

### 1.2 发送消息（SSE 流式）

**请求**
```
POST /api/chat/stream
```

请求体与同步接口相同。响应为 SSE 事件流。

**SSE 事件类型**

| 事件 | 说明 | 数据字段 |
|------|------|---------|
| `start` | 会话初始化 | `session_id`, `conversation_id`, `thread_id` |
| `token` | 文本片段 | `content` |
| `agent_switch` | Agent 切换通知 | `from`, `to` |
| `tool_call` | 工具调用 | `tool`, `status`(start/end), `input`, `output` |
| `done` | 完成 | `response`, `agent_type`, `stage`, `session_id`, `conversation_id` |
| `error` | 错误 | `message` |

**示例事件流**
```
data: {"event": "start", "session_id": "sess_abc", "conversation_id": "...", "thread_id": "..."}

data: {"event": "token", "content": "您好！"}

data: {"event": "token", "content": "我是小Eye"}

data: {"event": "tool_call", "tool": "get_doctor_free_time", "status": "start", "input": {...}}

data: {"event": "tool_call", "tool": "get_doctor_free_time", "status": "end", "output": "..."}

data: {"event": "done", "response": "完整回复...", "agent_type": "health", "stage": "appointment_inquiry"}
```

**响应 Headers**
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

---

### 1.3 获取会话状态

```
GET /api/chat/{session_id}/state?conversation_id={id}
```

| 参数 | 类型 | 说明 |
|-----|-----|-----|
| `session_id` | path | 会话 ID |
| `conversation_id` | query, 可选 | 数据库会话 ID |

**响应**
```json
{
  "session_id": "sess-abc123",
  "conversation_id": "...",
  "current_agent": "health",
  "stage": "health_consultation",
  "is_completed": false,
  "message_count": 6
}
```

---

### 1.4 获取消息历史

```
GET /api/chat/{session_id}/messages?conversation_id={id}
```

**响应**
```json
{
  "session_id": "sess-abc123",
  "conversation_id": "...",
  "thread_id": "...",
  "message_count": 6,
  "messages": [...]
}
```

---

### 1.5 获取 Agent 切换历史

```
GET /api/chat/{session_id}/agent-history?conversation_id={id}
```

**响应**
```json
{
  "session_id": "sess-abc123",
  "thread_id": "...",
  "history": [
    {
      "agent_type": "health",
      "checkpoint_id": "...",
      "started_at": "2026-02-27T10:00:00",
      "ended_at": "2026-02-27T10:05:00"
    }
  ]
}
```

---

### 1.6 获取状态检查点

```
GET /api/chat/{session_id}/checkpoints?conversation_id={id}&limit=10
```

**响应**
```json
{
  "session_id": "sess-abc123",
  "thread_id": "...",
  "count": 5,
  "checkpoints": [...]
}
```

---

### 1.7 删除会话

```
DELETE /api/chat/{session_id}?conversation_id={id}
```

**响应**
```json
{
  "message": "会话已删除",
  "session_id": "sess-abc123"
}
```

---

### 对话阶段 (stage) 说明

**HealthAgent**
| 阶段 | 说明 |
|-----|-----|
| `greeting` | 初次问候 |
| `health_consultation` | 健康咨询中 |
| `symptom_assessment` | 症状评估 |
| `ophthalmology_triage` | 眼科分诊 |
| `patient_info_collection` | 患者信息收集 |
| `medical_history` | 病史采集 |
| `appointment_inquiry` | 询问预约意向 |
| `appointment_booking` | 预约确认中 |
| `completed` | 对话完成 |

**ReportAgent / ReminderAgent / ComplianceAgent / RecommendationAgent**
| 阶段 | 说明 |
|-----|-----|
| `greeting` | 初次问候 |
| `processing` | 处理中 |
| `completed` | 完成 |

**ResearchAgent**
| 阶段 | 说明 |
|-----|-----|
| `greeting` | 初次问候 |
| `data_query` | 数据查询 |
| `web_search` | 文献检索 |
| `statistical_analysis` | 统计分析 |
| `research_design` | 研究设计 |
| `paper_writing` | 论文撰写 |
| `completed` | 完成 |

---

## 科研Agent接口

> 仅医生角色可访问。

### 2.1 科研对话（同步）

```
POST /api/research/chat
```

**请求体**
```json
{
  "message": "帮我查一下青光眼最新的治疗方案",
  "doctor_id": "660e8400-e29b-41d4-a716-446655440001",
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "session_id": null,
  "conversation_id": null,
  "enable_institution_data": false,
  "enable_web_search": true,
  "web_search_types": ["pubmed", "scholar"]
}
```

| 字段 | 类型 | 必需 | 说明 |
|-----|-----|-----|-----|
| `message` | string | 是 | 科研查询内容 |
| `doctor_id` | string | 是 | 医生 UUID（服务端校验） |
| `patient_id` | string | 否 | 目标患者 UUID |
| `session_id` | string | 否 | 会话 ID |
| `conversation_id` | string | 否 | 数据库会话 ID |
| `enable_institution_data` | boolean | 否 | 开启机构数据库访问，默认 `false` |
| `enable_web_search` | boolean | 否 | 开启网页搜索，默认 `false` |
| `web_search_types` | array | 否 | 搜索类型：`general`、`pubmed`、`scholar` |

**响应**
```json
{
  "response": "根据最新文献...",
  "session_id": "research_abc123",
  "conversation_id": "...",
  "is_completed": false,
  "stage": "web_search",
  "agent_type": "research",
  "metadata": {
    "doctor_id": "...",
    "patient_id": "...",
    "enable_institution_data": false,
    "enable_web_search": true,
    "web_search_types": ["pubmed", "scholar"],
    "thread_id": "..."
  }
}
```

---

### 2.2 科研对话（SSE 流式）

```
POST /api/research/chat/stream
```

请求体同 2.1，响应为 SSE 事件流。事件类型：`start`、`chunk`、`tool_call`、`done`、`error`。

---

### 2.3 获取科研会话列表

```
GET /api/research/conversations?doctor_id={uuid}&limit=20&offset=0
```

| 参数 | 类型 | 必需 | 说明 |
|-----|-----|-----|-----|
| `doctor_id` | string | 是 | 医生 UUID |
| `limit` | int | 否 | 返回数量，1-100，默认 20 |
| `offset` | int | 否 | 偏移量，默认 0 |

**响应**
```json
{
  "conversations": [...],
  "total": 5,
  "has_more": false
}
```

---

### 2.4 获取科研会话详情

```
GET /api/research/conversations/{conversation_id}?doctor_id={uuid}
```

---

### 2.5 删除科研会话

```
DELETE /api/research/conversations/{conversation_id}?doctor_id={uuid}
```

---

### 2.6 科研Agent健康检查

```
GET /api/research/health
```

**响应**
```json
{
  "status": "healthy",
  "agent_type": "research",
  "version": "3.0.0",
  "features": {
    "institution_data": true,
    "web_search": true,
    "sse_streaming": true,
    "statistical_analysis": true,
    "data_visualization": true,
    "literature_review": true,
    "research_design": true
  },
  "dependencies": {
    "search1api": true,
    "minio": false,
    "pandas": true,
    "scipy": true,
    "matplotlib": true
  }
}
```

---

## 合规审查Agent接口

> 仅医生角色可访问。

### 3.1 合规审查对话（同步）

```
POST /api/compliance/chat
```

**请求体**
```json
{
  "message": "请审查这位患者的处方是否合规",
  "doctor_id": "660e8400-e29b-41d4-a716-446655440001",
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "session_id": null,
  "conversation_id": null
}
```

| 字段 | 类型 | 必需 | 说明 |
|-----|-----|-----|-----|
| `message` | string | 是 | 审查内容/指令 |
| `doctor_id` | string | 是 | 医生 UUID（服务端校验） |
| `patient_id` | string | 是 | 目标患者 UUID |
| `session_id` | string | 否 | 会话 ID |
| `conversation_id` | string | 否 | 数据库会话 ID |

**响应**
```json
{
  "response": "处方合规性审查结果...",
  "session_id": "compliance_abc123",
  "conversation_id": "...",
  "is_completed": false,
  "stage": "processing",
  "agent_type": "compliance",
  "metadata": {
    "doctor_id": "...",
    "patient_id": "...",
    "thread_id": "..."
  }
}
```

---

### 3.2 合规审查对话（SSE 流式）

```
POST /api/compliance/chat/stream
```

请求体同 3.1，响应为 SSE 事件流。事件类型：`start`、`chunk`、`tool_call`、`done`、`error`。

---

### 3.3 合规Agent健康检查

```
GET /api/compliance/health
```

**响应**
```json
{
  "status": "healthy",
  "agent_type": "compliance",
  "access_control": "doctor_only",
  "features": {
    "prescription_review": true,
    "diagnosis_review": true,
    "medical_record_review": true,
    "examination_review": true,
    "web_search": true,
    "sse_streaming": true,
    "save_review": true,
    "export_pdf": true
  }
}
```

---

## 产品推荐Agent接口

> 患者和医生均可访问，功能范围不同。

### 4.1 产品推荐对话（同步）

```
POST /api/recommendation/chat
```

**患者端请求体**
```json
{
  "message": "我眼睛干涩，有什么眼药水推荐吗",
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "role": "patient"
}
```

**医生端请求体**
```json
{
  "message": "这位患者需要抗青光眼药物",
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "doctor_id": "660e8400-e29b-41d4-a716-446655440001",
  "role": "doctor"
}
```

| 字段 | 类型 | 必需 | 说明 |
|-----|-----|-----|-----|
| `message` | string | 是 | 推荐查询内容 |
| `patient_id` | string | 是 | 患者 UUID |
| `doctor_id` | string | 医生端必需 | 医生 UUID |
| `role` | string | 否 | `patient`（默认）或 `doctor` |
| `session_id` | string | 否 | 会话 ID |
| `conversation_id` | string | 否 | 数据库会话 ID |

**响应**
```json
{
  "response": "根据您的症状，推荐以下产品...",
  "session_id": "rec_abc123",
  "conversation_id": "...",
  "is_completed": false,
  "stage": "processing",
  "agent_type": "recommendation",
  "ui_elements": {
    "ui_type": "product_cards",
    "product_cards": [
      {
        "product_id": "prod-001",
        "product_name": "人工泪液滴眼液",
        "generic_name": "聚乙烯醇滴眼液",
        "product_type": "OTC",
        "category": "眼科用药",
        "image_url": "https://...",
        "unit_price": 35.00,
        "specification": "10ml/瓶",
        "stock_status": "IN_STOCK",
        "indications": "干眼症、视疲劳",
        "is_prescription": false,
        "action_type": "ADD_TO_CART",
        "action_label": "加入购物车"
      }
    ],
    "options": null
  },
  "metadata": {
    "patient_id": "...",
    "role": "patient",
    "thread_id": "..."
  }
}
```

**`ui_elements` 说明**

| 字段 | 类型 | 说明 |
|-----|-----|-----|
| `ui_type` | string | UI 类型：`product_cards`、`options`、`none` |
| `product_cards` | array | 产品卡片列表（见 ProductCard 模型） |
| `options` | array | 交互选项列表（见 OptionItem 模型） |

**角色权限差异**

| 功能 | 患者 | 医生 |
|------|------|------|
| 查看非处方药 | 可以 | 可以 |
| 查看处方药详情 | 仅查看（`VIEW_DETAIL`） | 可以 |
| 加入购物车 | 非处方药/器械（`ADD_TO_CART`） | — |
| 开具处方 | — | 处方药（`PRESCRIBE`） |

---

### 4.2 产品推荐对话（SSE 流式）

```
POST /api/recommendation/chat/stream
```

请求体同 4.1，响应为 SSE 事件流。

特有事件：
```
data: {"event": "ui_elements", "ui_type": "product_cards", "product_cards": [...]}
```

---

### 4.3 推荐Agent健康检查

```
GET /api/recommendation/health
```

---

## 会话管理接口

### 5.1 获取历史会话列表

```
GET /api/conversations?host_id={uuid}&user_type=patient&limit=20&offset=0
```

| 参数 | 类型 | 必需 | 说明 |
|-----|-----|-----|-----|
| `host_id` | string | 是 | 用户 UUID（患者或医生 ID） |
| `user_type` | string | 否 | 用户类型，默认 `patient`，可选 `doctor` |
| `limit` | int | 否 | 返回数量，1-100，默认 20 |
| `offset` | int | 否 | 偏移量，默认 0 |

**响应**
```json
{
  "conversations": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440099",
      "title": "眼睛干涩想预约医生",
      "summary": "患者描述眼睛干涩症状，已推荐预约眼科医生",
      "total_messages": 12,
      "create_time": "2026-02-27T10:00:00",
      "update_time": "2026-02-27T10:30:00"
    }
  ],
  "total": 5,
  "has_more": false
}
```

---

### 5.2 获取会话详情

```
GET /api/conversations/{conversation_id}
```

**响应**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440099",
  "user_type": "patient",
  "host_id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "眼睛干涩想预约医生",
  "summary": "...",
  "total_messages": 4,
  "create_time": "2026-02-27T10:00:00",
  "update_time": "2026-02-27T10:30:00",
  "messages": [
    {
      "id": "msg-001",
      "message_order": 1,
      "message_content": "我眼睛最近很干涩",
      "message_type": "user",
      "create_time": "2026-02-27T10:00:00",
      "context": null
    },
    {
      "id": "msg-002",
      "message_order": 2,
      "message_content": "您好！请问这种情况持续多长时间了？",
      "message_type": "assistant",
      "create_time": "2026-02-27T10:00:05",
      "context": [
        {"conversation_stage": "health_consultation"},
        {"agent_type": "health"}
      ]
    }
  ]
}
```

---

### 5.3 删除会话

```
DELETE /api/conversations/{conversation_id}
```

**响应**
```json
{
  "success": true,
  "message": "会话已删除",
  "conversation_id": "660e8400-e29b-41d4-a716-446655440099"
}
```

---

## 辅助接口

### 6.1 获取患者列表

```
GET /api/users
```

**响应**
```json
{
  "success": true,
  "users": [
    {
      "Patient_ID": "550e8400-e29b-41d4-a716-446655440000",
      "Name": "张三",
      "Gender": "男",
      "Age": 35,
      "Phone_Number": "13800138000"
    }
  ]
}
```

---

### 6.2 健康检查

```
GET /health
```

**响应**
```json
{
  "status": "healthy",
  "version": "3.0.0",
  "architecture": "langgraph"
}
```

---

### 6.3 API 信息

```
GET /api/info
```

**响应**
```json
{
  "title": "智能医疗咨询系统 API",
  "version": "3.0.0",
  "architecture": "langgraph",
  "endpoints": {
    "chat": "/api/chat",
    "chat_stream": "/api/chat/stream",
    "research": "/api/research/chat",
    "compliance": "/api/compliance/chat",
    "recommendation": "/api/recommendation/chat",
    "users": "/api/users",
    "conversations": "/api/conversations"
  },
  "features": [
    "state_persistence",
    "auto_routing",
    "streaming",
    "conversation_history",
    "input_security_guard",
    "role_verification"
  ]
}
```

---

### 6.4 导出会话数据

```
GET /api/export/{session_id}?conversation_id={id}
```

**响应**
```json
{
  "session_id": "sess-abc123",
  "conversation_id": "...",
  "message_count": 6,
  "messages": [...]
}
```

---

## 数据模型

### ChatRequest

```typescript
interface ChatRequest {
  message: string;              // 必需，用户消息
  patient_id: string;           // 必需，患者 UUID
  doctor_id?: string;           // 医生端必需，医生 UUID
  session_id?: string;          // 可选，会话 ID
  agent_type?: string;          // 可选，默认 "health"
  role?: string;                // 可选，默认 "patient"
  conversation_id?: string;     // 可选，数据库会话 ID
}
```

### ChatResponse

```typescript
interface ChatResponse {
  response: string;             // AI 响应内容
  session_id: string;           // 会话 ID
  conversation_id: string;      // 数据库会话 ID
  is_completed: boolean;        // 对话是否完成
  stage: string;                // 当前阶段
  agent_type: string;           // Agent 类型
  metadata: object;             // 附加元数据
}
```

### ResearchChatRequest

```typescript
interface ResearchChatRequest {
  message: string;                    // 必需
  doctor_id: string;                  // 必需，UUID
  patient_id?: string;                // 可选，UUID
  session_id?: string;
  conversation_id?: string;
  enable_institution_data?: boolean;  // 默认 false
  enable_web_search?: boolean;        // 默认 false
  web_search_types?: string[];        // ["general","pubmed","scholar"]
}
```

### ComplianceChatRequest

```typescript
interface ComplianceChatRequest {
  message: string;            // 必需
  doctor_id: string;          // 必需，UUID
  patient_id: string;         // 必需，UUID
  session_id?: string;
  conversation_id?: string;
}
```

### RecommendationChatRequest

```typescript
interface RecommendationChatRequest {
  message: string;            // 必需
  patient_id: string;         // 必需，UUID
  doctor_id?: string;         // 医生端必需
  role?: string;              // "patient" | "doctor"
  session_id?: string;
  conversation_id?: string;
}
```

### RecommendationChatResponse

```typescript
interface RecommendationChatResponse {
  response: string;           // 纯文本响应（不含标记）
  session_id: string;
  conversation_id: string;
  is_completed: boolean;
  stage: string;
  agent_type: string;
  ui_elements?: UIElements;   // 结构化 UI 元素
  metadata: object;
}
```

### UIElements

```typescript
interface UIElements {
  ui_type: "product_cards" | "options" | "none";
  product_cards?: ProductCard[];
  options?: OptionItem[];
}
```

### ProductCard

```typescript
interface ProductCard {
  product_id: string;
  product_name: string;
  generic_name?: string;
  product_type: "PRESCRIPTION" | "OTC" | "DEVICE";
  category: string;
  image_url?: string;
  unit_price: number;
  specification?: string;
  stock_status: "IN_STOCK" | "LOW_STOCK" | "OUT_OF_STOCK";
  indications?: string;
  is_prescription: boolean;
  action_type: "ADD_TO_CART" | "PRESCRIBE" | "VIEW_DETAIL";
  action_label: string;
}
```

### OptionItem

```typescript
interface OptionItem {
  option_id: string;
  label: string;
  value: string;
  description?: string;
  icon?: string;
}
```

### ConversationSummary

```typescript
interface ConversationSummary {
  id: string;
  title: string;
  summary?: string;
  total_messages: number;
  create_time: string;       // ISO 8601
  update_time: string;       // ISO 8601
}
```

### MessageResponse

```typescript
interface MessageResponse {
  id: string;
  message_order: number;
  message_content: string;
  message_type: "user" | "assistant" | "system";
  create_time: string;       // ISO 8601
  context?: object[];
}
```

---

## 错误处理

### HTTP 状态码

| 状态码 | 说明 |
|-------|-----|
| 200 | 请求成功 |
| 400 | 请求参数错误（UUID 格式无效、缺少必需字段） |
| 403 | 权限不足（角色校验失败，如患者访问 doctor-only 接口） |
| 404 | 资源不存在（会话不存在、session 未找到） |
| 500 | 服务器内部错误 |

### 错误响应格式

```json
{
  "detail": "错误描述信息"
}
```

### 常见错误

**1. UUID 格式错误 (400)**
```json
{
  "detail": "patient_id 必须是有效的UUID格式，收到: \"invalid-id\""
}
```

**2. 角色权限不足 (403)**
```json
{
  "detail": "仅医生用户可访问合规审查Agent，请提供有效的doctor_id"
}
```

**3. 医生端缺少 doctor_id (400)**
```json
{
  "detail": "医生端请求必须提供 doctor_id"
}
```

**4. 会话不存在 (404)**
```json
{
  "detail": "会话不存在: 660e8400-e29b-41d4-a716-446655440099"
}
```

---

## 使用流程

### 典型患者对话流程

```
┌─────────────────────────────────────────────────────┐
│ Step 1: 获取患者列表                                   │
│ GET /api/users → 获取 Patient_ID                     │
└───────────────────────┬─────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────┐
│ Step 2: 开始新对话                                    │
│ POST /api/chat                                      │
│ { message: "...", patient_id: "...",                 │
│   conversation_id: null }                           │
│ → 响应中获取 conversation_id                          │
└───────────────────────┬─────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────┐
│ Step 3: 继续对话（带上 conversation_id）               │
│ POST /api/chat                                      │
│ { message: "...", patient_id: "...",                 │
│   conversation_id: "上次响应的值" }                    │
│ 系统自动路由到合适的 Agent                              │
└───────────────────────┬─────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────┐
│ Step 4: 查看历史对话                                   │
│ GET /api/conversations?host_id={patient_id}          │
│ GET /api/conversations/{id}                          │
└─────────────────────────────────────────────────────┘
```

### 典型医生工作流程

```
┌─────────────────────────────────────────────────────┐
│ Step 1: 选择患者                                      │
│ GET /api/users → 选择目标 patient_id                  │
└───────────────────────┬─────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────┐
│ Step 2: 合规审查                                      │
│ POST /api/compliance/chat                            │
│ { message: "审查处方", doctor_id: "...",              │
│   patient_id: "..." }                               │
└───────────────────────┬─────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────┐
│ Step 3: 产品推荐/开处方                                │
│ POST /api/recommendation/chat                        │
│ { message: "推荐抗青光眼药物", role: "doctor",         │
│   doctor_id: "...", patient_id: "..." }              │
│ → 响应含 ui_elements.product_cards                    │
└───────────────────────┬─────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────┐
│ Step 4: 科研辅助                                      │
│ POST /api/research/chat                              │
│ { message: "查询最新文献", doctor_id: "...",           │
│   enable_web_search: true,                           │
│   web_search_types: ["pubmed"] }                     │
└─────────────────────────────────────────────────────┘
```

### 代码示例

#### JavaScript — 流式对话

```javascript
async function chatStream(patientId, message, conversationId) {
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      patient_id: patientId,
      conversation_id: conversationId
    })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        switch (data.event) {
          case 'token':
            appendToChat(data.content);
            break;
          case 'done':
            onComplete(data);
            break;
          case 'error':
            onError(data.message);
            break;
        }
      }
    }
  }
}
```

#### Python — 同步对话

```python
import requests

BASE_URL = "http://localhost:8000"

# 患者对话
def patient_chat(patient_id: str, message: str, conversation_id: str = None):
    response = requests.post(f"{BASE_URL}/api/chat", json={
        "message": message,
        "patient_id": patient_id,
        "conversation_id": conversation_id,
    })
    return response.json()

# 医生合规审查
def compliance_review(doctor_id: str, patient_id: str, message: str):
    response = requests.post(f"{BASE_URL}/api/compliance/chat", json={
        "message": message,
        "doctor_id": doctor_id,
        "patient_id": patient_id,
    })
    return response.json()

# 科研查询（带文献检索）
def research_query(doctor_id: str, message: str):
    response = requests.post(f"{BASE_URL}/api/research/chat", json={
        "message": message,
        "doctor_id": doctor_id,
        "enable_web_search": True,
        "web_search_types": ["pubmed", "scholar"],
    })
    return response.json()
```

---

## 注意事项

1. **patient_id 必须是有效 UUID** — 先调用 `/api/users` 获取
2. **conversation_id** — 新建对话传 `null`，继续对话传上次响应值
3. **安全防护** — 系统会自动检测注入攻击并拦截，无需前端处理
4. **角色校验** — 服务端校验角色，伪造 `role=doctor` 但无有效 `doctor_id` 将被降级
5. **流式接口** — SSE 事件流，需按行解析 `data:` 前缀的 JSON 数据

### 废弃说明

| 废弃接口 | 新接口 |
|---------|-------|
| `/api/chat/history/phone/{phone}` | `/api/conversations?host_id={uuid}` |
| `/api/chat/history/{type}/{id}` | `/api/conversations?host_id={uuid}&user_type={type}` |
| `/api/chat/messages/{chatId}` | `/api/conversations/{conversation_id}` |

---

## 版本历史

| 版本 | 日期 | 变更说明 |
|-----|-----|---------|
| 3.0.0 | 2026-02-27 | LangGraph 架构重构；新增科研、合规审查、产品推荐 Agent；新增多层安全防护（输入注入检测、角色校验、输出安全校验）；新增 SSE 流式接口；新增 Agent 自动路由 |
| 2.0.0 | 2025-12-02 | 新增对话持久化功能，重构 API 接口 |
| 1.0.0 | 2025-11-01 | 初始版本 |

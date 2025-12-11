# 智能医疗咨询系统 - API 接口文档

**版本**: 2.0.0
**基础URL**: `http://{host}:{port}`
**更新时间**: 2025-12-02

---

## 目录

1. [概述](#概述)
2. [通用说明](#通用说明)
3. [核心接口](#核心接口)
   - [聊天对话](#1-聊天对话)
   - [会话管理](#2-会话管理)
4. [辅助接口](#辅助接口)
   - [用户查询](#3-用户查询)
   - [系统管理](#4-系统管理)
5. [数据模型](#数据模型)
6. [错误处理](#错误处理)
7. [使用流程](#使用流程)

---

## 概述

本系统是基于LangChain的多Agent智能医疗咨询平台，提供眼科健康咨询、报告分析、提醒管理等功能。

### 主要功能
- **健康咨询Agent**: 症状评估、智能分诊、预约推荐
- **报告分析Agent**: 检查报告解读、历史对比分析
- **提醒管理Agent**: 用药提醒、复诊提醒、预约提醒

### Agent类型
| 类型 | 标识 | 说明 |
|-----|-----|-----|
| 健康咨询 | `health` | 默认Agent，处理健康咨询和预约 |
| 报告分析 | `report` | 分析检查报告和历史数据 |
| 提醒管理 | `reminder` | 管理各类提醒事项 |

---

## 通用说明

### 请求格式
- Content-Type: `application/json`
- 字符编码: `UTF-8`

### 响应格式
所有响应均为 JSON 格式，包含以下标准结构：
```json
{
  "字段1": "值1",
  "字段2": "值2"
}
```

### 认证方式
当前版本暂无认证要求（开发阶段）。正式环境建议添加 JWT 或 API Key 认证。

### UUID 格式要求
`patient_id`、`conversation_id` 等 ID 字段必须是有效的 UUID 格式：
- 带连字符: `550e8400-e29b-41d4-a716-446655440000`
- 不带连字符: `550e8400e29b41d4a716446655440000`

---

## 核心接口

### 1. 聊天对话

#### 1.1 发送消息

与Agent进行对话交互，支持新建对话和继续历史对话。

**请求**
```
POST /api/chat
```

**患者端请求体**
```json
{
  "message": "我眼睛最近很干涩，想预约医生",
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "session_id": "sess-abc123",
  "agent_type": "health",
  "role": "patient",
  "conversation_id": null
}
```

**医生端请求体**
```json
{
  "message": "帮我分析这位患者的眼底检查报告",
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "doctor_id": "660e8400-e29b-41d4-a716-446655440001",
  "session_id": "sess-doctor-456",
  "agent_type": "report",
  "role": "doctor",
  "conversation_id": null
}
```

| 字段 | 类型 | 必需 | 说明 |
|-----|-----|-----|-----|
| `message` | string | ✅ | 用户发送的消息内容 |
| `patient_id` | string | ✅ | 患者UUID（必须是有效UUID格式） |
| `doctor_id` | string | 医生端✅ | 医生UUID（医生端必需，用于记录医生的会话） |
| `session_id` | string | ❌ | 会话ID（为空则自动生成） |
| `agent_type` | string | ❌ | Agent类型，默认 `health`，可选 `report`、`reminder` |
| `role` | string | ❌ | 用户角色，默认 `patient`，可选 `doctor` |
| `conversation_id` | string | ❌ | 数据库会话ID。为空=新建对话，有值=继续对话 |

**患者 vs 医生调用区别**

| 角色 | `role` | `patient_id` | `doctor_id` | `host_id` (存储) |
|-----|--------|-------------|-------------|-----------------|
| 患者 | `patient` | 自己的UUID | 不需要 | patient_id |
| 医生 | `doctor` | 目标患者UUID | **自己的UUID** | doctor_id |

**响应**
```json
{
  "response": "您好！我是小Eye，很高兴为您服务。您提到眼睛干涩，请问这种情况持续多长时间了？",
  "session_id": "sess-abc123",
  "conversation_id": "660e8400-e29b-41d4-a716-446655440099",
  "is_completed": false,
  "stage": "health_consultation",
  "agent_type": "health",
  "metadata": {
    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
    "message_count": 2,
    "role": "patient"
  }
}
```

| 字段 | 类型 | 说明 |
|-----|-----|-----|
| `response` | string | AI响应内容 |
| `session_id` | string | 会话ID（用于标识内存中的Agent实例） |
| `conversation_id` | string | 数据库会话ID（**重要：后续请求需带上此值以继续对话**） |
| `is_completed` | boolean | 当前对话流程是否完成 |
| `stage` | string | 当前对话阶段 |
| `agent_type` | string | 当前使用的Agent类型 |
| `metadata` | object | 附加元数据 |

**对话阶段 (stage) 说明**
| 阶段 | 说明 |
|-----|-----|
| `greeting` | 初次问候 |
| `health_consultation` | 健康咨询中 |
| `symptom_assessment` | 症状评估中 |
| `appointment_inquiry` | 询问预约意向 |
| `appointment_booking` | 预约确认中 |
| `completed` | 对话完成 |

---

### 2. 会话管理

#### 2.1 获取历史会话列表

获取指定用户的所有历史对话记录。

**请求**
```
GET /api/conversations?host_id={uuid}&user_type={type}&limit={n}&offset={n}
```

**查询参数**
| 参数 | 类型 | 必需 | 说明 |
|-----|-----|-----|-----|
| `host_id` | string | ✅ | 用户UUID（患者或医生的ID） |
| `user_type` | string | ❌ | 用户类型，默认 `patient`，可选 `doctor` |
| `limit` | integer | ❌ | 返回数量，默认 20，最大 100 |
| `offset` | integer | ❌ | 偏移量，默认 0 |

**调用示例**

患者查询自己的历史对话：

```text
GET /api/conversations?host_id={患者UUID}&user_type=patient
```

医生查询自己的历史对话：

```text
GET /api/conversations?host_id={医生UUID}&user_type=doctor
```

**响应**
```json
{
  "conversations": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440099",
      "title": "眼睛干涩想预约医生",
      "summary": "患者描述眼睛干涩症状，已推荐预约眼科医生",
      "total_messages": 12,
      "create_time": "2025-12-01T10:00:00",
      "update_time": "2025-12-01T10:30:00"
    },
    {
      "id": "770e8400-e29b-41d4-a716-446655440088",
      "title": "查看检查报告",
      "summary": null,
      "total_messages": 4,
      "create_time": "2025-11-28T15:00:00",
      "update_time": "2025-11-28T15:15:00"
    }
  ],
  "total": 5,
  "has_more": false
}
```

| 字段 | 类型 | 说明 |
|-----|-----|-----|
| `conversations` | array | 会话摘要列表 |
| `conversations[].id` | string | 会话UUID（用于获取详情或继续对话） |
| `conversations[].title` | string | 会话标题（自动从首条消息生成） |
| `conversations[].summary` | string | 会话摘要（可选） |
| `conversations[].total_messages` | integer | 消息总数 |
| `conversations[].create_time` | datetime | 创建时间（ISO 8601格式） |
| `conversations[].update_time` | datetime | 最后更新时间 |
| `total` | integer | 该用户的会话总数 |
| `has_more` | boolean | 是否还有更多数据 |

---

#### 2.2 获取会话详情

获取指定会话的完整信息和所有消息记录。

**请求**
```
GET /api/conversations/{conversation_id}
```

**路径参数**
| 参数 | 类型 | 说明 |
|-----|-----|-----|
| `conversation_id` | string | 会话UUID |

**响应**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440099",
  "user_type": "patient",
  "host_id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "眼睛干涩想预约医生",
  "summary": "患者描述眼睛干涩症状，已推荐预约眼科医生",
  "total_messages": 4,
  "create_time": "2025-12-01T10:00:00",
  "update_time": "2025-12-01T10:30:00",
  "messages": [
    {
      "id": "msg-001",
      "message_order": 1,
      "message_content": "我眼睛最近很干涩",
      "message_type": "user",
      "create_time": "2025-12-01T10:00:00",
      "context": null
    },
    {
      "id": "msg-002",
      "message_order": 2,
      "message_content": "您好！我了解到您眼睛干涩，请问这种情况持续多长时间了？",
      "message_type": "assistant",
      "create_time": "2025-12-01T10:00:05",
      "context": [
        {"patient_info": {"name": "张三", "age": 35}},
        {"conversation_stage": "health_consultation"}
      ]
    }
  ]
}
```

**会话详情字段**
| 字段 | 类型 | 说明 |
|-----|-----|-----|
| `id` | string | 会话UUID |
| `user_type` | string | 用户类型 (patient/doctor) |
| `host_id` | string | 会话主体的UUID |
| `title` | string | 会话标题 |
| `summary` | string | 会话摘要（可选） |
| `total_messages` | integer | 消息总数 |
| `create_time` | datetime | 创建时间 |
| `update_time` | datetime | 更新时间 |
| `messages` | array | 消息列表 |

**消息字段**
| 字段 | 类型 | 说明 |
|-----|-----|-----|
| `id` | string | 消息UUID |
| `message_order` | integer | 消息顺序号（从1开始） |
| `message_content` | string | 消息内容 |
| `message_type` | string | 消息类型：`user`/`assistant`/`system` |
| `create_time` | datetime | 创建时间 |
| `context` | array | 上下文信息（可选，包含患者信息、对话阶段等） |

---

#### 2.3 删除会话

软删除指定会话（数据不会物理删除）。

**请求**
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

### 3. 用户查询

#### 3.1 获取患者列表

获取系统中所有患者，用于前端下拉选择。

**请求**
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
    },
    {
      "Patient_ID": "550e8400-e29b-41d4-a716-446655440001",
      "Name": "李四",
      "Gender": "女",
      "Age": 28,
      "Phone_Number": "13900139000"
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|-----|-----|-----|
| `success` | boolean | 请求是否成功 |
| `users` | array | 患者列表 |
| `users[].Patient_ID` | string | 患者UUID（用于 chat 接口的 patient_id） |
| `users[].Name` | string | 患者姓名 |
| `users[].Gender` | string | 性别（男/女/未知） |
| `users[].Age` | integer | 年龄 |
| `users[].Phone_Number` | string | 手机号 |

---

### 4. 系统管理

#### 4.1 健康检查

**请求**
```
GET /health
```

**响应**
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "architecture": "clean_architecture",
  "active_sessions": 5
}
```

---

#### 4.2 获取API信息

**请求**
```
GET /api/info
```

**响应**
```json
{
  "title": "智能医疗咨询系统 API",
  "version": "2.0.0",
  "architecture": "clean_architecture",
  "endpoints": {
    "chat": "/api/chat",
    "users": "/api/users",
    "conversations": "/api/conversations",
    "conversation_detail": "/api/conversations/{conversation_id}"
  }
}
```

---

#### 4.3 获取活跃会话列表

获取内存中所有活跃的Agent会话（调试用）。

**请求**
```
GET /api/agents/sessions
```

**响应**
```json
{
  "total": 3,
  "sessions": [
    {
      "session_id": "sess-abc123",
      "patient_id": "550e8400-e29b-41d4-a716-446655440000",
      "agent_type": "health",
      "created_at": "2025-12-01T10:00:00"
    }
  ]
}
```

---

#### 4.4 获取会话状态

获取指定Agent会话的详细状态。

**请求**
```
GET /api/agents/sessions/{session_id}
```

**响应**
```json
{
  "session_id": "sess-abc123",
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "health",
  "stage": "health_consultation",
  "is_completed": false,
  "message_count": 6,
  "role": "patient"
}
```

---

#### 4.5 清理过期会话

清理内存中超时的Agent会话。

**请求**
```
POST /api/agents/cleanup
```

**响应**
```json
{
  "message": "清理完成",
  "expired_count": 2
}
```

---

#### 4.6 获取系统统计

**请求**
```
GET /api/agents/stats
```

**响应**
```json
{
  "active_sessions": 5,
  "total_agents": 5
}
```

---

#### 4.7 导出会话数据

导出指定session的对话数据为JSON格式。

**请求**
```
GET /api/export/{session_id}
```

**响应**
```json
{
  "session_id": "sess-abc123",
  "agent_type": "health",
  "messages": [
    {
      "role": "user",
      "content": "我眼睛很干涩",
      "timestamp": "2025-12-01T10:00:00"
    },
    {
      "role": "assistant",
      "content": "您好！请问症状持续多久了？",
      "timestamp": "2025-12-01T10:00:05"
    }
  ],
  "patient_info": {},
  "summary": ""
}
```

---

## 数据模型

### ChatRequest（聊天请求）
```typescript
interface ChatRequest {
  message: string;           // 必需，用户消息
  patient_id: string;        // 必需，患者UUID
  session_id?: string;       // 可选，会话ID
  agent_type?: string;       // 可选，默认 "health"
  role?: string;             // 可选，默认 "patient"
  conversation_id?: string;  // 可选，数据库会话ID
}
```

### ChatResponse（聊天响应）
```typescript
interface ChatResponse {
  response: string;          // AI响应内容
  session_id: string;        // 会话ID
  conversation_id: string;   // 数据库会话ID
  is_completed: boolean;     // 对话是否完成
  stage: string;             // 当前阶段
  agent_type: string;        // Agent类型
  metadata: {
    patient_id: string;
    message_count: number;
    role: string;
  };
}
```

### ConversationSummary（会话摘要）
```typescript
interface ConversationSummary {
  id: string;                // 会话UUID
  title: string;             // 标题
  summary?: string;          // 摘要
  total_messages: number;    // 消息数
  create_time: string;       // ISO 8601
  update_time: string;       // ISO 8601
}
```

### MessageResponse（消息响应）
```typescript
interface MessageResponse {
  id: string;                // 消息UUID
  message_order: number;     // 顺序号
  message_content: string;   // 内容
  message_type: string;      // user/assistant/system
  create_time: string;       // ISO 8601
  context?: Array<object>;   // 上下文
}
```

---

## 错误处理

### HTTP 状态码
| 状态码 | 说明 |
|-------|-----|
| 200 | 请求成功 |
| 400 | 请求参数错误（如 patient_id 格式无效） |
| 404 | 资源不存在（如会话不存在） |
| 500 | 服务器内部错误 |

### 错误响应格式
```json
{
  "detail": "错误描述信息"
}
```

### 常见错误

**1. patient_id 格式错误**
```json
{
  "detail": "patient_id 必须是有效的UUID格式，收到: \"invalid-id\""
}
```

**2. 会话不存在**
```json
{
  "detail": "会话不存在: 660e8400-e29b-41d4-a716-446655440099"
}
```

---

## 使用流程

### 典型对话流程

```
┌─────────────────────────────────────────────────────────────┐
│                      前端应用                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 1: 获取患者列表                                         │
│ GET /api/users                                              │
│ → 获取 Patient_ID 供用户选择                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: 开始新对话                                           │
│ POST /api/chat                                              │
│ {                                                           │
│   "message": "我眼睛干涩",                                    │
│   "patient_id": "550e8400-...",                             │
│   "conversation_id": null  ← 新对话传null                     │
│ }                                                           │
│ → 响应中获取 conversation_id                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: 继续对话（带上conversation_id）                       │
│ POST /api/chat                                              │
│ {                                                           │
│   "message": "持续了一周左右",                                 │
│   "patient_id": "550e8400-...",                             │
│   "conversation_id": "660e8400-..."  ← 继续对话传上次的值      │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 4: 查看历史对话列表                                      │
│ GET /api/conversations?host_id=550e8400-...&user_type=patient│
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 5: 加载历史对话详情                                      │
│ GET /api/conversations/660e8400-...                         │
│ → 获取完整消息列表，可继续对话                                  │
└─────────────────────────────────────────────────────────────┘
```

### 代码示例

#### JavaScript/TypeScript
```javascript
// 1. 开始新对话
async function startNewChat(patientId, message) {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: message,
      patient_id: patientId,
      conversation_id: null  // 新对话
    })
  });
  const data = await response.json();

  // 保存conversation_id用于后续对话
  localStorage.setItem('conversationId', data.conversation_id);

  return data;
}

// 2. 继续对话
async function continueChat(patientId, message) {
  const conversationId = localStorage.getItem('conversationId');

  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: message,
      patient_id: patientId,
      conversation_id: conversationId  // 继续对话
    })
  });

  return response.json();
}

// 3. 获取历史会话列表
async function getConversationList(patientId) {
  const response = await fetch(
    `/api/conversations?host_id=${patientId}&user_type=patient&limit=20`
  );
  return response.json();
}

// 4. 加载历史对话详情
async function loadConversation(conversationId) {
  const response = await fetch(`/api/conversations/${conversationId}`);
  const data = await response.json();

  // 保存conversation_id以便继续对话
  localStorage.setItem('conversationId', conversationId);

  return data;
}
```

#### Python
```python
import requests

BASE_URL = "http://localhost:8000"

# 1. 开始新对话
def start_chat(patient_id: str, message: str):
    response = requests.post(f"{BASE_URL}/api/chat", json={
        "message": message,
        "patient_id": patient_id,
        "conversation_id": None
    })
    return response.json()

# 2. 继续对话
def continue_chat(patient_id: str, message: str, conversation_id: str):
    response = requests.post(f"{BASE_URL}/api/chat", json={
        "message": message,
        "patient_id": patient_id,
        "conversation_id": conversation_id
    })
    return response.json()

# 3. 获取历史会话
def get_conversations(patient_id: str):
    response = requests.get(f"{BASE_URL}/api/conversations", params={
        "host_id": patient_id,
        "user_type": "patient",
        "limit": 20
    })
    return response.json()

# 4. 获取会话详情
def get_conversation_detail(conversation_id: str):
    response = requests.get(f"{BASE_URL}/api/conversations/{conversation_id}")
    return response.json()
```

---

## 注意事项

### 重要提醒

1. **patient_id 必须是有效UUID**
   - 必须先调用 `/api/users` 获取有效的 Patient_ID
   - 不支持使用手机号或其他格式

2. **conversation_id 的使用**
   - 新建对话：传 `null` 或不传
   - 继续对话：传之前响应中返回的 `conversation_id`
   - 加载历史对话后继续：使用历史对话的 `id`

3. **会话持久化**
   - 对话内容自动保存到数据库
   - 即使服务重启，历史对话仍可通过 conversation_id 继续

4. **session_id vs conversation_id**
   - `session_id`: 内存中Agent实例的标识，服务重启后失效
   - `conversation_id`: 数据库中对话记录的标识，持久保存

### 废弃说明

以下旧接口已废弃，请使用新接口：

| 废弃接口 | 新接口 |
|---------|-------|
| `/api/chat/history/phone/{phone}` | `/api/conversations?host_id={uuid}` |
| `/api/chat/history/{type}/{id}` | `/api/conversations?host_id={uuid}&user_type={type}` |
| `/api/chat/messages/{chatId}` | `/api/conversations/{conversation_id}` |

---

## 版本历史

| 版本 | 日期 | 变更说明 |
|-----|-----|---------|
| 2.0.0 | 2025-12-02 | 新增对话持久化功能，重构API接口 |
| 1.0.0 | 2025-11-01 | 初始版本 |

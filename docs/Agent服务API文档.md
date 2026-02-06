# Agent 服务 API 文档

> 基础路径：`/api`
>
> 本文档描述智能医疗咨询系统对外提供的 Agent 服务接口，供前端/客户端调用实现AI对话功能。

---

## 目录

- [Agent 服务 API 文档](#agent-服务-api-文档)
  - [目录](#目录)
  - [概述](#概述)
    - [系统架构](#系统架构)
    - [API 版本](#api-版本)
    - [通用响应格式](#通用响应格式)
  - [第一部分：Agent API（通用对话系统）](#第一部分agent-api通用对话系统)
    - [1. 聊天对话接口](#1-聊天对话接口)
      - [1.1 同步对话](#11-同步对话)
      - [1.2 流式对话 (SSE)](#12-流式对话-sse)
      - [1.3 删除会话](#13-删除会话)
      - [1.4 获取会话状态](#14-获取会话状态)
      - [1.5 获取 Agent 切换历史](#15-获取-agent-切换历史)
      - [1.6 获取检查点列表](#16-获取检查点列表)
      - [1.7 获取消息历史](#17-获取消息历史)
    - [2. 会话管理接口](#2-会话管理接口)
      - [2.1 获取会话列表](#21-获取会话列表)
      - [2.2 获取会话详情](#22-获取会话详情)
      - [2.3 删除会话](#23-删除会话)
    - [3. 系统接口](#3-系统接口)
      - [3.1 健康检查](#31-健康检查)
      - [3.2 API 信息](#32-api-信息)
      - [3.3 获取患者列表](#33-获取患者列表)
      - [3.4 导出对话数据](#34-导出对话数据)
    - [4. 数据模型](#4-数据模型)
      - [ChatRequest](#chatrequest)
      - [ChatResponse](#chatresponse)
      - [ConversationSummary](#conversationsummary)
      - [ConversationDetailResponse](#conversationdetailresponse)
      - [MessageResponse](#messageresponse)
      - [SSE 事件格式](#sse-事件格式)
    - [5. 对话阶段说明](#5-对话阶段说明)
      - [Health Agent 阶段](#health-agent-阶段)
      - [Report Agent 阶段](#report-agent-阶段)
      - [Reminder Agent 阶段](#reminder-agent-阶段)
    - [6. 使用示例](#6-使用示例)
      - [Python 集成示例](#python-集成示例)
      - [JavaScript 前端示例](#javascript-前端示例)
  - [第二部分：科研 Agent API](#第二部分科研-agent-api)
    - [1. 概述](#1-概述)
    - [2. 科研对话接口](#2-科研对话接口)
      - [2.1 同步科研对话](#21-同步科研对话)
      - [2.2 流式科研对话 (SSE)](#22-流式科研对话-sse)
      - [2.3 获取科研会话列表](#23-获取科研会话列表)
      - [2.4 获取科研会话详情](#24-获取科研会话详情)
      - [2.5 删除科研会话](#25-删除科研会话)
      - [2.6 科研 Agent 健康检查](#26-科研-agent-健康检查)
    - [3. 数据模型](#3-数据模型)
      - [ResearchChatRequest](#researchchatrequest)
      - [ResearchChatResponse](#researchchatresponse)
      - [WebSearchType 枚举](#websearchtype-枚举)
      - [科研 SSE 事件格式](#科研-sse-事件格式)
    - [4. 科研工具详解](#4-科研工具详解)
      - [数据查询工具](#数据查询工具)
      - [统计分析工具](#统计分析工具)
      - [文献研究工具](#文献研究工具)
      - [研究设计工具](#研究设计工具)
      - [临床决策工具](#临床决策工具)
      - [数据导出工具](#数据导出工具)
    - [5. 对话阶段](#5-对话阶段)
    - [6. 权限控制](#6-权限控制)
    - [7. 使用示例](#7-使用示例)
      - [文献搜索流程](#文献搜索流程)
      - [数据分析流程](#数据分析流程)
      - [完整工作流示例](#完整工作流示例)
  - [附录](#附录)
    - [A. 错误码说明](#a-错误码说明)
    - [B. UUID 格式规范](#b-uuid-格式规范)
    - [C. 日期时间格式](#c-日期时间格式)
    - [D. 数据库表结构](#d-数据库表结构)
  - [更新日志](#更新日志)

---

## 概述

### 系统架构

本系统基于 **LangGraph 3.0** 架构，采用多 Agent 协作模式：

```
┌─────────────────────────────────────────────────────────────┐
│                     前端/客户端                              │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Python 服务 (本文档)                    │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐   │
│  │ /api/chat   │ │ /api/conv.  │ │ /api/research       │   │
│  └─────────────┘ └─────────────┘ └─────────────────────┘   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   LangGraph Agent                           │
│  ┌────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐          │
│  │ Health │ │ Report │ │ Reminder │ │ Research │          │
│  │ Agent  │ │ Agent  │ │  Agent   │ │  Agent   │          │
│  └────────┘ └────────┘ └──────────┘ └──────────┘          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│               Java 后端 (/agent/api)                        │
│        (预约、处方、扫描、提醒等业务接口)                     │
└─────────────────────────────────────────────────────────────┘
```

### API 版本

| 属性 | 值 |
|------|-----|
| 版本 | 3.0.1 |
| 架构 | LangGraph |
| 特性 | MySQL Checkpoint 持久化、自动意图路由、Token 级别 SSE 流式响应 |

### 通用响应格式

**成功响应：**

```json
{
  "response": "AI响应内容",
  "session_id": "sess-abc123",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "is_completed": false,
  "stage": "greeting",
  "agent_type": "health",
  "metadata": {}
}
```

**错误响应：**

```json
{
  "detail": "错误信息描述"
}
```

---

## 第一部分：Agent API（通用对话系统）

### 1. 聊天对话接口

#### 1.1 同步对话

与 Agent 进行同步对话，等待完整响应返回。

**请求**

```
POST /api/chat
Content-Type: application/json
```

**请求体**

```json
{
  "message": "我想预约眼科医生",
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "doctor_id": null,
  "session_id": null,
  "conversation_id": null,
  "agent_type": "health",
  "role": "patient"
}
```

**请求参数说明**

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| message | String | 是 | - | 用户消息内容 |
| patient_id | String | 是 | - | 患者 UUID（必须是有效的 UUID 格式） |
| doctor_id | String | 否 | null | 医生 UUID（医生端必需） |
| session_id | String | 否 | 自动生成 | 会话 ID，格式：`sess_{uuid[:16]}` |
| conversation_id | String | 否 | 自动创建 | 数据库会话 ID（继续对话时使用） |
| agent_type | String | 否 | "health" | Agent 类型：`health`/`report`/`reminder` |
| role | String | 否 | "patient" | 用户角色：`patient`/`doctor` |

**响应体**

```json
{
  "response": "您好，我是小Eye，请问有什么可以帮您？",
  "session_id": "sess_abc123def456",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440099",
  "is_completed": false,
  "stage": "greeting",
  "agent_type": "health",
  "metadata": {
    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
    "role": "patient",
    "thread_id": "conv_550e8400...",
    "version": "langgraph"
  }
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| response | String | AI 生成的响应内容 |
| session_id | String | 当前会话 ID |
| conversation_id | String | 数据库会话 ID（用于后续继续对话） |
| is_completed | Boolean | 对话是否完成（用户说再见等） |
| stage | String | 当前对话阶段（详见对话阶段说明） |
| agent_type | String | 当前使用的 Agent 类型 |
| metadata | Object | 附加元数据 |

---

#### 1.2 流式对话 (SSE)

使用 Server-Sent Events 实现流式响应，实时返回 AI 生成的内容。

**请求**

```
POST /api/chat/stream
Content-Type: application/json
```

**请求体**

与 [1.1 同步对话](#11-同步对话) 相同。

**响应**

返回 `text/event-stream` 类型的 SSE 流。

**SSE 事件流示例**

```
data: {"event":"start","session_id":"sess_abc123","conversation_id":"550e8400-...","thread_id":"conv_550e8400..."}

data: {"event":"token","content":"您好"}

data: {"event":"token","content":"，"}

data: {"event":"token","content":"我是小Eye"}

data: {"event":"tool_call","tool":"get_doctor_free_time","status":"start"}

data: {"event":"tool_call","tool":"get_doctor_free_time","status":"end"}

data: {"event":"agent_switch","from":"health","to":"report"}

data: {"event":"done","response":"您好，我是小Eye，请问有什么可以帮您？","agent_type":"health","stage":"greeting","session_id":"sess_abc123","conversation_id":"550e8400-..."}
```

**SSE 事件类型**

| 事件类型 | 说明 | 数据字段 |
|---------|------|---------|
| `start` | 开始处理 | session_id, conversation_id, thread_id |
| `token` | 响应内容块（逐 token 输出） | content |
| `tool_call` | 工具调用 | tool, status (start/end), input (start时), output (end时) |
| `agent_switch` | Agent 切换 | from, to |
| `done` | 完成 | response, agent_type, stage, session_id, conversation_id |
| `error` | 错误 | message |

> **v3.0.0 更新**：`token` 事件现在实现真正的 Token 级别流式输出（打字机效果），每个事件包含一个或几个字符。

---

#### 1.3 删除会话

删除指定的会话及其所有数据。

**请求**

```
DELETE /api/chat/{session_id}?conversation_id={conversation_id}
```

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| session_id | String | 会话 ID |

**查询参数**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| conversation_id | String | 否 | 数据库会话 ID |

**响应**

```json
{
  "message": "会话已删除",
  "session_id": "sess_abc123"
}
```

---

#### 1.4 获取会话状态

获取指定会话的当前状态信息。

**请求**

```
GET /api/chat/{session_id}/state?conversation_id={conversation_id}
```

**响应**

```json
{
  "session_id": "sess_abc123",
  "conversation_id": "550e8400-...",
  "current_agent": "health",
  "stage": "greeting",
  "is_completed": false,
  "message_count": 2
}
```

---

#### 1.5 获取 Agent 切换历史

获取会话中 Agent 切换的历史记录，用于调试和监控。

**请求**

```
GET /api/chat/{session_id}/agent-history?conversation_id={conversation_id}
```

**响应**

```json
{
  "session_id": "sess_abc123",
  "conversation_id": "550e8400-...",
  "thread_id": "conv_550e8400...",
  "history": [
    {
      "agent_type": "health",
      "checkpoint_id": "checkpoint_001",
      "started_at": "2025-12-01T10:00:00",
      "ended_at": "2025-12-01T10:01:00"
    },
    {
      "agent_type": "report",
      "checkpoint_id": "checkpoint_002",
      "started_at": "2025-12-01T10:01:00",
      "ended_at": null
    }
  ]
}
```

---

#### 1.6 获取检查点列表

获取会话的 LangGraph 检查点列表，用于状态回溯和调试。

**请求**

```
GET /api/chat/{session_id}/checkpoints?conversation_id={conversation_id}&limit=10
```

**查询参数**

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| conversation_id | String | 否 | - | 数据库会话 ID |
| limit | Integer | 否 | 10 | 返回数量限制 |

**响应**

```json
{
  "session_id": "sess_abc123",
  "conversation_id": "550e8400-...",
  "thread_id": "conv_550e8400...",
  "count": 3,
  "checkpoints": [
    {
      "ts": "2025-12-01T10:00:00",
      "id": "checkpoint_001",
      "metadata": {
        "agent_type": "health",
        "stage": "greeting"
      }
    }
  ]
}
```

---

#### 1.7 获取消息历史

获取会话的完整消息历史。

**请求**

```
GET /api/chat/{session_id}/messages?conversation_id={conversation_id}
```

**响应**

```json
{
  "session_id": "sess_abc123",
  "conversation_id": "550e8400-...",
  "thread_id": "conv_550e8400...",
  "message_count": 4,
  "messages": [
    {
      "type": "user",
      "content": "我想预约眼科医生"
    },
    {
      "type": "assistant",
      "content": "好的，我来帮您查询..."
    }
  ]
}
```

---

### 2. 会话管理接口

#### 2.1 获取会话列表

获取指定用户的会话列表（分页）。

**请求**

```
GET /api/conversations?host_id={host_id}&user_type={user_type}&limit={limit}&offset={offset}
```

**查询参数**

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| host_id | String | 是 | - | 用户 ID（患者或医生 UUID） |
| user_type | String | 否 | "patient" | 用户类型：`patient`/`doctor` |
| limit | Integer | 否 | 20 | 返回数量（1-100） |
| offset | Integer | 否 | 0 | 偏移量 |

**响应**

```json
{
  "conversations": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "眼睛不舒服想预约医生",
      "summary": "患者描述眼睛干涩，想预约眼科医生",
      "total_messages": 12,
      "create_time": "2025-12-01T10:00:00",
      "update_time": "2025-12-01T10:30:00"
    }
  ],
  "total": 5,
  "has_more": false
}
```

---

#### 2.2 获取会话详情

获取单个会话的详细信息，包括所有消息。

**请求**

```
GET /api/conversations/{conversation_id}
```

**响应**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_type": "patient",
  "host_id": "550e8400-e29b-41d4-a716-446655440001",
  "title": "眼睛不舒服想预约医生",
  "summary": "患者描述眼睛干涩，想预约眼科医生",
  "total_messages": 2,
  "create_time": "2025-12-01T10:00:00",
  "update_time": "2025-12-01T10:30:00",
  "messages": [
    {
      "id": "msg-001",
      "message_order": 1,
      "message_content": "我眼睛最近很干涩",
      "message_type": "user",
      "create_time": "2025-12-01T10:00:00",
      "context": [
        {"patient_info": {"name": "张三", "age": 35}},
        {"conversation_stage": "health_consultation"}
      ]
    },
    {
      "id": "msg-002",
      "message_order": 2,
      "message_content": "您好，我了解到您眼睛干涩...",
      "message_type": "assistant",
      "create_time": "2025-12-01T10:00:05",
      "context": null
    }
  ]
}
```

---

#### 2.3 删除会话

删除指定的会话（软删除）。

**请求**

```
DELETE /api/conversations/{conversation_id}
```

**响应**

```json
{
  "success": true,
  "message": "会话已删除",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### 3. 系统接口

#### 3.1 健康检查

检查系统运行状态。

**请求**

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

#### 3.2 API 信息

获取 API 概览信息。

**请求**

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
    "session_state": "/api/chat/{session_id}/state",
    "session_messages": "/api/chat/{session_id}/messages",
    "session_checkpoints": "/api/chat/{session_id}/checkpoints",
    "users": "/api/users",
    "conversations": "/api/conversations",
    "conversation_detail": "/api/conversations/{conversation_id}",
    "research_chat": "/api/research/chat",
    "research_chat_stream": "/api/research/chat/stream",
    "export": "/api/export/{session_id}"
  },
  "features": {
    "state_persistence": "MySQL Checkpoint 持久化",
    "auto_routing": "自动意图路由和 Agent 切换",
    "streaming": "SSE 流式响应",
    "conversation_history": "对话历史自动保存"
  }
}
```

---

#### 3.3 获取患者列表

获取所有患者列表（供前端选择框使用）。

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
    }
  ]
}
```

---

#### 3.4 导出对话数据

导出指定会话的对话数据为 JSON 格式。

**请求**

```
GET /api/export/{session_id}?conversation_id={conversation_id}
```

**响应**

```json
{
  "session_id": "sess_abc123",
  "conversation_id": "550e8400-...",
  "message_count": 4,
  "messages": [
    {
      "type": "user",
      "content": "我想预约眼科医生"
    },
    {
      "type": "assistant",
      "content": "好的，我来帮您查询..."
    }
  ]
}
```

---

### 4. 数据模型

#### ChatRequest

聊天请求模型

| 字段 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| message | String | 是 | - | 用户消息内容 |
| patient_id | String | 是 | - | 患者 UUID（必须是有效的 UUID 格式） |
| doctor_id | String | 否 | null | 医生 UUID（医生端必需） |
| session_id | String | 否 | 自动生成 | 会话 ID |
| conversation_id | String | 否 | 自动创建 | 数据库会话 ID |
| agent_type | String | 否 | "health" | Agent 类型：`health`/`report`/`reminder` |
| role | String | 否 | "patient" | 用户角色：`patient`/`doctor` |

#### ChatResponse

聊天响应模型

| 字段 | 类型 | 说明 |
|------|------|------|
| response | String | AI 生成的响应内容 |
| session_id | String | 当前会话 ID |
| conversation_id | String | 数据库会话 ID |
| is_completed | Boolean | 对话是否完成 |
| stage | String | 当前对话阶段 |
| agent_type | String | 当前使用的 Agent 类型 |
| metadata | Object | 附加元数据 |

#### ConversationSummary

会话摘要模型

| 字段 | 类型 | 说明 |
|------|------|------|
| id | String | 会话 UUID |
| title | String | 会话标题 |
| summary | String | 会话摘要（可空） |
| total_messages | Integer | 消息总数 |
| create_time | DateTime | 创建时间 |
| update_time | DateTime | 更新时间 |

#### ConversationDetailResponse

会话详情响应模型

| 字段 | 类型 | 说明 |
|------|------|------|
| id | String | 会话 UUID |
| user_type | String | 用户类型：`patient`/`doctor` |
| host_id | String | 会话主体 ID |
| title | String | 会话标题 |
| summary | String | 会话摘要 |
| total_messages | Integer | 消息总数 |
| create_time | DateTime | 创建时间 |
| update_time | DateTime | 更新时间 |
| messages | List | 消息列表 |

#### MessageResponse

消息响应模型

| 字段 | 类型 | 说明 |
|------|------|------|
| id | String | 消息 UUID |
| message_order | Integer | 消息顺序 |
| message_content | String | 消息内容 |
| message_type | String | 消息类型：`user`/`assistant`/`system` |
| create_time | DateTime | 创建时间 |
| context | List | 上下文信息列表（可空） |

#### SSE 事件格式

```typescript
// 开始事件
interface StartEvent {
  event: "start";
  session_id: string;
  conversation_id: string;
  thread_id: string;
}

// Token 事件（逐 token 输出，打字机效果）
interface TokenEvent {
  event: "token";
  content: string;  // 单个或少量字符
}

// 工具调用事件
interface ToolCallEvent {
  event: "tool_call";
  tool: string;
  status: "start" | "end";
  input?: object;   // 仅 status="start" 时存在
  output?: string;  // 仅 status="end" 时存在
}

// Agent 切换事件
interface AgentSwitchEvent {
  event: "agent_switch";
  from: string;
  to: string;
}

// 完成事件
interface DoneEvent {
  event: "done";
  response: string;
  agent_type: string;
  stage: string;
  session_id: string;
  conversation_id: string;
}

// 错误事件
interface ErrorEvent {
  event: "error";
  message: string;
}
```

---

### 5. 对话阶段说明

#### Health Agent 阶段

| 阶段 | 代码 | 说明 |
|------|------|------|
| 问候 | `greeting` | 初次问候，了解用户需求 |
| 健康咨询 | `health_consultation` | 健康问题咨询 |
| 症状评估 | `symptom_assessment` | 评估症状严重程度 |
| 预约询问 | `appointment_inquiry` | 询问是否需要预约 |
| 信息收集 | `patient_info_collection` | 收集患者基本信息 |
| 眼科分诊 | `ophthalmology_triage` | 眼科专业分诊 |
| 病史采集 | `medical_history` | 采集病史信息 |
| 预约医生 | `appointment_booking` | 完成医生预约 |
| 完成 | `completed` | 对话完成 |

#### Report Agent 阶段

| 阶段 | 代码 | 说明 |
|------|------|------|
| 选择操作 | `select_action` | 选择报告操作类型 |
| 生成报告 | `generate_report` | 生成病历/处方报告 |
| 分析历史 | `analyze_history` | 分析历史记录 |
| 回答问题 | `answer_question` | 回答报告相关问题 |
| 对比记录 | `compare_records` | 对比多次检查记录 |
| 完成 | `completed` | 对话完成 |

#### Reminder Agent 阶段

| 阶段 | 代码 | 说明 |
|------|------|------|
| 查看提醒 | `view_reminders` | 查看现有提醒 |
| 创建提醒 | `create_reminder` | 创建新提醒 |
| 更新提醒 | `update_reminder` | 更新提醒设置 |
| 配置设置 | `config_settings` | 配置提醒偏好 |
| 生物力学报告 | `generate_biomechanics_report` | 生成生物力学报告 |
| 完成 | `completed` | 对话完成 |

---

### 6. 使用示例

#### Python 集成示例

**同步对话**

```python
import requests

BASE_URL = "http://localhost:8000"

def chat(patient_id: str, message: str, agent_type: str = "health",
         session_id: str = None, conversation_id: str = None):
    """同步对话"""
    response = requests.post(
        f"{BASE_URL}/api/chat",
        json={
            "message": message,
            "patient_id": patient_id,
            "agent_type": agent_type,
            "role": "patient",
            "session_id": session_id,
            "conversation_id": conversation_id
        }
    )
    return response.json()

# 使用示例
patient_id = "550e8400-e29b-41d4-a716-446655440000"

# 第一轮对话
result = chat(patient_id, "我想预约眼科医生")
print(f"AI: {result['response']}")
print(f"会话ID: {result['conversation_id']}")

# 继续对话
result = chat(
    patient_id,
    "我最近眼睛很干涩",
    conversation_id=result['conversation_id']
)
print(f"AI: {result['response']}")
```

**流式对话**

```python
import requests
import json

def chat_stream(patient_id: str, message: str, conversation_id: str = None):
    """流式对话"""
    response = requests.post(
        f"{BASE_URL}/api/chat/stream",
        json={
            "message": message,
            "patient_id": patient_id,
            "agent_type": "health",
            "role": "patient",
            "conversation_id": conversation_id
        },
        stream=True
    )

    for line in response.iter_lines():
        if line:
            # 解析 SSE 格式
            if line.startswith(b"data: "):
                event_data = json.loads(line[6:])
                event_type = event_data.get("event")

                if event_type == "start":
                    print(f"开始处理，会话ID: {event_data['conversation_id']}")
                elif event_type == "token":
                    print(event_data["content"], end="", flush=True)
                elif event_type == "tool_call":
                    print(f"\n[工具调用] {event_data['tool']}: {event_data['status']}")
                elif event_type == "done":
                    print(f"\n完成，阶段: {event_data['stage']}")
                elif event_type == "error":
                    print(f"错误: {event_data['message']}")

# 使用示例
chat_stream("550e8400-e29b-41d4-a716-446655440000", "我想预约眼科医生")
```

**获取会话列表**

```python
def list_conversations(host_id: str, user_type: str = "patient"):
    """获取会话列表"""
    response = requests.get(
        f"{BASE_URL}/api/conversations",
        params={
            "host_id": host_id,
            "user_type": user_type,
            "limit": 20,
            "offset": 0
        }
    )
    return response.json()

# 使用示例
conversations = list_conversations("550e8400-e29b-41d4-a716-446655440000")
for conv in conversations["conversations"]:
    print(f"{conv['title']} - {conv['total_messages']}条消息")
```

#### JavaScript 前端示例

**同步对话**

```javascript
async function chat(patientId, message, conversationId = null) {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      message: message,
      patient_id: patientId,
      agent_type: 'health',
      role: 'patient',
      conversation_id: conversationId
    })
  });
  return response.json();
}

// 使用示例
const result = await chat('550e8400-e29b-41d4-a716-446655440000', '我想预约眼科医生');
console.log('AI:', result.response);
```

**SSE 流式对话**

```javascript
function chatStream(patientId, message, conversationId = null) {
  return new Promise((resolve, reject) => {
    fetch('/api/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        message: message,
        patient_id: patientId,
        agent_type: 'health',
        role: 'patient',
        conversation_id: conversationId
      })
    }).then(response => {
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullResponse = '';

      function read() {
        reader.read().then(({ done, value }) => {
          if (done) {
            resolve(fullResponse);
            return;
          }

          const text = decoder.decode(value);
          const lines = text.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const eventData = JSON.parse(line.slice(6));

              switch (eventData.event) {
                case 'start':
                  console.log('开始处理');
                  break;
                case 'token':
                  // 实时显示内容
                  document.getElementById('response').textContent += eventData.content;
                  fullResponse += eventData.content;
                  break;
                case 'tool_call':
                  console.log(`工具调用: ${eventData.tool} - ${eventData.status}`);
                  break;
                case 'done':
                  console.log('完成');
                  break;
                case 'error':
                  reject(new Error(eventData.message));
                  break;
              }
            }
          }

          read();
        });
      }

      read();
    });
  });
}

// 使用示例
await chatStream('550e8400-e29b-41d4-a716-446655440000', '我想预约眼科医生');
```

---

## 第二部分：科研 Agent API

### 1. 概述

科研 Agent 是专为医生用户设计的科研辅助工具，提供文献搜索、数据分析、研究设计等功能。

**主要特性：**

| 特性 | 说明 |
|------|------|
| 机构数据访问 | 访问机构内部脱敏患者数据 |
| 多源文献搜索 | 支持 PubMed、Google Scholar 等 |
| 统计分析 | 描述统计、相关分析、回归分析等 |
| 数据可视化 | 生成图表并存储到 MinIO |
| 研究设计 | 辅助设计研究方案和样本量估算 |
| 论文写作 | 提供论文各章节写作指导 |

**权限要求：**

- 必须提供有效的 `doctor_id`（UUID 格式）
- 机构数据访问需要 `enable_institution_data: true`
- 网络搜索需要 `enable_web_search: true`

---

### 2. 科研对话接口

#### 2.1 同步科研对话

**请求**

```
POST /api/research/chat
Content-Type: application/json
```

**请求体**

```json
{
  "message": "搜索关于糖尿病视网膜病变的最新研究",
  "doctor_id": "550e8400-e29b-41d4-a716-446655440000",
  "patient_id": null,
  "session_id": null,
  "conversation_id": null,
  "enable_institution_data": false,
  "enable_web_search": true,
  "web_search_types": ["pubmed", "scholar"]
}
```

**请求参数说明**

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| message | String | 是 | - | 用户消息 |
| doctor_id | String | 是 | - | 医生 UUID（必需，有效 UUID 格式） |
| patient_id | String | 否 | null | 患者 UUID（查看特定患者数据时需要） |
| session_id | String | 否 | 自动生成 | 会话 ID，格式：`research_{uuid[:16]}` |
| conversation_id | String | 否 | 自动创建 | 数据库会话 ID |
| enable_institution_data | Boolean | 否 | false | 启用机构数据库访问 |
| enable_web_search | Boolean | 否 | false | 启用网页搜索 |
| web_search_types | List | 否 | [] | 搜索类型：`general`/`pubmed`/`scholar` |

**响应体**

```json
{
  "response": "根据PubMed的最新研究...",
  "session_id": "research_abc123def456",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440099",
  "is_completed": false,
  "stage": "web_search",
  "agent_type": "research",
  "metadata": {
    "doctor_id": "550e8400-e29b-41d4-a716-446655440000",
    "patient_id": null,
    "enable_institution_data": false,
    "enable_web_search": true,
    "web_search_types": ["pubmed", "scholar"],
    "thread_id": "conv_550e8400..."
  }
}
```

---

#### 2.2 流式科研对话 (SSE)

**请求**

```
POST /api/research/chat/stream
Content-Type: application/json
```

**请求体**

与 [2.1 同步科研对话](#21-同步科研对话) 相同。

**响应**

返回 `text/event-stream` 类型的 SSE 流。

**SSE 事件流示例**

```
data: {"event":"start","session_id":"research_abc123","conversation_id":"550e8400-...","thread_id":"conv_550e8400..."}

data: {"event":"chunk","content":"根据"}

data: {"event":"chunk","content":"PubMed的"}

data: {"event":"tool_call","tool":"web_search_medical","status":"start","input":{"query":"糖尿病视网膜病变","search_types":["pubmed"]}}

data: {"event":"tool_call","tool":"web_search_medical","status":"end","output":"找到15篇相关文献..."}

data: {"event":"done","response":"根据PubMed的最新研究...","session_id":"research_abc123","conversation_id":"550e8400-...","stage":"web_search","agent_type":"research","metadata":{...}}
```

**响应 Headers**

```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
Access-Control-Allow-Origin: *
X-Accel-Buffering: no
```

---

#### 2.3 获取科研会话列表

**请求**

```
GET /api/research/conversations?doctor_id={doctor_id}&limit={limit}&offset={offset}
```

**查询参数**

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| doctor_id | String | 是 | - | 医生 UUID |
| limit | Integer | 否 | 20 | 返回数量（1-100） |
| offset | Integer | 否 | 0 | 偏移量 |

**响应**

```json
{
  "conversations": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "糖尿病研究讨论",
      "summary": "讨论了糖尿病的最新治疗指南和数据分析",
      "total_messages": 12,
      "create_time": "2025-12-01T10:00:00",
      "update_time": "2025-12-01T10:30:00"
    }
  ],
  "total": 42,
  "has_more": true
}
```

---

#### 2.4 获取科研会话详情

**请求**

```
GET /api/research/conversations/{conversation_id}?doctor_id={doctor_id}
```

**参数**

| 参数 | 类型 | 位置 | 必需 | 说明 |
|------|------|------|------|------|
| conversation_id | String | Path | 是 | 会话 ID |
| doctor_id | String | Query | 是 | 医生 UUID（权限验证） |

**响应**

```json
{
  "conversation": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "糖尿病研究讨论",
    "summary": "讨论了糖尿病的最新治疗指南和数据分析",
    "total_messages": 12,
    "create_time": "2025-12-01T10:00:00",
    "update_time": "2025-12-01T10:30:00"
  },
  "messages": [
    {
      "id": "msg-001",
      "message_order": 1,
      "message_content": "搜索关于糖尿病的最新治疗指南",
      "message_type": "user",
      "create_time": "2025-12-01T10:00:00"
    },
    {
      "id": "msg-002",
      "message_order": 2,
      "message_content": "根据最新研究...",
      "message_type": "assistant",
      "create_time": "2025-12-01T10:00:30"
    }
  ]
}
```

---

#### 2.5 删除科研会话

**请求**

```
DELETE /api/research/conversations/{conversation_id}?doctor_id={doctor_id}
```

**参数**

| 参数 | 类型 | 位置 | 必需 | 说明 |
|------|------|------|------|------|
| conversation_id | String | Path | 是 | 会话 ID |
| doctor_id | String | Query | 是 | 医生 UUID（权限验证） |

**响应**

```json
{
  "message": "会话已删除",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

#### 2.6 科研 Agent 健康检查

**请求**

```
GET /api/research/health
```

**响应**

```json
{
  "status": "healthy",
  "agent_type": "research",
  "version": "3.0.0",
  "architecture": "langgraph",
  "features": {
    "institution_data": true,
    "web_search": true,
    "sse_streaming": true,
    "statistical_analysis": true,
    "data_visualization": true,
    "visualization_storage": true,
    "literature_review": true,
    "research_design": true
  },
  "dependencies": {
    "search1api": true,
    "minio": true,
    "pandas": true,
    "scipy": true,
    "matplotlib": true
  },
  "endpoints": [
    "POST /api/research/chat",
    "POST /api/research/chat/stream",
    "GET /api/research/conversations",
    "GET /api/research/conversations/{id}",
    "DELETE /api/research/conversations/{id}",
    "GET /api/research/health"
  ]
}
```

---

### 3. 数据模型

#### ResearchChatRequest

科研对话请求模型

| 字段 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| message | String | 是 | - | 用户消息 |
| doctor_id | String | 是 | - | 医生 UUID |
| patient_id | String | 否 | null | 患者 UUID |
| session_id | String | 否 | 自动生成 | 会话 ID |
| conversation_id | String | 否 | 自动创建 | 数据库会话 ID |
| enable_institution_data | Boolean | 否 | false | 启用机构数据库访问 |
| enable_web_search | Boolean | 否 | false | 启用网页搜索 |
| web_search_types | List[String] | 否 | [] | 搜索类型列表 |

#### ResearchChatResponse

科研对话响应模型

| 字段 | 类型 | 说明 |
|------|------|------|
| response | String | AI 生成的响应内容 |
| session_id | String | 会话 ID |
| conversation_id | String | 数据库会话 ID |
| is_completed | Boolean | 对话是否完成 |
| stage | String | 当前对话阶段 |
| agent_type | String | 固定为 "research" |
| metadata | Object | 附加元数据 |

#### WebSearchType 枚举

| 值 | 说明 |
|-----|------|
| `general` | 通用网页搜索 |
| `pubmed` | PubMed 医学文献搜索 |
| `scholar` | Google Scholar 学术搜索 |

#### 科研 SSE 事件格式

```typescript
// 科研流式事件使用 "chunk" 而非 "token"
interface ChunkEvent {
  event: "chunk";
  content: string;
}

// 工具调用事件包含输入输出
interface ResearchToolCallEvent {
  event: "tool_call";
  tool: string;
  status: "start" | "end";
  input?: object;   // 仅 start 时
  output?: string;  // 仅 end 时
}

// 完成事件包含更多元数据
interface ResearchDoneEvent {
  event: "done";
  response: string;
  session_id: string;
  conversation_id: string;
  stage: string;
  agent_type: "research";
  metadata: {
    doctor_id: string;
    patient_id?: string;
    enable_institution_data: boolean;
    enable_web_search: boolean;
  };
}
```

---

### 4. 科研工具详解

#### 数据查询工具

**get_institution_research_data** - 机构数据查询

访问机构内部数据库进行科研分析。

| 参数 | 类型 | 说明 |
|------|------|------|
| data_type | String | 数据类型：`patients`/`appointments`/`prescriptions`/`scans`/`all` |
| date_from | String | 开始日期（YYYY-MM-DD） |
| date_to | String | 结束日期（YYYY-MM-DD） |
| limit | Integer | 返回数量限制 |

> 注意：返回数据自动脱敏处理

**web_search_medical** - 医学文献搜索

多来源医学文献搜索。

| 参数 | 类型 | 说明 |
|------|------|------|
| query | String | 搜索关键词 |
| search_types | List | 搜索类型：`general`/`pubmed`/`scholar` |
| max_results | Integer | 每个类型最大结果数（默认20） |
| fetch_content | Boolean | 是否爬取页面内容 |

#### 统计分析工具

**statistical_analysis** - 统计分析

执行各类统计分析。

| 分析类型 | 说明 |
|---------|------|
| `descriptive` | 描述性统计（均值、标准差、四分位数等） |
| `correlation` | 相关性分析（Pearson/Spearman） |
| `ttest` | t 检验 |
| `chi_square` | 卡方检验 |
| `regression` | 回归分析 |
| `anova` | 方差分析 |
| `survival` | 生存分析 |

**generate_research_visualization** - 数据可视化

生成研究图表。

| 图表类型 | 说明 |
|---------|------|
| `bar` | 柱状图 |
| `line` | 折线图 |
| `scatter` | 散点图 |
| `pie` | 饼图 |
| `boxplot` | 箱线图 |
| `histogram` | 直方图 |
| `heatmap` | 热力图 |

> 图表可存储到 MinIO，返回访问 URL

#### 文献研究工具

**summarize_medical_literature** - 文献处理

| 任务类型 | 说明 |
|---------|------|
| `summarize` | 生成摘要 |
| `extract_key_findings` | 提取关键发现 |
| `translate` | 中英文翻译 |
| `extract_methods` | 提取方法学 |
| `extract_conclusions` | 提取结论 |

**search_clinical_guidelines** - 临床指南查询

支持组织：WHO, NICE, 中华医学会, AAO, ADA, ESC 等

#### 研究设计工具

**design_research_protocol** - 研究方案设计

| 研究类型 | 说明 |
|---------|------|
| `rct` | 随机对照试验 |
| `cohort` | 队列研究 |
| `case_control` | 病例对照研究 |
| `cross_sectional` | 横断面研究 |
| `case_series` | 病例系列 |
| `meta_analysis` | 荟萃分析 |

提供样本量估算和完整研究方案模板

**ethics_review_assistant** - 伦理审查助手

- 伦理检查清单
- 知情同意书模板
- 风险评估报告
- 数据管理计划

**assist_paper_writing** - 论文写作助手

| 章节 | 说明 |
|-----|------|
| `abstract` | 摘要写作指导 |
| `introduction` | 引言写作指导 |
| `methods` | 方法学写作指导 |
| `results` | 结果写作指导 |
| `discussion` | 讨论写作指导 |

#### 临床决策工具

**check_drug_interactions** - 药物相互作用检查

- 药物相互作用数据库
- 疾病禁忌检查
- 严重程度分类（轻度/中度/重度）

**find_similar_cases** - 病例相似度匹配

- 多维度匹配策略
- 相似度阈值配置
- 隐私保护提醒

#### 数据导出工具

**export_research_data** - 数据导出

| 格式 | 说明 |
|-----|------|
| `excel` | Excel 格式 (.xlsx) |
| `csv` | CSV 格式 |
| `spss` | SPSS 格式 (.sav) |
| `json` | JSON 格式 |

> 导出数据自动脱敏，添加水印标记

---

### 5. 对话阶段

| 阶段 | 代码 | 说明 |
|------|------|------|
| 初始化 | `greeting` | 初次接待，了解研究目标 |
| 研究初始化 | `research_init` | 明确研究需求和方向 |
| 数据查询 | `data_query` | 机构数据库查询 |
| 网页搜索 | `web_search` | 文献/网页搜索 |
| 统计分析 | `statistical_analysis` | 执行统计分析 |
| 文献综述 | `literature_review` | 文献处理和综述 |
| 研究设计 | `research_design` | 设计研究方案 |
| 论文写作 | `paper_writing` | 论文写作辅助 |
| 完成 | `completed` | 任务完成 |

---

### 6. 权限控制

**身份验证**

所有科研接口要求有效的 `doctor_id`（UUID 格式）。

```python
# UUID 验证正则表达式
UUID_PATTERN = r'^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$'
```

**机构数据访问控制**

```json
{
  "enable_institution_data": true  // 启用后可访问 get_institution_research_data 工具
}
```

- 默认关闭
- 启用时可访问患者数据（自动脱敏）
- 敏感字段处理：姓名→代码化，电话→部分隐藏，地址→城市级别

**网络搜索控制**

```json
{
  "enable_web_search": true,
  "web_search_types": ["pubmed", "scholar"]  // 指定搜索源
}
```

- 默认关闭
- 支持选择搜索类型
- 每个类型最多返回 20 条结果

**会话所有权验证**

获取/删除会话时验证 `doctor_id` 与会话 `host_id` 匹配。

---

### 7. 使用示例

#### 文献搜索流程

```python
import requests

BASE_URL = "http://localhost:8000"
DOCTOR_ID = "550e8400-e29b-41d4-a716-446655440000"

# 1. 搜索文献
response = requests.post(
    f"{BASE_URL}/api/research/chat",
    json={
        "message": "搜索关于糖尿病视网膜病变的最新治疗进展",
        "doctor_id": DOCTOR_ID,
        "enable_web_search": True,
        "web_search_types": ["pubmed", "scholar"]
    }
)
result = response.json()
conversation_id = result["conversation_id"]
print(f"搜索结果：{result['response'][:200]}...")

# 2. 要求总结
response = requests.post(
    f"{BASE_URL}/api/research/chat",
    json={
        "message": "请总结这些文献的主要发现",
        "doctor_id": DOCTOR_ID,
        "conversation_id": conversation_id,
        "enable_web_search": True
    }
)
print(f"文献总结：{response.json()['response']}")
```

#### 数据分析流程

```python
# 1. 查询机构数据
response = requests.post(
    f"{BASE_URL}/api/research/chat",
    json={
        "message": "查询最近一年的糖尿病患者数据",
        "doctor_id": DOCTOR_ID,
        "enable_institution_data": True
    }
)
result = response.json()
conversation_id = result["conversation_id"]

# 2. 执行统计分析
response = requests.post(
    f"{BASE_URL}/api/research/chat",
    json={
        "message": "对年龄和血糖水平进行相关性分析",
        "doctor_id": DOCTOR_ID,
        "conversation_id": conversation_id,
        "enable_institution_data": True
    }
)
print(f"分析结果：{response.json()['response']}")

# 3. 生成可视化
response = requests.post(
    f"{BASE_URL}/api/research/chat",
    json={
        "message": "生成年龄分布的柱状图",
        "doctor_id": DOCTOR_ID,
        "conversation_id": conversation_id,
        "enable_institution_data": True
    }
)
print(f"可视化：{response.json()['response']}")
```

#### 完整工作流示例

```python
import requests
import json

class ResearchAssistant:
    def __init__(self, doctor_id: str, base_url: str = "http://localhost:8000"):
        self.doctor_id = doctor_id
        self.base_url = base_url
        self.conversation_id = None

    def chat(self, message: str, enable_institution_data: bool = False,
             enable_web_search: bool = False, web_search_types: list = None):
        """发送消息"""
        response = requests.post(
            f"{self.base_url}/api/research/chat",
            json={
                "message": message,
                "doctor_id": self.doctor_id,
                "conversation_id": self.conversation_id,
                "enable_institution_data": enable_institution_data,
                "enable_web_search": enable_web_search,
                "web_search_types": web_search_types or []
            }
        )
        result = response.json()
        self.conversation_id = result["conversation_id"]
        return result["response"]

    def chat_stream(self, message: str, enable_institution_data: bool = False,
                    enable_web_search: bool = False, web_search_types: list = None):
        """流式对话"""
        response = requests.post(
            f"{self.base_url}/api/research/chat/stream",
            json={
                "message": message,
                "doctor_id": self.doctor_id,
                "conversation_id": self.conversation_id,
                "enable_institution_data": enable_institution_data,
                "enable_web_search": enable_web_search,
                "web_search_types": web_search_types or []
            },
            stream=True
        )

        full_response = ""
        for line in response.iter_lines():
            if line and line.startswith(b"data: "):
                event_data = json.loads(line[6:])
                if event_data["event"] == "chunk":
                    print(event_data["content"], end="", flush=True)
                    full_response += event_data["content"]
                elif event_data["event"] == "done":
                    self.conversation_id = event_data["conversation_id"]

        print()
        return full_response

    def list_conversations(self, limit: int = 20):
        """获取会话列表"""
        response = requests.get(
            f"{self.base_url}/api/research/conversations",
            params={"doctor_id": self.doctor_id, "limit": limit}
        )
        return response.json()["conversations"]

    def delete_conversation(self, conversation_id: str = None):
        """删除会话"""
        conv_id = conversation_id or self.conversation_id
        response = requests.delete(
            f"{self.base_url}/api/research/conversations/{conv_id}",
            params={"doctor_id": self.doctor_id}
        )
        if conv_id == self.conversation_id:
            self.conversation_id = None
        return response.json()


# 使用示例
assistant = ResearchAssistant("550e8400-e29b-41d4-a716-446655440000")

# 文献搜索
print("=== 文献搜索 ===")
response = assistant.chat(
    "搜索关于青光眼治疗的最新进展",
    enable_web_search=True,
    web_search_types=["pubmed"]
)
print(response[:500])

# 数据分析
print("\n=== 数据分析 ===")
response = assistant.chat(
    "查询机构内青光眼患者数据并进行年龄分布分析",
    enable_institution_data=True
)
print(response)

# 研究设计
print("\n=== 研究设计 ===")
response = assistant.chat(
    "帮我设计一个青光眼新药疗效的随机对照试验方案"
)
print(response)

# 查看会话历史
print("\n=== 会话列表 ===")
conversations = assistant.list_conversations()
for conv in conversations[:5]:
    print(f"- {conv['title']} ({conv['total_messages']}条消息)")
```

---

## 附录

### A. 错误码说明

| HTTP 状态码 | 说明 | 常见场景 |
|------------|------|---------|
| 200 | 成功 | 请求处理成功 |
| 400 | 请求错误 | 参数格式错误、UUID 无效 |
| 403 | 禁止访问 | 医生身份验证失败、无权访问会话 |
| 404 | 未找到 | 会话不存在 |
| 500 | 服务器错误 | 内部处理失败 |

**常见错误信息**

| 错误信息 | 说明 |
|---------|------|
| `patient_id 必须是有效的UUID格式` | patient_id 格式错误 |
| `doctor_id 必须是有效的UUID格式` | doctor_id 格式错误 |
| `医生端请求必须提供 doctor_id` | 医生角色缺少 doctor_id |
| `仅医生用户可访问科研Agent` | 非医生用户访问科研接口 |
| `会话不存在` | 指定的会话 ID 不存在 |
| `无权访问此会话` | 会话不属于当前用户 |

---

### B. UUID 格式规范

**验证规则**

```regex
^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$
```

**支持格式**

| 格式 | 示例 |
|------|------|
| 带连字符 | `550e8400-e29b-41d4-a716-446655440000` |
| 不带连字符 | `550e8400e29b41d4a716446655440000` |

> 大小写不敏感

---

### C. 日期时间格式

| 类型 | 格式 | 示例 |
|------|------|------|
| 日期 | `YYYY-MM-DD` | `2025-12-17` |
| 时间 | `YYYY-MM-DDTHH:mm:ss` | `2025-12-17T10:00:00` |
| ISO 8601 | `YYYY-MM-DDTHH:mm:ss.sssZ` | `2025-12-17T10:00:00.000Z` |

---

### D. 数据库表结构

**chat_conversation 表**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 会话 UUID (主键) |
| user_type | VARCHAR(20) | 用户类型：patient/doctor |
| host_id | VARCHAR(36) | 会话主体 ID |
| title | VARCHAR(255) | 会话标题 |
| summary | TEXT | 会话摘要 |
| total_messages | INT | 消息总数 |
| create_time | DATETIME | 创建时间 |
| create_by | VARCHAR(50) | 创建者 |
| update_time | DATETIME | 更新时间 |
| update_by | VARCHAR(50) | 更新者 |
| deleted | TINYINT | 软删除标记 |
| version | INT | 乐观锁版本号 |

**chat_message 表**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 消息 UUID (主键) |
| chat_id | VARCHAR(36) | 所属会话 ID (外键) |
| message_order | INT | 消息顺序 |
| message_content | LONGTEXT | 消息内容 |
| message_type | VARCHAR(20) | 消息类型：user/assistant/system |
| sender_id | VARCHAR(36) | 发送者 ID |
| context | JSON | 上下文信息 |
| token_used | INT | 使用的 Token 数 |
| status | VARCHAR(20) | 状态：running/success/failed/cancelled |
| error_message | TEXT | 错误信息 |
| create_time | DATETIME | 创建时间 |
| create_by | VARCHAR(50) | 创建者 |
| update_time | DATETIME | 更新时间 |
| update_by | VARCHAR(50) | 更新者 |
| deleted | TINYINT | 软删除标记 |
| version | INT | 乐观锁版本号 |

---

## 更新日志

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| 3.0.1 | 2025-12-16 | 流式输出升级为真正的 Token 级别（打字机效果），tool_call 事件增加 input/output 字段 |
| 3.0.0 | 2025-12-16 | 初始版本，基于 LangGraph 架构重构 |

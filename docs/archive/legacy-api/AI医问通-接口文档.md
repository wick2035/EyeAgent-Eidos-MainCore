# AI 医问通 接口文档（后端工程师集成手册）

> 版本：v3.0.0 ·  最后更新：2026-06-28 ·  适用环境：LangGraph 多 Agent 架构

---

## 0. 文档说明

### 0.1 系统简介

「AI 医问通」是一套基于 **LangGraph** 的多 Agent 智能医疗咨询服务，对外以 **FastAPI**（`0.109.x`）提供 HTTP / WebSocket / SSE 接口，内部通过 6 个业务 Agent（健康咨询、报告、提醒、科研、合规审查、产品推荐）完成意图路由与工具调用，并回调 Java 业务后端（`/agent/api/*`）读写真实医疗数据。

- 技术栈：FastAPI + Uvicorn + LangGraph + 通义千问（Qwen）
- 服务端口：**20602**（`main.py` 中 `uvicorn.run(..., port=20602)`）
- 持久化：MySQL（对话历史 + LangGraph Checkpoint 状态快照）

### 0.2 文档范围（双向）

本文档同时覆盖两侧接口契约：

| 部分 | 方向 | 内容 |
| --- | --- | --- |
| **Part A** | AI 医问通 **对外暴露** | FastAPI 提供的全部 HTTP / WebSocket / SSE 接口，供业务后端、前端、外部系统调用 |
| **Part B** | AI 医问通 **依赖后端** | AI 服务回调 Java 后端 `/agent/api/*` 的接口契约，后端需保证实现/兼容 |

### 0.3 阅读对象

- 集成调用 AI 医问通服务的**业务后端 / 前端工程师** → 重点看 Part A
- 维护 `/agent/api/*` 契约的 **Java 后端工程师** → 重点看 Part B + 附录

### 0.4 关联文档

- Java 后端 `AgentToolController` 3 个新增接口的详细字段说明见：[ADDAgentToolController-API文档.md](../../ADDAgentToolController-API文档.md)，本文 Part B §B.6 给出摘要并引用。

---

## 1. 简要架构

### 1.1 整体拓扑

```
┌──────────────┐   HTTP / SSE / WS    ┌─────────────────────────────┐
│ 前端 / 业务后端 │ ───────────────────► │  AI 医问通 (FastAPI :20602)    │
│  / 外部系统    │ ◄─────────────────── │                             │
└──────────────┘                      │  ┌───────────────────────┐  │
                                       │  │  LangGraph 多 Agent 图  │  │
                                       │  │  router → 业务Agent →   │  │
                                       │  │  output_handler         │  │
                                       │  └───────────────────────┘  │
                                       └───────┬─────────┬───────────┘
                         ┌─────────────────────┘         └──────────────────┐
                         ▼                                                    ▼
           ┌──────────────────────────┐                       ┌──────────────────────────┐
           │ Java 业务后端 :8081        │                       │ MySQL :3306（对话/Checkpoint）│
           │ /agent/api/*（Part B）     │                       └──────────────────────────┘
           └──────────────────────────┘
                         ▲
        ┌────────────────┼─────────────────┐
        ▼                ▼                  ▼
  Search1API        DashScope ASR        MinIO（附件/可视化）
  （联网检索）        （语音识别）          （可选）
```

### 1.2 六个业务 Agent

| Agent (`agent_type`) | 职责 | 可用角色 |
| --- | --- | --- |
| `health` | 健康/眼科咨询、分诊、预约挂号 | 患者 + 医生 |
| `report` | 病历/处方查看、历史对比、生成 PDF | 患者 + 医生 |
| `reminder` | 提醒查看/创建、提醒配置、用药提醒 | 患者 + 医生 |
| `research` | 科研助手：文献检索、数据统计、研究设计 | **仅医生** |
| `compliance` | 合规审查：处方/诊断/病历/检查合理性 | **仅医生** |
| `recommendation` | 用药/医药商品推荐（医生开方 / 患者购药） | 患者(OTC) + 医生(处方) |

### 1.3 路由与角色鉴权

- 路由采用**两层混合**策略：`EnhancedRuleEngine`（规则，~90% 流量，<1ms）+ `LightweightLLMRouter`（LLM 兜底，~10%），融合得到目标 Agent。
- 角色鉴权在**服务端**执行（`utils/role_verification.py::verify_role()`），fail-closed 策略：医生身份校验失败时降级为 `patient`；`research` / `compliance` 仅医生可访问。

**角色权限矩阵**

| 能力 | patient | doctor |
| --- | :---: | :---: |
| health（问诊/预约） | ✅ | ✅ |
| report（报告/处方） | ✅ | ✅ |
| reminder（提醒） | ✅ | ✅ |
| recommendation | ✅（仅 OTC/器械/保健品） | ✅（可开处方） |
| research（科研） | ❌ | ✅ |
| compliance（合规审查） | ❌ | ✅ |

### 1.4 请求生命周期

```
接收请求
  → 生成/复用 session_id + conversation_id
  → （若有附件）附件预分析，得到 attachment_analysis 文本
  → 装载患者综合画像（patient_info / patient_full_data）
  → router 路由意图 + 角色鉴权
  → 业务 Agent（ReAct + 工具调用，可能回调 Part B 后端）
  → output_handler 响应后处理（清洗 ID / 安全校验）
  → 返回 JSON（非流式）或 SSE 事件流（流式）
```

> **重要**：每次 `chat` 调用（一次 HTTP 请求）只处理**一条**用户消息并产出一条响应；多轮对话通过多次调用同一 `session_id` + `conversation_id` 实现，状态由 MySQL Checkpoint 持久化。

---

## 2. 通用约定

### 2.1 Base URL

```
http://<host>:20602
```

- 监听地址 `0.0.0.0`，端口 `20602`。
- 本文样例统一使用 `http://localhost:20602`。

### 2.2 鉴权

| 维度 | 说明 |
| --- | --- |
| API Key | 对外暴露层**当前未启用** API Key / Bearer 鉴权 |
| CORS | 全开：`allow_origins=["*"]`、`allow_credentials=True`、`allow_methods/headers=["*"]` |
| 角色鉴权 | 通过请求体 `role` + `doctor_id` 字段；医生专属接口（research/compliance）会校验 `doctor_id` 的 UUID 合法性，失败返回 **403** |
| 自我提权防护 | `doctor_id == patient_id` 视为非法，降级为 patient |

> 生产环境建议在网关层补充统一鉴权（本服务自身不做 Token 校验）。

### 2.3 通用标识字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `patient_id` | string(UUID) | 患者 UUID，**多数接口必填** |
| `doctor_id` | string(UUID) | 医生 UUID；医生态 / 医生专属接口必填 |
| `role` | string | `patient`（默认）/ `doctor` |
| `session_id` | string | 前端会话标识；为空时服务端自动生成（各接口前缀不同，见下） |
| `conversation_id` | string | 数据库会话 ID；为空时自动新建会话，用于多轮续聊 |
| `agent_type` | string | 目标 Agent，默认 `health`；取值见 §1.2 |

**`session_id` 自动生成前缀**（缺省时）：

| 接口 | 前缀格式 |
| --- | --- |
| `/api/chat*` | `sess_<16位hex>` |
| `/api/recommendation/*` | `rec_<16位hex>` |
| `/api/research/*` | `research_<16位hex>` |
| `/api/compliance/*` | `compliance_<16位hex>` |

### 2.4 数据格式

- 请求/响应均为 `application/json`（文件上传为 `multipart/form-data`），编码 UTF-8。
- 时间统一 ISO-8601（如 `2026-06-28T09:30:00`）。
- UUID 支持「带连字符」与「不带连字符」两种格式（正则 `^[0-9a-f]{8}-?[0-9a-f]{4}-?...$`，大小写不敏感）。

### 2.5 HTTP 状态码

| 状态码 | 含义 |
| --- | --- |
| 200 | 成功 |
| 400 | 参数错误（如缺 `doctor_id`、UUID 格式错误、空音频、录音过短） |
| 403 | 无权限（非医生访问 research/compliance；访问他人会话） |
| 404 | 资源不存在（会话/消息不存在） |
| 413 | 文件过大（图片 >10MB / PDF >30MB） |
| 415 | 不支持的媒体类型（上传非图片/PDF） |
| 422 | 无法处理（PDF 转图片失败 / 无可提取页面） |
| 500 | 服务端内部错误 |
| 502 | 上游服务异常（DashScope ASR 调用失败） |

**错误响应体**（FastAPI `HTTPException`）：

```json
{ "detail": "错误描述（可能是字符串，也可能是对象，如 ASR 错误）" }
```

### 2.6 SSE 流式约定

- 响应头：`Content-Type: text/event-stream`、`Cache-Control: no-cache`、`Connection: keep-alive`、`X-Accel-Buffering: no`。
- 每个事件为一行：`data: {json}\n\n`，客户端按行解析 JSON，并以 JSON 中的 `event` 字段分发。
- **注意 token 事件名差异**：`/api/chat/stream` 增量内容事件名为 **`token`**；`/api/research|compliance|recommendation/chat/stream` 增量内容事件名为 **`chunk`**（详见各接口）。

---

# Part A — 对外暴露接口

> 每个接口统一给出：方法+路径 / 说明 / 权限 / 参数 / 请求体 / 响应 / 样例 / （流式）SSE 事件 / 错误码。

## A.1 系统与根接口

### A.1.1 GET `/health` — 健康检查

无参数。

**响应 200**
```json
{ "status": "healthy", "version": "3.0.0", "architecture": "langgraph" }
```

**样例**
```bash
curl http://localhost:20602/health
```

---

### A.1.2 GET `/api/info` — API 信息

返回服务版本与端点索引。无参数。

**响应 200**
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
    "recommendation_chat": "/api/recommendation/chat",
    "recommendation_chat_stream": "/api/recommendation/chat/stream",
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

### A.1.3 GET `/api/users` — 患者列表

拉取全部患者（供前端下拉选择），内部回调后端 `/agent/api/get-all-patient` 并刷新 ID 映射缓存。无参数。

**响应 200**（注意：即使后端异常也返回 200，用 `success` 区分）
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
失败时：`{ "success": false, "users": [], "error": "错误信息" }`

> 性别映射：后端 `MALE/FEMALE` → `男/女`，未知 → `未知`。

---

### A.1.4 GET `/api/export/{session_id}` — 导出会话数据

导出某会话的全部消息为 JSON。

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | path | string | 是 | 会话 ID |
| `conversation_id` | query | string | 否 | 数据库会话 ID |

**响应 200**
```json
{
  "session_id": "sess_ab12...",
  "conversation_id": "550e8400-...",
  "message_count": 8,
  "messages": [ { "type": "user", "content": "...", "...": "..." } ]
}
```
**错误码**：404（会话不存在或无消息）、500。

---

### A.1.5 页面接口（HTML，非 JSON）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/` | 聊天界面（`templates/index.html`） |
| GET | `/research-test` | 科研 Agent 测试页 |
| GET | `/recommendation-test` | 产品推荐 Agent 测试页 |

> 这三个返回 `text/html`，仅用于调试，不属于集成接口。

---

## A.2 通用聊天 Chat（前缀 `/api/chat`）

### A.2.1 POST `/api/chat` — 同步对话

**说明**：核心对话接口，自动路由到合适的 Agent。患者态且命中 `health/reminder/report` 时，响应会解析出交互选项 `ui_elements`。
**权限**：患者 + 医生（`role=doctor` 时必须传 `doctor_id`，否则 400）。

**请求体 `ChatRequest`**

| 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `message` | string | 是 | - | 用户消息 |
| `patient_id` | string(UUID) | 是 | - | 患者 UUID（格式校验） |
| `session_id` | string | 否 | 自动 `sess_*` | 会话 ID |
| `doctor_id` | string(UUID) | 否 | null | 医生 UUID（医生端必填） |
| `agent_type` | string | 否 | `health` | health/report/reminder/research/compliance/recommendation |
| `role` | string | 否 | `patient` | patient/doctor |
| `conversation_id` | string | 否 | null | 为空则新建会话 |
| `attachments` | array<AttachmentRef> | 否 | null | 图片/PDF 附件，见 §A.8 与附录 |

**`AttachmentRef` 结构**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `file_type` | string | 是 | `image` / `pdf` |
| `filename` | string | 是 | 原始文件名 |
| `minio_url` | string | 否 | MinIO 备份 URL（不传给 AI，仅记录） |
| `base64` | string | 否 | 图片 base64（不含 `data:` 前缀） |
| `mime_type` | string | 否 | 如 `image/jpeg` |
| `page_images` | array<PageImage> | 否 | PDF 各页图片，`PageImage{base64, mime_type, page}` |

**响应体 `ChatResponse`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `response` | string | AI 响应内容（已清洗，患者态可能已剥离选项标记） |
| `session_id` | string | 会话 ID |
| `conversation_id` | string\|null | 数据库会话 ID（用于续聊） |
| `is_completed` | bool | 本轮是否完成 |
| `stage` | string | 当前对话阶段 |
| `agent_type` | string | 实际处理的 Agent |
| `ui_elements` | UIElements\|null | 交互选项（仅患者态 health/reminder/report） |
| `metadata` | object | `{patient_id, role, thread_id, version:"langgraph"}` |

**`UIElements` 结构**：`{ product_cards: array|null, options: array<OptionItem>|null, ui_type: "product_cards"|"options"|"none" }`；`OptionItem{ option_id, label, value, description?, icon? }`。

**请求样例**
```bash
curl -X POST http://localhost:20602/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "我眼睛最近很干涩，想约个眼科医生",
    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
    "role": "patient",
    "agent_type": "health"
  }'
```

**响应样例 200**
```json
{
  "response": "您好，我是小Eye。了解到您眼睛干涩，请问症状持续多久了？",
  "session_id": "sess_3f9a1c2d4e6b8a0f",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440099",
  "is_completed": false,
  "stage": "symptom_collect",
  "agent_type": "health",
  "ui_elements": {
    "options": [
      {"option_id": "opt_1", "label": "今天刚开始", "value": "今天刚开始", "description": null, "icon": null},
      {"option_id": "opt_2", "label": "持续一周以上", "value": "持续一周以上", "description": null, "icon": null}
    ],
    "ui_type": "options",
    "product_cards": null
  },
  "metadata": {"patient_id": "550e8400-...", "role": "patient", "thread_id": "thread_...", "version": "langgraph"}
}
```

**错误码**：400（缺 doctor_id / UUID 非法）、500。

---

### A.2.2 POST `/api/chat/stream` — 流式对话（SSE）

**说明**：与 A.2.1 入参完全一致（`ChatRequest`），以 SSE 返回 token 级流式输出。
**权限**：同 A.2.1（医生态缺 `doctor_id` 时返回一个 `error` 事件并结束）。

**SSE 事件**

| `event` | 触发时机 | 负载字段 |
| --- | --- | --- |
| `start` | 开始 | `session_id`, `conversation_id`, `thread_id` |
| `token` | 每个增量片段 | `content`（拼接得到完整回复） |
| `agent_switch` | Agent 切换 | `from`, `to` |
| `tool_call` | 工具开始/结束 | `tool`, `status`(`start`/`end`), `input`（start）/`output`（end） |
| `ui_elements` | 解析到选项（患者态特定 Agent） | `ui_type`, `options`, `product_cards`（展开自 UIElements） |
| `done` | 完成 | `response`, `agent_type`, `stage`, `session_id`, `conversation_id`, `ui_elements`(可选) |
| `error` | 异常 | `message` |

**样例**
```bash
curl -N -X POST http://localhost:20602/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"帮我看看预约流程","patient_id":"550e8400-e29b-41d4-a716-446655440000","role":"patient"}'
```
```
data: {"event": "start", "session_id": "sess_3f9a...", "conversation_id": "550e...", "thread_id": "thread_..."}

data: {"event": "token", "content": "您好"}

data: {"event": "token", "content": "，预约"}

data: {"event": "tool_call", "tool": "get_all_hospitals", "status": "start", "input": {}}

data: {"event": "tool_call", "tool": "get_all_hospitals", "status": "end", "output": "[...]"}

data: {"event": "done", "response": "您好，预约流程如下……", "agent_type": "health", "stage": "greeting", "session_id": "sess_3f9a...", "conversation_id": "550e..."}
```

---

### A.2.3 GET `/api/chat/{session_id}/state` — 会话状态

| 参数 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| `session_id` | path | 是 | 会话 ID |
| `conversation_id` | query | 否 | 数据库会话 ID |

**响应 200**
```json
{
  "session_id": "sess_3f9a...",
  "conversation_id": "550e...",
  "current_agent": "health",
  "stage": "greeting",
  "is_completed": false,
  "message_count": 6
}
```
**错误码**：404（会话不存在）、500。

---

### A.2.4 GET `/api/chat/{session_id}/messages` — 消息历史

参数同 A.2.3（path `session_id` + query `conversation_id`）。

**响应 200**
```json
{
  "session_id": "sess_3f9a...",
  "conversation_id": "550e...",
  "thread_id": "thread_...",
  "message_count": 6,
  "messages": [ {"type": "user", "content": "..."}, {"type": "assistant", "content": "..."} ]
}
```
**错误码**：500。

---

### A.2.5 GET `/api/chat/{session_id}/agent-history` — Agent 切换历史

参数同 A.2.3。用于调试 Agent 切换轨迹。

**响应 200**
```json
{
  "session_id": "sess_3f9a...",
  "conversation_id": "550e...",
  "thread_id": "thread_...",
  "history": [
    {"agent_type": "health", "checkpoint_id": "ckpt_1", "started_at": "2026-06-28T09:00:00", "ended_at": "2026-06-28T09:05:00"}
  ]
}
```
**错误码**：500。

---

### A.2.6 GET `/api/chat/{session_id}/checkpoints` — 检查点列表

| 参数 | 位置 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | path | 是 | - | 会话 ID |
| `conversation_id` | query | 否 | - | 数据库会话 ID |
| `limit` | query | 否 | 10 | 返回数量 |

**响应 200**
```json
{
  "session_id": "sess_3f9a...",
  "conversation_id": "550e...",
  "thread_id": "thread_...",
  "count": 3,
  "checkpoints": [ /* LangGraph 检查点快照 */ ]
}
```
**错误码**：500。

---

### A.2.7 DELETE `/api/chat/{session_id}` — 删除会话

| 参数 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| `session_id` | path | 是 | 会话 ID |
| `conversation_id` | query | 否 | 数据库会话 ID |

**响应 200**：`{ "message": "会话已删除", "session_id": "sess_3f9a..." }`
**错误码**：404（会话不存在）、500。

---

## A.3 会话管理 Conversations（前缀 `/api/conversations`）

### A.3.1 GET `/api/conversations` — 会话列表（分页）

| 参数 | 位置 | 类型 | 必填 | 默认 | 约束 |
| --- | --- | --- | --- | --- | --- |
| `host_id` | query | string | 是 | - | 用户 UUID（患者/医生） |
| `user_type` | query | string | 否 | `patient` | patient/doctor |
| `limit` | query | int | 否 | 20 | 1–100 |
| `offset` | query | int | 否 | 0 | ≥0 |

**响应 `ConversationListResponse`**
```json
{
  "conversations": [
    {
      "id": "550e8400-...",
      "title": "眼睛不舒服想预约医生",
      "summary": "患者描述眼睛干涩，想预约眼科医生",
      "total_messages": 12,
      "create_time": "2026-06-28T10:00:00",
      "update_time": "2026-06-28T10:30:00"
    }
  ],
  "total": 5,
  "has_more": false
}
```

**样例**
```bash
curl "http://localhost:20602/api/conversations?host_id=550e8400-e29b-41d4-a716-446655440000&user_type=patient&limit=20&offset=0"
```
**错误码**：500。

---

### A.3.2 GET `/api/conversations/{conversation_id}` — 会话详情（含消息）

| 参数 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| `conversation_id` | path | 是 | 会话 UUID |

**响应 `ConversationDetailResponse`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 会话 UUID |
| `user_type` | string | patient/doctor |
| `host_id` | string | 会话主体 ID |
| `title` | string | 标题 |
| `summary` | string\|null | 摘要 |
| `total_messages` | int | 消息总数 |
| `create_time` / `update_time` | datetime | 时间 |
| `messages` | array<MessageResponse> | 消息列表 |

`MessageResponse{ id, message_order, message_content, message_type(user/assistant/system), create_time, context?(array) }`

**错误码**：404（会话不存在）、500。

---

### A.3.3 DELETE `/api/conversations/{conversation_id}` — 软删除会话

**响应 `DeleteConversationResponse`**：`{ "success": true, "message": "会话已删除", "conversation_id": "550e..." }`
**错误码**：404、500。

---

## A.4 科研助手 Research（前缀 `/api/research`，**仅医生**）

> 全部接口先经 `verify_doctor_role(doctor_id)` 校验，失败返回 **403**。

### A.4.1 POST `/api/research/chat` — 科研对话（非流式）

**请求体 `ResearchChatRequest`**

| 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `message` | string | 是 | - | 用户消息 |
| `doctor_id` | string(UUID) | 是 | - | 医生 UUID |
| `patient_id` | string(UUID) | 否 | null | 查看特定患者数据时提供 |
| `session_id` | string | 否 | 自动 `research_*` | 会话 ID |
| `conversation_id` | string | 否 | null | 续聊会话 |
| `enable_institution_data` | bool | 否 | false | 机构数据库访问开关 |
| `enable_web_search` | bool | 否 | false | 联网搜索开关 |
| `web_search_types` | array<string> | 否 | `[]` | `general`/`pubmed`/`scholar`（校验白名单） |

**响应 `ResearchChatResponse`**：`{ response, session_id, conversation_id, is_completed, stage, agent_type:"research", metadata }`
其中 `metadata` 含 `{doctor_id, patient_id, enable_institution_data, enable_web_search, web_search_types, thread_id}`。

**样例**
```bash
curl -X POST http://localhost:20602/api/research/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "帮我检索近三年青光眼药物治疗的随机对照试验",
    "doctor_id": "660e8400-e29b-41d4-a716-446655440001",
    "enable_web_search": true,
    "web_search_types": ["pubmed", "scholar"]
  }'
```
**错误码**：403（非医生）、400（参数）、500。

---

### A.4.2 POST `/api/research/chat/stream` — 科研对话（SSE）

入参同 A.4.1。SSE 事件：

| `event` | 说明 | 负载 |
| --- | --- | --- |
| `start` | 开始 | `session_id`, `conversation_id`, `thread_id` |
| `chunk` | **增量内容**（注意：非 `token`） | `content` |
| `tool_call` | 工具开始/结束 | `tool`, `status`, `input`/`output` |
| `done` | 完成 | `response`, `session_id`, `conversation_id`, `stage`, `agent_type:"research"`, `metadata{doctor_id,patient_id,enable_institution_data,enable_web_search}` |
| `error` | 异常（含非医生拦截） | `message` |

> 非医生访问时仅返回一个 `error` 事件即结束（HTTP 仍为 200 的 SSE 流）。

---

### A.4.3 GET `/api/research/conversations` — 科研会话列表

| 参数 | 位置 | 必填 | 默认 | 约束 |
| --- | --- | --- | --- | --- |
| `doctor_id` | query | 是 | - | 医生 UUID |
| `limit` | query | 否 | 20 | 内部夹取 1–100 |
| `offset` | query | 否 | 0 | ≥0 |

**响应 `ResearchConversationListResponse`**：`{ conversations: [ConversationSummary], total, has_more }`（`ConversationSummary` 同 §A.3.1）。
**错误码**：403、500。

---

### A.4.4 GET `/api/research/conversations/{conversation_id}` — 科研会话详情

| 参数 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| `conversation_id` | path | 是 | 会话 ID |
| `doctor_id` | query | 是 | 医生 UUID（用于权限与归属校验） |

**响应 200**
```json
{
  "conversation": {
    "id": "...", "title": "科研对话", "summary": null,
    "total_messages": 4, "create_time": "2026-06-28T10:00:00", "update_time": "2026-06-28T10:10:00"
  },
  "messages": [
    {"id": "...", "message_order": 1, "message_content": "...", "message_type": "user", "create_time": "..."}
  ]
}
```
**错误码**：403（非医生 / 非本人会话）、404（不存在）、500。

---

### A.4.5 DELETE `/api/research/conversations/{conversation_id}` — 删除科研会话

参数同 A.4.4。**响应**：`{ "message": "会话已删除", "conversation_id": "..." }`。
**错误码**：403、404、500。

---

### A.4.6 GET `/api/research/health` — 科研 Agent 健康检查

无参数。返回功能可用性与依赖状态（`search1api`/`minio`/`pandas`/`scipy`/`matplotlib` 是否就绪）。

**响应 200**（节选）
```json
{
  "status": "healthy", "agent_type": "research", "version": "3.0.0", "architecture": "langgraph",
  "features": {"institution_data": true, "web_search": true, "sse_streaming": true,
               "statistical_analysis": true, "data_visualization": true, "visualization_storage": false,
               "literature_review": true, "research_design": true},
  "dependencies": {"search1api": true, "minio": false, "pandas": true, "scipy": true, "matplotlib": true},
  "endpoints": ["POST /api/research/chat", "POST /api/research/chat/stream", "..."]
}
```

---

## A.5 合规审查 Compliance（前缀 `/api/compliance`，**仅医生**）

### A.5.1 POST `/api/compliance/chat` — 合规审查对话（非流式）

**请求体 `ComplianceChatRequest`**

| 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `message` | string | 是 | - | 用户消息 |
| `doctor_id` | string(UUID) | 是 | - | 医生 UUID |
| `patient_id` | string(UUID) | 是 | - | 审查目标患者 UUID |
| `session_id` | string | 否 | 自动 `compliance_*` | 会话 ID |
| `conversation_id` | string | 否 | null | 续聊会话 |

**响应 `ComplianceChatResponse`**：`{ response, session_id, conversation_id, is_completed, stage, agent_type:"compliance", metadata{doctor_id,patient_id,thread_id} }`

**样例**
```bash
curl -X POST http://localhost:20602/api/compliance/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "审查该患者最近一次处方的合理性",
    "doctor_id": "660e8400-e29b-41d4-a716-446655440001",
    "patient_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```
**错误码**：403（非医生）、400（参数）、500。

---

### A.5.2 POST `/api/compliance/chat/stream` — 合规审查对话（SSE）

入参同 A.5.1。SSE 事件：`start` / `chunk`（增量内容） / `tool_call` / `done`（`metadata{doctor_id,patient_id}`） / `error`。事件结构同 §A.4.2（无 `web_search` 相关字段）。

---

### A.5.3 GET `/api/compliance/health` — 合规 Agent 健康检查

无参数。**响应 200**（节选）
```json
{
  "status": "healthy", "agent_type": "compliance", "version": "1.0.0",
  "architecture": "langgraph", "access_control": "doctor_only",
  "features": {"prescription_review": true, "diagnosis_review": true, "medical_record_review": true,
               "examination_review": true, "web_search": true, "sse_streaming": true,
               "save_review": true, "export_pdf": true},
  "endpoints": ["POST /api/compliance/chat", "POST /api/compliance/chat/stream", "GET /api/compliance/health"]
}
```

---

## A.6 产品推荐 Recommendation（前缀 `/api/recommendation`，患者 + 医生）

### A.6.1 POST `/api/recommendation/chat` — 推荐对话（非流式）

**说明**：医生态 = 开处方/推荐用药；患者态 = OTC 购药。响应通过 `parse_ui_elements` 解析出产品卡片 / 选项。
**权限**：`role=doctor` 时必须传 `doctor_id`（否则 400）。

**请求体 `RecommendationChatRequest`**

| 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `message` | string | 是 | - | 用户消息 |
| `patient_id` | string(UUID) | 是 | - | 患者 UUID |
| `doctor_id` | string(UUID) | 否 | null | 医生 UUID（医生态必填） |
| `role` | string | 否 | `patient` | patient/doctor（校验白名单） |
| `session_id` | string | 否 | 自动 `rec_*` | 会话 ID |
| `conversation_id` | string | 否 | null | 续聊会话 |

**响应 `RecommendationChatResponse`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `response` | string | **纯文本**（已剥离卡片标记） |
| `session_id` / `conversation_id` | string | 会话标识 |
| `is_completed` / `stage` | bool / string | 状态 |
| `agent_type` | string | `recommendation` |
| `ui_elements` | UIElements\|null | 产品卡片 / 交互选项 |
| `metadata` | object | `{patient_id, doctor_id, role, thread_id}` |

**`ProductCard` 结构**（`ui_elements.product_cards[]`）

| 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `product_id` | string | 是 | - | 产品 UUID |
| `product_name` | string | 是 | - | 产品名称 |
| `generic_name` | string | 否 | null | 通用名 |
| `product_type` | string | 是 | - | PRESCRIPTION/OTC/DEVICE |
| `category` | string | 否 | "" | 分类 |
| `image_url` | string | 否 | null | 图片 URL |
| `unit_price` | float | 是 | - | 单价（元） |
| `specification` | string | 否 | null | 规格 |
| `stock_status` | string | 否 | IN_STOCK | IN_STOCK/LOW_STOCK/OUT_OF_STOCK |
| `indications` | string | 否 | null | 适应症 |
| `is_prescription` | bool | 否 | false | 是否需处方 |
| `action_type` | string | 是 | - | ADD_TO_CART/PRESCRIBE/VIEW_DETAIL |
| `action_label` | string | 是 | - | 按钮文本 |

**样例（患者态）**
```bash
curl -X POST http://localhost:20602/api/recommendation/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"有没有缓解眼睛干涩的滴眼液","patient_id":"550e8400-e29b-41d4-a716-446655440000","role":"patient"}'
```
**响应样例 200**
```json
{
  "response": "根据您的描述，为您推荐以下缓解干眼的非处方滴眼液：",
  "session_id": "rec_77ac1b2c3d4e5f60",
  "conversation_id": "550e8400-...",
  "is_completed": false,
  "stage": "recommendation",
  "agent_type": "recommendation",
  "ui_elements": {
    "ui_type": "product_cards",
    "product_cards": [
      {"product_id": "p-001", "product_name": "玻璃酸钠滴眼液", "product_type": "OTC", "unit_price": 64.0,
       "stock_status": "IN_STOCK", "is_prescription": false, "action_type": "ADD_TO_CART", "action_label": "加入购物车"}
    ],
    "options": null
  },
  "metadata": {"patient_id": "550e8400-...", "doctor_id": null, "role": "patient", "thread_id": "thread_..."}
}
```
**错误码**：400（医生态缺 doctor_id / UUID 非法 / role 非法）、500。

---

### A.6.2 POST `/api/recommendation/chat/stream` — 推荐对话（SSE）

入参同 A.6.1。SSE 事件：

| `event` | 说明 | 负载 |
| --- | --- | --- |
| `start` | 开始 | `session_id`, `conversation_id`, `thread_id` |
| `chunk` | **增量内容** | `content` |
| `tool_call` | 工具开始/结束 | `tool`, `status`, `input`/`output` |
| `ui_elements` | 解析到卡片/选项 | `ui_type`, `product_cards`, `options`（展开自 UIElements） |
| `done` | 完成 | `response`(纯文本), `session_id`, `conversation_id`, `stage`, `agent_type:"recommendation"`, `metadata{patient_id,doctor_id,role}` |
| `error` | 异常 | `message` |

> 该接口额外带响应头 `Access-Control-Allow-Origin: *`。

---

### A.6.3 GET `/api/recommendation/health` — 推荐 Agent 健康检查

无参数。**响应 200**（节选）
```json
{
  "status": "healthy", "agent_type": "recommendation", "version": "1.0.0",
  "architecture": "langgraph", "access_control": "all_roles",
  "features": {"doctor_prescription": true, "patient_purchase": true, "product_search": true,
               "product_cards": true, "interactive_options": true, "sse_streaming": true},
  "endpoints": ["POST /api/recommendation/chat", "POST /api/recommendation/chat/stream", "GET /api/recommendation/health"]
}
```

---

## A.7 语音识别 ASR

### A.7.1 POST `/api/asr/transcribe` — 语音转文字（文件上传）

**说明**：上传 WAV 音频，返回识别文本（浏览器 Push-to-Talk 场景）。内部调用 DashScope ASR。
**Content-Type**：`multipart/form-data`

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `audio` | file(WAV) | 是 | **采样率 16000Hz、单声道、16-bit**；时长 ≥ 0.5s |

**响应 200 `ASRTranscribeResponse`**：`{ "text": "识别出的文本" }`

**样例**
```bash
curl -X POST http://localhost:20602/api/asr/transcribe \
  -F "audio=@speech.wav;type=audio/wav"
```

**错误响应**（`detail` 为对象 `ASRErrorResponse{error_code, message}`）

| HTTP | error_code | 场景 |
| --- | --- | --- |
| 400 | `INVALID_FORMAT` | 空文件 / 非 WAV / 采样率·声道·位深不符 |
| 400 | `AUDIO_TOO_SHORT` | 录音 < 0.5s |
| 400 | `NO_SPEECH_DETECTED` | 未识别到语音 |
| 500 | `INTERNAL_ERROR` | ASR 配置错误 / 内部错误 |
| 502 | `ASR_API_ERROR` | DashScope 服务异常 |

```json
{ "detail": { "error_code": "AUDIO_TOO_SHORT", "message": "录音时长过短，请按住按钮后再说话" } }
```

---

### A.7.2 WS `/ws/asr` — 实时流式语音识别（WebSocket）

**说明**：外部系统通过 WebSocket 推送 PCM 音频帧，实时返回识别结果。

**客户端 → 服务端**

| 消息 | 类型 | 格式 |
| --- | --- | --- |
| 开始 | text(JSON) | `{"event":"start","request_id":"可选追踪ID","language":"zh"}` |
| 音频帧 | binary | 原始 PCM（int16 小端，16kHz，单声道），可连续多帧 |
| 结束 | text(JSON) | `{"event":"stop"}` |

**服务端 → 客户端**

| `event` | 说明 | 字段 |
| --- | --- | --- |
| `started` | 任务已启动 | `request_id` |
| `result` | 识别结果（中间/最终） | `request_id`, `text`, `is_final` |
| `done` | 任务完成 | `request_id`, `text` |
| `error` | 错误 | `request_id`, `error_code`, `message` |

> 约束：未发 `start` 前的二进制帧会被忽略；`stop` 时累计 PCM < 0.5s 返回 `AUDIO_TOO_SHORT`；`error_code` 枚举同 §A.7.1。

**交互样例**
```
C → {"event":"start","request_id":"r-001","language":"zh"}
S → {"event":"started","request_id":"r-001"}
C → <binary PCM frame> ...
C → {"event":"stop"}
S → {"event":"result","request_id":"r-001","text":"我想预约眼科","is_final":true}
S → {"event":"done","request_id":"r-001","text":"我想预约眼科"}
```

---

## A.8 文件上传（前缀 `/api`）

### A.8.1 POST `/api/upload` — 上传图片 / PDF 附件

**说明**：上传后返回结构化结果；前端将整个响应对象塞入 `ChatRequest.attachments[]` 随消息发送，由 chat 接口触发附件预分析。
**Content-Type**：`multipart/form-data`

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `file` | file | 是 | 图片：`image/jpeg`/`image/png`/`image/webp`（≤10MB）；PDF：`application/pdf`（≤30MB，最多取前 8 页） |

**响应 200 `FileUploadResponse`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `file_type` | string | `image` / `pdf` |
| `filename` | string | 文件名 |
| `minio_url` | string\|null | MinIO 备份 URL（内网，可能为空） |
| `base64` | string\|null | 图片 base64（图片专用，不含 `data:` 前缀） |
| `mime_type` | string\|null | 图片 MIME（图片专用） |
| `page_images` | array\|null | PDF 各页：`{base64, mime_type:"image/jpeg", page}`（PDF 专用） |
| `page_count` | int\|null | PDF 提取页数（PDF 专用） |

**样例（图片）**
```bash
curl -X POST http://localhost:20602/api/upload -F "file=@report.jpg;type=image/jpeg"
```
```json
{ "file_type": "image", "filename": "report.jpg", "minio_url": "http://minio/.../report.jpg",
  "base64": "/9j/4AAQSk...", "mime_type": "image/jpeg" }
```

**错误码**：415（类型不支持）、413（过大）、422（PDF 转图失败 / 无可提取页面）。

---

# Part B — 依赖的后端接口契约（`/agent/api/*`）

> 本部分是 AI 医问通**回调** Java 业务后端的接口契约，后端需保证实现并兼容字段。来源：`infrastructure/api/backend_client.py`。

## B.0 通用约定

| 项 | 值 |
| --- | --- |
| Base URL | `http://127.0.0.1:8081`（环境变量 `BACKEND_API_URL`，默认值） |
| 路径前缀 | `/agent/api` |
| 鉴权头 | `Agent-Token: <BACKEND_API_TOKEN>`（每个请求携带；默认值由环境变量 `BACKEND_API_TOKEN` 配置） |
| 内容类型 | `Content-Type: application/json` |
| 超时 | 30 秒 |
| 统一响应 | `SaResult` 包装：`{ "code": 200, "msg": "...", "data": <payload> }`，`code != 200` 视为业务失败（AI 端抛 `APIError`），网络异常抛 `NetworkError` |

**通用成功 / 失败响应**
```json
{ "code": 200, "msg": "success", "data": { } }
{ "code": 500, "msg": "错误信息", "data": null }
```
> 分页接口（如 `medicine-page`）会在顶层附加 `total / pageNum / pageSize / pages`。

**接口总览（按业务分组）**

| 分组 | 方法 | 路径 | AI 端方法 |
| --- | --- | --- | --- |
| 预约/问诊 | GET | `/agent/api/patient-prescription` | `get_patient_prescription` |
| 预约/问诊 | GET | `/agent/api/doctor-free-time` | `get_doctor_free_time` |
| 预约/问诊 | POST | `/agent/api/reserve-doctor` | `reserve_doctor` |
| 预约/问诊 | GET | `/agent/api/all-hospitals` | `get_all_hospitals` |
| 报告/处方 | GET | `/agent/api/patient-prescription-limit` | `get_patient_prescription_limit` |
| 报告/处方 | GET | `/agent/api/patient-prescription-detail` | `get_patient_prescription_detail` |
| 报告/处方 | GET | `/agent/api/patient-scan-data` | `get_patient_scan_data` |
| 报告/处方 | POST | `/agent/api/generate-medical-record-pdf` | `generate_medical_record_pdf` |
| 报告/处方 | POST | `/agent/api/generate-prescription-pdf` | `generate_prescription_pdf` |
| 提醒 | GET | `/agent/api/patient-reminder` | `get_patient_reminder` |
| 提醒 | GET | `/agent/api/patient-reminder-config` | `get_patient_reminder_config` |
| 提醒 | POST | `/agent/api/init-patient-reminder-config` | `init_patient_reminder_config` |
| 提醒 | POST | `/agent/api/modify-patient-reminder-config` | `modify_patient_reminder_config` |
| 提醒 | POST | `/agent/api/create-reminder` | `create_reminder` |
| 提醒 | POST | `/agent/api/create-medical-reminder` | `create_medical_reminder` |
| 患者数据 | GET | `/agent/api/get-all-patient` | `get_all_patients` |
| 患者数据 | GET | `/agent/api/get-medical-record` | `get_medical_records` |
| 患者数据 | GET | `/agent/api/patient-appointments` | `get_patient_appointments`（优雅降级） |
| 推荐/商品 | GET | `/agent/api/search-products` | `search_products` |
| 推荐/商品 | GET | `/agent/api/product-detail` | `get_product_detail` |
| 推荐/商品 | GET | `/agent/api/recommended-products` | `get_recommended_products` |
| 推荐/商品 | POST | `/agent/api/add-to-cart` | `add_to_cart` |
| 推荐/商品 | POST | `/agent/api/create-product-prescription` | `create_product_prescription` |
| AgentTool | GET | `/agent/api/patient-comprehensive-profile` | `get_patient_comprehensive_profile` |
| AgentTool | GET | `/agent/api/medicine-page` | `search_medicines` |
| AgentTool | POST | `/agent/api/create-prescription-order` | `create_prescription_order` |

---

## B.1 预约 / 问诊

### B.1.1 GET `/agent/api/patient-prescription`
查询患者所有处方。

| 参数 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| `patientId` | query | 是 | 患者 UUID |

`data`：处方信息。

### B.1.2 GET `/agent/api/doctor-free-time`
查询指定日期某医院医生的空闲时间段。

| 参数 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| `patientId` | query | 是 | 患者 UUID |
| `date` | query | 是 | `yyyy-MM-dd`，如 `2026-07-01` |
| `hospitalKey` | query | 是 | 医院关键字 |

`data`：空闲时间段与医生信息。

### B.1.3 POST `/agent/api/reserve-doctor`
创建预约（含病历）。

**请求体**
```json
{
  "patientId": "uuid",
  "doctorId": "uuid",
  "reserveTime": "2026-07-01T09:00:00",
  "medicalRecord": {
    "department": "眼科", "chiefComplaint": "主诉", "presentIllness": "现病史",
    "medicalHistory": "既往史", "allergyHistory": "过敏史", "familyHistory": "家族史",
    "medicationHistory": "用药史", "physicalExamination": "", "eyeExamResults": "",
    "specialExams": "", "auxiliaryExams": "", "diagnosis": "", "treatmentPlan": ""
  }
}
```
`data`：`Agenda` 对象（含预约 ID、病历 ID）。

### B.1.4 GET `/agent/api/all-hospitals`
返回全部医院列表。无参数。`data`：`List<HospitalSimpleResponse>`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 医院 UUID |
| `hospitalName` | string | 名称 |
| `province` / `city` / `address` | string | 省/市/详细地址 |
| `hospitalType` | string | GENERAL/SPECIALIZED 等 |
| `hospitalLevel` | string | TERTIARY_A/TERTIARY_B 等 |
| `star` | float | 评分 0–5 |

---

## B.2 报告 / 处方

### B.2.1 GET `/agent/api/patient-prescription-limit`
最近 N 份处方摘要。参数：`patientId`、`limit`。

### B.2.2 GET `/agent/api/patient-prescription-detail`
最近 N 份处方明细（含药品）。参数：`patientId`、`limit`。

### B.2.3 GET `/agent/api/patient-scan-data`
生物力学扫描数据。参数：`medicalRecordId`。

### B.2.4 POST `/agent/api/generate-medical-record-pdf`
生成病历 PDF。参数（query）：`medicalRecordId`。
**`data` 为 URL 字符串**（非对象）。

### B.2.5 POST `/agent/api/generate-prescription-pdf`
生成处方 PDF。参数（query）：`medicalRecordId`。**`data` 为 URL 字符串**。

---

## B.3 提醒

### B.3.1 GET `/agent/api/patient-reminder`
患者提醒列表。参数：`patientId`、`limit`（默认 5）。`data`：患者信息 + 提醒列表。

### B.3.2 GET `/agent/api/patient-reminder-config`
患者提醒配置。参数：`patientId`。

### B.3.3 POST `/agent/api/init-patient-reminder-config`
初始化提醒配置（仅首次）。请求体：初始化数据。`data`：`ReminderConfig`。

### B.3.4 POST `/agent/api/modify-patient-reminder-config`
修改提醒配置。请求体：修改数据。`data`：更新后的 `ReminderConfig`。

### B.3.5 POST `/agent/api/create-reminder`
创建通用提醒。请求体：提醒数据。`data`：`Reminder`。

### B.3.6 POST `/agent/api/create-medical-reminder`
批量创建用药提醒（按天生成多条 Reminder + Agenda）。

**请求体**
```json
{
  "patientId": "患者UUID",
  "title": "玻璃酸钠滴眼液",
  "content": "缓解干眼，每日滴眼",
  "medicalType": "DROP",
  "time": "09:00:00",
  "duration": 7
}
```
`medicalType` 枚举：`DROP`/`PILL`/`CAPSULE`/`INJECT`；`time` 格式 `HH:mm:ss`；`duration` 为天数。
**`data` 为 null**，成功信息在 `msg` 中（不抛异常即视为成功）。

---

## B.4 患者数据

### B.4.1 GET `/agent/api/get-all-patient`
全部患者列表。无参数。`data`：`List<Patient>`（字段含 `id/patientName/gender(male/female)/age/phone`）。

### B.4.2 GET `/agent/api/get-medical-record`
患者病历列表（含基本信息）。参数：`patientId`。

**`data`**
```json
{
  "patient": {"id": "uuid", "patientName": "张三", "gender": "male", "age": 35, "phone": "138...", "idNumber": "..."},
  "medicalRecords": [
    {"id": "病历UUID", "medicalHistory": "既往史", "allergyHistory": "过敏史", "familyHistory": "家族史"}
  ]
}
```

### B.4.3 GET `/agent/api/patient-appointments`
患者历史预约。参数：`patientId`。
> **降级说明**：若后端未实现该接口，AI 端捕获异常并返回空列表，不影响主流程。

> 另：AI 端 `get_patient_all_scan_data(patientId)` 为**组合调用**（先 `get-medical-record` 取病历，再对每条病历调 `patient-scan-data`），不对应新端点。

---

## B.5 推荐 / 商品

### B.5.1 GET `/agent/api/search-products`
搜索医药产品。

| 参数 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| `query` | query | 是 | 关键词 |
| `limit` | query | 否 | 数量（默认 10） |
| `category` | query | 否 | 分类 |
| `productType` | query | 否 | PRESCRIPTION/OTC/DEVICE |

### B.5.2 GET `/agent/api/product-detail`
产品详情。参数：`productId`。

### B.5.3 GET `/agent/api/recommended-products`
基于诊断/症状推荐。参数：`patientId`（必填）、`diagnosis`、`symptoms`（可选）。

### B.5.4 POST `/agent/api/add-to-cart`
加入购物车。
```json
{ "patientId": "uuid", "productId": "uuid", "quantity": 1 }
```

### B.5.5 POST `/agent/api/create-product-prescription`
开具产品处方。
```json
{ "doctorId": "uuid", "patientId": "uuid", "productId": "uuid", "dosageInstruction": "每日3次，每次1滴", "notes": "备注" }
```

---

## B.6 AgentToolController（已有专文）

以下 3 个接口字段较多，本文仅摘要，**完整字段与示例见**：[ADDAgentToolController-API文档.md](../../ADDAgentToolController-API文档.md)。

| 接口 | 方法 | 路径 | 摘要 |
| --- | --- | --- | --- |
| 患者综合画像 | GET | `/agent/api/patient-comprehensive-profile` | 参数 `patientId`；`data` 含 `patient / medicalRecords / checkHistory / prescriptions`（处方最多最近 20 条） |
| 药品分页 | GET | `/agent/api/medicine-page` | 参数 `pageNum`(默认1) / `pageSize`(默认10) / `keyword`；顶层附加 `total/pageNum/pageSize/pages`，`data` 为 `List<Drugs>` |
| 创建处方订单 | POST | `/agent/api/create-prescription-order` | 请求体 `{prescriptionId, remark?}`；后端经 `StpUtil` 读取登录医生 ID，**需携带 `satoken` 登录态**；`data` 为 `DrugOrder` |

> ⚠️ **现状提示**：AI 端 `create_prescription_order` 预留了 `sa_token` 形参（携带时加 `satoken` 头），但当前系统**尚未接入 sa-token 流转**；推荐 Agent 内部的下单工具目前为 Mock 实现，待后端登录态打通后切换为真实调用。

---

# 附录

## 附录 A — 对外接口完整清单

| # | 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- | --- |
| 1 | GET | `/health` | 公开 | 健康检查 |
| 2 | GET | `/api/info` | 公开 | API 信息 |
| 3 | GET | `/api/users` | 公开 | 患者列表 |
| 4 | GET | `/api/export/{session_id}` | 公开 | 导出会话 |
| 5 | GET | `/` | 公开 | 聊天页面(HTML) |
| 6 | GET | `/research-test` | 公开 | 科研测试页(HTML) |
| 7 | GET | `/recommendation-test` | 公开 | 推荐测试页(HTML) |
| 8 | POST | `/api/chat` | 患者+医生 | 同步对话 |
| 9 | POST | `/api/chat/stream` | 患者+医生 | 流式对话(SSE) |
| 10 | DELETE | `/api/chat/{session_id}` | 患者+医生 | 删除会话 |
| 11 | GET | `/api/chat/{session_id}/state` | 患者+医生 | 会话状态 |
| 12 | GET | `/api/chat/{session_id}/messages` | 患者+医生 | 消息历史 |
| 13 | GET | `/api/chat/{session_id}/agent-history` | 患者+医生 | Agent 切换历史 |
| 14 | GET | `/api/chat/{session_id}/checkpoints` | 患者+医生 | 检查点列表 |
| 15 | GET | `/api/conversations` | 患者+医生 | 会话列表 |
| 16 | GET | `/api/conversations/{conversation_id}` | 患者+医生 | 会话详情 |
| 17 | DELETE | `/api/conversations/{conversation_id}` | 患者+医生 | 软删除会话 |
| 18 | POST | `/api/research/chat` | 仅医生 | 科研对话 |
| 19 | POST | `/api/research/chat/stream` | 仅医生 | 科研对话(SSE) |
| 20 | GET | `/api/research/conversations` | 仅医生 | 科研会话列表 |
| 21 | GET | `/api/research/conversations/{conversation_id}` | 仅医生 | 科研会话详情 |
| 22 | DELETE | `/api/research/conversations/{conversation_id}` | 仅医生 | 删除科研会话 |
| 23 | GET | `/api/research/health` | 公开 | 科研健康检查 |
| 24 | POST | `/api/compliance/chat` | 仅医生 | 合规审查对话 |
| 25 | POST | `/api/compliance/chat/stream` | 仅医生 | 合规审查对话(SSE) |
| 26 | GET | `/api/compliance/health` | 公开 | 合规健康检查 |
| 27 | POST | `/api/recommendation/chat` | 患者+医生 | 推荐对话 |
| 28 | POST | `/api/recommendation/chat/stream` | 患者+医生 | 推荐对话(SSE) |
| 29 | GET | `/api/recommendation/health` | 公开 | 推荐健康检查 |
| 30 | POST | `/api/asr/transcribe` | 公开 | 语音转文字 |
| 31 | POST | `/api/upload` | 公开 | 上传附件 |
| 32 | WS | `/ws/asr` | 公开 | 实时语音识别 |

## 附录 B — 错误码总表

**HTTP**：400 / 403 / 404 / 413 / 415 / 422 / 500 / 502（含义见 §2.5）。

**ASR `error_code`（`ASRErrorCode`）**

| 枚举 | 说明 |
| --- | --- |
| `NO_SPEECH_DETECTED` | 未检测到语音 |
| `AUDIO_TOO_SHORT` | 音频时长不足（<0.5s） |
| `INVALID_FORMAT` | 格式不支持或损坏 |
| `ASR_API_ERROR` | DashScope 连接/识别失败 |
| `INTERNAL_ERROR` | 服务端内部错误 |

## 附录 C — 枚举值

| 维度 | 取值 |
| --- | --- |
| `agent_type` | health / report / reminder / research / compliance / recommendation |
| `role` / `user_type` | patient / doctor |
| `message_type` | user / assistant / system |
| `product_type` | PRESCRIPTION / OTC / DEVICE |
| `stock_status` | IN_STOCK / LOW_STOCK / OUT_OF_STOCK |
| `action_type`（ProductCard） | ADD_TO_CART / PRESCRIBE / VIEW_DETAIL |
| `medicalType`（用药提醒） | DROP / PILL / CAPSULE / INJECT |
| `orderStatus`（处方订单） | PENDING_PAYMENT / PAID / COMPLETED / CANCELLED / EXPIRED |
| `compliance_review_type`（内部状态） | prescription / diagnosis / record / examination / full |

## 附录 D — 环境变量与配置

| 变量 | 用途 | 默认 / 示例 |
| --- | --- | --- |
| 服务端口 | FastAPI 监听端口 | `20602`（硬编码于 `main.py`） |
| `BACKEND_API_URL` | Java 后端 Base URL | `http://127.0.0.1:8081` |
| `BACKEND_API_TOKEN` | 后端鉴权头 `Agent-Token` | 由部署方配置（请勿硬编码进客户端） |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | MySQL（对话/Checkpoint） | `3306` / `eye_agent_db` 等 |
| `DASHSCOPE_API_KEY` | DashScope ASR | 由部署方配置 |
| `SEARCH1API_KEY` | 联网检索（科研/合规） | 由部署方配置 |
| `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` / `MINIO_BUCKET` | 附件/可视化存储（可选） | 可禁用 |

> 安全提示：以上密钥/令牌请通过环境变量或密钥管理服务注入，**不要写入前端或日志**。

## 附录 E — 核心会话状态（`MedicalState`，内部）

> 该状态为 LangGraph 内部数据契约，**外部调用方无需直接构造**；列出以便理解响应字段来源与多 Agent 协作。来源 `agents/graph/state.py`。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `messages` | List[BaseMessage] | 消息历史（`add_messages` reducer 自动合并） |
| `patient_id` / `doctor_id` / `role` | str | 用户身份 |
| `session_id` / `conversation_id` | str | 会话标识 |
| `patient_info` / `patient_full_data` | dict | 患者画像缓存 |
| `current_agent` / `stage` / `is_completed` / `is_streaming` | - | 对话状态（对应响应中的 `agent_type/stage/is_completed`） |
| `route_result` / `should_switch_agent` | - | 路由决策 |
| `needs_appointment` / `collected_fields` / `chief_complaint` / `present_illness` / `appointment_confirmed` | - | health 专有 |
| `report_type` / `selected_records` | - | report 专有 |
| `reminder_type` / `reminder_created` | - | reminder 专有 |
| `compliance_review_type` / `compliance_review_completed` | - | compliance 专有 |
| `recommendation_mode` / `recommendation_ui_elements` / `recommendation_completed` / `selected_products` | - | recommendation 专有 |
| `enable_institution_data` / `enable_web_search` / `web_search_types` / `search_history` / `current_research_task` / `collected_data` | - | research 专有 |
| `security_blocked` / `security_events` | - | 安全 |
| `attachments` / `attachment_analysis` | - | 多模态附件 |
| `response` / `error` | str | 输出 |

## 附录 F — 端到端调用样例（患者多轮 + Agent 切换）

```bash
# 1) 患者发起问诊（不传 session_id/conversation_id → 自动新建）
curl -X POST http://localhost:20602/api/chat -H "Content-Type: application/json" -d '{
  "message": "我眼睛干涩",
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "role": "patient", "agent_type": "health"
}'
# → 返回 { "session_id": "sess_xxx", "conversation_id": "conv_yyy", "agent_type": "health", ... }

# 2) 续聊（带上一步返回的 session_id + conversation_id）
curl -X POST http://localhost:20602/api/chat -H "Content-Type: application/json" -d '{
  "message": "有什么药可以缓解",
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "role": "patient",
  "session_id": "sess_xxx", "conversation_id": "conv_yyy"
}'
# → 路由自动切到 recommendation，返回 ui_elements.product_cards

# 3) 流式获取下一轮（SSE）
curl -N -X POST http://localhost:20602/api/chat/stream -H "Content-Type: application/json" -d '{
  "message": "第一个加入购物车",
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "role": "patient", "session_id": "sess_xxx", "conversation_id": "conv_yyy"
}'

# 4) 查看本轮会话完整消息
curl "http://localhost:20602/api/chat/sess_xxx/messages?conversation_id=conv_yyy"
```

---

## 版本记录

| 版本 | 日期 | 说明 |
| --- | --- | --- |
| 1.0 | 2026-06-28 | 首版：覆盖对外暴露接口（32 个）+ 依赖后端契约（26 端点）+ 数据模型与附录 |

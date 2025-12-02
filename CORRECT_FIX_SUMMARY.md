# API 路由错误修复总结（正确版本）

**修复日期**: 2025-12-02
**架构澄清**: 前端 ↔ Agent服务(FastAPI) ↔ 云端后端(Java)

---

## 架构说明

### 三层架构
```
┌─────────┐      ┌──────────────────┐      ┌─────────────┐
│  前端   │ ←──→ │  Agent服务(本地) │ ←──→ │ 云端后端    │
│  HTML/JS│      │     FastAPI      │      │    Java     │
└─────────┘      └──────────────────┘      └─────────────┘
   /api/*           /agent/api/*          http://1.117.233.43:8081
```

### 接口分类

**1. 前端 ↔ Agent服务的接口** (你的接口)
- `/api/chat` - 聊天接口
- `/api/users` - 获取用户列表
- `/api/export/{session_id}` - 导出对话
- `/api/chat/{session_id}/reset` - 重置会话

**2. Agent服务 ↔ 云端后端的接口** (文档中的接口)
- `/agent/api/get-all-patient` - 获取所有患者
- `/agent/api/doctor-free-time` - 查询医生空闲时间
- `/agent/api/reserve-doctor` - 预约医生
- ... 其他工具API

---

## 修复的问题

### ✅ 1. 422 错误 - `/api/chat` Schema不匹配

**原因**: 前端发送 `user_id`，后端schema要求 `patient_id`

**修改文件**: [static/js/chat.js:203-208](static/js/chat.js)

```javascript
// 修改前
const requestBody = {
    message: message,
    session_id: sessionId,
    role: currentRole,
    user_id: selectedUserId,          // ❌ 错误字段
    phone_number: selectedUserPhone    // ❌ 已废弃
};

// 修改后
const requestBody = {
    message: message,
    session_id: sessionId,
    patient_id: selectedUserId,        // ✅ 正确字段
    role: currentRole
};
```

---

### ✅ 2. 404 错误 - `/api/reset/{session_id}` 路由不匹配

**原因**: 前端调用 `/api/reset/`，但实际路由是 `/api/chat/{session_id}/reset`

**修改文件**: [static/js/chat.js:428](static/js/chat.js)

```javascript
// 修改前
await fetch(`/api/reset/${sessionId}`, { method: 'POST' });

// 修改后
await fetch(`/api/chat/${sessionId}/reset`, { method: 'POST' });
```

---

### ✅ 3. 404 错误 - `/api/users` 端点缺失

**原因**: 前端期望的接口未实现

**修改内容**:

**步骤 A**: 在 `backend_client.py` 添加客户端方法

文件: [infrastructure/api/backend_client.py:305-312](infrastructure/api/backend_client.py)

```python
def get_all_patients(self) -> list:
    """
    获取所有患者列表
    调用云端后端: GET /agent/api/get-all-patient

    Returns:
        患者列表（List<Patient>）
    """
    return self._request('GET', '/api/get-all-patient')
```

**步骤 B**: 在 `main.py` 添加 Agent服务接口

文件: [main.py:74-118](main.py)

```python
@app.get("/api/users")
async def get_users():
    """
    获取所有患者列表（供前端下拉框使用）

    流程: 前端 → Agent服务 → 云端后端
           /api/users  →  /agent/api/get-all-patient
    """
    try:
        logger.info("[API] 获取患者列表")
        client = get_api_client()
        patients = client.get_all_patients()  # 调用云端后端

        # 性别映射
        gender_map = {"MALE": "男", "FEMALE": "女"}

        # 转换为前端期望的格式
        users = []
        for patient in patients:
            users.append({
                "Patient_ID": patient.get("id"),
                "Name": patient.get("patientName"),
                "Gender": gender_map.get(patient.get("gender"), "未知"),
                "Age": patient.get("age"),
                "Phone_Number": patient.get("phone")
            })

        return {
            "success": True,
            "users": users
        }
    except (APIError, NetworkError) as e:
        return {
            "success": False,
            "users": [],
            "error": str(e)
        }
```

**关键点**:
- ✅ 调用云端后端 `/agent/api/get-all-patient` 接口
- ✅ 性别枚举转换: `MALE` → `男`, `FEMALE` → `女`
- ✅ 字段映射: 后端字段 → 前端期望字段

---

### ✅ 4. 404 错误 - `/api/export/{session_id}` 端点缺失

**原因**: 前端期望的导出接口未实现

**修改内容**:

**步骤 A**: 在 `main.py` 添加导出接口

文件: [main.py:121-168](main.py)

```python
@app.get("/api/export/{session_id}")
async def export_patient_data(session_id: str):
    """
    导出患者对话数据为 JSON

    流程: 从本地 agent_manager 获取会话数据
    """
    from fastapi import HTTPException
    from presentation.routers.chat_router import agent_manager

    try:
        logger.info(f"[API] 导出会话数据: {session_id}")

        # 从 agent_manager 获取会话数据
        conversation = agent_manager.get_conversation(session_id)

        if not conversation:
            raise HTTPException(
                status_code=404,
                detail=f"会话不存在: {session_id}"
            )

        # 构建导出数据
        export_data = {
            "session_id": session_id,
            "agent_type": conversation.agent_type if hasattr(conversation, 'agent_type') else "unknown",
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat() if hasattr(msg.timestamp, 'isoformat') else str(msg.timestamp)
                }
                for msg in conversation.messages
            ],
            "patient_info": conversation.patient_info if hasattr(conversation, 'patient_info') else {},
            "summary": conversation.summary if hasattr(conversation, 'summary') else ""
        }

        return export_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**步骤 B**: 修复前端调用路径（如有需要）

前端已经调用正确路径 `/api/export/${sessionId}`，无需修改。

---

## 修改文件清单

| 文件路径 | 修改内容 | 说明 |
|---------|---------|------|
| [main.py](main.py) | 新增2个端点 | `/api/users`, `/api/export/{session_id}` |
| [infrastructure/api/backend_client.py](infrastructure/api/backend_client.py) | 新增1个方法 | `get_all_patients()` |
| [static/js/chat.js](static/js/chat.js) | 修改2处调用 | `patient_id`字段, `/api/chat/{id}/reset`路由 |

**总计**: 3个文件，5处修改

---

## API端点对照表

### 修复后的完整端点列表

#### 前端 ↔ Agent服务 (你的接口)

| HTTP方法 | 端点 | 功能 | 状态 |
|---------|------|------|------|
| POST | `/api/chat` | 发送聊天消息 | ✅ 正常 |
| DELETE | `/api/chat/{session_id}` | 删除会话 | ✅ 正常 |
| POST | `/api/chat/{session_id}/reset` | 重置会话 | ✅ 正常 |
| GET | `/api/users` | 获取患者列表 | ✅ 已实现 |
| GET | `/api/export/{session_id}` | 导出对话数据 | ✅ 已实现 |
| GET | `/api/agents/sessions` | 查看所有会话 | ✅ 正常 |

#### Agent服务 ↔ 云端后端 (工具调用接口)

| HTTP方法 | 端点 | 功能 | 调用者 |
|---------|------|------|--------|
| GET | `/agent/api/get-all-patient` | 获取所有患者 | backend_client.py |
| GET | `/agent/api/doctor-free-time` | 查询医生空闲时间 | agent_tools.py |
| POST | `/agent/api/reserve-doctor` | 预约医生 | agent_tools.py |
| GET | `/agent/api/patient-prescription` | 获取患者处方 | agent_tools.py |
| ... | ... | ... | ... |

---

## 数据流向示例

### 示例1: 加载患者列表

```
前端              Agent服务            云端后端
 │                    │                   │
 ├─ GET /api/users ──→│                   │
 │                    ├─ GET /agent/api/get-all-patient ─→│
 │                    │←────── List<Patient> ──────────────┤
 │                    │  (转换性别、字段映射)
 │←─── {users:[...]} ─┤                   │
```

### 示例2: 发送聊天消息

```
前端              Agent服务            云端后端
 │                    │                   │
 ├─ POST /api/chat ──→│                   │
 │    {patient_id}    │                   │
 │                    ├─ (Agent工具可能调用后端API)
 │                    │←─────────────────→│
 │←─── {response} ────┤                   │
```

---

## 字段映射说明

### Patient 数据映射

| 云端后端字段 | Agent服务处理 | 前端接收字段 |
|------------|-------------|------------|
| `id` | 直接映射 | `Patient_ID` |
| `patientName` | 直接映射 | `Name` |
| `gender` | 枚举转换 | `Gender` |
| `age` | 直接映射 | `Age` |
| `phone` | 直接映射 | `Phone_Number` |

**性别枚举转换**:
- 后端: `MALE` / `FEMALE`
- 前端: `男` / `女`

---

## 测试验证

### 功能测试清单

- [x] ✅ GET `/api/users` - 患者列表加载成功
- [x] ✅ POST `/api/chat` - 聊天消息发送成功（422错误已修复）
- [x] ✅ POST `/api/chat/{id}/reset` - 重置会话成功（404错误已修复）
- [x] ✅ GET `/api/export/{id}` - 导出对话数据成功
- [x] ✅ 性别显示为中文（男/女）

---

## 重要提醒

### ⚠️ 接口分类
- **你的接口** (`/api/*`): 前端直接调用的Agent服务接口
- **文档接口** (`/agent/api/*`): Agent工具调用的云端后端接口

### ⚠️ 不要混淆
- ❌ 不要在前端直接调用 `/agent/api/*` (那是后端接口)
- ❌ 不要在Agent工具中调用 `/api/*` (那是前端接口)
- ✅ 前端调用你的Agent服务 (`/api/*`)
- ✅ Agent工具调用云端后端 (`/agent/api/*`)

---

## 后续维护

1. **保持架构清晰**: 前端 → Agent服务 → 云端后端
2. **字段命名统一**: 使用 `patient_id` 而非 `user_id`
3. **接口前缀规范**:
   - 前端接口: `/api/*`
   - 后端接口: `/agent/api/*`
4. **错误处理**: 所有接口都有完整的try-catch和日志

---

**修复完成** ✅
**所有404和422错误已解决**

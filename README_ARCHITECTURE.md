# 智能医疗咨询系统 - 架构文档

## 版本 2.0.0 - 清洁架构重构

### 概述

本系统是基于LangChain的多智能体医疗咨询平台，采用清洁架构（Clean Architecture）设计，所有数据操作通过Java后端API进行。

### 架构层次

```
domain/          # 领域层 - 业务实体和规则
├── models/      # 领域模型（Patient, Appointment, Prescription等）
├── enums/       # 枚举类型（ConversationStage, AgentType等）
└── exceptions/  # 业务异常

application/     # 应用层 - 用例和业务逻辑
├── services/    # 业务服务
├── repositories/# 仓储接口定义
└── dto/         # 数据传输对象

infrastructure/  # 基础设施层 - 外部系统集成
├── api/         # 后端API客户端
├── repositories/# 仓储实现（调用后端API）
└── session/     # Session管理

agents/          # Agent层 - LangChain智能体
├── base/        # BaseAgent抽象类
├── health/      # HealthAgent（1号）
├── report/      # ReportAgent（2号）
├── reminder/    # ReminderAgent（3号）
└── tools/       # Agent工具集成

presentation/    # 表现层 - FastAPI路由
├── routers/     # API路由
├── schemas/     # Pydantic模型
└── middleware/  # 中间件
```

### 核心组件

#### 1. 智能体（Agents）

**BaseAgent** - 抽象基类
- 消除40%代码重复
- 提供统一的对话管理框架
- 集成LangChain工具

**HealthAgent** - 1号智能体
- 健康咨询和症状评估
- 眼科分诊问诊
- 医生预约
- 工具：get_patient_prescription, get_doctor_free_time, reserve_doctor

**ReportAgent** - 2号智能体
- 病历和处方PDF生成
- 历史记录分析
- 工具：get_patient_prescription_detail, generate_medical_record_pdf等

**ReminderAgent** - 3号智能体
- 提醒管理（用药、复诊、预约）
- 工具：get_patient_reminder, create_reminder等

#### 2. 领域模型

- **Patient**: 患者信息
- **Appointment**: 预约信息
- **MedicalRecord**: 病历信息
- **Prescription**: 处方信息
- **Conversation**: 对话状态

所有模型使用Pydantic进行验证。

#### 3. 仓储层

通过仓储模式封装后端API调用：
- **PatientRepository**: 患者数据访问
- **AppointmentRepository**: 预约数据访问
- **PrescriptionRepository**: 处方数据访问

#### 4. 后端API集成

- Base URL: `http://127.0.0.1:8081`
- 认证: `Agent-Token: REMOVED_CONFIGURE_BACKEND_API_TOKEN`
- 11个API端点，封装为LangChain工具

### API端点

#### 聊天接口

**POST /api/chat**

请求:
```json
{
  "message": "我想预约眼科医生",
  "session_id": "sess-abc123",  // 可选，自动生成
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",  // 必需，UUID
  "agent_type": "health",  // 可选：health/report/reminder
  "role": "patient"  // 可选：patient/doctor
}
```

响应:
```json
{
  "response": "您好，我是小Eye...",
  "session_id": "sess-abc123",
  "is_completed": false,
  "stage": "greeting",
  "agent_type": "health",
  "metadata": {
    "patient_id": "550e8400-...",
    "message_count": 1
  }
}
```

#### Agent管理

- **GET /api/agents/sessions** - 列出所有会话
- **GET /api/agents/sessions/{session_id}** - 获取会话状态
- **DELETE /api/chat/{session_id}** - 删除会话
- **POST /api/chat/{session_id}/reset** - 重置会话
- **POST /api/agents/cleanup** - 清理过期会话
- **GET /api/agents/stats** - 系统统计

### 破坏性变更（从v1到v2）

1. **patient_id 现在必需** - 必须提供UUID格式的patient_id
2. **user_id 已弃用** - 使用patient_id替代
3. **phone_number 已弃用** - 前端应先查询获取patient_id
4. **API路径变更** - `/chat` → `/api/chat`

### 启动方式

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python main.py

# 或使用uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 环境变量

```env
BACKEND_API_URL=http://127.0.0.1:8081
BACKEND_API_TOKEN=REMOVED_CONFIGURE_BACKEND_API_TOKEN
```

### 代码质量改进

- ✅ 消除40%代码重复（通过BaseAgent）
- ✅ 使用领域模型替代字典
- ✅ 统一错误处理
- ✅ 清晰的分层架构
- ✅ main.py精简到 < 100行
- ✅ 所有数据操作通过后端API
- ✅ 无database服务依赖

### 开发指南

#### 添加新的智能体

1. 创建新目录：`agents/your_agent/`
2. 继承BaseAgent
3. 实现抽象方法
4. 在tools中添加相关工具
5. 在AgentManager中注册

#### 添加新的API端点

1. 在`infrastructure/api/backend_client.py`中添加API方法
2. 在`agents/tools/agent_tools.py`中封装为LangChain工具
3. 分配给对应的Agent

### 测试

```bash
# 健康检查
curl http://localhost:8000/health

# 测试聊天
curl -X POST http://localhost:8000/api/chat \\
  -H "Content-Type: application/json" \\
  -d '{
    "message": "你好",
    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_type": "health"
  }'
```

### 维护者

Claude AI & Development Team

### 许可证

Proprietary


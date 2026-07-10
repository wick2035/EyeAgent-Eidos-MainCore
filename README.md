# 智能医疗咨询系统

基于 **LangGraph** 的多智能体状态图系统，实现眼科健康咨询、智能分诊、医生预约、病历管理、合规审查、科研辅助和医药产品推荐等全流程医疗服务。

## 系统架构

```
用户消息 --> Router（混合意图路由）
               |
    +----------+----------+----------+----------+----------+
    |          |          |          |          |          |
  Health    Report    Reminder  Research  Compliance  Recommendation
  (Agent1)  (Agent2)  (Agent3)  (Agent4)  (Agent5)    (Agent6)
    |          |          |          |          |          |
    +----------+----------+----------+----------+----------+
               |
         Response Handler --> 返回结果
```

- 每次 `graph.invoke()` 处理一条用户消息，多轮对话通过多次调用实现
- 状态通过 MySQL Checkpointer 持久化，支持断点续接
- Router 每条消息重新评估，支持对话中途切换 Agent

## 功能特性

### Agent 1 - 健康咨询智能体 (HealthAgent)
- 眼科健康咨询与症状评估
- 智能分诊问诊（主诉、现病史、体征采集）
- 医生空闲时间查询与预约
- 患者历史处方记录查看

### Agent 2 - 医疗报告智能体 (ReportAgent)
- 处方记录查询（列表 / 详情）
- 影像及检查数据查看
- 病历报告 PDF 生成
- 处方 PDF 生成（含 Code128 条形码）

### Agent 3 - 提醒管理智能体 (ReminderAgent)
- 复诊 / 用药 / 预约提醒的创建与查看
- 提醒配置管理（通知方式、免打扰时间等）
- 配置初始化与修改

### Agent 4 - 科研智能体 (ResearchAgent) [仅医生]
- 机构数据库查询（需权限开关）
- 医学文献搜索（general / pubmed / scholar）
- 统计分析（描述性统计、相关性、t 检验、回归等）
- 文献综述与摘要提取
- 研究方案设计与样本量估算
- 论文写作辅助
- 临床指南查询、药物相互作用检查
- 数据可视化生成（MinIO 存储）

### Agent 5 - 合规审查智能体 (ComplianceAgent) [仅医生]
- **处方合规审查**：药物剂量、适应症匹配、禁忌症、药物相互作用
- **诊断合规审查**：诊断依据充分性、指南诊断标准、ICD 编码规范
- **病历文书合规审查**：主诉 / 现病史 / 体征记录完整性、格式规范性
- **检查合理性审查**：临床必要性、指南推荐路径
- 每条审查意见附带权威标准 / 文献引用（联网实时搜索）
- 审查结果保存与 PDF 导出

### Agent 6 - 医药产品推荐智能体 (RecommendationAgent)
- **医生端**：根据患者诊断报告 / 病历推荐处方药、非处方药及医疗器械
- **患者端**：通过症状描述或购药需求推荐 OTC 药品和医疗器械
- **产品卡片**：响应中包含结构化产品卡片（图片、名称、规格、价格、操作按钮）
- **交互选项**：问询过程中提供可点击的选项卡片，点击后自动作为消息继续对话
- 产品搜索、详情查看、加入购物车（stub）、开具处方（stub）
- 患者端自动过滤处方药直接推荐，仅展示"查看详情"

### 智能路由系统（混合架构）

- **规则引擎**（第一层）：精确模式匹配 + 关键词加权，处理 ~90% 请求，<1ms 延迟
- **LLM 路由**（第二层）：轻量级 LLM 处理复杂语义，支持融合决策
- **角色权限控制**：患者无法访问 Research / Compliance Agent（路由层拦截）；Recommendation Agent 医生患者均可使用
- **状态保持**：关键对话阶段中自动保持当前 Agent，防止误切换

## 技术栈

| 类别 | 技术 |
|------|------|
| **核心框架** | LangGraph (StateGraph) + LangChain |
| **Web 框架** | FastAPI + Uvicorn |
| **AI 模型** | 硅基流动 Qwen/Qwen2.5-32B-Instruct |
| **状态持久化** | MySQL Checkpointer (langgraph-checkpoint) |
| **数据库** | MySQL + Java 后端 API |
| **搜索引擎** | Search1API (general / pubmed / scholar) |
| **对象存储** | MinIO（科研文件 / 可视化存储，可选） |
| **数据分析** | numpy, pandas, scipy, matplotlib |
| **文档生成** | python-docx, python-barcode (Code128) |
| **测试前端** | HTML5 + CSS3 + JavaScript (SSE) |

## 项目结构

```
├── agents/                         # 智能体层
│   ├── graph/
│   │   ├── graph_builder.py        # LangGraph 状态图构建
│   │   ├── state.py                # MedicalState 全局状态定义
│   │   ├── graph_manager.py        # 图调用管理器（同步/异步/流式）
│   │   ├── checkpointer.py         # MySQL Checkpoint 持久化
│   │   ├── nodes/
│   │   │   ├── router_node.py      # 路由节点（意图识别 + 角色拦截）
│   │   │   ├── health_node.py      # Agent 1 - 健康咨询
│   │   │   ├── report_node.py      # Agent 2 - 医疗报告
│   │   │   ├── reminder_node.py    # Agent 3 - 提醒管理
│   │   │   ├── research_node.py    # Agent 4 - 科研辅助
│   │   │   ├── compliance_node.py  # Agent 5 - 合规审查
│   │   │   ├── recommendation_node.py # Agent 6 - 产品推荐
│   │   │   └── response_node.py    # 响应后处理
│   │   └── edges/
│   │       └── routing.py          # 条件边路由 + 阶段流定义
│   ├── prompts/                    # 各 Agent 提示词模块
│   └── tools/                      # 各 Agent 工具定义
│       ├── agent_tools.py          # Agent 1-3 工具
│       ├── research_tools.py       # Agent 4 工具
│       ├── compliance_tools.py     # Agent 5 工具
│       └── recommendation_tools.py # Agent 6 工具
├── domain/                         # 领域模型层（实体、枚举）
├── application/                    # 应用服务层（仓储接口、DTO、持久化服务）
├── infrastructure/                 # 基础设施层（数据库、API 客户端、MinIO）
├── presentation/                   # 表现层
│   ├── routers/
│   │   ├── chat_router.py          # 通用对话 API
│   │   ├── research_router.py      # 科研 Agent 专用 API
│   │   ├── compliance_router.py    # 合规审查 Agent 专用 API
│   │   ├── recommendation_router.py # 产品推荐 Agent 专用 API
│   │   └── conversation_router.py  # 会话管理 API
│   └── schemas/                    # Pydantic 请求/响应模型
├── utils/                          # 工具函数
│   ├── hybrid_intent_router.py     # 混合意图路由器
│   ├── enhanced_rules.py           # 规则引擎
│   ├── llm_router.py              # LLM 路由器
│   └── llm_config.py              # LLM 配置
├── main.py                         # FastAPI 入口
└── requirements.txt
```

## API 接口

### 通用对话（自动路由）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat` | 同步对话 |
| POST | `/api/chat/stream` | SSE 流式对话 |
| GET  | `/api/chat/{session_id}/state` | 查询会话状态 |
| GET  | `/api/chat/{session_id}/messages` | 查询消息历史 |

### 科研 Agent 专用 [仅医生]

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/research/chat` | 科研对话 |
| POST | `/api/research/chat/stream` | 科研对话 (SSE) |
| GET  | `/api/research/conversations` | 会话列表 |
| GET  | `/api/research/health` | 健康检查 |

### 合规审查 Agent 专用 [仅医生]

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/compliance/chat` | 合规审查对话 |
| POST | `/api/compliance/chat/stream` | 合规审查对话 (SSE) |
| GET  | `/api/compliance/health` | 健康检查 |

### 产品推荐 Agent 专用

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/recommendation/chat` | 产品推荐对话 |
| POST | `/api/recommendation/chat/stream` | 产品推荐对话 (SSE) |
| GET | `/api/recommendation/health` | 健康检查 |

### 其他

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/users` | 患者列表 |
| GET | `/api/conversations` | 会话管理 |
| GET | `/api/export/{session_id}` | 导出对话数据 |
| GET | `/api/info` | API 信息 |
| GET | `/health` | 系统健康检查 |

## 内部调用认证边界

MainCore 的 HTTP 业务接口统一以 `/api` 或 `/api/**` 为边界验证 Java 网关签发的
短期 RS256 JWT，无需在每个路由重复声明依赖。认证模式由服务端环境变量
`INTERNAL_AUTH_MODE` 控制：

- `off`：默认值。不构造 verifier、不解析 token，保持现有请求行为；
- `observe`：验证已携带的 token，并记录缺失、无效或 JWKS 不可用等结果，但仍放行
  请求，用于上线前观测；
- `enforce`：仅对下述平台独占路由启用强制认证。缺失或无效 token 返回 `401`，无可用
  JWKS 时返回 `503`；其他 `/api/**` 路由仍按 `observe` 兼容放行。认证成功后把可信主体
  写入 `request.state.internal_principal`。

全局配置 `INTERNAL_AUTH_MODE=enforce` 不等于全部 `/api/**` 都强制认证。当前只有以下
五类平台独占路由的有效模式为 `enforce`（会话 ID 只匹配一个非空路径段）：

- `GET /api/conversations/{conversation_id}`；
- `POST /api/chat/edit-resend/stream`；
- `POST /api/chat/regenerate/stream`；
- `POST /api/research/chat/stream`；
- `PUT /api/conversations/{conversation_id}/active-branch`。

以下四类共享或患者兼容路由在全局配置为 `enforce` 时，有效模式仍为 `observe`：

- `POST /api/chat`；
- `POST /api/chat/stream`；
- `POST /api/upload`；
- `POST /api/asr/transcribe`。

其他未盘点 `/api/**`、方法不匹配、额外路径段或尾斜杠变体也默认使用 `observe`，避免
破坏既有患者调用；已携带合法 JWT 的请求仍会验证并绑定可信主体。

`observe` 和 `enforce` 必须配置 Java 后端的 JWKS URL。例如在容器内网中：

```env
INTERNAL_AUTH_MODE=observe
INTERNAL_JWT_JWKS_URL=http://eye-agent-backend:8081/.well-known/eye-agent-internal-jwks.json
```

建议先确认 Java JWKS 仅可被 MainCore 所在内网访问，再按 `off` → `observe` →
路由级 `enforce` 顺序发布。没有访问日志提供“遗留直连请求为零”的流量证据时，不得宣称
或启用全局 `enforce`；即使配置为 `enforce`，上述共享、患者兼容及未盘点 API 仍保持
`observe`。

本周期的 surface 边界如下：

- `/health` 是明确公开的业务健康接口，不进入内部 JWT 验证；
- `/`、测试页面、`/static/**`、`/docs`、`/redoc`、`/openapi.json` 等非
  `/api/**` surface 保持现状，不属于本周期的安全承诺；
- `/ws/asr` 是 WebSocket 接口，不进入当前 HTTP JWT 中间件，当前边界保持不变，
  必须依赖网关与内网访问控制；
- 生产环境不得把 MainCore 作为公网入口暴露，外部业务请求必须先经过 Java 网关。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

在项目根目录创建 `.env` 文件：

```env
# 硅基流动 API 配置
SILICONFLOW_API_KEY=your_api_key_here
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
MODEL_NAME=Qwen/Qwen2.5-32B-Instruct

# 数据库配置
DB_HOST=your_mysql_host
DB_PORT=3306
DB_USER=your_user
DB_PASSWORD=your_password
DB_NAME=eye_agent_db
DB_CHARSET=utf8mb4

# 后端 API 配置
BACKEND_API_URL=http://your_backend:8081
BACKEND_API_TOKEN=your_token

# 搜索 API 配置（ResearchAgent / ComplianceAgent 使用）
SEARCH1API_KEY=your_search_api_key

# 对象存储配置（可选）
# MINIO_ENDPOINT=your_minio_endpoint
# MINIO_ACCESS_KEY=your_access_key
# MINIO_SECRET_KEY=your_secret_key
# MINIO_BUCKET=research-files
```

### 3. 启动服务

```bash
python main.py
```

或使用 uvicorn：

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. 访问应用

打开浏览器访问：http://127.0.0.1:8000

## 使用说明

### 患者端

患者可使用 Agent 1-3、Agent 6：

1. **健康咨询**：描述眼部症状，AI 评估严重程度并引导就诊
2. **预约挂号**：系统化收集信息（主诉、现病史、既往史），完成医生预约
3. **报告查看**：查看历史处方和检查记录
4. **提醒管理**：创建 / 查看复诊和用药提醒
5. **购药推荐**（Agent 6）：根据症状推荐 OTC 药品和医疗器械，产品卡片展示

### 医生端

医生可使用全部 6 个 Agent：

1. **Agent 1-3**：同患者端功能，另有 PDF 生成等高级权限
2. **科研助手**（Agent 4）：文献检索、统计分析、研究方案设计、论文写作辅助
3. **合规审查**（Agent 5）：对患者诊断 / 处方 / 病历进行合规性审查，每条审查意见附带权威指南引用
4. **产品推荐**（Agent 6）：根据患者诊断推荐处方药 / 非处方药 / 医疗器械，支持开具处方

### 角色切换

在前端界面可切换角色：

- **患者模式**：健康咨询、报告查看、提醒管理、购药推荐
- **医生模式**：以上全部 + 科研助手 + 合规审查 + 产品推荐（处方权限）

## 相关文档

- [API 接口文档](docs/API_DOCUMENTATION.md)
- [系统架构文档](docs/README_ARCHITECTURE.md)
- [科研 Agent 设计文档](docs/RESEARCH_AGENT_DESIGN.md)
- [Agent 工具 API 文档](docs/Agent工具API文档.md)

## 文档规则

- 所有文档统一放置于 `docs/`
- 所有总结类 Markdown 文件统一放置于 `docs/summary/`

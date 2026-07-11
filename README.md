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
  写入 `request.state.internal_principal`。中间件同时把 effective mode 写入服务端专用
  ASGI scope 键 `_internal_auth_effective_mode`；该值不来自客户端，也不包含 token 或主体。

旧版科研 normal/edit/regenerate 路由只在 effective mode 为 `enforce` 时执行
subject/scope 强校验；`off` 与 `observe` 即使 token 缺失、无效或 scope 不匹配也继续
按既有行为放行。旧分支仍会独立校验会话 owner 与源用户消息的 canonical agent/patient
配置，缺失、损坏或冲突时 fail closed，且不创建任何消息节点。

全局配置 `INTERNAL_AUTH_MODE=enforce` 不等于全部 `/api/**` 都强制认证。当前只有以下
11 条平台独占路由的有效模式为 `enforce`（动态 ID 只匹配一个非空路径段）：

- `GET /api/conversations/{conversation_id}`；
- `POST /api/chat/edit-resend/stream`；
- `POST /api/chat/regenerate/stream`；
- `POST /api/platform/chat/turns/prepare`；
- `POST /api/platform/chat/turns/execute`；
- `GET /api/platform/chat/turns/{request_id}`；
- `POST /api/platform/chat/turns/{request_id}/abort`；
- `DELETE /api/platform/research-documents/{attachment_id}`；
- `POST /api/research/chat`；
- `POST /api/research/chat/stream`；
- `PUT /api/conversations/{conversation_id}/active-branch`。

以下四类共享或患者兼容路由在全局配置为 `enforce` 时，有效模式仍为 `observe`：

- `POST /api/chat`；
- `POST /api/chat/stream`；
- `POST /api/upload`；
- `POST /api/asr/transcribe`。

其他未盘点 `/api/**`、方法不匹配、额外路径段或尾斜杠变体也默认使用 `observe`，避免
破坏既有患者调用；已携带合法 JWT 的请求仍会验证并绑定可信主体。

`observe` 和 `enforce` 必须配置 Java 后端的 JWKS URL。默认示例使用 HTTPS：

```env
INTERNAL_AUTH_MODE=observe
INTERNAL_JWT_JWKS_URL=https://eye-agent-backend.example/.well-known/eye-agent-internal-jwks.json
```

默认只允许 HTTPS，或 `localhost`、IPv4/IPv6 loopback HTTP；例如本机联调可使用
`http://127.0.0.1:8081/.well-known/eye-agent-internal-jwks.json`。非 loopback HTTP 默认拒绝。
只有部署方已经证明链路位于已认证 service mesh 或其他有书面证据的受信网络边界时，才可
显式设置：

```env
INTERNAL_JWT_ALLOW_INSECURE_NON_LOOPBACK_HTTP=true
```

该变量默认 `false`，且只接受精确小写 `true`/`false`；空字符串、大小写变体、`1`、
`yes` 等值都会 fail-fast。此开关只是显式接受明文传输风险，不会让 HTTP 获得加密、端点
身份认证或防篡改能力，也不能替代生产 HTTPS/mTLS 或已认证 mesh 的部署证据。

认证中间件输出可按 method+规范化 route 聚合的安全事件：

```text
internal_auth_valid
internal_auth_missing
internal_auth_invalid
internal_auth_unavailable
internal_auth_internal_error
jwks_refresh_success
jwks_refresh_failed
```

认证事件至少包含 effective `mode`、安全 HTTP `method` 和固定 route template；动态
`conversation_id/session_id` 不写入日志，未知 API 固定分类为 `/api/{unknown}`。valid 事件
额外包含白名单 `principal_type` 与已验签 token `kid` 的 16 位 SHA-256 指纹；JWKS success
只记录 key count 与可信 `kid` 指纹。失败事件不记录 token、subject、攻击者原始 `kid`、
动态路径参数、异常消息/堆栈或上游响应正文。

建议先确认 JWKS 使用 HTTPS/mTLS、已认证 service mesh、loopback 或等效公钥固定，并且
Java JWKS 仅可被 MainCore 所在网络边界访问，再按 `off` → `observe` → 路由级 `enforce`
顺序发布。缺少上述传输证据，或没有访问日志提供“遗留直连请求为零”的流量证据时，不得宣称
或启用全局 `enforce`；即使配置为 `enforce`，上述共享、患者兼容及未盘点 API 仍保持
`observe`。

本周期的 surface 边界如下：

- `/health` 是明确公开的业务健康接口，不进入内部 JWT 验证；
- `/`、测试页面、`/static/**`、`/docs`、`/redoc`、`/openapi.json` 等非
  `/api/**` surface 保持现状，不属于本周期的安全承诺；
- `/ws/asr` 是 WebSocket 接口，不进入当前 HTTP JWT 中间件，当前边界保持不变，
  必须依赖网关与内网访问控制；
- 生产环境不得把 MainCore 作为公网入口暴露，外部业务请求必须先经过 Java 网关。

### 2026-07-10 自动化验收与部署边界

当前周期已完成平台 7 条 Java 调用与 MainCore 身份桥的代码、本地自动化验收；最终审查
又补入 `kid` 的 `1..128` UTF-8 字节契约、USER/DOCTOR 登录绑定失败补偿、完整安全遥测和
Token-Session 单次持久化。仓库外 2048-bit 临时 RSA 密钥签出的 compact JWT 和公开 JWKS
已通过生产 `CachedJwksProvider`、`RS256JWTVerifier` 的离线跨语言验签；探针断言主体类型、
`aud` 数组、scope 和 `kid` 契约，未记录临时 `kid`、token 或密钥材料。精确最终测试计数以
本周期 Task 12 验收报告为准。

第二轮独立复审又补齐 Java 公私钥真实 sign/verify 自检、Python 空白 `kid` 拒绝、至少
2048-bit RSA JWK 门禁，以及 HTTPS/loopback 默认安全的 JWKS URL 策略。

实际部署只使用以下变量名，secret 值由部署环境提供，不写入 README、镜像或 YAML：

```text
Java:
  INTERNAL_JWT_MODE=off
  INTERNAL_JWT_TTL_SECONDS=300
  INTERNAL_JWT_KEY_ID
  INTERNAL_JWT_PRIVATE_KEY_LOCATION
  INTERNAL_JWT_PUBLIC_KEY_LOCATION
  INTERNAL_JWT_ADDITIONAL_PUBLIC_JWKS_LOCATION

Python:
  INTERNAL_AUTH_MODE=off
  INTERNAL_JWT_JWKS_URL
  INTERNAL_JWT_CACHE_TTL_SECONDS
  INTERNAL_JWT_NEGATIVE_CACHE_SECONDS
  INTERNAL_JWT_REFRESH_COOLDOWN_SECONDS
  INTERNAL_JWT_REQUEST_TIMEOUT_SECONDS
  INTERNAL_JWT_CLOCK_SKEW_SECONDS
  INTERNAL_JWT_ALLOW_INSECURE_NON_LOOPBACK_HTTP=false
```

`off` 是两端默认配置。“代码与本地自动化完成”不等于“生产 enforce 就绪”。本次没有
staging/生产访问日志、真实 Sa-Token 或患者流量、部署权限
及编排环境，因此没有启动任何全局 enforce，也没有完成 staging 30 分钟/生产高峰流量
gate、真实平台/患者 JSON/SSE 探针、滚动 SSE drain、K1/K2 重叠发布/bake/signer 回滚或
前滚/回滚演练，也没有提供生产 HTTPS/mTLS、已认证 mesh、loopback 或等效公钥固定证据。
部署状态应判定为：平台范围代码与本地自动化验收完成，外部部署 gate 和演练待执行。

在外部 gate 完成前，上述 11 条平台独占路由以外的 `POST /api/chat`、
`POST /api/chat/stream`、`POST /api/upload`、`POST /api/asr/transcribe` 和未知
`/api/**` 均继续按 observe 兼容；没有患者端零流量或明确下线证据，全局 enforce gate
明确未满足。回滚顺序仍为 Python enforce → observe，完成实例 unready、在途 SSE drain
后再将 Java enforce → observe → off；这套部署回滚流程尚未在外部编排环境实际演练。

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

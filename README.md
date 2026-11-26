# EyeAgent Eidos

[English](README.en.md) | 简体中文

EyeAgent Eidos 是基于 FastAPI 和 LangGraph 的多智能体医疗咨询系统，围绕眼科场景提供健康咨询、报告查询、提醒管理、科研辅助、合规审查及医药产品推荐。它结合规则与大模型路由，并通过 MySQL 保存对话状态和历史。

> 本项目用于研究和开发，模型输出可能出错，不能替代专业医疗判断、诊断或治疗。临床使用需要由有资质的专业人员审核，并完成适用的安全、隐私和合规评估。

## 功能

| 智能体 | 主要能力 | 适用角色 |
| --- | --- | --- |
| Health | 眼科健康咨询、症状采集、分诊、医生查询及预约 | 患者、医生 |
| Report | 处方与检查记录查询、病历及处方文档生成 | 患者、医生 |
| Reminder | 复诊、用药和预约提醒及通知配置 | 患者、医生 |
| Research | 文献检索、统计分析、研究设计及写作辅助 | 医生 |
| Compliance | 处方、诊断、病历与检查合理性审查 | 医生 |
| Recommendation | 根据症状或诊断推荐药品、器械和结构化产品卡片 | 患者、医生 |

支持同步与 SSE 流式对话、会话历史、图片/PDF 附件及语音识别。具体能力依赖模型、业务后端、数据库及相应第三方服务；推荐中的购物车和开处方工具目前是占位实现。角色路由限制不能代替服务端身份认证和授权。

## 架构

```text
浏览器 / API 客户端
       │
       ▼
FastAPI 路由 → 输入与角色校验 → LangGraph 混合意图路由
                                  │
             Health / Report / Reminder / Research / Compliance / Recommendation
                                  │
                         响应处理与状态持久化
                         │                  │
                    MySQL              外部服务/API
```

规则和 LLM 路由协作选择智能体；MySQL Checkpointer 保存图状态，消息持久化组件管理会话历史。外部集成包括业务后端、DashScope、SiliconFlow、Search1API 和 MinIO。详细设计见 [项目结构](docs/项目结构.md)和[技术路线](docs/我们的工作.md)。

## 环境要求

- Python 3.10 或更新版本，以及 `pip`；依赖版本见 [requirements.txt](requirements.txt)。
- MySQL：完整会话持久化需要检查点表及项目所依赖的业务表。
- DashScope API 密钥：业务智能体调用模型和语音识别使用。
- 与本项目接口兼容的业务后端：患者、预约、处方等数据和操作依赖该服务；本仓库不包含完整后端及业务表建表脚本。
- 按需配置 SiliconFlow、Search1API 和 MinIO。外部服务可能产生费用。
- 文档转换功能可能需要安装 Microsoft Word、Pandoc 等系统组件；具体取决于所用转换路径和操作系统。

## 快速开始

### 1. 获取代码并安装依赖

```bash
git clone https://github.com/wick2035/EyeAgent-MainCore.git
cd EyeAgent-MainCore
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell：.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. 配置环境变量

在项目根目录创建 `.env`，按实际环境填写；以下值均为示例，不要提交真实密钥。

```dotenv
# 业务智能体及语音识别
DASHSCOPE_API_KEY=your_dashscope_key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
ALIYUN_MODEL_NAME=qwen3.5-plus

# MySQL
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=eye_agent_db
DB_CHARSET=utf8mb4

# 与本项目兼容的业务后端；务必显式设置
BACKEND_API_URL=http://127.0.0.1:8081
BACKEND_API_TOKEN=your_backend_token

# 按需：LLM 意图路由
SILICONFLOW_API_KEY=your_siliconflow_key
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
# 按需：PDF 页面视觉分析，注意变量名与上方不同
SILICON_FLOW_API_KEY=your_siliconflow_key
# 按需：科研和合规检索
SEARCH1API_KEY=your_search1api_key
# 按需：附件和科研文件对象存储
MINIO_ENDPOINT=127.0.0.1:9000
MINIO_ACCESS_KEY=your_minio_access_key
MINIO_SECRET_KEY=your_minio_secret_key
MINIO_BUCKET=research-files
```

`SILICONFLOW_API_KEY` 和 `SILICON_FLOW_API_KEY` 是代码中两个不同的变量。数据库连接池还支持 `DB_POOL_MIN`、`DB_POOL_MAX` 和 `DB_POOL_MAX_CONN`。不配置 MinIO 时，依赖对象存储的功能可能不可用。

### 3. 准备数据库和业务后端

创建数据库并配置具备适当权限的账号。检查 [检查点建表脚本](scripts/create_checkpoint_tables.sql)后，使用支持 `DELIMITER` 的 MySQL 客户端将其导入目标数据库：

```bash
mysql -h 127.0.0.1 -u your_db_user -p eye_agent_db < scripts/create_checkpoint_tables.sql
```

以上重定向示例适用于 Bash；PowerShell 可使用 `cmd /c "mysql -h 127.0.0.1 -u your_db_user -p eye_agent_db < scripts/create_checkpoint_tables.sql"`。脚本只创建 LangGraph 相关表和过程，**不包含完整业务数据库**。另有 [chat_message 升级脚本](scripts/alter_chat_message_add_status.sql)，仅在已有兼容业务表且确认需要时使用。请自行准备匹配的业务表、数据及后端服务。启动时数据库连接失败不会阻止应用启动，但相关功能可能不可用。

### 4. 启动

在项目根目录运行：

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 20602 --reload
```

- 聊天界面：<http://127.0.0.1:20602/>
- 交互式 API 文档：<http://127.0.0.1:20602/docs>
- 健康检查：<http://127.0.0.1:20602/health>
- 科研测试页：<http://127.0.0.1:20602/research-test>
- 推荐测试页：<http://127.0.0.1:20602/recommendation-test>

也可运行 `python main.py`；实际监听端口为 `20602`。`/health` 只报告应用状态，并不验证所有外部依赖。

## API 示例

`patient_id` 必须为 UUID，实际业务调用应使用后端中存在的患者 ID。医生请求可提供 `doctor_id`、`role: "doctor"`；角色身份需要由可信的服务端认证机制保证。

```bash
curl -X POST http://127.0.0.1:20602/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"眼睛干涩怎么办？","patient_id":"550e8400-e29b-41d4-a716-446655440000","role":"patient"}'
```

上述示例使用 Bash 语法；PowerShell 可使用 `curl.exe` 并按其规则转义 JSON，或通过 `/docs` 调试。响应包含 `response`、`session_id`、`conversation_id`、`stage` 和 `agent_type` 等字段；继续会话时传回返回的会话标识。流式调用使用 `POST /api/chat/stream` 和 SSE。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/chat`、`/api/chat/stream` | 普通及流式对话 |
| GET | `/api/chat/{session_id}/state`、`/messages`、`/checkpoints`、`/agent-history` | 查询状态、消息、检查点和智能体历史（后面三个路径均以 `/api/chat/{session_id}` 为前缀） |
| GET / DELETE | `/api/conversations`、`/api/conversations/{conversation_id}` | 会话列表、详情与删除；列表不支持 DELETE |
| POST | `/api/research/chat`、`/api/compliance/chat`、`/api/recommendation/chat` | 专用智能体对话；各自提供 `/stream` 路径 |
| POST | `/api/upload` | 上传图片或 PDF 附件 |
| GET | `/api/users`、`/api/info`、`/api/export/{session_id}` | 患者列表、接口信息和会话导出 |

完整参数、语音接口及返回模型以运行时 `/docs` 为准。更多说明见 [AI 医问通接口](docs/AI医问通-接口文档.md)、[多模态附件](docs/多模态附件接口文档.md)、[语音识别](docs/ASR语音识别接口文档.md)和 [Agent 工具 API](docs/Agent工具API文档.md)。

## 项目结构

```text
agents/          LangGraph 状态图、智能体节点、提示词与工具
application/     应用服务与仓储接口
domain/          领域模型、枚举和异常
infrastructure/  MySQL、业务 API、搜索、语音及对象存储适配
presentation/    FastAPI 路由与请求/响应模型
utils/           路由、模型配置、输入检查及文档生成工具
scripts/         数据库脚本
templates/       Jinja2 页面
static/          前端资源和测试页面
docs/            架构与接口文档
main.py          应用入口
```

## 部署与安全

此仓库包含演示和集成代码，部署前应实现可靠的身份认证、服务端授权、敏感数据保护、审计及网络隔离。当前 CORS 配置允许所有来源，角色字段本身不是身份凭证。务必配置业务后端地址与令牌；检查和轮换所有可能已暴露的凭据。检查点使用 Python pickle 序列化，只能从可信数据库读取。不要将真实患者数据、`.env` 或密钥提交到仓库，也不要将敏感信息放入公开 Issue。

## 常见问题

- **服务启动了但对话失败？** 检查 DashScope 密钥、模型权限、数据库及业务后端的地址和日志；`/health` 不检查依赖。
- **会话无法保存？** 检查 MySQL 连接、业务表和检查点表是否就绪，查看应用日志。
- **路由或 PDF 分析失败？** 分别检查 `SILICONFLOW_API_KEY` 和 `SILICON_FLOW_API_KEY`；两者拼写不同。
- **科研搜索或文件功能不可用？** 检查 Search1API、MinIO 的配置和网络可达性。

## 参与贡献

欢迎提交 Issue 和 Pull Request。请说明问题、复现步骤或变更动机；修改时保持现有分层结构，并验证受影响的功能。请勿提交密钥、个人健康信息或生产数据。

## 许可证

本项目采用 [Apache License 2.0](LICENSE)。使用、修改和分发时请遵循许可证条款。第三方服务与依赖各自适用其许可和使用条款。PDF 渲染使用 [pypdfium2 / PDFium](https://github.com/pypdfium2-team/pypdfium2#licensing)；分发其二进制文件时应保留其及其依赖的许可声明。依赖版本未全部锁定，发布构建时请审核实际安装版本及其传递依赖。

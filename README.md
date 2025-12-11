# 智能医疗咨询系统

基于Langchain的多智能体集群系统，实现眼科健康咨询、智能分诊、医生预约、病历生成和处方管理等全流程医疗服务。

## 功能特性

### Agent 1 - 健康咨询智能体 (HealthAgent)
- ✅ **健康信息咨询**：提供专业的眼科健康咨询服务
- ✅ **场景智能判断**：根据症状评估严重程度，主动询问是否需要预约医生
- ✅ **眼科分诊问诊**：系统化收集患者信息，包括症状、病史等
- ✅ **医生预约**：帮助患者完成预约流程
- ✅ **历史记录管理**：自动加载和关联患者历史就诊记录

### Agent 2 - 医疗报告智能体 (ReportAgent)
- ✅ **病历报告生成**：基于问诊记录生成标准化医疗报告（ PDF）
- ✅ **处方管理**：创建、查询和生成带条形码的电子处方（ PDF）
- ✅ **历史记录分析**：智能分析患者历史就诊和用药记录
- ✅ **角色权限控制**：医生专属功能，患者无法访问
- ✅ **条形码生成**：为处方单生成Code128标准条形码

### Agent 3 - 提醒管理智能体 (ReminderAgent)
- ✅ **复诊提醒管理**：创建和管理患者复诊提醒
- ✅ **用药提醒管理**：设置药物服用时间和剂量提醒
- ✅ **预约提醒管理**：自动提醒即将到来的预约
- ✅ **提醒配置管理**：支持通知方式、免打扰时间等个性化设置
- ✅ **生物力学报告**：生成眼部生物力学检查报告

### Agent 4 - 医问通科研智能体 (ResearchAgent)
- ✅ **机构数据查询**：访问机构内部科研数据库（需权限）
- ✅ **医学文献搜索**：支持 general/pubmed/scholar 多类型搜索
- ✅ **统计分析**：描述性统计、相关性分析、t检验、回归分析等
- ✅ **文献处理**：摘要提取、关键发现整理、文献翻译
- ✅ **研究方案设计**：研究设计建议、样本量估算
- ✅ **论文写作协助**：各章节写作指导（摘要、方法、讨论等）
- ✅ **临床指南查询**：查询 WHO/NICE/中华医学会等权威指南
- ✅ **药物相互作用检查**：检查多种药物的相互作用风险
- ✅ **伦理审查协助**：提供研究伦理审查相关建议
- ⚠️ **角色权限控制**：仅医生可访问

### 智能路由系统（混合架构）

- ✅ **规则引擎**：处理90%常见请求，响应时间<1ms
- ✅ **LLM路由**：处理复杂意图识别，支持融合决策
- ✅ **意图识别**：自动识别用户意图，置信度≥0.7时智能切换智能体
- ✅ **会话管理**：保持对话上下文，支持多轮交互，会话自动持久化
- ✅ **角色控制**：基于角色（患者/医生）的权限管理

## 技术栈

- **后端框架**：FastAPI + LangChain
- **测试前端**：HTML5 + CSS3 + JavaScript
- **AI模型**：硅基流动平台 Qwen/Qwen2.5-32B-Instruct
- **数据库**：MySQL + Java后端API
- **文档生成**：python-docx + python-barcode（Code128条形码）
- **搜索引擎**：Search1API（支持 general/pubmed/scholar）
- **对象存储**：MinIO（科研文件存储，可选）
- **数据分析**：numpy、pandas、scipy、matplotlib

## 项目架构

本项目采用**清洁架构（Clean Architecture）**设计，分为5层：

```text
├── domain/          # 领域模型层（实体、枚举）
├── application/     # 应用服务层（仓储接口、DTO）
├── infrastructure/  # 基础设施层（数据库、API客户端）
├── agents/          # 智能体层（Agent实现、工具定义）
├── presentation/    # 表现层（FastAPI路由、Schema）
└── utils/           # 工具函数（LLM配置、报告生成）
```

## 相关文档

- [API接口文档](docs/API_DOCUMENTATION.md)
- [系统架构文档](docs/README_ARCHITECTURE.md)
- [科研Agent设计文档](docs/RESEARCH_AGENT_DESIGN.md)
- [Agent工具API文档](docs/Agent工具API文档.md)

## 文档存放规则

- 所有文档统一放置于 `docs`
- 所有总结类 Markdown 文件统一放置于 `docs/summary`


### 3. 配置环境变量

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

# 搜索 API 配置（ResearchAgent 使用）
SEARCH1API_KEY=your_search_api_key

# 对象存储配置（可选）
# MINIO_ENDPOINT=your_minio_endpoint
# MINIO_ACCESS_KEY=your_access_key
# MINIO_SECRET_KEY=your_secret_key
# MINIO_BUCKET=research-files
```

### 4. 启动服务

```bash
python main.py
```

或使用uvicorn：

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. 访问应用

打开浏览器访问：http://127.0.0.1:8000



## 使用说明

### 患者端对话流程

1. **初次接待**：系统问候并询问健康问题
2. **健康咨询**：描述您的眼部症状
3. **症状评估**：AI评估症状严重程度
4. **预约询问**：系统主动询问是否需要预约医生
5. **信息收集**：收集患者基本信息（姓名、年龄、性别、联系方式）
6. **眼科分诊**：详细了解眼部症状和现病史
7. **病史采集**：收集既往病史、用药史、过敏史等
8. **预约确认**：确认期望就诊时间和紧急程度
9. **完成**：生成完整病例数据

### 医生端功能

医生登录后可使用以下专属功能：

1. **病历报告生成**：基于患者就诊记录生成标准化医疗报告
2. **处方管理**：
   - 创建新处方（包含药品信息、用法用量）
   - 查询历史处方记录
   - 生成带条形码的电子处方PDF
3. **历史记录分析**：查看和分析患者完整就诊历史
4. **科研助手**（ResearchAgent）：
   - 医学文献检索（PubMed、Google Scholar）
   - 数据统计分析（描述性统计、相关性、t检验等）
   - 研究方案设计与样本量估算
   - 论文写作指导
   - 临床指南查询
   - 药物相互作用检查

### 功能按钮

- **📄 导出病例**：查看并下载患者病例JSON数据
- **🔄 重新开始**：清空当前对话，开始新的咨询

### 角色切换

在前端界面可以切换角色：
- **患者模式**：健康咨询、预约挂号
- **医生模式**：病历生成、处方管理、历史分析



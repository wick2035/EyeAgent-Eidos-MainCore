# 智能医疗咨询系统【注意！！！！此版本弃用！！！！】

基于Langchain的多智能体集群系统，实现眼科健康咨询、智能分诊、医生预约、病历生成和处方管理等全流程医疗服务。

## 功能特性

### Agent 1 - 健康咨询智能体 (HealthAgent)
- ✅ **健康信息咨询**：提供专业的眼科健康咨询服务
- ✅ **场景智能判断**：根据症状评估严重程度，主动询问是否需要预约医生
- ✅ **眼科分诊问诊**：系统化收集患者信息，包括症状、病史等
- ✅ **医生预约**：帮助患者完成预约流程
- ✅ **数据导出**：生成标准JSON格式的患者病例数据
- ✅ **历史记录管理**：自动加载和关联患者历史就诊记录

### Agent 2 - 医疗报告智能体 (ReportAgent)
- ✅ **病历报告生成**：基于问诊记录生成标准化医疗报告（Word + PDF）
- ✅ **处方管理**：创建、查询和生成带条形码的电子处方
- ✅ **历史记录分析**：智能分析患者历史就诊和用药记录
- ✅ **角色权限控制**：医生专属功能，患者无法访问
- ✅ **条形码生成**：为处方单生成Code128标准条形码

### 智能路由系统
- ✅ **意图识别**：自动识别用户意图，智能切换智能体
- ✅ **会话管理**：保持对话上下文，支持多轮交互
- ✅ **角色控制**：基于角色（患者/医生）的权限管理

## 技术栈

- **后端框架**：FastAPI + Langchain
- **前端技术**：HTML5 + CSS3 + JavaScript
- **AI模型**：硅基流动平台 Qwen/Qwen2.5-7B-Instruct
- **数据库**：MySQL 8.0+
- **文档生成**：python-docx + docx2pdf + barcode
- **数据格式**：JSON

## 安装步骤

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置数据库

**安装MySQL 8.0+**，然后执行数据库初始化脚本：

```bash
# 方式1：直接使用MySQL命令行
mysql -u root -p medical_db < database/init_database_v2.sql

# 方式2：使用Python脚本执行
python database/execute_init_v2.py
```

**修改数据库配置**（[database/db_config.py](database/db_config.py)）：

```python
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'your_password',  # 修改为你的MySQL密码
    'database': 'medical_db',
}
```

### 3. 配置环境变量

在项目根目录创建 `.env` 文件，配置硅基流动API：

```env
SILICONFLOW_API_KEY=your_api_key_here
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
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

**测试功能**：

```bash
# 测试处方生成功能
python test_prescription_fix.py

# 测试Agent 2功能
python test_agent2_fix.py

# 测试条形码生成
python test_barcode_header.py
```

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

### 功能按钮

- **📄 导出病例**：查看并下载患者病例JSON数据
- **🔄 重新开始**：清空当前对话，开始新的咨询

### 角色切换

在前端界面可以切换角色：
- **患者模式**：健康咨询、预约挂号
- **医生模式**：病历生成、处方管理、历史分析

## 输出数据格式

系统会生成标准的JSON格式病例数据，包含以下字段：

```json
{
  "patient_info": {
    "name": "患者姓名",
    "age": "年龄",
    "gender": "性别",
    "contact": "联系方式",
    "id_number": "身份证号"
  },
  "chief_complaint": "主诉症状",
  "present_illness": "现病史",
  "symptoms": {
    "vision_change": "视力变化情况",
    "eye_pain": "眼痛",
    "redness": "红眼",
    "discharge": "分泌物",
    "other": "其他症状"
  },
  "medical_history": "既往病史",
  "medication_history": "用药史",
  "allergy_history": "过敏史",
  "family_history": "家族病史",
  "appointment": {
    "department": "眼科",
    "preferred_time": "期望就诊时间",
    "doctor_preference": "医生偏好",
    "urgency": "紧急程度"
  },
  "diagnosis_suggestion": "初步诊断建议",
  "timestamp": "记录时间"
}
```

## 数据库架构

### 核心表结构

- **patient** - 患者基本信息（手机号唯一标识）
- **medical_record** - 就诊记录（一次就诊一条记录）
- **appointment** - 预约信息（关联就诊记录和医生）
- **prescription** - 处方信息（详细药品信息）
- **doctor** - 医生档案

### 数据关联

- 一个患者（phone_number）可以有多条就诊记录
- 每条就诊记录可以有一个预约
- 每条就诊记录可以有多个处方
- 使用V2版本的数据服务支持多记录查询

## API接口

### 聊天相关

#### POST /api/chat
智能对话接口（自动路由到合适的Agent）

**请求体**：
```json
{
  "message": "用户消息",
  "session_id": "会话ID（可选）",
  "role": "patient/doctor"
}
```

**响应**：
```json
{
  "response": "AI响应",
  "session_id": "会话ID",
  "is_completed": false,
  "stage": "当前阶段",
  "current_agent": "agent_1/agent_2"
}
```

#### POST /api/chat/report
直接与ReportAgent对话（医生专用）

### 报告管理

#### POST /api/report/generate
生成医疗报告（Word + PDF）

**请求体**：
```json
{
  "phone_number": "患者手机号",
  "record_id": "就诊记录ID（可选）"
}
```

#### GET /api/report/history/{phone_number}
获取患者历史报告列表

#### POST /api/report/analyze
分析患者历史就诊记录

### 处方管理

#### POST /api/prescription/create
创建新处方（医生专用）

**请求体**：
```json
{
  "phone_number": "患者手机号",
  "record_id": "就诊记录ID",
  "medications": [
    {
      "name": "药品名称",
      "dosage": "剂量",
      "frequency": "频次",
      "duration": "疗程"
    }
  ]
}
```

#### POST /api/prescription/generate
生成处方PDF（带条形码）

**请求体**：
```json
{
  "prescription_id": "处方ID"
}
```

#### GET /api/prescription/history/{phone_number}
查询患者历史处方

### 预约相关

#### GET /api/appointments/{phone_number}
查询患者预约记录

### 患者信息

#### GET /api/patients/{phone_number}
获取患者完整信息（包括就诊历史）

### 会话管理

#### POST /api/reset/{session_id}
重置会话

#### GET /api/session/{session_id}
获取会话信息

#### GET /api/export/{session_id}
导出患者病例数据

#### GET /api/stats
获取系统统计信息

## 项目结构

```
pythonProject1/
├── requirements.txt                  # Python依赖
├── .env                              # 环境变量配置
├── main.py                           # FastAPI主应用
├── README.md                         # 项目说明文档
├── CLAUDE.md                         # Claude Code开发指南
├── agents/
│   ├── __init__.py
│   ├── agent_1.py                   # Agent 1: 健康咨询智能体
│   ├── agent_2.py                   # Agent 2: 医疗报告智能体
│   └── agent_manager.py             # 智能体管理器
├── database/
│   ├── db_config.py                 # 数据库连接配置
│   ├── db_connection.py             # 数据库连接封装
│   ├── init_database_v2.sql         # 数据库初始化脚本
│   ├── execute_init_v2.py           # 数据库初始化执行脚本
│   ├── appointment_service_v2.py    # 预约服务V2（支持多记录）
│   ├── user_history_service_v2.py   # 用户历史服务V2
│   ├── report_service.py            # 医疗报告数据服务
│   └── prescription_service.py      # 处方数据服务
├── utils/
│   ├── __init__.py
│   ├── llm_config.py                # LLM配置和初始化
│   ├── intent_detector.py           # 意图识别和智能路由
│   ├── data_handler.py              # JSON数据处理
│   ├── report_generator.py          # 医疗报告生成器（Word + PDF）
│   └── prescription_generator.py    # 处方生成器（PDF + 条形码）
├── example/
│   ├── bingli_template.docx         # 医疗报告Word模板
│   ├── prescription_template.docx   # 处方Word模板
│   ├── logo@1x.png                  # 系统Logo
│   ├── reports/                     # 生成的报告输出目录
│   └── prescriptions/               # 生成的处方输出目录
├── static/
│   ├── css/
│   │   └── style.css                # 界面样式
│   └── js/
│       └── chat.js                  # 聊天交互逻辑
├── templates/
│   └── index.html                   # 聊天界面
└── tests/
    ├── test_prescription_fix.py     # 处方功能测试
    ├── test_agent2_fix.py           # Agent 2功能测试
    └── test_barcode_header.py       # 条形码生成测试
```

## 文档生成功能

### 医疗报告生成

系统可以根据患者就诊记录自动生成标准化医疗报告：

**功能特点**：
- 基于Word模板生成报告
- 自动填充患者信息、症状、诊断、医嘱等
- 支持导出为Word (.docx) 和 PDF 格式
- 模板文件：[example/bingli_template.docx](example/bingli_template.docx)
- 输出目录：[example/reports/](example/reports/)

**使用方式**：
1. 医生端对话中要求"生成报告"
2. 或通过API调用 `POST /api/report/generate`

### 处方生成

系统支持创建和打印带条形码的电子处方：

**功能特点**：
- 详细记录药品信息（名称、剂量、频次、疗程）
- 自动生成Code128标准条形码
- 包含医生签名、处方日期、有效期
- 支持处方号快速检索
- 模板文件：[example/prescription_template.docx](example/prescription_template.docx)
- 输出目录：[example/prescriptions/](example/prescriptions/)

**使用方式**：
1. 医生端创建处方记录
2. 调用生成接口生成PDF
3. 打印或电子分发给患者

## 注意事项

1. **环境配置**：确保 `.env` 文件中配置了有效的硅基流动API密钥
2. **数据库配置**：修改 [database/db_config.py](database/db_config.py) 中的MySQL密码
3. **依赖安装**：首次运行需要安装所有依赖包
4. **会话管理**：系统使用内存存储会话数据，重启后会丢失
5. **生产部署**：生产环境建议使用Redis等持久化存储方案
6. **PDF生成**：Windows环境下，PDF转换功能需要安装Microsoft Word
7. **用户标识**：建议使用手机号 (phone_number) 作为患者唯一标识，支持多次就诊记录

## 系统架构特点

### 多智能体协作

- **Agent 1 (HealthAgent)**：专注于患者咨询和预约服务
- **Agent 2 (ReportAgent)**：专注于医生端文档生成和分析
- **AgentManager**：负责智能体生命周期管理和会话映射
- **IntentDetector**：自动识别用户意图，智能路由到合适的Agent

### 数据服务架构

采用V2版本的数据服务，支持：
- 基于手机号的多记录查询
- 完整的历史就诊数据加载
- 智能体自动加载用户历史上下文

### 对话状态管理

每个智能体使用Enum定义对话阶段：
- 清晰的状态转换逻辑
- 自动判断对话完成状态
- 支持中断和恢复

## 扩展功能

### 添加新智能体

当前已实现Agent 1（健康咨询）和Agent 2（医疗报告），可通过以下方式添加新智能体：

1. 在 [agents/](agents/) 目录下创建新的智能体类（如 `agent_3.py`）
2. 定义对话阶段枚举（ConversationStage）
3. 实现 `chat()`, `is_completed()` 等核心方法
4. 在 [agents/agent_manager.py](agents/agent_manager.py) 中注册新智能体
5. 在 [utils/intent_detector.py](utils/intent_detector.py) 添加路由规则
6. 如需数据库访问，创建对应的数据服务

### 自定义文档模板

可以自定义医疗报告和处方模板：

1. 修改 [example/bingli_template.docx](example/bingli_template.docx)（医疗报告模板）
2. 修改 [example/prescription_template.docx](example/prescription_template.docx)（处方模板）
3. 在模板中使用占位符（如 `{{patient_name}}`, `{{diagnosis}}` 等）
4. 生成器会自动替换占位符并生成文档

## 开发指南

详细的开发指南请参考 [CLAUDE.md](CLAUDE.md)，包含：
- 常用命令和开发流程
- 架构设计详解
- 数据库设计模式
- Agent开发最佳实践
- API接口规范

## 许可证

MIT License


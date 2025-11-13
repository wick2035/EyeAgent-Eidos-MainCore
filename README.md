# 智能医疗咨询系统

基于Langchain的智能体集群系统，实现眼科健康咨询、智能分诊和医生预约功能。

## 功能特性

### 1号智能体功能
- ✅ **健康信息咨询**：提供专业的眼科健康咨询服务
- ✅ **场景智能判断**：根据症状评估严重程度，主动询问是否需要预约医生
- ✅ **眼科分诊问诊**：系统化收集患者信息，包括症状、病史等
- ✅ **医生预约**：帮助患者完成预约流程
- ✅ **数据导出**：生成标准JSON格式的患者病例数据

## 技术栈

- **后端**：FastAPI + Langchain
- **前端**：HTML5 + CSS3 + JavaScript
- **AI模型**：硅基流动平台 Qwen
- **数据格式**：JSON

## 安装步骤

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

在项目根目录的 `.env` 文件中配置硅基流动API：

```
SILICONFLOW_API_KEY=your_api_key_here
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
```

### 3. 启动服务

```bash
python main.py
```

或使用uvicorn：

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. 访问应用

打开浏览器访问：http://127.0.0.1:8000

## 使用说明

### 对话流程

1. **初次接待**：系统问候并询问健康问题
2. **健康咨询**：描述您的眼部症状
3. **症状评估**：AI评估症状严重程度
4. **预约询问**：系统主动询问是否需要预约医生
5. **信息收集**：收集患者基本信息（姓名、年龄、性别、联系方式）
6. **眼科分诊**：详细了解眼部症状和现病史
7. **病史采集**：收集既往病史、用药史、过敏史等
8. **预约确认**：确认期望就诊时间和紧急程度
9. **完成**：生成完整病例数据

### 功能按钮

- **📄 导出病例**：查看并下载患者病例JSON数据
- **🔄 重新开始**：清空当前对话，开始新的咨询

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

## API接口

### POST /api/chat
发送聊天消息

**请求体**：
```json
{
  "message": "用户消息",
  "session_id": "会话ID（可选）"
}
```

**响应**：
```json
{
  "response": "AI响应",
  "session_id": "会话ID",
  "is_completed": false,
  "stage": "当前阶段"
}
```

### GET /api/export/{session_id}
导出患者病例数据

**响应**：返回JSON格式的患者病例数据

### POST /api/reset/{session_id}
重置会话

### GET /api/session/{session_id}
获取会话信息

### GET /api/stats
获取系统统计信息

## 项目结构

```
pythonProject1/
├── requirements.txt          # Python依赖
├── .env                      # 环境变量配置
├── main.py                   # FastAPI主应用
├── README.md                 # 项目说明文档
├── agents/
│   ├── __init__.py
│   ├── agent_1.py           # 1号智能体核心逻辑
│   └── agent_manager.py     # 智能体管理器
├── utils/
│   ├── __init__.py
│   ├── llm_config.py        # LLM配置
│   └── data_handler.py      # JSON数据处理
├── static/
│   ├── css/
│   │   └── style.css        # 界面样式
│   └── js/
│       └── chat.js          # 聊天交互逻辑
└── templates/
    └── index.html           # 聊天界面
```

## 注意事项

1. 确保 `.env` 文件中配置了有效的硅基流动API密钥
2. 首次运行需要安装所有依赖包
3. 系统使用内存存储会话数据，重启后会丢失
4. 生产环境建议使用Redis等持久化存储方案

## 扩展功能

当前实现了1号智能体（健康咨询、眼科分诊、医生预约），其他智能体可以通过以下方式添加：

1. 在 `agents/` 目录下创建新的智能体类
2. 在 `AgentManager` 中注册新的智能体类型
3. 添加对应的API路由和前端交互逻辑

## 许可证

MIT License


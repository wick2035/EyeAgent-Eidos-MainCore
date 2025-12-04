# 医问通Agent集群设计方案

**版本**: 1.0.0  
**创建日期**: 2025-12-02  
**目标**: 为医生用户打造专业的科研Agent系统

---

## 目录

1. [概述](#概述)
2. [核心架构设计](#核心架构设计)
3. [功能模块设计](#功能模块设计)
4. [建议的额外功能](#建议的额外功能)
5. [完整文件结构](#完整文件结构)
6. [API接口设计](#api接口设计)
7. [安全与权限设计](#安全与权限设计)
8. [系统提示词设计](#系统提示词设计)
9. [实施建议](#实施建议)

---

## 概述

### 设计目标

医问通Agent集群是一个**完全独立**的科研支持系统，专门为医生用户设计，提供以下核心能力：

1. ✅ **继承现有功能**（除报告生成外）
   - 健康咨询工具（预约、查询处方等）
   - 提醒管理工具
   - 患者数据查询工具

2. ✅ **机构数据库科研分析**
   - 可开关的机构数据库访问权限
   - 支持全量数据查询和统计分析
   - 数据脱敏保护

3. ✅ **网页搜索Agent**
   - 医学文献搜索
   - 最新研究动态
   - 临床指南查询

4. ✅ **科研辅助功能**
   - 统计分析
   - 文献处理
   - 论文写作辅助
   - 数据可视化

### 核心特性

- 🔒 **完全独立的API接口**：`/api/research/*`
- 👨‍⚕️ **仅医生用户访问**：强制角色验证
- 🔐 **权限控制**：机构数据库访问开关
- 📊 **科研导向**：专为医学研究设计
- 🛡️ **数据安全**：脱敏、审计、追踪

---

## 核心架构设计

### 1. 新增Agent类型

在 `domain/enums/agent_type.py` 中新增：

```python
class AgentType(str, Enum):
    HEALTH = "health"      # 健康咨询Agent
    REPORT = "report"      # 报告分析Agent
    REMINDER = "reminder"  # 提醒管理Agent
    RESEARCH = "research"  # 医问通科研Agent（新增）
```

### 2. 独立API路由

创建 `presentation/routers/research_router.py`，提供独立的 `/api/research/*` 接口路径。

### 3. 权限控制机制

- ✅ 所有接口强制验证 `role == "doctor"`
- ✅ 验证 `doctor_id` 有效性
- ✅ 机构数据库访问开关（通过配置或API参数控制）
- ✅ 操作审计日志

---

## 功能模块设计

### 模块1：基础功能继承（除报告生成外）

**继承的工具列表**：

```python
# 从现有Agent继承的工具
INHERITED_TOOLS = [
    # Agent 1 工具（预约相关）
    get_patient_prescription,
    get_doctor_free_time,
    reserve_doctor,
    
    # Agent 2 工具（数据查询，排除报告生成）
    get_patient_prescription_limit,
    get_patient_prescription_detail,
    get_patient_scan_data,
    # ❌ 排除：generate_medical_record_pdf
    # ❌ 排除：generate_prescription_pdf
    
    # Agent 3 工具（提醒管理）
    get_patient_reminder,
    get_patient_reminder_config,
    init_patient_reminder_config,
    modify_patient_reminder_config,
    create_reminder,
]
```

### 模块2：机构数据库科研分析工具

#### 工具定义

```python
@tool
def get_institution_research_data(
    doctor_id: str,
    data_type: str,  # "patients", "appointments", "prescriptions", "scans", "all"
    date_range_start: Optional[str] = None,
    date_range_end: Optional[str] = None,
    filters: Optional[Dict] = None,
    enable_anonymization: bool = True  # 数据脱敏开关
) -> str:
    """
    获取机构数据库全部内容进行科研分析
    
    权限要求：
    - 仅医生可调用
    - 需要机构数据库访问权限开关开启
    - 验证doctor_id所属机构
    
    参数说明：
    - data_type: 数据类型
      * "patients": 患者基础信息
      * "appointments": 预约记录
      * "prescriptions": 处方记录
      * "scans": 扫描检查数据
      * "all": 全部数据
    
    - date_range_start/end: 日期范围过滤（格式：yyyy-MM-dd）
    - filters: 自定义过滤条件（JSON格式）
    - enable_anonymization: 是否启用数据脱敏（默认True）
    
    数据脱敏规则：
    - 患者姓名：替换为"患者A"、"患者B"等
    - 手机号：保留前3位和后4位，中间用*替代
    - 身份证号：仅保留前6位和后4位
    - 地址：仅保留到城市级别
    
    返回格式：
    JSON字符串，包含：
    - total_count: 总记录数
    - data: 数据列表
    - metadata: 元数据（字段说明、统计信息等）
    - anonymization_status: 脱敏状态
    """
```

#### 使用场景

- 疾病流行病学研究
- 治疗效果统计分析
- 药物使用模式分析
- 患者队列研究

### 模块3：网页搜索Agent

#### 工具定义

```python
@tool
def web_search_medical_literature(
    query: str,
    max_results: int = 5,
    search_type: str = "general"  # "general", "pubmed", "scholar"
) -> str:
    """
    搜索医学文献和最新研究
    
    支持的搜索类型：
    - "general": 通用网页搜索（Google/Bing）
    - "pubmed": PubMed医学文献数据库
    - "scholar": Google Scholar学术搜索
    
    返回内容：
    - 文献标题
    - 作者信息
    - 发表期刊/会议
    - 摘要
    - 链接地址
    - 引用次数（如可用）
    
    使用场景：
    - 查找最新研究进展
    - 文献综述准备
    - 治疗方案参考
    - 临床指南更新
    """
```

#### 实现建议

- 使用 `langchain.tools.DuckDuckGoSearchRun` 或 `TavilySearchResults` 进行通用搜索
- PubMed API集成（需要API密钥）
- Google Scholar爬虫（注意反爬虫策略）

---

## 额外功能

### 1. 统计分析工具

```python
@tool
def statistical_analysis(
    data: str,  # JSON格式的数据
    analysis_type: str,  # "descriptive", "correlation", "regression", "survival"
    variables: List[str]
) -> str:
    """
    对科研数据进行统计分析
    
    支持的分析类型：
    - "descriptive": 描述性统计
      * 均值、标准差、中位数、四分位数
      * 频数分布
      * 缺失值统计
    
    - "correlation": 相关性分析
      * Pearson相关系数
      * Spearman秩相关
      * 相关性矩阵可视化
    
    - "regression": 回归分析
      * 线性回归
      * 逻辑回归
      * 多因素回归
    
    - "survival": 生存分析
      * Kaplan-Meier曲线
      * Cox回归
      * 生存率计算
    
    返回内容：
    - 统计结果表格
    - 显著性检验结果（P值、置信区间）
    - 可视化图表（可选）
    - 结果解释说明
    """
```

**实现建议**：
- 使用 `pandas` 进行数据处理
- 使用 `scipy` 和 `statsmodels` 进行统计分析
- 使用 `matplotlib` 或 `plotly` 生成图表

### 2. 文献摘要与翻译

```python
@tool
def summarize_medical_literature(
    article_url: str,
    language: str = "zh"  # "zh", "en"
) -> str:
    """
    提取医学文献摘要并翻译
    
    功能：
    - 提取文献关键信息
      * 研究目的
      * 研究方法
      * 主要结果
      * 结论
    
    - 中英文翻译
    - 提取关键数据
      * 样本量
      * P值
      * OR值、RR值、HR值
      * 置信区间
    
    - 生成结构化摘要
      * 背景
      * 方法
      * 结果
      * 结论
    
    返回格式：
    JSON字符串，包含：
    - title: 标题
    - authors: 作者列表
    - abstract: 摘要
    - key_findings: 关键发现
    - statistics: 统计数据
    - translated_content: 翻译内容（如需要）
    """
```

**实现建议**：
- 使用网页爬虫提取文献内容
- 使用LLM进行摘要提取和翻译
- 使用正则表达式提取统计数据

### 3. 研究方案设计助手

```python
@tool
def design_research_protocol(
    research_question: str,
    study_type: str,  # "observational", "interventional", "meta_analysis"
    target_population: str
) -> str:
    """
    辅助设计研究方案
    
    输入：
    - research_question: 研究问题
    - study_type: 研究类型
      * "observational": 观察性研究（队列、病例对照、横断面）
      * "interventional": 干预性研究（RCT、非随机对照试验）
      * "meta_analysis": Meta分析
    
    - target_population: 目标人群描述
    
    输出：
    - 研究设计框架
      * 研究类型建议
      * 研究假设
      * 主要终点和次要终点
    
    - 纳入排除标准建议
      * 纳入标准
      * 排除标准
      * 退出标准
    
    - 样本量计算
      * 基于统计功效的样本量
      * 考虑失访率的调整样本量
      * 分组方案
    
    - 统计方法建议
      * 描述性统计方法
      * 推断性统计方法
      * 缺失数据处理方法
    
    - 伦理考虑
      * 知情同意要求
      * 风险收益评估
    """
```

### 4. 数据可视化生成

```python
@tool
def generate_research_visualization(
    data: str,
    chart_type: str,  # "bar", "line", "scatter", "heatmap", "forest"
    title: str,
    x_label: str,
    y_label: str,
    export_format: str = "png"  # "png", "svg", "html"
) -> str:
    """
    生成科研数据可视化图表
    
    支持的图表类型：
    - "bar": 柱状图（用于分类数据比较）
    - "line": 折线图（用于时间序列数据）
    - "scatter": 散点图（用于相关性分析）
    - "heatmap": 热力图（用于相关性矩阵、数据分布）
    - "forest": 森林图（用于Meta分析）
    - "box": 箱线图（用于数据分布）
    - "survival": 生存曲线（Kaplan-Meier曲线）
    
    导出格式：
    - "png": 静态图片
    - "svg": 矢量图
    - "html": 交互式图表（Plotly）
    
    返回：
    - 图表文件URL或base64编码
    - 图表说明文字
    """
```

**实现建议**：
- 使用 `matplotlib` 生成静态图表
- 使用 `plotly` 生成交互式图表
- 使用 `seaborn` 生成统计图表

### 5. 论文写作助手

```python
@tool
def assist_paper_writing(
    section: str,  # "abstract", "introduction", "methods", "results", "discussion"
    research_data: str,
    template_type: str = "imrad"  # IMRAD格式
) -> str:
    """
    辅助撰写科研论文
    
    支持的章节：
    - "abstract": 摘要
      * 结构化摘要（目的、方法、结果、结论）
      * 关键词提取
    
    - "introduction": 引言
      * 研究背景
      * 文献综述
      * 研究目的和假设
    
    - "methods": 方法
      * 研究设计描述
      * 统计方法描述
      * 伦理声明
    
    - "results": 结果
      * 数据描述
      * 统计结果呈现
      * 图表说明
    
    - "discussion": 讨论
      * 结果解释
      * 与既往研究比较
      * 局限性分析
      * 结论
    
    模板类型：
    - "imrad": 标准IMRAD格式
    - "case_report": 病例报告格式
    - "systematic_review": 系统综述格式
    
    返回：
    - 生成的文本内容
    - 建议的参考文献
    - 格式检查清单
    """
```

### 6. 临床指南查询

```python
@tool
def search_clinical_guidelines(
    disease: str,
    organization: Optional[str] = None  # "WHO", "NICE", "中华医学会"
) -> str:
    """
    查询相关临床指南
    
    支持的指南来源：
    - "WHO": 世界卫生组织指南
    - "NICE": 英国国家健康与临床优化研究所
    - "中华医学会": 中华医学会各专业委员会指南
    - "美国指南": 美国各专业学会指南
    
    返回内容：
    - 指南标题和版本
    - 发布机构
    - 发布日期和更新日期
    - 指南摘要
    - 关键推荐意见
    - 证据等级
    - 指南链接
    """
```

**实现建议**：
- 维护指南数据库或索引
- 使用网页搜索API查找最新指南
- 定期更新指南库

### 7. 药物相互作用检查

```python
@tool
def check_drug_interactions(
    drug_list: List[str],
    patient_conditions: Optional[List[str]] = None
) -> str:
    """
    检查药物相互作用和禁忌症
    
    功能：
    - 药物-药物相互作用
      * 严重相互作用（禁用）
      * 中等相互作用（需谨慎）
      * 轻微相互作用（注意监测）
    
    - 药物-疾病禁忌
      * 特定疾病禁用药物
      * 疾病状态下的剂量调整
    
    - 剂量调整建议
      * 肾功能不全
      * 肝功能不全
      * 老年患者
      * 儿童患者
    
    返回：
    - 相互作用列表（按严重程度排序）
    - 禁忌症警告
    - 剂量调整建议
    - 监测建议
    """
```

**实现建议**：
- 集成药物数据库API（如DrugBank、RxNorm）
- 维护本地药物相互作用数据库
- 使用LLM进行自然语言查询匹配

### 8. 病例相似度匹配

```python
@tool
def find_similar_cases(
    case_description: str,
    max_results: int = 10,
    similarity_threshold: float = 0.7
) -> str:
    """
    在机构数据库中查找相似病例
    
    匹配维度：
    - 主要诊断
    - 症状描述
    - 检查结果
    - 治疗方案
    - 患者特征（年龄、性别等）
    
    用途：
    - 辅助诊断参考
    - 治疗方案参考
    - 预后评估参考
    - 罕见病例发现
    
    返回：
    - 相似病例列表（按相似度排序）
    - 相似度评分
    - 关键匹配点
    - 病例摘要
    """
```

**实现建议**：
- 使用向量数据库（如Milvus、Pinecone）存储病例嵌入
- 使用LLM生成病例向量表示
- 使用余弦相似度或更高级的相似度算法

### 9. 研究伦理审查助手

```python
@tool
def ethics_review_assistant(
    research_protocol: str
) -> str:
    """
    辅助研究伦理审查准备
    
    输出内容：
    - 伦理审查要点检查清单
      * 研究风险评估
      * 知情同意完整性
      * 数据隐私保护
      * 利益冲突声明
    
    - 知情同意书模板
      * 研究目的说明
      * 研究过程描述
      * 风险和收益说明
      * 退出权利说明
    
    - 风险评估报告
      * 风险等级评估
      * 风险缓解措施
      * 应急预案
    
    - 数据管理计划
      * 数据收集和存储
      * 数据访问控制
      * 数据保留和销毁
    """
```

### 10. 数据导出工具

```python
@tool
def export_research_data(
    data: str,
    format: str,  # "excel", "csv", "spss", "json"
    include_metadata: bool = True,
    anonymization: bool = True
) -> str:
    """
    导出科研数据为多种格式
    
    支持的格式：
    - "excel": Excel文件（.xlsx）
      * 多工作表支持
      * 格式化和公式
      * 数据验证
    
    - "csv": CSV文件（.csv）
      * UTF-8编码
      * 逗号分隔
    
    - "spss": SPSS格式（.sav）
      * 变量标签
      * 值标签
      * 缺失值定义
    
    - "json": JSON格式
      * 结构化数据
      * 元数据包含
    
    安全特性：
    - 数据脱敏（默认启用）
    - 访问水印（包含导出时间、医生ID）
    - 导出记录追踪
    - 文件访问权限控制
    
    返回：
    - 文件下载URL
    - 文件大小
    - 导出时间戳
    - 数据摘要
    """
```

---

## 完整文件结构

```
pythonProject1/
├── agents/
│   ├── base/
│   │   └── base_agent.py              # 基础Agent类
│   ├── health/
│   │   └── health_agent.py            # 健康咨询Agent
│   ├── report/
│   │   └── report_agent.py           # 报告分析Agent
│   ├── reminder/
│   │   └── reminder_agent.py         # 提醒管理Agent
│   ├── research/                      # 新增：医问通科研Agent
│   │   ├── __init__.py
│   │   └── research_agent.py         # ResearchAgent类
│   ├── tools/
│   │   ├── agent_tools.py             # 现有工具
│   │   └── research_tools.py         # 新增：科研专用工具
│   └── agent_manager.py               # Agent管理器
│
├── domain/
│   ├── enums/
│   │   ├── agent_type.py             # 新增 RESEARCH 类型
│   │   └── conversation_stage.py
│   └── models/
│       └── ...
│
├── presentation/
│   ├── routers/
│   │   ├── chat_router.py             # 现有聊天路由
│   │   ├── agent_router.py            # 现有Agent路由
│   │   ├── conversation_router.py     # 现有会话路由
│   │   └── research_router.py        # 新增：科研独立路由
│   └── schemas/
│       └── research_schemas.py       # 新增：科研API模型
│
├── infrastructure/
│   ├── api/
│   │   └── backend_client.py         # 后端API客户端
│   └── services/
│       └── research_service.py       # 新增：科研服务层
│
├── application/
│   └── services/
│       └── ...
│
└── main.py                            # 主应用入口
```

---

## API接口设计

### 基础路径

所有科研相关接口使用独立的基础路径：`/api/research/*`

### 接口列表

#### 1. 科研对话接口

```http
POST /api/research/chat
```

**请求体**：
```json
{
  "message": "帮我分析一下我们医院最近一年的糖尿病患者的用药情况",
  "doctor_id": "660e8400-e29b-41d4-a716-446655440001",
  "session_id": "sess-research-123",
  "conversation_id": null,
  "enable_institution_data": true  // 机构数据库访问开关
}
```

**响应**：
```json
{
  "response": "我已经为您分析了...",
  "session_id": "sess-research-123",
  "conversation_id": "770e8400-e29b-41d4-a716-446655440088",
  "is_completed": false,
  "stage": "research_analysis",
  "agent_type": "research",
  "metadata": {
    "doctor_id": "660e8400-e29b-41d4-a716-446655440001",
    "message_count": 2,
    "tools_used": ["get_institution_research_data", "statistical_analysis"]
  }
}
```

#### 2. 科研会话列表

```http
GET /api/research/conversations?doctor_id={uuid}&limit=20&offset=0
```

**响应**：
```json
{
  "conversations": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440088",
      "title": "糖尿病患者用药分析",
      "summary": "分析了2024年糖尿病患者的处方数据",
      "total_messages": 15,
      "create_time": "2025-12-01T10:00:00",
      "update_time": "2025-12-01T11:30:00"
    }
  ],
  "total": 5,
  "has_more": false
}
```

#### 3. 科研数据统计

```http
GET /api/research/stats?doctor_id={uuid}&data_type=patients
```

**响应**：
```json
{
  "total_patients": 1250,
  "total_appointments": 8560,
  "total_prescriptions": 3420,
  "date_range": {
    "start": "2024-01-01",
    "end": "2024-12-31"
  },
  "anonymization_enabled": true
}
```

#### 4. 数据导出

```http
POST /api/research/export
```

**请求体**：
```json
{
  "doctor_id": "660e8400-e29b-41d4-a716-446655440001",
  "data": "{...}",  // JSON格式的数据
  "format": "excel",
  "include_metadata": true,
  "anonymization": true
}
```

**响应**：
```json
{
  "file_url": "https://example.com/exports/research_20251202_123456.xlsx",
  "file_size": 1024000,
  "export_time": "2025-12-02T12:34:56",
  "data_summary": {
    "total_records": 500,
    "fields": ["patient_id", "diagnosis", "medication", ...]
  }
}
```

#### 5. 临床指南查询

```http
GET /api/research/guidelines?disease=糖尿病&organization=中华医学会
```

**响应**：
```json
{
  "guidelines": [
    {
      "title": "中国2型糖尿病防治指南（2020年版）",
      "organization": "中华医学会糖尿病学分会",
      "publish_date": "2021-01-01",
      "update_date": "2021-01-01",
      "summary": "指南摘要...",
      "key_recommendations": ["推荐1", "推荐2", ...],
      "evidence_level": "A",
      "url": "https://..."
    }
  ],
  "total": 3
}
```

#### 6. 统计分析

```http
POST /api/research/analysis
```

**请求体**：
```json
{
  "doctor_id": "660e8400-e29b-41d4-a716-446655440001",
  "data": "{...}",
  "analysis_type": "correlation",
  "variables": ["age", "blood_pressure", "cholesterol"]
}
```

**响应**：
```json
{
  "analysis_results": {
    "correlation_matrix": [[1.0, 0.65, 0.42], ...],
    "p_values": [[null, 0.001, 0.023], ...],
    "significance": "p < 0.05",
    "interpretation": "年龄与血压呈中等正相关..."
  },
  "visualization_url": "https://..."
}
```

---

## 安全与权限设计

### 1. 医生身份验证

#### 验证机制

```python
# 所有接口必须验证
def verify_doctor_access(doctor_id: str) -> bool:
    """
    验证医生身份和权限
    
    检查项：
    1. doctor_id 是否存在于系统中
    2. 用户角色是否为 "doctor"
    3. 医生账户是否激活
    4. 医生所属机构
    5. 机构数据库访问权限
    """
```

#### 实现位置

- 中间件层：`presentation/middleware/doctor_auth_middleware.py`
- 装饰器：`@require_doctor_role`

### 2. 数据访问控制

#### 机构数据库访问开关

**配置方式**（优先级从高到低）：

1. **API参数控制**（会话级别）
   ```json
   {
     "enable_institution_data": true  // 每次请求可控制
   }
   ```

2. **医生级别配置**（数据库存储）
   ```sql
   doctors表：
   - doctor_id
   - institution_data_access_enabled (boolean)
   - access_granted_date
   - access_expiry_date
   ```

3. **机构级别配置**（系统配置）
   ```python
   # config.py
   INSTITUTION_DATA_ACCESS_ENABLED = True  # 全局开关
   ```

#### 数据脱敏规则

```python
ANONYMIZATION_RULES = {
    "patient_name": {
        "method": "replace",
        "pattern": "患者{A-Z}",
        "preserve_length": False
    },
    "phone_number": {
        "method": "mask",
        "keep_prefix": 3,
        "keep_suffix": 4,
        "mask_char": "*"
    },
    "id_number": {
        "method": "mask",
        "keep_prefix": 6,
        "keep_suffix": 4,
        "mask_char": "*"
    },
    "address": {
        "method": "truncate",
        "keep_level": "city"  # 仅保留到城市级别
    }
}
```

#### 访问审计日志

```python
# 记录所有数据访问操作
audit_log = {
    "doctor_id": "660e8400-...",
    "action": "get_institution_research_data",
    "data_type": "patients",
    "record_count": 1250,
    "anonymization_enabled": True,
    "timestamp": "2025-12-02T10:00:00",
    "ip_address": "192.168.1.100",
    "user_agent": "..."
}
```

### 3. 数据导出限制

#### 频率限制

```python
EXPORT_LIMITS = {
    "per_hour": 5,      # 每小时最多5次
    "per_day": 20,      # 每天最多20次
    "per_week": 100,    # 每周最多100次
    "file_size_limit": 100 * 1024 * 1024  # 100MB
}
```

#### 水印标记

```python
# 导出的文件自动添加水印
watermark = {
    "exported_by": "doctor_id",
    "export_time": "2025-12-02T10:00:00",
    "institution": "医院名称",
    "data_range": "2024-01-01 to 2024-12-31",
    "anonymization": True
}
```

#### 导出记录追踪

```python
# 数据库表：export_records
export_record = {
    "id": "uuid",
    "doctor_id": "uuid",
    "file_url": "https://...",
    "file_hash": "sha256...",  # 文件哈希值
    "export_time": "timestamp",
    "data_summary": "json",
    "access_count": 0,
    "last_access_time": "timestamp"
}
```

---

## 系统提示词设计

### ResearchAgent 系统提示词

```python
def _create_system_prompt(self) -> str:
    return """
你是医问通科研助手，专门为医生用户提供科研支持。

## 你的身份
- 专业的医学研究助手
- 严格遵守数据隐私和伦理规范
- 提供准确、可靠的科研支持

## 核心能力

### 1. 机构数据库科研分析
- 可以访问机构数据库进行科研分析（需权限开启）
- 所有数据查询默认启用脱敏保护
- 支持多维度数据查询和统计分析
- 严格遵守数据使用规范

### 2. 医学文献搜索
- 搜索最新医学文献和研究进展
- 支持PubMed、Google Scholar等数据库
- 提取文献关键信息和统计数据
- 提供文献摘要和翻译

### 3. 统计分析辅助
- 描述性统计分析
- 相关性分析、回归分析
- 生存分析
- 结果解释和可视化

### 4. 研究方案设计
- 辅助设计研究方案
- 样本量计算
- 统计方法建议
- 伦理审查准备

### 5. 论文写作辅助
- 辅助撰写论文各章节
- 符合医学期刊格式
- 自动引用相关文献
- 格式检查

## 重要原则

### 数据安全
1. **数据脱敏**：所有患者数据默认脱敏，除非医生明确要求
2. **权限控制**：仅在有权限时访问机构数据库
3. **审计追踪**：所有数据访问都会被记录
4. **最小化原则**：只查询必要的数据

### 科研伦理
1. **知情同意**：提醒医生注意研究伦理要求
2. **数据使用**：确保数据使用符合伦理规范
3. **结果解释**：统计结果需准确解释，避免误导
4. **局限性**：提醒研究设计的局限性

### 学术规范
1. **引用准确**：所有文献引用需准确标注来源
2. **方法透明**：统计方法需清晰说明
3. **结果客观**：客观呈现结果，不夸大结论
4. **格式规范**：符合医学期刊写作规范

## 工具使用规则

1. **机构数据库访问**
   - 仅在 `enable_institution_data=true` 时访问
   - 默认启用数据脱敏
   - 记录所有访问操作

2. **统计分析**
   - 明确说明使用的统计方法
   - 提供P值、置信区间等关键指标
   - 解释结果的临床意义

3. **文献搜索**
   - 优先使用高质量数据库（PubMed等）
   - 标注文献来源和发表时间
   - 提取关键信息时保持准确性

4. **数据导出**
   - 提醒医生注意数据安全
   - 建议启用脱敏
   - 说明数据使用限制

## 对话风格

- 专业、严谨、客观
- 使用医学术语，但解释清晰
- 提供具体建议和操作步骤
- 主动提醒注意事项和伦理要求

## 禁止事项

❌ 生成或修改医疗报告（这是ReportAgent的职责）
❌ 在无权限时访问机构数据库
❌ 提供未脱敏的患者数据（除非明确要求）
❌ 夸大研究结果或误导性解释
❌ 违反数据隐私和伦理规范的操作
"""
```

---

## 实施建议

### 阶段一：基础功能（2-3周）

**目标**：实现核心功能框架

1. ✅ 创建 `ResearchAgent` 类
2. ✅ 实现基础功能继承（排除报告生成）
3. ✅ 实现机构数据库访问工具（基础版本）
4. ✅ 实现网页搜索工具
5. ✅ 创建独立API路由 `/api/research/*`
6. ✅ 实现医生权限验证
7. ✅ 基础数据脱敏功能

**交付物**：
- ResearchAgent类
- 基础工具集
- 独立API接口
- 权限验证机制

### 阶段二：核心科研功能（3-4周）

**目标**：实现核心科研分析能力

1. ✅ 完善机构数据库访问工具
   - 多数据类型支持
   - 高级过滤功能
   - 数据脱敏规则完善

2. ✅ 实现统计分析工具
   - 描述性统计
   - 相关性分析
   - 基础回归分析

3. ✅ 实现文献处理工具
   - 文献摘要提取
   - 关键数据提取
   - 中英文翻译

4. ✅ 实现数据可视化工具
   - 基础图表生成
   - 图表导出功能

**交付物**：
- 完整的科研工具集
- 统计分析能力
- 数据可视化功能

### 阶段三：高级功能（4-5周）

**目标**：实现高级科研辅助功能

1. ✅ 研究方案设计助手
2. ✅ 论文写作助手
3. ✅ 临床指南查询
4. ✅ 病例相似度匹配
5. ✅ 药物相互作用检查
6. ✅ 伦理审查助手

**交付物**：
- 高级科研辅助功能
- 完整的科研工作流支持

### 阶段四：优化与完善（2-3周）

**目标**：性能优化和功能完善

1. ✅ 性能优化
   - 大数据查询优化
   - 搜索结果缓存
   - 异步处理优化

2. ✅ 安全加固
   - 访问审计完善
   - 数据导出安全
   - 权限管理细化

3. ✅ 用户体验优化
   - 错误处理完善
   - 响应速度优化
   - 交互提示优化

4. ✅ 文档和测试
   - API文档完善
   - 单元测试
   - 集成测试

**交付物**：
- 优化后的系统
- 完整文档
- 测试报告

### 技术栈建议

#### 数据处理
- `pandas`: 数据处理和分析
- `numpy`: 数值计算
- `scipy`: 科学计算和统计分析
- `statsmodels`: 统计建模

#### 可视化
- `matplotlib`: 基础图表
- `seaborn`: 统计图表
- `plotly`: 交互式图表

#### 搜索和爬虫
- `langchain.tools.DuckDuckGoSearchRun`: 通用搜索
- `requests` + `BeautifulSoup`: 网页爬取
- `pubmed-api`: PubMed API（如可用）

#### 向量数据库（用于病例匹配）
- `Milvus`: 开源向量数据库
- `Pinecone`: 云向量数据库（可选）

#### 配置管理
- `pydantic-settings`: 配置管理
- 环境变量：敏感配置

### 注意事项

1. **数据隐私**
   - 严格遵守数据保护法规
   - 默认启用数据脱敏
   - 完整的访问审计

2. **性能考虑**
   - 大数据查询使用分页
   - 搜索结果缓存
   - 统计分析异步处理

3. **可扩展性**
   - 工具模块化设计
   - 易于添加新功能
   - 支持插件机制

4. **维护性**
   - 清晰的代码结构
   - 完整的文档
   - 单元测试覆盖

---

## 总结

医问通Agent集群是一个**完全独立**的科研支持系统，为医生用户提供：

✅ **完整的科研工具链**：从数据获取到论文写作  
✅ **严格的安全控制**：权限验证、数据脱敏、访问审计  
✅ **专业的科研支持**：统计分析、文献处理、方案设计  
✅ **良好的用户体验**：独立API、清晰交互、快速响应  

通过分阶段实施，可以逐步构建一个功能完善、安全可靠的医生科研助手系统。

---

**文档版本**: 1.0.0  
**最后更新**: 2025-12-02  
**维护者**: 开发团队


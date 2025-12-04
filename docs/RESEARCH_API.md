# ResearchAgent API 文档

> 医问通科研Agent API 接口文档 v1.0.0

## 基础信息

| 项目 | 值 |
|------|-----|
| 基础路径 | `/api/research` |
| 版本 | 1.0.0 |
| 认证方式 | doctor_id (UUID) |
| 响应格式 | JSON / SSE |

---

## 1. 科研对话（非流式）

### 接口信息

```
POST /api/research/chat
Content-Type: application/json
```

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| message | string | ✅ | 用户消息 |
| doctor_id | string | ✅ | 医生UUID（必须是有效UUID格式） |
| patient_id | string | ❌ | 患者UUID（查询特定患者数据时需要） |
| session_id | string | ❌ | 会话ID（不传则自动生成） |
| conversation_id | string | ❌ | 数据库会话ID（传入可继续历史对话） |
| enable_institution_data | boolean | ❌ | 机构数据库访问开关，默认 `false` |
| enable_web_search | boolean | ❌ | 网页搜索开关，默认 `false` |
| web_search_types | string[] | ❌ | 搜索类型数组，可选值见下表 |

#### web_search_types 可选值

| 值 | 说明 |
|-----|------|
| `general` | 通用网页搜索（Google） |
| `pubmed` | PubMed医学文献数据库 |
| `scholar` | Google Scholar学术搜索 |

**注意**：可多选，如 `["pubmed", "scholar"]`，系统会并行搜索并合并结果。

### 请求示例

```json
{
    "message": "帮我搜索青光眼最新治疗进展",
    "doctor_id": "550e8400-e29b-41d4-a716-446655440000",
    "patient_id": null,
    "enable_institution_data": false,
    "enable_web_search": true,
    "web_search_types": ["pubmed", "scholar"]
}
```

### 响应参数

| 参数 | 类型 | 说明 |
|------|------|------|
| response | string | AI响应内容 |
| session_id | string | 会话ID |
| conversation_id | string | 数据库会话ID |
| is_completed | boolean | 对话是否完成 |
| stage | string | 当前对话阶段 |
| agent_type | string | 固定为 `"research"` |
| metadata | object | 附加元数据 |

### 响应示例

```json
{
    "response": "根据最新的PubMed文献，青光眼治疗进展主要包括以下几个方面...",
    "session_id": "research_a1b2c3d4e5f6",
    "conversation_id": "conv_123456",
    "is_completed": false,
    "stage": "web_search",
    "agent_type": "research",
    "metadata": {
        "doctor_id": "550e8400-e29b-41d4-a716-446655440000",
        "patient_id": null,
        "message_count": 2,
        "enable_institution_data": false,
        "enable_web_search": true,
        "web_search_types": ["pubmed", "scholar"]
    }
}
```

### 错误响应

| HTTP状态码 | 说明 |
|------------|------|
| 400 | 参数错误（如UUID格式无效） |
| 403 | 权限不足（非医生用户） |
| 500 | 服务器内部错误 |

```json
{
    "detail": "doctor_id 必须是有效的UUID格式，收到: \"invalid\""
}
```

---

## 2. 科研对话（SSE流式）

### 接口信息

```
POST /api/research/chat/stream
Content-Type: application/json
Accept: text/event-stream
```

### 请求参数

与 `/api/research/chat` 完全相同。

### 请求示例

```json
{
    "message": "分析眼科门诊近3个月的患者年龄分布",
    "doctor_id": "550e8400-e29b-41d4-a716-446655440000",
    "enable_institution_data": true,
    "enable_web_search": false
}
```

### SSE 事件类型

| event | 说明 | 数据结构 |
|-------|------|---------|
| `start` | 开始处理 | `{session_id, conversation_id, message}` |
| `chunk` | 响应内容块 | `{index, content, is_last}` |
| `tool_call` | 工具调用通知 | `{tool_name, status}` |
| `done` | 处理完成 | `{response, session_id, conversation_id, is_completed, stage, metadata}` |
| `error` | 发生错误 | `{message}` |

### SSE 响应示例

```
data: {"event": "start", "session_id": "research_a1b2c3", "conversation_id": "conv_123", "message": "开始处理..."}

data: {"event": "chunk", "index": 0, "content": "根据最新的研究", "is_last": false}

data: {"event": "chunk", "index": 1, "content": "，青光眼的治疗方法", "is_last": false}

data: {"event": "chunk", "index": 2, "content": "主要包括药物、激光和手术三种。", "is_last": true}

data: {"event": "done", "response": "根据最新的研究，青光眼的治疗方法主要包括药物、激光和手术三种。", "session_id": "research_a1b2c3", "conversation_id": "conv_123", "is_completed": false, "stage": "web_search", "agent_type": "research", "metadata": {"doctor_id": "550e8400-e29b-41d4-a716-446655440000", "message_count": 2}}

```

### 前端 JavaScript 接入示例

```javascript
async function chatWithResearchAgent(message, doctorId, options = {}) {
    const response = await fetch('/api/research/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message: message,
            doctor_id: doctorId,
            enable_web_search: options.enableWebSearch || false,
            web_search_types: options.searchTypes || [],
            enable_institution_data: options.enableInstitutionData || false,
            conversation_id: options.conversationId || null
        })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullResponse = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const data = JSON.parse(line.slice(6));

                switch (data.event) {
                    case 'start':
                        console.log('开始处理:', data.message);
                        break;
                    case 'chunk':
                        fullResponse += data.content;
                        // 更新UI显示
                        updateChatUI(data.content);
                        break;
                    case 'done':
                        console.log('完成:', data);
                        return data;
                    case 'error':
                        console.error('错误:', data.message);
                        throw new Error(data.message);
                }
            }
        }
    }
}

// 使用示例
chatWithResearchAgent(
    '帮我搜索青光眼最新治疗进展',
    '550e8400-e29b-41d4-a716-446655440000',
    {
        enableWebSearch: true,
        searchTypes: ['pubmed', 'scholar']
    }
).then(result => {
    console.log('对话完成:', result.response);
});
```

---

## 3. 获取科研会话列表

### 接口信息

```
GET /api/research/conversations?doctor_id={doctor_id}&limit={limit}&offset={offset}
```

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| doctor_id | string | ✅ | 医生UUID |
| limit | integer | ❌ | 返回数量，1-100，默认20 |
| offset | integer | ❌ | 偏移量，默认0 |

### 请求示例

```
GET /api/research/conversations?doctor_id=550e8400-e29b-41d4-a716-446655440000&limit=10&offset=0
```

### 响应参数

| 参数 | 类型 | 说明 |
|------|------|------|
| conversations | array | 会话列表 |
| conversations[].id | string | 会话ID |
| conversations[].title | string | 会话标题 |
| conversations[].summary | string | 会话摘要 |
| conversations[].total_messages | integer | 消息总数 |
| conversations[].create_time | datetime | 创建时间 |
| conversations[].update_time | datetime | 更新时间 |
| total | integer | 总会话数 |
| has_more | boolean | 是否还有更多 |

### 响应示例

```json
{
    "conversations": [
        {
            "id": "conv_123456",
            "title": "科研对话",
            "summary": "青光眼治疗进展研究",
            "total_messages": 8,
            "create_time": "2025-12-03T10:30:00",
            "update_time": "2025-12-03T11:45:00"
        },
        {
            "id": "conv_789012",
            "title": "科研对话",
            "summary": "患者年龄分布分析",
            "total_messages": 4,
            "create_time": "2025-12-02T14:20:00",
            "update_time": "2025-12-02T14:35:00"
        }
    ],
    "total": 15,
    "has_more": true
}
```

---

## 4. 获取科研会话详情

### 接口信息

```
GET /api/research/conversations/{conversation_id}?doctor_id={doctor_id}
```

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| conversation_id | string | ✅ | 路径参数，会话ID |
| doctor_id | string | ✅ | 查询参数，医生UUID（权限验证） |

### 请求示例

```
GET /api/research/conversations/conv_123456?doctor_id=550e8400-e29b-41d4-a716-446655440000
```

### 响应示例

```json
{
    "conversation": {
        "id": "conv_123456",
        "title": "科研对话",
        "summary": "青光眼治疗进展研究",
        "total_messages": 4,
        "create_time": "2025-12-03T10:30:00",
        "update_time": "2025-12-03T11:45:00"
    },
    "messages": [
        {
            "id": "msg_001",
            "message_order": 1,
            "message_content": "帮我搜索青光眼最新治疗进展",
            "message_type": "user",
            "create_time": "2025-12-03T10:30:00"
        },
        {
            "id": "msg_002",
            "message_order": 2,
            "message_content": "根据最新的PubMed文献，青光眼治疗进展主要包括...",
            "message_type": "assistant",
            "create_time": "2025-12-03T10:30:15"
        }
    ]
}
```

### 错误响应

| HTTP状态码 | 说明 |
|------------|------|
| 403 | 无权访问此会话（非本人会话） |
| 404 | 会话不存在 |

---

## 5. 删除科研会话

### 接口信息

```
DELETE /api/research/conversations/{conversation_id}?doctor_id={doctor_id}
```

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| conversation_id | string | ✅ | 路径参数，会话ID |
| doctor_id | string | ✅ | 查询参数，医生UUID（权限验证） |

### 请求示例

```
DELETE /api/research/conversations/conv_123456?doctor_id=550e8400-e29b-41d4-a716-446655440000
```

### 响应示例

```json
{
    "message": "会话已删除",
    "conversation_id": "conv_123456"
}
```

---

## 6. 健康检查

### 接口信息

```
GET /api/research/health
```

### 响应示例

```json
{
    "status": "healthy",
    "agent_type": "research",
    "version": "1.0.0",
    "features": {
        "institution_data": true,
        "web_search": true,
        "sse_streaming": true,
        "statistical_analysis": false,
        "literature_review": false,
        "research_design": false,
        "paper_writing": false
    },
    "endpoints": [
        "POST /api/research/chat",
        "POST /api/research/chat/stream",
        "GET /api/research/conversations",
        "GET /api/research/conversations/{id}",
        "DELETE /api/research/conversations/{id}",
        "GET /api/research/health"
    ]
}
```

**features 说明**：
- `true` = 功能已实现可用
- `false` = 功能尚未实现（阶段二/三）
- `web_search` 状态取决于 `SEARCH1API_KEY` 是否配置

---

## 使用场景示例

### 场景1：医学文献搜索

```json
{
    "message": "帮我查找近5年关于SMILE手术并发症的临床研究",
    "doctor_id": "550e8400-e29b-41d4-a716-446655440000",
    "enable_web_search": true,
    "web_search_types": ["pubmed", "scholar"]
}
```

### 场景2：机构数据分析

```json
{
    "message": "分析本院近3个月白内障手术患者的年龄分布",
    "doctor_id": "550e8400-e29b-41d4-a716-446655440000",
    "enable_institution_data": true,
    "enable_web_search": false
}
```

### 场景3：特定患者数据查询

```json
{
    "message": "查看这位患者的处方记录",
    "doctor_id": "550e8400-e29b-41d4-a716-446655440000",
    "patient_id": "660e8400-e29b-41d4-a716-446655440001",
    "enable_institution_data": false,
    "enable_web_search": false
}
```

### 场景4：继续历史对话

```json
{
    "message": "继续上次的分析，再加上性别分布",
    "doctor_id": "550e8400-e29b-41d4-a716-446655440000",
    "conversation_id": "conv_123456",
    "enable_institution_data": true
}
```

---

---

# 阶段二功能

## 7. 统计分析工具

ResearchAgent 支持以下统计分析类型：

### 分析类型

| 类型 | 说明 | 适用场景 |
|------|------|---------|
| `descriptive` | 描述性统计 | 均值、标准差、中位数、四分位数 |
| `correlation` | 相关性分析 | Pearson/Spearman相关系数 |
| `ttest` | t检验 | 两组均值比较 |
| `chi_square` | 卡方检验 | 分类变量关联性 |
| `regression` | 线性回归 | 变量间线性关系 |
| `anova` | 方差分析 | 多组均值比较 |
| `survival` | 生存分析 | 生存率、事件时间分析 |

### 使用示例

```json
{
    "message": "请对以下数据进行描述性统计分析",
    "doctor_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

Agent 会调用 `statistical_analysis` 工具，返回统计量、p值等结果。

---

## 8. 数据可视化工具

### 支持的图表类型

| 类型 | 说明 | 数据格式 |
|------|------|---------|
| `bar` | 柱状图 | `{"labels": [], "values": []}` |
| `line` | 折线图 | `{"x": [], "y": []}` |
| `scatter` | 散点图 | `{"x": [], "y": []}` |
| `pie` | 饼图 | `{"labels": [], "values": []}` |
| `boxplot` | 箱线图 | `{"groups": {"A": [], "B": []}}` |
| `histogram` | 直方图 | `{"values": []}` |
| `heatmap` | 热力图 | `{"matrix": [[]], "row_labels": [], "col_labels": []}` |

### 返回格式

```json
{
    "success": true,
    "chart_type": "bar",
    "title": "患者年龄分布",
    "description": "柱状图显示了5个年龄段的分布情况",
    "image_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
    "image_url": "https://minio.example.com/research-files/xxx.png"
}
```

- `image_base64`: 始终返回（可直接在前端显示）
- `image_url`: 仅在 Minio 配置正确时返回

---

## 9. 文献处理工具

### 处理类型

| 类型 | 说明 |
|------|------|
| `summarize` | 生成结构化摘要 |
| `extract_key_findings` | 提取关键发现 |
| `translate` | 翻译（中英互译） |
| `extract_methods` | 提取研究方法 |
| `extract_conclusions` | 提取结论 |

### 使用示例

```json
{
    "message": "请帮我翻译这篇英文摘要并提取关键发现",
    "doctor_id": "550e8400-e29b-41d4-a716-446655440000",
    "enable_web_search": false
}
```

---

## 10. 研究方案设计工具

### 支持的研究类型

| 类型 | 名称 | 证据等级 |
|------|------|---------|
| `rct` | 随机对照试验 | I级 |
| `cohort` | 队列研究 | II级 |
| `case_control` | 病例对照研究 | III级 |
| `cross_sectional` | 横断面研究 | IV级 |
| `case_series` | 病例系列 | V级 |
| `meta_analysis` | 荟萃分析 | I级 |

### 返回内容

- 推荐研究类型及理由
- 研究方案模板（背景、目的、对象、方法、结局指标、统计计划、伦理考虑）
- 样本量估算建议

### 使用示例

```json
{
    "message": "我想研究青光眼手术后眼压控制效果，请帮我设计研究方案",
    "doctor_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 环境配置

### .env 配置项

```bash
# Search1API 配置（网页搜索功能必需）
SEARCH1API_KEY=your_search1api_key_here

# Minio 配置（数据可视化文件存储）
MINIO_ENDPOINT=your_minio_endpoint
MINIO_ACCESS_KEY=your_access_key
MINIO_SECRET_KEY=your_secret_key
MINIO_BUCKET=research-files
```

### 依赖安装

```bash
# 阶段一依赖
pip install aiohttp>=3.9.0

# 阶段二依赖
pip install numpy>=1.24.0
pip install pandas>=2.0.0
pip install scipy>=1.10.0
pip install matplotlib>=3.7.0
pip install minio>=7.0.0
```

---

## 工具列表汇总

### 阶段一工具（2个）

| 工具 | 说明 |
|------|------|
| `get_institution_research_data` | 机构数据库查询 |
| `web_search_medical` | 医学文献搜索 |

### 阶段二工具（4个）

| 工具 | 说明 |
|------|------|
| `statistical_analysis` | 统计分析 |
| `summarize_medical_literature` | 文献处理 |
| `generate_research_visualization` | 数据可视化 |
| `design_research_protocol` | 研究方案设计 |

### 继承工具（11个）

| 工具 | 来源 |
|------|------|
| `get_patient_prescription` | Agent 1 |
| `get_doctor_free_time` | Agent 1 |
| `reserve_doctor` | Agent 1 |
| `get_patient_prescription_limit` | Agent 2 |
| `get_patient_prescription_detail` | Agent 2 |
| `get_patient_scan_data` | Agent 2 |
| `get_patient_reminder` | Agent 3 |
| `get_patient_reminder_config` | Agent 3 |
| `init_patient_reminder_config` | Agent 3 |
| `modify_patient_reminder_config` | Agent 3 |
| `create_reminder` | Agent 3 |

---

# 阶段三功能

## 11. 论文写作助手

协助医生撰写学术论文各章节。

### 支持的章节

| 章节 | 说明 |
|------|------|
| `abstract` | 摘要 |
| `introduction` | 引言 |
| `methods` | 方法 |
| `results` | 结果 |
| `discussion` | 讨论 |

### 模板类型

| 类型 | 说明 |
|------|------|
| `imrad` | 标准医学论文格式 |
| `case_report` | 病例报告 |
| `systematic_review` | 系统综述 |

### 使用示例

```json
{
    "message": "帮我写论文引言部分，研究主题是青光眼微创手术",
    "doctor_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 12. 临床指南查询

查询权威临床指南推荐意见。

### 支持的指南来源

| 来源 | 说明 |
|------|------|
| WHO | 世界卫生组织 |
| NICE | 英国国家卫生与临床优化研究所 |
| 中华医学会 | 中国权威医学指南 |
| ACC/AHA | 美国心脏病学会/心脏协会 |
| ESMO | 欧洲肿瘤内科学会 |

### 返回内容

- 指南标题和发布机构
- 推荐意见列表
- 证据等级（A/B/C/D）
- 推荐强度（强/弱）
- 发布/更新日期

### 使用示例

```json
{
    "message": "查询糖尿病治疗的最新指南推荐",
    "doctor_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 13. 药物相互作用检查

检查多种药物之间的相互作用及药物-疾病禁忌。

### 检查内容

| 类型 | 说明 |
|------|------|
| 药物-药物相互作用 | DDI (Drug-Drug Interaction) |
| 药物-疾病禁忌 | 特定疾病状态下的禁忌 |
| 剂量调整建议 | 根据相互作用的剂量调整 |

### 严重程度分级

| 等级 | 说明 |
|------|------|
| `contraindicated` | 禁忌 |
| `major` | 严重 |
| `moderate` | 中度 |
| `minor` | 轻度 |

### 使用示例

```json
{
    "message": "检查阿司匹林、华法林和布洛芬之间的相互作用",
    "doctor_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 14. 病例相似度匹配

基于诊断、症状、检查结果查找相似病例。

### 匹配维度

| 维度 | 说明 |
|------|------|
| 诊断 | 主要诊断和合并症 |
| 症状 | 主诉和临床表现 |
| 检查结果 | 实验室和影像学检查 |
| 年龄/性别 | 人口学特征 |

### 使用示例

```json
{
    "message": "查找与当前病例相似的历史病例：55岁女性，2型糖尿病合并高血压",
    "doctor_id": "550e8400-e29b-41d4-a716-446655440000",
    "enable_institution_data": true
}
```

**注意**：需开启 `enable_institution_data` 才能查询机构历史病例。

---

## 15. 伦理审查助手

生成科研伦理相关文档。

### 文档类型

| 类型 | 说明 |
|------|------|
| `checklist` | 伦理审查清单 |
| `consent_form` | 知情同意书模板 |
| `risk_assessment` | 风险评估报告 |
| `data_management` | 数据管理计划 |

### 返回内容

- 结构化文档模板
- 关键要点提示
- 合规要求说明

### 使用示例

```json
{
    "message": "为我的临床试验生成知情同意书模板",
    "doctor_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 16. 科研数据导出

导出科研数据为多种格式。

### 支持的格式

| 格式 | 说明 | 用途 |
|------|------|------|
| `excel` | Excel文件 (.xlsx) | 通用数据分析 |
| `csv` | 逗号分隔值 | 跨平台兼容 |
| `spss` | SPSS数据格式 | 专业统计分析 |
| `json` | JSON格式 | 程序化处理 |

### 返回格式

```json
{
    "success": true,
    "format": "excel",
    "filename": "research_data_20251203_143052.xlsx",
    "file_base64": "UEsDBBQAAAAIAA...",
    "file_url": "https://minio.example.com/research-files/xxx.xlsx",
    "record_count": 150,
    "export_time": "2025-12-03T14:30:52",
    "watermark": "医问通科研导出 - 仅供学术研究使用"
}
```

### 使用示例

```json
{
    "message": "将查询结果导出为Excel格式",
    "doctor_id": "550e8400-e29b-41d4-a716-446655440000",
    "enable_institution_data": true
}
```

---

## 工具列表汇总（更新）

### 阶段一工具（2个）

| 工具 | 说明 |
|------|------|
| `get_institution_research_data` | 机构数据库查询 |
| `web_search_medical` | 医学文献搜索 |

### 阶段二工具（4个）

| 工具 | 说明 |
|------|------|
| `statistical_analysis` | 统计分析 |
| `summarize_medical_literature` | 文献处理 |
| `generate_research_visualization` | 数据可视化 |
| `design_research_protocol` | 研究方案设计 |

### 阶段三工具（6个）

| 工具 | 说明 |
|------|------|
| `assist_paper_writing` | 论文写作助手 |
| `search_clinical_guidelines` | 临床指南查询 |
| `check_drug_interactions` | 药物相互作用检查 |
| `find_similar_cases` | 病例相似度匹配 |
| `ethics_review_assistant` | 伦理审查助手 |
| `export_research_data` | 科研数据导出 |

### 继承工具（11个）

| 工具 | 来源 |
|------|------|
| `get_patient_prescription` | Agent 1 |
| `get_doctor_free_time` | Agent 1 |
| `reserve_doctor` | Agent 1 |
| `get_patient_prescription_limit` | Agent 2 |
| `get_patient_prescription_detail` | Agent 2 |
| `get_patient_scan_data` | Agent 2 |
| `get_patient_reminder` | Agent 3 |
| `get_patient_reminder_config` | Agent 3 |
| `init_patient_reminder_config` | Agent 3 |
| `modify_patient_reminder_config` | Agent 3 |
| `create_reminder` | Agent 3 |

### 总工具数量

| 分类 | 数量 |
|------|------|
| 阶段一 | 2 |
| 阶段二 | 4 |
| 阶段三 | 6 |
| 继承工具 | 11 |
| **总计** | **23** |

---

## 注意事项

1. **权限控制**：所有接口仅限医生用户访问，需提供有效的 `doctor_id`
2. **UUID格式**：`doctor_id` 和 `patient_id` 必须是有效的UUID格式
3. **功能开关**：`enable_institution_data` 和 `enable_web_search` 默认关闭，需显式开启
4. **数据脱敏**：机构数据库返回的患者数据已经过后端脱敏处理
5. **会话持久化**：对话自动保存到数据库，可通过 `conversation_id` 继续历史对话
6. **SSE连接**：流式接口需保持长连接，注意设置适当的超时时间
7. **阶段三工具**：部分工具返回模板和指导，需由 Agent 配合完成最终内容生成

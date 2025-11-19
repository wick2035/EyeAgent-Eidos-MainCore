# 生物力学报告生成模块

## 概述

这是一个集成到 agent3 的生物力学报告生成模块，可以自动从数据库读取眼科检查数据并生成专业的 Word 报告。

## 功能特性

- **双模板支持**：支持基础报告和详细报告两种模板
- **自动数据填充**：从数据库自动读取患者检查数据
- **智能占位符替换**：处理 Word 文档中被分散的占位符
- **完整性验证**：生成后自动验证是否有未替换的占位符

## 文件结构

```
example/TemplateScan/
├── template/
│   ├── aidocx1.docx          # 基础报告模板
│   └── aidocx2.docx          # 详细报告模板
├── reports/                   # 生成的报告输出目录
├── main1.py                   # 基础报告生成示例
├── main2.py                   # 详细报告生成示例
└── README.md                  # 本文档
```

## 核心组件

### 1. BiomechanicsReportGenerator (utils/biomechanics_report_generator.py)

报告生成器，负责：
- 加载 Word 模板
- 替换占位符
- 生成报告文件
- 验证替换结果

**主要方法：**

```python
from utils.biomechanics_report_generator import BiomechanicsReportGenerator

generator = BiomechanicsReportGenerator()

# 生成基础报告
result = generator.generate_basic_report(data_dict)

# 生成详细报告
result = generator.generate_detailed_report(data_dict)
```

### 2. BiomechanicsService (database/biomechanics_service.py)

数据库服务，负责：
- 从数据库读取检查数据
- 格式化数据为模板占位符格式
- 管理检查记录的 CRUD 操作

**主要方法：**

```python
from database.biomechanics_service import BiomechanicsService

service = BiomechanicsService()

# 获取最新检查数据
scan_data = service.get_latest_scan_by_phone(phone_number)

# 格式化为报告模板数据
template_data = service.format_scan_for_report(scan_data, 'basic')
```

### 3. ReminderAgent 集成 (agents/agent_3.py)

agent3 现在支持生物力学报告生成功能。

## 使用方法

### 方式1: 通过 agent3 对话生成

```python
from agents.agent_3 import ReminderAgent

# 创建 agent（需要医生角色）
agent = ReminderAgent(phone_number="13800000000", role="doctor")

# 对话生成报告
response, completed = agent.chat("生成生物力学报告")
# Agent 会引导选择报告类型（基础/详细）

response, completed = agent.chat("基础报告")
# Agent 会自动从数据库获取数据并生成报告
```

### 方式2: 直接调用生成器

```python
from utils.biomechanics_report_generator import BiomechanicsReportGenerator

generator = BiomechanicsReportGenerator()

# 准备数据（占位符格式）
data = {
    '[Name]': '张三',
    '[Gender]': '男',
    '[ScanTime]': '2025-11-18',
    # ... 其他字段
}

# 生成报告
result = generator.generate_basic_report(data)

if result['success']:
    print(f"报告已生成: {result['output_path']}")
else:
    print(f"生成失败: {result['message']}")
```

### 方式3: 使用数据库服务

```python
from database.biomechanics_service import BiomechanicsService
from utils.biomechanics_report_generator import BiomechanicsReportGenerator

service = BiomechanicsService()
generator = BiomechanicsReportGenerator()

# 1. 从数据库获取数据
scan_data = service.get_latest_scan_by_phone("13800000000")

# 2. 格式化为模板格式
template_data = service.format_scan_for_report(scan_data, 'basic')

# 3. 生成报告
result = generator.generate_basic_report(template_data)
```

## 模板占位符说明

### 基础报告 (aidocx1.docx)

包含 36 个占位符：

**基本信息**
- `[Name]` - 姓名
- `[Gender]` - 性别
- `[ScanTime]` - 检查时间
- `[ID]` - 患者ID
- `[BirthDay]` - 出生日期
- `[Operator]` - 操作员

**眼科测量数据**
- `[AXL-R/L]` - 眼轴长度（右/左眼）
- `[CCT-R/L]` - 角膜中央厚度
- `[ACD-R/L]` - 前房深度
- `[LT-R/L]` - 晶状体厚度
- `[K1-D-R/L]`, `[K1-mm-R/L]`, `[K1-DEG-R/L]` - K1 角膜曲率
- `[K2-D-R/L]`, `[K2-mm-R/L]`, `[K2-DEG-R/L]` - K2 角膜曲率
- `[DK-R/L]`, `[DK-DEG-R/L]` - 散光
- `[WTW-R/L]` - 角膜直径
- `[PD-R/L]` - 瞳孔直径

### 详细报告 (aidocx2.docx)

包含 126 个占位符，在基础报告基础上增加：

**多区域角膜分析**
- `[Ac-T1]` 到 `[Ac-T8]` - 8个区域的角膜厚度
- `[P-T1]` 到 `[P-T8]` - 8个区域的角膜屈光力

**生物力学参数矩阵**
- `[I1-T1]` 到 `[I5-T8]` - 5x8 矩阵的 I 参数
- `[R1-T1]` 到 `[R5-T8]` - 5x8 矩阵的 R 参数

## 数据库表结构

需要创建 `biomechanics_scan` 表来存储检查数据：

```sql
CREATE TABLE biomechanics_scan (
    Scan_ID INT PRIMARY KEY AUTO_INCREMENT,
    Patient_ID INT NOT NULL,
    Patient_Name VARCHAR(100),
    Gender VARCHAR(10),
    Birth_Date DATE,
    Age INT,
    Scan_Date DATETIME NOT NULL,
    Operator VARCHAR(100),

    -- 基础测量数据
    AXL_R DECIMAL(5,2),
    AXL_L DECIMAL(5,2),
    CCT_R DECIMAL(5,1),
    CCT_L DECIMAL(5,1),
    ACD_R DECIMAL(4,2),
    ACD_L DECIMAL(4,2),
    LT_R DECIMAL(4,2),
    LT_L DECIMAL(4,2),
    VT_R DECIMAL(5,2),
    VT_L DECIMAL(5,2),

    -- 角膜曲率
    K1_D_R DECIMAL(5,2),
    K1_mm_R DECIMAL(5,2),
    K1_Axis_R INT,
    K1_D_L DECIMAL(5,2),
    K1_mm_L DECIMAL(5,2),
    K1_Axis_L INT,
    K2_D_R DECIMAL(5,2),
    K2_mm_R DECIMAL(5,2),
    K2_Axis_R INT,
    K2_D_L DECIMAL(5,2),
    K2_mm_L DECIMAL(5,2),
    K2_Axis_L INT,

    -- 其他参数
    Astigmatism_R DECIMAL(5,2),
    Astigmatism_L DECIMAL(5,2),
    WTW_R DECIMAL(5,2),
    WTW_L DECIMAL(5,2),
    Pupil_Diameter_R DECIMAL(4,2),
    Pupil_Diameter_L DECIMAL(4,2),
    TR_R DECIMAL(5,2),
    TR_L DECIMAL(5,2),

    -- 详细报告需要的额外字段
    -- Ac_T1 到 Ac_T8, P_T1 到 P_T8
    -- I1_T1 到 I5_T8, R1_T1 到 R5_T8

    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (Patient_ID) REFERENCES patient(Patient_ID)
);
```

## 测试

运行集成测试：

```bash
python test_biomechanics_integration.py
```

测试包括：
1. 数据库服务数据格式化
2. 基础报告生成
3. 详细报告生成

## 注意事项

1. **权限控制**：只有医生角色 (`role="doctor"`) 可以生成报告
2. **数据验证**：生成前会检查是否存在检查数据
3. **占位符处理**：使用改进的算法处理被 Word 分散的占位符
4. **输出路径**：报告默认保存在 `example/TemplateScan/reports/` 目录
5. **文件命名**：自动生成带时间戳的文件名，格式为 `biomechanics_{type}_{name}_{timestamp}.docx`

## API 调用示例

### 从 main.py 调用

```python
from agents.agent_3 import ReminderAgent

@app.post("/api/biomechanics/generate")
async def generate_biomechanics_report(request: dict):
    """生成生物力学报告 API"""
    phone_number = request.get('phone_number')
    report_type = request.get('report_type', 'basic')  # 'basic' 或 'detailed'

    # 创建 agent（医生角色）
    agent = ReminderAgent(phone_number=phone_number, role="doctor")

    # 获取数据并生成报告
    from database.biomechanics_service import BiomechanicsService

    service = BiomechanicsService()
    scan_data = service.get_latest_scan_by_phone(phone_number)

    if not scan_data:
        return {"success": False, "message": "未找到检查数据"}

    # 格式化并生成
    template_data = service.format_scan_for_report(scan_data, report_type)

    if report_type == 'basic':
        result = agent.generate_basic_biomechanics_report(template_data)
    else:
        result = agent.generate_detailed_biomechanics_report(template_data)

    return result
```

## 更新日志

- **2025-11-18**: 初始版本，集成到 agent3
  - 实现基础报告和详细报告生成
  - 创建数据库服务层
  - 完成 agent3 集成
  - 通过所有测试

## 开发者

- 集成人：Claude Code
- 基于模板：main1.py, main2.py
- 版本：1.0.0

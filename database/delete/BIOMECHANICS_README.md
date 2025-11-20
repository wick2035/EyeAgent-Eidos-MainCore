# 生物力学检查数据库功能说明

## 概述

生物力学检查模块用于存储和管理眼科生物力学测量数据,支持生成基础和详细两种类型的报告。

## 数据库表结构

### biomechanics_scan 表

**核心字段:**
- `Scan_ID`: 扫描ID(主键)
- `Patient_ID`: 患者ID(外键,关联patient表)
- `Medical_Record_ID`: 病例ID(外键,关联medical_record表,可选)
- `Scan_Date`: 扫描日期
- `Operator`: 操作员/检查医生

**基础测量字段:**
- 眼轴相关: `AXL_R`, `AXL_L` (右眼/左眼眼轴长度)
- 角膜厚度: `CCT_R`, `CCT_L` (右眼/左眼中央角膜厚度)
- 前房深度: `ACD_R`, `ACD_L`
- 晶状体厚度: `LT_R`, `LT_L`
- 玻璃体深度: `VT_R`, `VT_L`
- 角膜曲率K1: `K1_D_R`, `K1_mm_R`, `K1_Axis_R` (右眼), `K1_D_L`, `K1_mm_L`, `K1_Axis_L` (左眼)
- 角膜曲率K2: `K2_D_R`, `K2_mm_R`, `K2_Axis_R` (右眼), `K2_D_L`, `K2_mm_L`, `K2_Axis_L` (左眼)
- 散光: `Astigmatism_R`, `Astigmatism_L`
- 角膜直径: `WTW_R`, `WTW_L`
- 瞳孔直径: `Pupil_Diameter_R`, `Pupil_Diameter_L`

**详细报告字段:**
- 多区域角膜厚度: `Ac_T1` 到 `Ac_T8` (8个区域)
- 角膜屈光力: `P_T1` 到 `P_T8` (8个区域)
- 生物力学参数I系列: `I1_T1` 到 `I5_T8` (5行×8列,共40个字段)
- 生物力学参数R系列: `R1_T1` 到 `R5_T8` (5行×8列,共40个字段)

**状态和审核字段:**
- `Report_Status`: 报告状态(待生成/已生成/已归档)
- `Report_Type`: 报告类型(basic/detailed)
- `Report_Path`: 生成的报告文件路径
- `Reviewed_By`: 审核医生
- `Reviewed_At`: 审核时间

## 使用步骤

### 1. 初始化数据库表

运行完整的数据库初始化脚本(包含生物力学表):

```bash
# 方法1: 使用MySQL命令行
mysql -u root -p medical_db < database/init_database_v2.sql

# 方法2: 使用Python执行脚本
python database/execute_init_v2.py
```

或者单独创建生物力学表:

```bash
# 单独创建生物力学表
mysql -u root -p medical_db < database/biomechanics_table.sql

# 或使用Python脚本
python database/execute_biomechanics_init.py
```

### 2. 使用BiomechanicsService服务

```python
from database.biomechanics_service import BiomechanicsService

service = BiomechanicsService()

# 查询患者最新的扫描数据
scan_data = service.get_latest_scan_by_patient(patient_id=1)

# 通过手机号查询
scan_data = service.get_latest_scan_by_phone(phone_number="13900000001")

# 查询患者所有扫描记录
all_scans = service.get_all_scans_by_patient(patient_id=1, limit=10)

# 创建新的扫描记录
new_scan = {
    'Patient_ID': 1,
    'Scan_Date': '2025-11-18',
    'Operator': '张医生',
    'AXL_R': 24.89,
    'AXL_L': 24.73,
    'CCT_R': 540.1,
    'CCT_L': 542.2,
    # ... 其他字段
}
result = service.create_scan_record(new_scan)

# 更新扫描记录
update_data = {
    'Report_Status': '已生成',
    'Report_Path': 'example/TemplateScan/reports/report.docx'
}
result = service.update_scan_record(scan_id=1, update_data=update_data)
```

### 3. 生成报告

```python
from utils.biomechanics_report_generator import BiomechanicsReportGenerator
from database.biomechanics_service import BiomechanicsService

# 初始化
service = BiomechanicsService()
generator = BiomechanicsReportGenerator()

# 从数据库获取扫描数据
scan_data = service.get_latest_scan_by_patient(patient_id=1)

# 格式化为模板数据
template_data = service.format_scan_for_report(scan_data, 'basic')

# 生成基础报告
result = generator.generate_basic_report(template_data)
if result['success']:
    print(f"报告生成成功: {result['output_path']}")

# 或生成详细报告
template_data = service.format_scan_for_report(scan_data, 'detailed')
result = generator.generate_detailed_report(template_data)
```

### 4. 测试

运行集成测试:

```bash
python test_biomechanics_integration.py
```

测试包括:
- 查询扫描记录
- 服务数据格式化
- 基础报告生成
- 详细报告生成
- 数据库集成测试

## 演示数据

数据库初始化脚本会自动插入4条演示数据:

1. **张三 (Patient_ID=1)** - 两次检查记录
   - 2025-11-10: 基础检查
   - 2025-11-15: 复查数据

2. **李四 (Patient_ID=2)** - 详细检查
   - 2025-11-12: 包含完整的多区域和生物力学参数数据

3. **王五 (Patient_ID=3)** - 术前检查
   - 2025-11-18: 基础检查数据,待生成报告

## 数据库关系

```
patient (患者表)
  ├── biomechanics_scan (生物力学扫描表)
  │   └── medical_record (病例表,可选关联)
```

- 一个患者可以有多条生物力学检查记录
- 每条检查记录可以选择性关联到某次就诊的病例
- 支持独立的生物力学检查(不关联病例)

## 文件结构

```
database/
├── init_database_v2.sql              # 完整数据库初始化(包含生物力学表)
├── biomechanics_table.sql            # 生物力学表单独创建脚本
├── biomechanics_service.py           # 生物力学数据服务
├── execute_biomechanics_init.py      # 执行生物力学表初始化
└── BIOMECHANICS_README.md            # 本文档

utils/
└── biomechanics_report_generator.py  # 生物力学报告生成器

example/TemplateScan/
├── template/
│   ├── aidocx1.docx                  # 基础报告模板
│   └── aidocx2.docx                  # 详细报告模板
└── reports/                          # 报告输出目录

test_biomechanics_integration.py      # 集成测试脚本
```

## 注意事项

1. **数据精度**:
   - 眼轴长度等使用DECIMAL(5,2),支持如24.89mm
   - 角膜厚度使用DECIMAL(5,1),支持如540.1μm
   - 生物力学参数使用DECIMAL(6,2),支持更大范围

2. **必需字段**:
   - `Patient_ID`: 必须存在于patient表
   - `Scan_Date`: 扫描日期必填
   - `Operator`: 操作员必填

3. **报告模板**:
   - 基础报告(aidocx1.docx): 需要35个基础字段
   - 详细报告(aidocx2.docx): 需要约100+字段(包括矩阵数据)

4. **字段映射**:
   - 基础模板使用-R/-L后缀(如AXL-R)
   - 详细模板使用-OD/-OS后缀(如AXL-OD,代表右眼OD=Oculus Dexter)

## API端点建议

可以添加以下API端点到main.py:

```python
# 查询扫描记录
@app.get("/api/biomechanics/scan/{patient_id}")
def get_scans(patient_id: int)

# 创建扫描记录
@app.post("/api/biomechanics/scan")
def create_scan(scan_data: dict)

# 生成报告
@app.post("/api/biomechanics/report/{scan_id}")
def generate_report(scan_id: int, report_type: str)
```

## PDF 生成功能

### 概述

从 2025-11-18 开始，生物力学报告生成器支持自动生成 PDF 格式的报告文件。

### 功能特性

- ✅ 自动将生成的 `.docx` 文件转换为 `.pdf` 格式
- ✅ 支持 Windows 环境（使用 `docx2pdf`）
- ✅ 支持跨平台（使用 `pypandoc` 作为备选方案）
- ✅ 同时保留 `.docx` 和 `.pdf` 文件
- ✅ 优先返回 PDF 路径，转换失败时 fallback 到 DOCX

### 依赖安装

```bash
# Windows 环境（推荐 - 需要安装 Microsoft Word）
pip install docx2pdf

# 跨平台备选方案
pip install pypandoc
# 还需要安装 pandoc: https://pandoc.org/installing.html
```

### 使用示例

```python
from utils.biomechanics_report_generator import BiomechanicsReportGenerator
from database.biomechanics_service import BiomechanicsService

# 初始化
service = BiomechanicsService()
generator = BiomechanicsReportGenerator()

# 从数据库获取扫描数据
scan_data = service.get_latest_scan_by_patient(patient_id=1)

# 格式化为模板数据
template_data = service.format_scan_for_report(scan_data, 'basic')

# 生成报告（自动生成 DOCX 和 PDF）
result = generator.generate_basic_report(template_data)

if result['success']:
    print(f"DOCX文件: {result['docx_path']}")
    print(f"PDF文件: {result['pdf_path']}")
    print(f"主要输出: {result['output_path']}")  # 优先返回PDF
```

### 返回值结构

```python
{
    'success': True,                           # 是否成功
    'docx_path': 'path/to/file.docx',         # Word 文档路径
    'pdf_path': 'path/to/file.pdf',           # PDF 文档路径（可能为 None）
    'output_path': 'path/to/file.pdf',        # 优先返回 PDF，否则返回 DOCX
    'replacement_count': 36,                   # 成功替换的占位符数量
    'remaining_placeholders': [],              # 未替换的占位符列表
    'message': '[OK] 基础报告生成成功！...'   # 详细消息
}
```

### 输出文件

生成的报告会同时包含 `.docx` 和 `.pdf` 两种格式：

```
example/TemplateScan/reports/
├── biomechanics_basic_张三_20251118_212000.docx    (30KB)
├── biomechanics_basic_张三_20251118_212000.pdf     (137KB)
├── biomechanics_detailed_张三_20251118_212017.docx (31KB)
└── biomechanics_detailed_张三_20251118_212017.pdf  (184KB)
```

### PDF 转换失败处理

如果 PDF 转换失败：

1. 系统会记录警告日志但不会中断流程
2. 返回值中 `pdf_path` 将为 `None`
3. `output_path` 会 fallback 到 `docx_path`
4. `message` 中会包含 `[WARN] PDF转换失败，仅生成docx文件`

你可以：
- 检查是否安装了 `docx2pdf` 或 `pypandoc`
- 手动打开 `.docx` 文件另存为 PDF
- 查看日志了解具体错误原因

### 日志输出示例

```
INFO:utils.biomechanics_report_generator:生成docx文件: example/TemplateScan/reports\biomechanics_basic_张三_20251118_212000.docx
INFO:utils.biomechanics_report_generator:使用docx2pdf转换成功: example/TemplateScan/reports\biomechanics_basic_张三_20251118_212000.pdf
```

## 更新日志

- **2025-11-18**:
  - 创建生物力学检查表，添加演示数据，集成到init_database_v2.sql
  - **新增**：PDF 自动生成功能
    - 支持 `docx2pdf`（Windows 环境）
    - 支持 `pypandoc`（跨平台备选）
    - 优化返回值结构，同时返回 `docx_path` 和 `pdf_path`
    - 添加详细的日志输出
    - 测试验证：基础报告和详细报告均可成功生成 PDF

# 处方单生成功能使用说明

## 功能概述

为医生端（agent_2）新增了完整的处方单PDF生成功能，支持：
- 从数据库读取处方主表和详情表数据
- 自动生成处方编号条形码
- 使用Word模板填充数据生成A4格式处方单
- 转换为PDF格式
- 集成到agent_2对话系统和REST API

## 文件结构

```
pythonProject1/
├── database/
│   └── prescription_service.py          # 处方数据库服务
├── utils/
│   └── prescription_generator.py        # 处方PDF生成器
├── agents/
│   └── agent_2.py                       # 已集成处方生成功能
├── example/
│   ├── prescription_template.docx       # Word模板
│   ├── logo@1x.png                      # Logo图片
│   └── prescriptions/                   # 生成的处方单输出目录
├── main.py                              # 已添加处方API接口
├── test_prescription_fix.py             # 测试脚本
└── requirements.txt                     # 已添加依赖
```

## 使用方法

### 1. 通过Agent对话生成（医生端）

```python
from agents.agent_2 import ReportAgent

# 创建医生角色的agent
agent = ReportAgent(
    phone_number="13900000001",
    role="doctor"  # 重要：必须是doctor角色
)

# 对话生成处方单
response, is_completed = agent.chat("请生成处方ID为1的处方单")
print(response)
```

**支持的命令示例：**
- "生成处方单 ID:1"
- "打印处方 1"
- "导出最新处方"

### 2. 通过API接口调用

#### 生成处方单

```bash
POST /api/prescription/generate
Content-Type: application/json

{
  "prescription_id": 1,
  "patient_id": 1,     # 可选，用于验证权限
  "phone_number": ""   # 可选，用于验证权限
}
```

**响应示例：**
```json
{
  "success": true,
  "message": "处方单生成成功",
  "file_path": "D:/Agent/pythonProject1/example/prescriptions/prescription_1_RX20251117001.pdf",
  "prescription_id": 1
}
```

#### 获取患者处方列表

```bash
GET /api/prescription/list/{patient_id}?limit=50
```

**或通过手机号查询：**
```bash
GET /api/prescription/list/phone/{phone_number}?limit=50
```

**响应示例：**
```json
{
  "success": true,
  "patient_id": 1,
  "count": 1,
  "prescriptions": [
    {
      "prescription_id": 1,
      "prescription_number": "RX20251117001",
      "prescription_date": "2025-11-17 18:06:59",
      "prescription_type": "普通",
      "diagnosis": "干眼症",
      "status": "待审核",
      "total_amount": 102.0,
      "prescriber_name": "李医生",
      "doctor_name": "李医生",
      "doctor_title": "主治医师"
    }
  ]
}
```

#### 获取处方详情

```bash
GET /api/prescription/detail/{prescription_id}
```

**响应示例：**
```json
{
  "success": true,
  "prescription": {
    "prescription_info": {
      "prescription_id": 1,
      "prescription_number": "RX20251117001",
      "total_amount": 102.0,
      ...
    },
    "patient_info": {
      "patient_id": 1,
      "name": "张三",
      "gender": "男",
      "age": 36,
      ...
    },
    "drug_details": [
      {
        "index": 1,
        "drug_name": "玻璃酸钠滴眼液",
        "specification": "10ml:5mg",
        "quantity": 2,
        "unit": "盒",
        ...
      }
    ]
  }
}
```

### 3. 直接使用生成器类

```python
from utils.prescription_generator import PrescriptionGenerator

# 创建生成器
generator = PrescriptionGenerator()

# 从数据库生成处方单
pdf_path = generator.generate_prescription_from_db(prescription_id=1)

if pdf_path:
    print(f"处方单生成成功: {pdf_path}")
```

## 处方单格式说明

生成的处方单包含以下内容：

1. **顶部区域**
   - 左上角：EYEagent Logo
   - 中央：标题"EA 中国视光中心 - 处方笺"
   - 右侧：处方编号条形码

2. **患者信息区**
   - 费别、医保卡号
   - 患者姓名、性别、年龄
   - 患者ID、联系电话
   - 就诊时间、就诊科室

3. **处方内容（RP:）**
   - 药物序号
   - 药物名称、规格、数量
   - 用法用量、频率、疗程
   - 超量原因/慢性病标记

4. **底部信息**
   - 医生签名、药品金额
   - 调配人、核发人
   - 打印时间

5. **注意事项**
   - 处方当日有效
   - 大病、特检通道结算者到门诊缴费
   - 自助缴费处无需到窗口盖收费章

## 权限控制

- **医生角色**：可以生成处方单、查看处方信息
- **患者角色**：只能查看自己的处方信息，不能生成处方单

```python
# 患者尝试生成处方单会被拒绝
agent = ReportAgent(phone_number="13900000001", role="patient")
response, _ = agent.chat("生成处方单")
# 返回：❌ 抱歉，只有医生才能生成处方单...
```

## 技术要点

### 条形码生成
- 使用 `python-barcode` 库生成 Code128 格式条形码
- 条形码图片临时保存后插入Word文档
- 生成完成后自动清理临时文件

### Word模板填充
- 使用 `python-docx` 处理Word文档
- 支持占位符替换（如 `{{patient_name}}`）
- 动态填充药物明细表格（支持任意数量药物）

### PDF转换
- Windows环境优先使用 `docx2pdf`（需要Microsoft Word）
- 跨平台备选方案：`pypandoc`
- 如果转换失败，返回docx文件路径

## 测试验证

运行测试脚本验证功能：

```bash
python test_prescription_fix.py
```

测试包括：
1. 数据库查询功能测试
2. 处方单PDF生成测试
3. 患者处方列表查询测试

## 依赖库

已添加到 `requirements.txt`：
- `python-barcode==0.15.1` - 条形码生成
- `Pillow>=10.0.0` - 图像处理（条形码所需）

安装依赖：
```bash
pip install -r requirements.txt
```

## 输出示例

生成的处方单文件位于：
```
example/prescriptions/prescription_{id}_{number}.pdf
```

例如：
```
example/prescriptions/prescription_1_RX20251117001.pdf
```

## 注意事项

1. **数据库要求**
   - 需要处方主表 `prescription` 和详情表 `prescription_detail` 存在
   - 需要关联的 `patient`、`doctor`、`medical_record` 表数据完整

2. **Word模板**
   - 模板文件：`example/prescription_template.docx`
   - 包含占位符和表格结构
   - 可根据需要自定义样式

3. **Logo图片**
   - 位置：`example/logo@1x.png`
   - 建议尺寸：适合处方单左上角显示
   - 支持PNG格式

4. **PDF转换**
   - Windows环境需要安装Microsoft Word
   - 如果转换失败，会返回docx文件路径
   - 可手动使用Word或其他工具转换为PDF

## 故障排查

### 处方单生成失败
1. 检查数据库中是否存在对应的处方记录
2. 验证处方详情表中是否有药物明细
3. 确认Word模板文件是否存在

### PDF转换失败
1. Windows环境：确认已安装Microsoft Word
2. 检查 `docx2pdf` 库是否正确安装
3. 如果使用 `pypandoc`，需要先安装 Pandoc

### 条形码不显示
1. 确认 `python-barcode` 和 `Pillow` 已安装
2. 检查临时目录是否有写入权限
3. 验证处方编号格式是否正确

## 开发者信息

- 创建日期：2025-11-17
- 集成位置：`agents/agent_2.py`（医生端）
- API路由：`/api/prescription/*`
- 数据库服务：`database/prescription_service.py`
- 生成器：`utils/prescription_generator.py`



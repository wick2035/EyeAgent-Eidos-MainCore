# Word模板使用指南

## ✅ 已完成的工作

1. **创建了新的Word模板** (`example/bingli.docx`)
2. **备份了旧模板** (`example/bingli_backup.docx`)
3. **测试验证通过** - 已生成测试报告 (`example/reports/test_template_sample.pdf`)

---

## 📋 模板占位符说明

新模板使用 `{{字段名}}` 格式作为占位符，程序会自动将这些占位符替换为数据库中的实际数据。

### 完整占位符列表

#### 1️⃣ 患者基本信息
```
{{name}}         - 患者姓名
{{gender}}       - 性别
{{age}}          - 年龄
{{patient_id}}   - 患者ID
{{report_id}}    - 报告编号（格式：FILE-年份-序号）
{{visit_time}}   - 就诊时间
{{department}}   - 就诊科室
```

#### 2️⃣ 病史信息
```
{{chief_complaint}}          - 主诉
{{present_illness_history}}  - 现病史
{{past_history}}             - 既往病史
{{allergy_history}}          - 过敏史
{{family_history}}           - 家族史
```

#### 3️⃣ 检查信息
```
{{special_exams}}     - 专项检查（如：EyeAgent 生物力学检查）
{{auxiliary_exams}}   - 辅助检查
```

#### 4️⃣ 诊断信息
```
{{ai_diagnosis}}         - AI诊断结果
{{initial_diagnosis}}    - 初步诊断
```

#### 5️⃣ 治疗方案
```
{{treatment_plan}}   - 处理意见/治疗方案
```

#### 6️⃣ 元信息
```
{{doctor_signature}}  - 医生签名
{{print_time}}        - 打印时间
```

---

## 🎨 模板格式特点

新模板完全按照你提供的病例单图片设计，包含：

1. **标题区域** - 蓝色Logo + 标题居中
2. **基本信息表格** - 3行3列表格，包含患者基本信息
3. **病史信息** - 每个字段独立一行，标签加粗
4. **检查信息** - 专项检查和辅助检查
5. **诊断信息** - AI诊断 + 初步诊断
6. **处理意见** - 治疗方案
7. **签名区域** - 医生签名（右对齐）+ 打印时间（左下角）

---

## 🔧 如何使用

### 方式1：从数据库生成报告

```python
from utils.report_generator import ReportGenerator

generator = ReportGenerator()

# 使用病例ID生成报告
pdf_path = generator.generate_report_from_db(medical_record_id=1)
print(f"报告已生成: {pdf_path}")
```

### 方式2：使用自定义数据生成报告

```python
from utils.report_generator import ReportGenerator

data = {
    "patient_info": {
        "name": "张三",
        "gender": "男",
        "age": "36",
        "patient_id": "20134148943293",
        "report_id": "FILE-2970-32434",
        "visit_time": "2025年11月16日",
        "department": "眼科"
    },
    "medical_history": {
        "chief_complaint": "双眼视物模糊 1 个月",
        "present_illness_history": "患者1个月前...",
        "past_history": "无",
        "allergy_history": "对阿莫西林过敏",
        "family_history": "无"
    },
    "examinations": {
        "special_exams": "EyeAgent 生物力学检查",
        "auxiliary_exams": "无"
    },
    "diagnosis": {
        "ai_diagnosis": "双眼近视",
        "initial_diagnosis": "1. 双眼近视（OD 100°、OS 280°）\n2. 眼底未见明显异常"
    },
    "treatment": {
        "treatment_plan": "1. 建议根据验光结果配戴框架眼镜\n2. 注意用眼卫生..."
    },
    "meta": {
        "doctor_signature": "",
        "print_time": "2025-11-16 22:22"
    }
}

generator = ReportGenerator()
pdf_path = generator.generate_report_from_data(data, "custom_report")
print(f"报告已生成: {pdf_path}")
```

### 方式3：批量生成报告

```python
from utils.report_generator import ReportGenerator

generator = ReportGenerator()

# 批量生成某个用户的所有报告
pdf_paths = generator.batch_generate(patient_id=1)
print(f"成功生成 {len(pdf_paths)} 份报告")
```

---

## 📝 修改模板

如果你想修改模板的样式或布局：

1. **打开模板文件**：`example/bingli.docx`
2. **修改样式**：
   - 可以修改字体、颜色、大小
   - 可以调整表格布局
   - 可以添加Logo图片
3. **保持占位符**：确保所有 `{{字段名}}` 占位符保持不变
4. **保存文件**：保存后即可生效

### 注意事项

- ✅ 占位符必须使用 `{{字段名}}` 格式（两个大括号）
- ✅ 字段名必须完全匹配（大小写敏感）
- ✅ 可以在段落中或表格单元格中使用占位符
- ✅ 程序会保留占位符所在文本的格式（字体、颜色等）
- ⚠️ 如果数据库中某字段为空，占位符会被替换为空字符串

---

## 🧪 测试模板

运行测试脚本验证模板是否正常工作：

```bash
python test_new_template.py
```

测试脚本会：
1. 使用示例数据生成测试报告
2. 尝试从数据库生成报告（如果有数据）
3. 在 `example/reports/` 目录生成PDF文件

---

## 📂 相关文件

```
pythonProject1/
├── example/
│   ├── bingli.docx              # 主模板（新）
│   ├── bingli_backup.docx       # 旧模板备份
│   ├── bingli_template.docx     # 模板副本
│   └── reports/                 # 生成的报告存放目录
│       └── test_template_sample.pdf
├── utils/
│   └── report_generator.py      # 报告生成器
├── create_template.py           # 模板创建脚本
├── test_new_template.py         # 模板测试脚本
└── Word模板使用指南.md          # 本文档
```

---

## 🔍 占位符到数据库字段的映射

| 占位符 | 数据库表 | 数据库字段 |
|--------|----------|------------|
| `{{name}}` | patient | Name |
| `{{gender}}` | patient | Gender |
| `{{age}}` | patient | Age (计算得出) |
| `{{patient_id}}` | patient | Patient_ID |
| `{{report_id}}` | medical_record | Report_ID |
| `{{visit_time}}` | medical_record | Visit_Time |
| `{{department}}` | medical_record | Department |
| `{{chief_complaint}}` | medical_record | Chief_Complaint |
| `{{present_illness_history}}` | medical_record | Present_Illness_History |
| `{{past_history}}` | medical_record | Past_History |
| `{{allergy_history}}` | medical_record | Allergy_History |
| `{{family_history}}` | medical_record | Family_History |
| `{{special_exams}}` | medical_record | Special_Exams |
| `{{auxiliary_exams}}` | medical_record | Auxiliary_Exams |
| `{{ai_diagnosis}}` | medical_record | AI_Diagnosis |
| `{{initial_diagnosis}}` | medical_record | Diagnosis |
| `{{treatment_plan}}` | medical_record | Treatment_Plan |
| `{{doctor_signature}}` | medical_record | Doctor_Signature |
| `{{print_time}}` | medical_record | Print_Time |

---

## ❓ 常见问题

### Q1: 生成的报告中有些字段是空的？
**A:** 检查数据库中对应字段是否有数据。如果字段为空，占位符会被替换为空字符串。

### Q2: PDF转换失败？
**A:** 系统会优先使用 `docx2pdf`（Windows）转换，如果失败会返回 `.docx` 文件。你可以手动转换为PDF。

### Q3: 想添加新的字段？
**A:** 
1. 在模板中添加新占位符 `{{new_field}}`
2. 在 `report_generator.py` 的 `_create_placeholder_mapping` 方法中添加映射
3. 确保数据源包含该字段

### Q4: 如何修改报告样式？
**A:** 直接在Word中打开 `example/bingli.docx`，修改样式后保存即可。

---

## ✨ 下一步

现在你可以：

1. ✅ 查看生成的测试报告：`example/reports/test_template_sample.pdf`
2. ✅ 根据需要修改模板样式
3. ✅ 集成到你的应用中使用
4. ✅ 批量生成历史病例报告

如有任何问题，请参考 `病例报告功能说明.md` 获取更多信息。


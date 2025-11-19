
import re
from docx import Document

# 替换段落中的占位符
def replace_placeholder_in_paragraph(para, placeholder, replacement):
    if re.search(re.escape(placeholder), para.text):
        inline = para.runs
        for i in inline:
            if re.search(re.escape(placeholder), i.text):
                i.text = re.sub(re.escape(placeholder), replacement, i.text)
                print(f"替换：{placeholder} 为 {replacement}")  # 输出替换的信息，便于调试

# 替换表格中的占位符
def replace_placeholder_in_table(table, placeholder, replacement):
    for row in table.rows:
        for cell in row.cells:
            for para in cell.paragraphs:
                replace_placeholder_in_paragraph(para, placeholder, replacement)

# 替换文档中的所有占位符
def replace_placeholder(doc, placeholder, replacement):
    for para in doc.paragraphs:
        replace_placeholder_in_paragraph(para, placeholder, replacement)

    for table in doc.tables:
        replace_placeholder_in_table(table, placeholder, replacement)


# 主程序
if __name__ == "__main__":
    # 加载文档
    doc_path = "template/aidocx2.docx"
    doc = Document(doc_path)

    
    replacements = {
        '[Name]': '张三',
        '[Gender]': '男',
        '[ScanDate]': '2025-11-18',
        '[Age]': '30',
        '[ID]': '123456',
        '[BirthDay]': '1990-01-01',
        '[Doctor]': '李医生',
        '[AXL-OD]': '24.89',
        '[AXL-OS]': '24.73',
        '[K1-D-OD]': '47.47',
        '[K1-mm-OD]': '7.11',
        '[K1-DEG-OD]': '178',
        '[K1-D-OS]': '47.27',
        '[K1-mm-OS]': '7.14',
        '[K1-DEG-OS]': '14',
        '[K2-D-OD]': '48.31',
        '[K2-mm-OD]': '6.99',
        '[K2-DEG-OD]': '88',
        '[K2-D-OS]': '48.09',
        '[K2-mm-OS]': '7.02',
        '[K2-DEG-OS]': '104',
        '[ACD-OD]': '3.66',
        '[ACD-OS]': '3.51',
        '[CCT-OD]': '540.1',
        '[CCT-OS]': '542.2',
        '[WTW-OD]': '11.80',
        '[WTW-OS]': '12.00',
        '[TR-OD]': '-0.5',
        '[TR-OS]': '-0.5',
        '[Ac-T1]': '118.5',
        '[Ac-T2]': '118.8',
        '[Ac-T3]': '118.5',
        '[Ac-T4]': '118.5',
        '[P-T1]': '11.50',
        '[P-T2]': '12.50',
        '[P-T3]': '12.50',
        '[P-T4]': '13.50',
        '[I1-T1]': '11.50',
        '[R1-T1]': '-1.15',
        '[I1-T2]': '12.50',
        '[R1-T2]': '-0.95',
        '[I1-T3]': '12.50',
        '[R1-T3]': '-1.24',
        '[I1-T4]': '13.50',
        '[R1-T4]': '-1.09',
        '[I2-T1]': '12.50',
        '[R2-T1]': '-0.83',
        '[I2-T2]': '12.00',
        '[R2-T2]': '-0.66',
        '[I2-T3]': '12.00',
        '[R2-T3]': '-0.92',
        '[I2-T4]': '13.00',
        '[R2-T4]': '-0.78',
        '[I3-T1]': '10.50',
        '[R3-T1]': '-0.51',
        '[I3-T2]': '11.50',
        '[R3-T2]': '-0.37',
        '[I3-T3]': '11.50',
        '[R3-T3]': '-0.60',
        '[I3-T4]': '12.50',
        '[R3-T4]': '-0.49',
        '[I4-T1]': '11.00',
        '[R4-T1]': '-0.20',
        '[I4-T2]': '11.00',
        '[R4-T2]': '-0.08',
        '[I4-T3]': '12.00',
        '[R4-T3]': '-0.28',
        '[I4-T4]': '12.00',
        '[R4-T4]': '-0.19',
        '[I5-T1]': '10.50',
        '[R5-T1]': '0.11',
        '[I5-T2]': '10.50',
        '[R5-T2]': '0.21',
        '[I5-T3]': '11.50',
        '[R5-T3]': '0.03',
        '[I5-T4]': '11.50',
        '[R5-T4]': '0.10',

        # 补充缺失的占位符数据
        '[Ac-T5]': '118.2',
        '[Ac-T6]': '118.3',
        '[Ac-T7]': '118.4',
        '[Ac-T8]': '118.6',
        '[I1-T5]': '11.50',
        '[R1-T5]': '-1.10',
        '[I1-T6]': '12.00',
        '[R1-T6]': '-1.00',
        '[I1-T7]': '12.50',
        '[R1-T7]': '-1.05',
        '[I1-T8]': '13.00',
        '[R1-T8]': '-0.90',
        '[I2-T5]': '12.00',
        '[R2-T5]': '-0.78',
        '[I2-T6]': '12.50',
        '[R2-T6]': '-0.82',
        '[I2-T7]': '13.00',
        '[R2-T7]': '-0.90',
        '[I2-T8]': '13.50',
        '[R2-T8]': '-0.85',

        # 添加缺失的占位符数据
        '[I3-T5]': '11.50',
        '[R3-T5]': '-0.50',
        '[I3-T6]': '12.00',
        '[R3-T6]': '-0.45',
        '[I3-T7]': '12.50',
        '[R3-T7]': '-0.55',
        '[I3-T8]': '13.00',
        '[R3-T8]': '-0.40',
        '[I4-T5]': '11.00',
        '[R4-T5]': '-0.20',
        '[I4-T6]': '11.50',
        '[R4-T6]': '-0.15',
        '[I4-T7]': '12.00',
        '[R4-T7]': '-0.25',
        '[I4-T8]': '12.50',
        '[R4-T8]': '-0.10',
        '[I5-T5]': '10.50',
        '[R5-T5]': '0.10',
        '[I5-T6]': '11.00',
        '[R5-T6]': '0.15',
        '[I5-T7]': '11.50',
        '[R5-T7]': '0.05',
        '[I5-T8]': '12.00',
        '[R5-T8]': '0.20',

        # 修正Power占位符
        '[P-T5]': '11.42',
        '[P-T6]': '11.12',
        '[P-T7]': '12.19',
        '[P-T8]': '11.93',

        '[PrintTime]': '2025-11-18'
    }

    print("开始替换占位符...\n")

    # 替换文档中的占位符
    for placeholder, replacement in replacements.items():
        replace_placeholder(doc, placeholder, replacement)

    # 保存修改后的文档
    output_path = "modified_report_final_v2.docx"  # 设置输出文件路径
    doc.save(output_path)

    print(f"\n✓ 文档已成功更新并保存到: {output_path}")

    # 验证是否还有未替换的占位符
    print("\n验证结果:")
    doc_verify = Document(output_path)
    remaining_placeholders = []

    for para in doc_verify.paragraphs:
        if '[' in para.text and ']' in para.text:
            remaining_placeholders.append(para.text)

    for table in doc_verify.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    if '[' in para.text and ']' in para.text:
                        remaining_placeholders.append(para.text)

    if remaining_placeholders:
        print("⚠ 警告：仍有未替换的占位符:")
        for item in remaining_placeholders:
            print(f"  - {item}")
    else:
        print("✓ 所有占位符都已成功替换！")


import re
from docx import Document


# 改进的段落占位符替换函数
def replace_placeholder_in_paragraph(para, placeholder, replacement):
    """
    改进版：处理占位符被分散在多个runs中的情况
    通过合并所有runs的文本，查找并替换，然后重建runs
    """
    # 获取完整的段落文本
    full_text = para.text

    # 检查是否包含占位符
    if placeholder not in full_text:
        return False

    # 执行替换
    new_text = full_text.replace(placeholder, replacement)

    # 如果文本有变化
    if new_text != full_text:
        # 保存第一个run的格式
        if para.runs:
            first_run_font = para.runs[0].font

            # 清除所有现有的runs
            for run in para.runs:
                run.text = ''

            # 在第一个run中设置新文本
            para.runs[0].text = new_text
            print(f"✓ 替换成功: {placeholder} → {replacement}")
            return True

    return False


# 替换表格中的占位符
def replace_placeholder_in_table(table, placeholder, replacement):
    """替换表格中所有单元格的占位符"""
    for row in table.rows:
        for cell in row.cells:
            for para in cell.paragraphs:
                replace_placeholder_in_paragraph(para, placeholder, replacement)


# 替换文档中的所有占位符
def replace_placeholder(doc, placeholder, replacement):
    """替换文档中段落和表格中的所有占位符"""
    # 替换段落中的占位符
    for para in doc.paragraphs:
        replace_placeholder_in_paragraph(para, placeholder, replacement)

    # 替换表格中的占位符
    for table in doc.tables:
        replace_placeholder_in_table(table, placeholder, replacement)


# 主程序
if __name__ == "__main__":
    # 加载文档
    doc_path = "template/aidocx1.docx"
    doc = Document(doc_path)

    # 替换占位符的数据
    replacements = {
        '[Name]': '张三',
        '[Gender]': '男',
        '[ScanTime]': '2025-11-18',
        '[ID]': '123456',
        '[BirthDay]': '1990-01-01',
        '[Operator]': '李医生',
        '[AXL-R]': '24.89',
        '[AXL-L]': '24.73',
        '[CCT-R]': '540.1',
        '[CCT-L]': '542.2',
        '[ACD-R]': '3.66',
        '[ACD-L]': '3.51',
        '[LT-R]': '4.28',
        '[LT-L]': '4.30',
        '[AXL-ACD-LT-R]': '16.95',
        '[AXL-ACD-LT-L]': '16.94',
        '[K1-D-R]': '47.47',
        '[K1-mm-R]': '7.11',
        '[K1-DEG-R]': '178',
        '[K1-D-L]': '47.27',
        '[K1-mm-L]': '7.14',
        '[K1-DEG-L]': '14',
        '[K2-D-R]': '48.31',
        '[K2-mm-R]': '6.99',
        '[K2-DEG-R]': '88',
        '[K2-D-L]': '48.09',
        '[K2-mm-L]': '7.02',
        '[K2-DEG-L]': '104',
        '[DK-R]': '-0.84',
        '[DK-DEG-R]': '178',
        '[DK-L]': '-0.81',
        '[DK-DEG-L]': '90',
        '[WTW-R]': '11.80',
        '[WTW-L]': '12.00',
        '[PD-R]': '3.86',
        '[PD-L]': '3.80'
    }

    print("开始替换占位符...\n")

    # 替换文档中的占位符
    for placeholder, replacement in replacements.items():
        replace_placeholder(doc, placeholder, replacement)

    # 保存修改后的文档
    output_path = "modified_report_final.docx"
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
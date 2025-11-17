"""创建新的病例单Word模板"""
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

def create_template():
    """创建病例单模板"""
    doc = Document()
    
    # 设置默认中文字体
    doc.styles['Normal'].font.name = 'SimSun'
    doc.styles['Normal']._element.rPr.rFonts.set(qn('w:eastAsia'), 'SimSun')
    doc.styles['Normal'].font.size = Pt(10.5)
    
    # ========== 标题部分 ==========
    # Logo和标题（居中）
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_para.add_run('EA 中国视光中心')
    title_run.font.size = Pt(16)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(0, 102, 204)  # 蓝色
    
    # 副标题
    subtitle_para = doc.add_paragraph()
    subtitle_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle_run = subtitle_para.add_run('眼科门诊病例单')
    subtitle_run.font.size = Pt(18)
    subtitle_run.font.bold = True
    
    # 添加空行
    doc.add_paragraph()
    
    # ========== 患者基本信息表格 ==========
    info_table = doc.add_table(rows=3, cols=3)
    info_table.style = 'Table Grid'
    
    # 第一行：姓名、性别、年龄
    cells = info_table.rows[0].cells
    cells[0].text = '姓名：{{name}}'
    cells[1].text = '性别：{{gender}}'
    cells[2].text = '年龄：{{age}}'
    
    # 第二行：患者ID、报告编号
    cells = info_table.rows[1].cells
    cells[0].text = '患者ID：{{patient_id}}'
    merged_cell = cells[1].merge(cells[2])
    merged_cell.text = '报告编号：{{report_id}}'
    
    # 第三行：就诊时间、就诊科室
    cells = info_table.rows[2].cells
    cells[0].text = '就诊时间：{{visit_time}}'
    merged_cell = cells[1].merge(cells[2])
    merged_cell.text = '就诊科室：{{department}}'
    
    # 设置表格字体
    for row in info_table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(10.5)
                    run.font.name = 'SimSun'
    
    # 添加分隔线
    doc.add_paragraph('_' * 80)
    
    # ========== 病史信息 ==========
    # 主诉
    p = doc.add_paragraph()
    p.add_run('主诉：').bold = True
    p.add_run('{{chief_complaint}}')
    
    # 现病史
    p = doc.add_paragraph()
    p.add_run('现病史：').bold = True
    p.add_run('{{present_illness_history}}')
    
    # 既往史
    p = doc.add_paragraph()
    p.add_run('既往史：').bold = True
    p.add_run('{{past_history}}')
    
    # 过敏史
    p = doc.add_paragraph()
    p.add_run('过敏史：').bold = True
    p.add_run('{{allergy_history}}')
    
    # 家族史
    p = doc.add_paragraph()
    p.add_run('家族史：').bold = True
    p.add_run('{{family_history}}')
    
    # ========== 检查信息 ==========
    # 专项检查
    p = doc.add_paragraph()
    p.add_run('专项检查：').bold = True
    p.add_run('{{special_exams}}')
    
    # 辅助检查
    p = doc.add_paragraph()
    p.add_run('辅助检查：').bold = True
    p.add_run('{{auxiliary_exams}}')
    
    # AI诊断结果
    p = doc.add_paragraph()
    p.add_run('AI 诊断结果：').bold = True
    p.add_run('{{ai_diagnosis}}')
    
    # ========== 诊断 ==========
    p = doc.add_paragraph()
    p.add_run('初步诊断：').bold = True
    doc.add_paragraph('{{initial_diagnosis}}')
    
    # ========== 处理意见 ==========
    p = doc.add_paragraph()
    p.add_run('处理意见：').bold = True
    doc.add_paragraph('{{treatment_plan}}')
    
    # 添加分隔线
    doc.add_paragraph('_' * 80)
    
    # ========== 签名和时间 ==========
    # 添加空行
    doc.add_paragraph()
    doc.add_paragraph()
    
    # 医生签名（右对齐）
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.add_run('医生签名：{{doctor_signature}}')
    
    # 添加空行
    doc.add_paragraph()
    doc.add_paragraph()
    doc.add_paragraph()
    
    # 打印时间（左对齐）
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.add_run('打印时间：{{print_time}}')
    
    # 保存文档
    doc.save('example/bingli_template.docx')
    print("[OK] 新模板创建成功: example/bingli_template.docx")
    
    # 备份旧模板
    import shutil
    from pathlib import Path
    old_template = Path('example/bingli.docx')
    if old_template.exists():
        backup_path = Path('example/bingli_backup.docx')
        shutil.copy(old_template, backup_path)
        print(f"[OK] 旧模板已备份: {backup_path}")
    
    # 替换旧模板
    shutil.copy('example/bingli_template.docx', 'example/bingli.docx')
    print("[OK] 已将新模板设置为主模板: example/bingli.docx")

if __name__ == '__main__':
    create_template()


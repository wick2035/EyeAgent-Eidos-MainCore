"""
创建处方单Word模板
完全复刻处方筏.pdf的样式，无多余边框
"""

from docx import Document
from docx.shared import Pt, Inches, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from pathlib import Path
import shutil

def remove_table_borders(table):
    """完全移除表格的所有边框"""
    tbl = table._element
    tblPr = tbl.tblPr
    if tblPr is None:
        tblPr = OxmlElement('w:tblPr')
        tbl.insert(0, tblPr)
    
    # 移除表格边框
    tblBorders = OxmlElement('w:tblBorders')
    for border_name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        border = OxmlElement(f'w:{border_name}')
        border.set(qn('w:val'), 'none')
        border.set(qn('w:sz'), '0')
        border.set(qn('w:space'), '0')
        border.set(qn('w:color'), 'auto')
        tblBorders.append(border)
    
    tblPr.append(tblBorders)

def create_prescription_template():
    """创建处方单Word模板"""
    
    # 创建文档
    doc = Document()
    
    # 设置页面大小为A4
    section = doc.sections[0]
    section.page_height = Cm(29.7)  # A4高度
    section.page_width = Cm(21.0)   # A4宽度
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)
    section.top_margin = Cm(1.5)
    section.bottom_margin = Cm(1.5)
    
    # ========== 顶部Logo和标题（无边框表格） ==========
    header_table = doc.add_table(rows=1, cols=2)
    header_table.autofit = False
    header_table.allow_autofit = False
    
    # Logo单元格（左侧）
    logo_cell = header_table.rows[0].cells[0]
    logo_cell.width = Cm(5.0)
    logo_para = logo_cell.paragraphs[0]
    logo_para.text = "[LOGO]"
    logo_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    
    # 标题单元格（右侧）
    title_cell = header_table.rows[0].cells[1]
    title_para = title_cell.paragraphs[0]
    title_run = title_para.add_run("EA 中国视光中心")
    title_run.font.size = Pt(18)
    title_run.font.bold = True
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # 移除表格边框
    remove_table_borders(header_table)
    
    # ========== 处方笺标题 + 条形码（无边框表格布局） ==========
    title_barcode_table = doc.add_table(rows=1, cols=2)
    title_barcode_table.autofit = False
    
    # 左侧：处方笺标题
    left_cell = title_barcode_table.rows[0].cells[0]
    left_cell.width = Cm(12.0)
    title_para = left_cell.paragraphs[0]
    title_run = title_para.add_run("处 方 笺")
    title_run.font.size = Pt(22)
    title_run.font.bold = True
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_para.space_before = Pt(6)
    title_para.space_after = Pt(6)
    
    # 右侧：条形码+处方类型+处方编号
    right_cell = title_barcode_table.rows[0].cells[1]
    right_cell.width = Cm(5.0)
    
    # 条形码占位符
    barcode_para = right_cell.paragraphs[0]
    barcode_para.text = "{{barcode}}"
    barcode_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    
    # 处方类型
    type_para = right_cell.add_paragraph()
    type_run = type_para.add_run("{{prescription_type}}")
    type_run.font.size = Pt(10)
    type_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    type_para.space_before = Pt(0)
    type_para.space_after = Pt(0)
    
    # 处方编号（小字）
    number_para = right_cell.add_paragraph()
    number_run = number_para.add_run("{{prescription_number}}")
    number_run.font.size = Pt(8)
    number_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    number_para.space_before = Pt(0)
    
    # 移除表格边框
    remove_table_borders(title_barcode_table)
    
    # ========== 费别和处方编号行 ==========
    fee_para = doc.add_paragraph()
    fee_para.add_run("费别：自费        ")
    fee_para.add_run("医保卡号：                    ")
    fee_para.add_run("处方编号：{{prescription_number}}")
    fee_para.space_before = Pt(6)
    fee_para.space_after = Pt(6)
    
    # ========== 患者信息表格（保留边框） ==========
    patient_table = doc.add_table(rows=2, cols=7)
    patient_table.style = 'Table Grid'
    
    # 第一行：姓名、性别、年龄、患者ID
    row1_cells = patient_table.rows[0].cells
    row1_cells[0].text = "姓名：{{patient_name}}"
    row1_cells[1].text = "性别：{{patient_gender}}"
    row1_cells[2].text = "年龄：{{patient_age}}"
    row1_cells[3].text = ""
    row1_cells[4].text = "患者 ID：{{patient_id}}"
    row1_cells[5].text = ""
    row1_cells[6].text = ""
    
    # 合并单元格
    row1_cells[2].merge(row1_cells[3])
    row1_cells[4].merge(row1_cells[5])
    row1_cells[4].merge(row1_cells[6])
    
    # 第二行：就诊时间、就诊科室、联系电话
    row2_cells = patient_table.rows[1].cells
    row2_cells[0].text = "就诊时间：{{visit_time}}"
    row2_cells[1].text = ""
    row2_cells[2].text = "就诊科室：{{department}}"
    row2_cells[3].text = ""
    row2_cells[4].text = "联系电话：{{patient_phone}}"
    row2_cells[5].text = ""
    row2_cells[6].text = ""
    
    # 合并单元格
    row2_cells[0].merge(row2_cells[1])
    row2_cells[2].merge(row2_cells[3])
    row2_cells[4].merge(row2_cells[5])
    row2_cells[4].merge(row2_cells[6])
    
    # ========== RP:标题 ==========
    rp_para = doc.add_paragraph()
    rp_run = rp_para.add_run("RP:")
    rp_run.font.size = Pt(14)
    rp_run.font.bold = True
    rp_para.space_before = Pt(12)
    rp_para.space_after = Pt(6)
    
    # ========== 药物明细列表（无表格，纯文本）==========
    # 这部分会被程序动态填充，这里只放占位符
    # 示例格式：
    # 1、[100mg×13 粒/盒] x 4 盒子
    #    用法：200mg  口服  每日一次  超量原因：慢性病
    
    drug_placeholder = doc.add_paragraph()
    drug_placeholder.text = "{{drug_list}}"
    drug_placeholder.space_before = Pt(3)
    drug_placeholder.space_after = Pt(3)
    
    # 空行和"以下空白"
    doc.add_paragraph()
    blank_para = doc.add_paragraph()
    blank_para.text = "（以下空白）"
    blank_para.space_before = Pt(6)
    blank_para.space_after = Pt(6)
    doc.add_paragraph()
    doc.add_paragraph()
    doc.add_paragraph()
    
    # ========== 底部信息（无边框表格布局） ==========
    bottom_table = doc.add_table(rows=3, cols=2)
    bottom_table.autofit = False
    
    # 第一行：医生签名 | 药品金额
    row1 = bottom_table.rows[0]
    row1.cells[0].text = "医生签名：{{doctor_name}}"
    row1.cells[1].text = "药品金额：{{total_amount}} 元"
    
    # 第二行：审核药师 | 调配
    row2 = bottom_table.rows[1]
    row2.cells[0].text = "审核药师："
    row2.cells[1].text = "调配："
    
    # 第三行：打印时间 | 核发
    row3 = bottom_table.rows[2]
    row3.cells[0].text = "打印时间：{{print_time}}"
    row3.cells[1].text = "核发："
    
    # 移除表格边框
    remove_table_borders(bottom_table)
    
    # 空行
    doc.add_paragraph()
    
    # ========== 注意事项 ==========
    note1 = doc.add_paragraph()
    note1.text = "1、处方当日有效"
    note1.space_before = Pt(6)
    
    note2 = doc.add_paragraph()
    note2.text = "2、大病、特检通道结算者到门诊缴费"
    
    note3 = doc.add_paragraph()
    note3.text = "3、自助缴费处无需到窗口盖收费章。"
    
    # 保存文档
    output_path = Path("example/prescription_template.docx")
    doc.save(str(output_path))
    print(f"[OK] 模板创建成功: {output_path}")
    
    # 如果有logo文件，复制一份说明
    logo_path = Path("example/logo@1x.png")
    if logo_path.exists():
        print(f"[OK] Logo文件已存在: {logo_path}")
        print("   提示：在实际使用时，程序会自动将logo插入到文档中")
    
    return str(output_path)


if __name__ == "__main__":
    create_prescription_template()

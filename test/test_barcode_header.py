"""
测试页眉条形码功能
验证条形码能否正确插入到页眉左上角
"""

from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

def create_test_template():
    """创建一个带页眉条形码占位符的测试模板"""
    
    doc = Document()
    
    # 设置页面
    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21.0)
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)
    section.top_margin = Cm(2.5)  # 增加上边距给页眉留空间
    section.bottom_margin = Cm(1.5)
    
    # 设置页眉 - 在左上角放置条形码占位符
    header = section.header
    header_para = header.paragraphs[0]
    header_para.text = "{{barcode}}"
    header_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    
    # 添加正文标题
    title = doc.add_heading('EA 中国视光中心', level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    subtitle = doc.add_heading('处 方 笺', level=1)
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # 添加一些测试内容
    doc.add_paragraph("处方编号：{{prescription_number}}")
    doc.add_paragraph("患者姓名：{{patient_name}}")
    doc.add_paragraph("处方类型：{{prescription_type}}")
    
    # 保存模板
    template_path = Path("example/test_header_template.docx")
    doc.save(str(template_path))
    print(f"[OK] 测试模板已创建: {template_path}")
    return str(template_path)


def test_barcode_in_header():
    """测试条形码插入到页眉"""
    
    from utils.prescription_generator import PrescriptionGenerator
    
    # 创建测试模板
    template_path = create_test_template()
    
    # 准备测试数据
    test_data = {
        'prescription_info': {
            'prescription_number': 'RX20251117999',
            'prescription_date': '2025-11-17 10:30:00',
            'prescription_type': '普通',
            'diagnosis': '近视',
            'usage_instruction': '按医嘱服用',
            'total_amount': 120.50,
            'notes': '测试处方',
            'prescriber_name': '张医生',
            'prescriber_signature': '张三'
        },
        'patient_info': {
            'name': '测试患者',
            'gender': '男',
            'age': 30,
            'patient_id': 'P001',
            'phone': '13800138000'
        },
        'doctor_info': {
            'name': '张医生',
            'title': '主任医师'
        },
        'medical_record_info': {
            'visit_time': '2025-11-17 10:00:00',
            'visit_date': '2025-11-17',
            'department': '眼科',
            'chief_complaint': '视力下降'
        },
        'drug_details': [
            {
                'index': 1,
                'drug_name': '测试药物A',
                'specification': '100mg×10片/盒',
                'quantity': 2,
                'unit': '盒',
                'dosage': '1片',
                'frequency': '每日3次',
                'duration': '7天',
                'route': '口服',
                'special_instructions': '饭后服用'
            }
        ]
    }
    
    # 创建生成器，使用测试模板
    generator = PrescriptionGenerator(
        template_path=template_path,
        output_dir="../example/prescriptions"
    )
    
    # 生成处方
    print("\n开始生成测试处方...")
    pdf_path = generator.generate_prescription_from_data(
        test_data, 
        output_filename="test_header_barcode"
    )
    
    if pdf_path:
        print(f"[OK] 测试处方生成成功: {pdf_path}")
        print("\n请打开生成的文件检查：")
        print("1. 条形码是否出现在页面左上角（页眉位置）")
        print("2. 正文排版是否完整不受影响")
        print("3. 条形码是否清晰可读")
    else:
        print("[ERROR] 测试处方生成失败")
    
    return pdf_path


if __name__ == "__main__":
    print("=" * 60)
    print("测试条形码页眉功能")
    print("=" * 60)
    
    try:
        test_barcode_in_header()
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()


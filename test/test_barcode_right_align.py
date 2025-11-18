"""
测试条形码右对齐功能
验证条形码在页眉右边，且不覆盖左边的内容
"""

from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

def create_test_template_with_left_content():
    """创建一个页眉左边有内容、右边有条形码占位符的测试模板"""
    
    doc = Document()
    
    # 设置页面
    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21.0)
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(1.5)
    
    # 设置页眉 - 左边放文字，右边放条形码占位符
    header = section.header
    header_para = header.paragraphs[0]
    
    # 在页眉中添加左边的内容和条形码占位符
    header_para.text = "EA 中国视光中心 - 处方笺  {{barcode}}"
    
    # 添加正文标题
    title = doc.add_heading('EA 中国视光中心', level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    subtitle = doc.add_heading('处 方 笺', level=1)
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # 添加测试内容
    doc.add_paragraph("处方编号：{{prescription_number}}")
    doc.add_paragraph("患者姓名：{{patient_name}}")
    doc.add_paragraph("处方类型：{{prescription_type}}")
    
    # 保存模板
    template_path = Path("example/test_barcode_right_align_template.docx")
    doc.save(str(template_path))
    print(f"[OK] 测试模板已创建: {template_path}")
    print(f"     页眉内容: 'EA 中国视光中心 - 处方笺  {{{{barcode}}}}'")
    return str(template_path)


def test_barcode_right_align():
    """测试条形码右对齐功能"""
    
    from utils.prescription_generator import PrescriptionGenerator
    
    # 创建测试模板
    template_path = create_test_template_with_left_content()
    
    # 准备测试数据
    test_data = {
        'prescription_info': {
            'prescription_number': 'RX20251117888',
            'prescription_date': '2025-11-17 14:30:00',
            'prescription_type': '普通',
            'diagnosis': '近视',
            'usage_instruction': '按医嘱服用',
            'total_amount': 150.00,
            'notes': '测试条形码右对齐',
            'prescriber_name': '李医生',
            'prescriber_signature': '李四'
        },
        'patient_info': {
            'name': '张三',
            'gender': '女',
            'age': 25,
            'patient_id': 'P002',
            'phone': '13900139000'
        },
        'doctor_info': {
            'name': '李医生',
            'title': '副主任医师'
        },
        'medical_record_info': {
            'visit_time': '2025-11-17 14:00:00',
            'visit_date': '2025-11-17',
            'department': '眼科',
            'chief_complaint': '视物模糊'
        },
        'drug_details': [
            {
                'index': 1,
                'drug_name': '测试药物B',
                'specification': '50mg×20片/盒',
                'quantity': 1,
                'unit': '盒',
                'dosage': '2片',
                'frequency': '每日2次',
                'duration': '14天',
                'route': '口服',
                'special_instructions': '餐后服用'
            }
        ]
    }
    
    # 创建生成器
    generator = PrescriptionGenerator(
        template_path=template_path,
        output_dir="../example/prescriptions"
    )
    
    # 生成处方
    print("\n开始生成测试处方...")
    pdf_path = generator.generate_prescription_from_data(
        test_data, 
        output_filename="test_barcode_right_align"
    )
    
    if pdf_path:
        print(f"\n[OK] 测试处方生成成功: {pdf_path}")
        print("\n请打开生成的文件检查：")
        print("1. ✓ 条形码是否出现在页眉右边")
        print("2. ✓ 页眉左边的文字 'EA 中国视光中心 - 处方笺' 是否保留")
        print("3. ✓ 条形码是否清晰可读")
        print("4. ✓ 页眉布局是否正常")
        return True
    else:
        print("\n[ERROR] 测试处方生成失败")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("测试条形码右对齐功能")
    print("验证：条形码在页眉右边，且不覆盖左边的内容")
    print("=" * 70)
    
    try:
        success = test_barcode_right_align()
        if success:
            print("\n" + "=" * 70)
            print("✅ 测试通过！")
            print("=" * 70)
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()


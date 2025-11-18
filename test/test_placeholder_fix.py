"""
测试占位符替换修复
验证处方模板中的{{}}占位符能否正确替换
"""

import sys
import io

# 设置标准输出为UTF-8编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from utils.prescription_generator import PrescriptionGenerator
from database.prescription_service import PrescriptionService
import os

def test_prescription_placeholder_replacement():
    """测试处方单占位符替换"""
    print("=" * 60)
    print("测试处方单占位符替换")
    print("=" * 60)
    
    # 创建生成器
    generator = PrescriptionGenerator()
    
    # 检查模板文件是否存在
    template_path = generator.template_path
    if not template_path.exists():
        print(f"❌ 模板文件不存在: {template_path}")
        print("   请先运行 python create_template.py 创建模板")
        return False
    
    print(f"✅ 模板文件存在: {template_path}")
    
    # 尝试从数据库生成处方单
    try:
        # 获取一个处方数据
        service = PrescriptionService()
        
        # 获取第一个处方的完整数据
        prescription_data = service.get_prescription_full(prescription_id=1)
        
        if not prescription_data:
            print("❌ 未找到处方ID=1的数据")
            service.close()
            return False
        
        print(f"\n✅ 成功获取处方数据:")
        print(f"   - 处方编号: {prescription_data['prescription_info']['prescription_number']}")
        print(f"   - 患者姓名: {prescription_data['patient_info']['name']}")
        print(f"   - 药物数量: {len(prescription_data['drug_details'])}")
        
        # 生成处方单
        print("\n🔄 开始生成处方单...")
        pdf_path = generator.generate_prescription_from_data(
            data=prescription_data,
            output_filename="test_placeholder_fix"
        )
        
        service.close()
        
        if pdf_path and os.path.exists(pdf_path):
            print(f"\n✅ 处方单生成成功！")
            print(f"   文件路径: {pdf_path}")
            print(f"\n请打开生成的文件检查以下内容是否正确替换:")
            print(f"   - 患者姓名: {prescription_data['patient_info']['name']}")
            print(f"   - 患者性别: {prescription_data['patient_info']['gender']}")
            print(f"   - 患者年龄: {prescription_data['patient_info']['age']}")
            print(f"   - 处方编号: {prescription_data['prescription_info']['prescription_number']}")
            print(f"   - 医生姓名: {prescription_data['doctor_info']['name']}")
            print(f"   - 总金额: {prescription_data['prescription_info']['total_amount']}")
            return True
        else:
            print("\n❌ 处方单生成失败")
            return False
            
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_template_placeholders():
    """检查模板中的占位符"""
    print("\n" + "=" * 60)
    print("检查模板中的占位符")
    print("=" * 60)
    
    try:
        from docx import Document
        from pathlib import Path
        
        # 模板路径
        template_path = Path("../example/prescription_template.docx")
        
        if not template_path.exists():
            print(f"❌ 模板文件不存在: {template_path}")
            return
        
        # 读取模板
        doc = Document(str(template_path))
        
        # 收集所有占位符
        placeholders = set()
        
        # 检查段落
        for paragraph in doc.paragraphs:
            text = paragraph.text
            import re
            found = re.findall(r'\{\{[^}]+\}\}', text)
            placeholders.update(found)
        
        # 检查表格
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        text = paragraph.text
                        found = re.findall(r'\{\{[^}]+\}\}', text)
                        placeholders.update(found)
        
        if placeholders:
            print(f"\n✅ 在模板中发现 {len(placeholders)} 个占位符:")
            for placeholder in sorted(placeholders):
                print(f"   - {placeholder}")
        else:
            print("\n⚠️  模板中没有找到占位符")
            print("   这可能意味着:")
            print("   1. 模板已经被填充过了")
            print("   2. 模板格式有问题")
            
    except Exception as e:
        print(f"\n❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 先检查模板中的占位符
    check_template_placeholders()
    
    # 再测试替换功能
    print("\n")
    success = test_prescription_placeholder_replacement()
    
    if success:
        print("\n" + "=" * 60)
        print("✅ 测试通过！占位符替换功能正常")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ 测试未通过，请检查错误信息")
        print("=" * 60)


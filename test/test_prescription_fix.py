"""
测试处方单生成功能
创建日期：2025-11-17
更新日期：2025-11-17
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.prescription_generator import PrescriptionGenerator
from database.prescription_service import PrescriptionService


def test_database_query():
    """测试数据库查询功能"""
    print("\n" + "=" * 60)
    print("测试1：数据库查询功能")
    print("=" * 60)
    
    try:
        service = PrescriptionService()
        
        # 测试获取处方完整信息
        print("\n正在查询处方ID=1的完整信息...")
        prescription_data = service.get_prescription_full(prescription_id=1)
        
        if prescription_data:
            print("[OK] 查询成功！")
            print(f"  - 处方编号: {prescription_data['prescription_info']['prescription_number']}")
            print(f"  - 患者姓名: {prescription_data['patient_info']['name']}")
            print(f"  - 药物数量: {len(prescription_data['drug_details'])}")
            print(f"  - 总金额: {prescription_data['prescription_info']['total_amount']} 元")
            
            # 打印药物明细
            print("\n  药物明细:")
            for drug in prescription_data['drug_details']:
                print(f"    {drug['index']}. {drug['drug_name']} - {drug['specification']} × {drug['quantity']}{drug['unit']}")
            
            service.close()
            return True
        else:
            print("[ERROR] 未找到处方数据")
            service.close()
            return False
            
    except Exception as e:
        print(f"[ERROR] 数据库查询失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_prescription_generation():
    """测试处方单生成功能"""
    print("\n" + "=" * 60)
    print("测试2：处方单PDF生成功能")
    print("=" * 60)
    
    try:
        # 创建生成器
        generator = PrescriptionGenerator()
        
        # 测试生成处方ID为1的处方单
        print("\n正在生成处方ID=1的处方单...")
        pdf_path = generator.generate_prescription_from_db(prescription_id=1)
        
        if pdf_path:
            print(f"[OK] 成功！处方单已生成：{pdf_path}")
            if os.path.exists(pdf_path):
                file_size = os.path.getsize(pdf_path)
                print(f"  - 文件大小：{file_size} 字节")
                print(f"  - 文件类型：{os.path.splitext(pdf_path)[1]}")
                return True
            else:
                print("[ERROR] 文件路径存在但文件不存在")
                return False
        else:
            print("[ERROR] 处方单生成失败")
            return False
            
    except Exception as e:
        print(f"[ERROR] 生成处方单时发生异常：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_patient_prescriptions():
    """测试获取患者处方列表"""
    print("\n" + "=" * 60)
    print("测试3：患者处方列表查询")
    print("=" * 60)
    
    try:
        service = PrescriptionService()
        
        # 测试获取患者ID=1的处方列表
        print("\n正在查询患者ID=1的处方列表...")
        prescriptions = service.get_prescriptions_by_patient(patient_id=1, limit=10)
        
        if prescriptions:
            print(f"[OK] 查询成功！共找到 {len(prescriptions)} 条处方记录")
            
            for idx, presc in enumerate(prescriptions[:5], 1):
                print(f"\n  {idx}. 处方编号: {presc['prescription_number']}")
                print(f"     日期: {presc['prescription_date']}")
                print(f"     诊断: {presc['diagnosis']}")
                print(f"     金额: {presc['total_amount']} 元")
                print(f"     状态: {presc['status']}")
            
            service.close()
            return True
        else:
            print("[INFO] 未找到处方记录（可能数据库中没有数据）")
            service.close()
            return True  # 没有数据不算错误
            
    except Exception as e:
        print(f"[ERROR] 查询患者处方列表失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("开始测试处方单生成系统")
    print("=" * 60)
    
    results = []
    
    # 测试1：数据库查询
    results.append(("数据库查询", test_database_query()))
    
    # 测试2：处方单生成
    results.append(("处方单生成", test_prescription_generation()))
    
    # 测试3：患者处方列表
    results.append(("患者处方列表", test_patient_prescriptions()))
    
    # 输出测试结果总结
    print("\n" + "=" * 60)
    print("测试结果总结")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {test_name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n[SUCCESS] 所有测试通过！")
        return True
    else:
        print("\n[WARNING] 部分测试失败，请检查错误信息")
        return False


if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] 测试过程中发生严重异常：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


"""测试新模板的数据填充功能"""
from utils.report_generator import ReportGenerator
from datetime import datetime

def test_template_with_sample_data():
    """使用示例数据测试模板"""
    
    # 创建示例数据（模拟你图片中的病例单）
    sample_data = {
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
            "chief_complaint": "双眼视物模糊 1 个月未见好转。",
            "present_illness_history": "患者 1 个月前无明显诱因出现双眼视物模糊，远距离视物模糊较近距离更明显。期间无眼红、眼痛、畏光、流泪、无闪光感或暗影遮挡，症状呈逐渐加重趋势，未予系统治疗。",
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
            "treatment_plan": "1. 建议根据验光结果配戴框架眼镜\n2. 注意用眼卫生，避免长时间近距离用眼\n3. 建议 6 个月复查视力与眼底"
        },
        "meta": {
            "doctor_signature": "",
            "print_time": datetime.now().strftime('%Y-%m-%d %H:%M')
        }
    }
    
    print("=" * 60)
    print("开始测试新模板")
    print("=" * 60)
    
    # 创建报告生成器
    generator = ReportGenerator()
    
    # 生成报告
    print("\n[1] 使用示例数据生成报告...")
    pdf_path = generator.generate_report_from_data(
        sample_data, 
        output_filename="test_template_sample"
    )
    
    if pdf_path:
        print(f"[OK] 报告生成成功: {pdf_path}")
    else:
        print("[ERROR] 报告生成失败")
        return False
    
    print("\n" + "=" * 60)
    print("测试完成！请检查生成的报告文件。")
    print("=" * 60)
    
    return True

def test_template_from_database():
    """从数据库测试模板"""
    print("\n" + "=" * 60)
    print("从数据库测试模板")
    print("=" * 60)
    
    from database.report_service import ReportService
    
    service = ReportService()
    
    # 获取所有病例
    all_records = service.conn.execute("SELECT Medical_Record_ID FROM medical_record LIMIT 1").fetchone()
    
    if all_records:
        record_id = all_records[0]
        print(f"\n[2] 使用数据库病例 ID={record_id} 生成报告...")
        
        generator = ReportGenerator()
        pdf_path = generator.generate_report_from_db(record_id)
        
        if pdf_path:
            print(f"[OK] 数据库报告生成成功: {pdf_path}")
        else:
            print("[ERROR] 数据库报告生成失败")
    else:
        print("[WARN] 数据库中没有病例记录")
    
    service.close()

if __name__ == '__main__':
    # 测试1: 使用示例数据
    test_template_with_sample_data()
    
    # 测试2: 从数据库生成（如果有数据）
    try:
        test_template_from_database()
    except Exception as e:
        print(f"\n[WARN] 数据库测试跳过: {e}")
    
    print("\n请打开 example/reports/ 目录查看生成的报告文件。")


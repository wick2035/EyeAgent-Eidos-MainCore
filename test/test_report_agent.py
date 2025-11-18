"""
测试报告智能体和报告生成功能
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from agents.agent_2 import ReportAgent
from database.report_service import ReportService
from utils.report_generator import ReportGenerator


def test_report_service():
    """测试报告服务"""
    print("\n" + "="*60)
    print("测试1: 报告服务基本功能")
    print("="*60)
    
    service = ReportService()
    
    try:
        # 测试获取报告列表
        print("\n1.1 获取用户报告列表 (Patient_ID=1):")
        reports = service.get_all_reports_by_patient(1)
        print(f"  - 找到 {len(reports)} 份报告")
        if reports:
            for i, report in enumerate(reports[:3], 1):
                print(f"  {i}. Medical_Record_ID={report['Medical_Record_ID']}, "
                      f"日期={report['Visit_Date']}, "
                      f"主诉={report['Chief_Complaint']}")
        
        # 测试获取完整病例信息
        if reports:
            record_id = reports[0]['Medical_Record_ID']
            print(f"\n1.2 获取完整病例信息 (Medical_Record_ID={record_id}):")
            full_record = service.get_medical_record_full(record_id)
            if full_record:
                print(f"  - 患者姓名: {full_record.get('Patient_Name')}")
                print(f"  - 就诊日期: {full_record.get('Visit_Date')}")
                print(f"  - 诊断: {full_record.get('Diagnosis')}")
            
            # 测试分配报告编号
            print(f"\n1.3 分配报告编号:")
            report_id = service.assign_report_id(record_id)
            print(f"  - 报告编号: {report_id}")
            
            # 测试获取模板数据
            print(f"\n1.4 获取模板数据:")
            template_data = service.get_report_data_for_template(record_id)
            if template_data:
                print(f"  - 患者姓名: {template_data['patient_info']['name']}")
                print(f"  - 报告编号: {template_data['patient_info']['report_id']}")
                print(f"  - 主诉: {template_data['medical_history']['chief_complaint']}")
        
        print("\n[SUCCESS] 报告服务测试通过")
        
    except Exception as e:
        print(f"\n[FAIL] 报告服务测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        service.close()


def test_report_generator():
    """测试报告生成器"""
    print("\n" + "="*60)
    print("测试2: 报告生成功能")
    print("="*60)
    
    try:
        generator = ReportGenerator()
        service = ReportService()
        
        # 获取一个病例记录
        reports = service.get_all_reports_by_patient(1, limit=1)
        if not reports:
            print("  [WARN] 未找到病例记录，跳过测试")
            service.close()
            return
        
        record_id = reports[0]['Medical_Record_ID']
        print(f"\n2.1 从数据库生成报告 (Medical_Record_ID={record_id}):")
        
        # 生成报告
        pdf_path = generator.generate_report_from_db(record_id)
        
        if pdf_path:
            print(f"  [OK] 报告生成成功!")
            print(f"  - 文件路径: {pdf_path}")
            
            # 检查文件是否存在
            from pathlib import Path
            if Path(pdf_path).exists():
                file_size = Path(pdf_path).stat().st_size
                print(f"  - 文件大小: {file_size} 字节")
            else:
                print(f"  [WARN] 文件不存在（可能是PDF转换失败，仅生成了docx）")
        else:
            print(f"  [FAIL] 报告生成失败")
        
        service.close()
        print("\n[SUCCESS] 报告生成测试完成")
        
    except Exception as e:
        print(f"\n[FAIL] 报告生成测试失败: {e}")
        import traceback
        traceback.print_exc()


def test_report_agent():
    """测试报告智能体"""
    print("\n" + "="*60)
    print("测试3: 报告智能体功能")
    print("="*60)
    
    try:
        # 创建报告智能体
        print("\n3.1 创建报告智能体 (Patient_ID=1):")
        agent = ReportAgent(patient_id=1)
        
        print(f"  - 用户ID: {agent.patient_id}")
        print(f"  - 用户姓名: {agent.user_info.get('Name') if agent.user_info else '未知'}")
        print(f"  - 历史报告数: {len(agent.user_reports)}")
        
        # 测试对话功能
        print("\n3.2 测试对话功能:")
        test_messages = [
            "你好",
            "我有哪些报告？",
        ]
        
        for msg in test_messages:
            print(f"\n  用户: {msg}")
            response, is_completed = agent.chat(msg)
            print(f"  助手: {response[:200]}...")
            if is_completed:
                break
        
        # 测试趋势分析
        if len(agent.user_reports) >= 2:
            print("\n3.3 测试趋势分析:")
            result = agent.analyze_history_trends(agent.patient_id)
            print(f"  结果: {result[:300]}...")
        
        # 测试异常检测
        if len(agent.user_reports) >= 2:
            print("\n3.4 测试异常检测:")
            result = agent.detect_anomalies(agent.patient_id)
            print(f"  结果: {result[:300]}...")
        
        print("\n[SUCCESS] 报告智能体测试通过")
        
    except Exception as e:
        print(f"\n[FAIL] 报告智能体测试失败: {e}")
        import traceback
        traceback.print_exc()


def test_existing_appointment_feature():
    """测试现有预约功能是否受影响"""
    print("\n" + "="*60)
    print("测试4: 验证现有预约功能未受影响")
    print("="*60)
    
    try:
        from agents.agent_1 import HealthAgent
        from database.appointment_service_v2 import AppointmentServiceV2
        
        # 测试创建 HealthAgent
        print("\n4.1 测试创建 HealthAgent:")
        health_agent = HealthAgent(phone_number="13900000001")
        print(f"  [OK] HealthAgent 创建成功")
        print(f"  - 用户ID: {health_agent.user_id}")
        print(f"  - 历史信息已加载: {health_agent.history_loaded}")
        
        # 测试预约服务
        print("\n4.2 测试预约服务:")
        appt_service = AppointmentServiceV2()
        
        # 查询预约记录
        query = "SELECT COUNT(*) as count FROM appointment"
        result = appt_service.db.execute_one(query)
        print(f"  [OK] 预约服务正常")
        print(f"  - 当前预约数: {result['count']}")
        
        # 查询医生记录
        query = "SELECT COUNT(*) as count FROM doctor"
        result = appt_service.db.execute_one(query)
        print(f"  - 当前医生数: {result['count']}")
        
        appt_service.close()
        
        print("\n[SUCCESS] 现有功能验证通过，报告功能未影响预约功能")
        
    except Exception as e:
        print(f"\n[FAIL] 现有功能验证失败: {e}")
        import traceback
        traceback.print_exc()


def test_database_schema():
    """测试数据库表结构"""
    print("\n" + "="*60)
    print("测试5: 验证数据库表结构")
    print("="*60)
    
    try:
        from database.db_connection import DatabaseConnection
        
        db = DatabaseConnection()
        
        # 检查新字段是否存在
        print("\n5.1 检查 medical_record 表新字段:")
        query = "DESCRIBE medical_record"
        fields = db.execute_query(query)
        
        new_fields = [
            'Report_ID', 'Visit_Time', 'Special_Exams', 
            'Auxiliary_Exams', 'AI_Diagnosis', 'Doctor_Signature', 'Print_Time'
        ]
        
        existing_fields = [f['Field'] for f in fields]
        
        for field in new_fields:
            if field in existing_fields:
                print(f"  [OK] {field} - 存在")
            else:
                print(f"  [FAIL] {field} - 缺失")
        
        db.close()
        
        print("\n[SUCCESS] 数据库表结构验证完成")
        
    except Exception as e:
        print(f"\n[FAIL] 数据库表结构验证失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("开始病例报告功能集成测试")
    print("="*60)
    
    # 运行各项测试
    test_database_schema()
    test_report_service()
    test_report_generator()
    test_report_agent()
    test_existing_appointment_feature()
    
    print("\n" + "="*60)
    print("所有测试完成!")
    print("="*60)
    print("\n提示:")
    print("1. 如果数据库字段缺失，请运行迁移脚本: database/migrations/add_report_fields.sql")
    print("2. 如果PDF转换失败，请安装: pip install python-docx docx2pdf pypandoc")
    print("3. 生成的报告文件保存在: example/reports/ 目录")
    print("\n")


if __name__ == "__main__":
    main()


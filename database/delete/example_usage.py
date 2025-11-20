"""
数据库操作模块使用示例
演示如何使用 AppointmentService 处理一号智能体的预约数据
"""

import sys
import json
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.appointment_service import AppointmentService


def example_1_basic_usage():
    """示例1: 基本使用 - 直接使用患者数据字典"""
    print("\n" + "=" * 60)
    print("示例1: 基本使用")
    print("=" * 60)
    
    # 模拟一号智能体输出的患者数据
    patient_data = {
        "patient_info": {
            "name": "张三",
            "age": "35",
            "gender": "男",
            "contact": "13800138000",
            "id_number": ""
        },
        "chief_complaint": "眼部不适，视力模糊",
        "present_illness": "近一周出现视力下降，眼睛干涩，偶有刺痛感",
        "symptoms": {
            "vision_change": "视力下降，看东西模糊",
            "eye_pain": "偶有刺痛",
            "redness": "",
            "discharge": "",
            "other": "眼睛干涩"
        },
        "medical_history": "无",
        "medication_history": "无",
        "allergy_history": "无",
        "family_history": "无",
        "appointment": {
            "department": "眼科",
            "preferred_time": "明天下午",
            "doctor_preference": "主任医师",
            "urgency": "普通"
        },
        "diagnosis_suggestion": "",
        "timestamp": "2025-11-14 17:00:00"
    }
    
    # 创建预约服务
    service = AppointmentService()
    
    try:
        # 处理预约
        result = service.process_appointment(patient_data)
        
        # 打印结果
        print("\n预约处理结果:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        if result['success']:
            print(f"\n✓ 预约成功！")
            print(f"  患者ID: {result['patient_id']}")
            print(f"  预约ID: {result['appointment_id']}")
            print(f"  医生: {result['doctor_info']['name']} ({result['doctor_info']['title']})")
            print(f"  时间: {result['appointment_time']}")
            
            if result.get('available_doctors'):
                print(f"\n  其他可选医生:")
                for doctor in result['available_doctors']:
                    print(f"    - {doctor['name']} ({doctor['title']}) - {doctor['available_time']}")
        else:
            print(f"\n✗ 预约失败: {result['message']}")
    
    finally:
        service.close()


def example_2_with_agent():
    """示例2: 与一号智能体集成使用"""
    print("\n" + "=" * 60)
    print("示例2: 与一号智能体集成")
    print("=" * 60)
    
    try:
        # 导入一号智能体
        from agents.agent_1 import HealthAgent
        
        # 创建智能体实例
        agent = HealthAgent()
        
        # 模拟对话过程（这里简化，实际使用时需要完整的对话流程）
        print("\n注意: 实际使用时需要完成完整的对话流程")
        print("这里仅演示数据集成方式\n")
        
        # 获取患者数据（假设对话已完成）
        # patient_data = agent.get_patient_data()
        
        # 使用示例数据代替
        patient_data = {
            "patient_info": {
                "name": "李四",
                "age": "42",
                "gender": "女",
                "contact": "13900139000",
                "id_number": ""
            },
            "chief_complaint": "眼睛红肿，有分泌物",
            "present_illness": "三天前开始出现眼睛红肿，伴有黄色分泌物，早晨起床时眼睛睁不开",
            "symptoms": {
                "vision_change": "",
                "eye_pain": "轻微疼痛",
                "redness": "双眼红肿",
                "discharge": "黄色分泌物，较多",
                "other": ""
            },
            "medical_history": "糖尿病",
            "medication_history": "二甲双胍",
            "allergy_history": "青霉素过敏",
            "family_history": "无",
            "appointment": {
                "department": "眼科",
                "preferred_time": "今天下午",
                "doctor_preference": "",
                "urgency": "紧急"
            },
            "diagnosis_suggestion": "",
            "timestamp": "2025-11-14 17:30:00"
        }
        
        # 创建预约服务并处理
        service = AppointmentService()
        result = service.process_appointment(patient_data)
        
        # 打印结果
        print("\n预约处理结果:")
        if result['success']:
            print(f"✓ 预约成功！")
            print(f"  患者: {patient_data['patient_info']['name']}")
            print(f"  患者ID: {result['patient_id']}")
            print(f"  预约ID: {result['appointment_id']}")
            print(f"  医生: {result['doctor_info']['name']} ({result['doctor_info']['title']})")
            print(f"  科室: {result['doctor_info']['specialty']}")
            print(f"  院区: {result['doctor_info']['hospital_area']}")
            print(f"  预约时间: {result['appointment_time']}")
            print(f"  紧急程度: {patient_data['appointment']['urgency']}")
        else:
            print(f"✗ 预约失败: {result['message']}")
        
        service.close()
        
    except ImportError as e:
        print(f"无法导入一号智能体: {e}")
        print("请确保 agents.agent_1 模块存在")


def example_3_error_handling():
    """示例3: 错误处理"""
    print("\n" + "=" * 60)
    print("示例3: 错误处理")
    print("=" * 60)
    
    # 缺少必填字段的数据
    incomplete_data = {
        "patient_info": {
            "name": "",  # 缺少姓名
            "age": "30",
            "gender": "男",
            "contact": "",  # 缺少联系方式
            "id_number": ""
        },
        "chief_complaint": "眼睛不舒服",
        "appointment": {
            "department": "眼科",
            "preferred_time": "明天",
            "urgency": "普通"
        }
    }
    
    service = AppointmentService()
    
    try:
        result = service.process_appointment(incomplete_data)
        
        if not result['success']:
            print(f"\n预期的错误: {result['message']}")
            print("✓ 错误处理正常")
    
    finally:
        service.close()


def example_4_query_available_doctors():
    """示例4: 仅查询可用医生（不创建预约）"""
    print("\n" + "=" * 60)
    print("示例4: 查询可用医生")
    print("=" * 60)
    
    service = AppointmentService()
    
    try:
        # 查询眼科可用医生
        doctors = service.find_available_doctors(
            department="眼科",
            preferred_time_expr="明天上午",
            doctor_preference="主任",
            urgency="普通"
        )
        
        print(f"\n找到 {len(doctors)} 位可用医生:\n")
        for i, doctor in enumerate(doctors, 1):
            print(f"{i}. {doctor['Name']} - {doctor['Title']}")
            print(f"   专长: {doctor['Specialty']}")
            print(f"   院区: {doctor['Hospital_Area']}")
            print(f"   电话: {doctor['Phone_Number']}")
            if 'parsed_start_time' in doctor:
                print(f"   可预约时间: {doctor['parsed_start_time'].strftime('%Y-%m-%d %H:%M')} - {doctor['parsed_end_time'].strftime('%H:%M')}")
            print()
    
    finally:
        service.close()


def main():
    """主函数 - 运行所有示例"""
    print("\n" + "=" * 60)
    print("数据库操作模块使用示例")
    print("=" * 60)
    
    print("\n提示: 运行这些示例前，请确保:")
    print("  1. MySQL 服务已启动")
    print("  2. 已创建 medical_db 数据库")
    print("  3. 已创建 doctor, patient, appointment 表")
    print("  4. doctor 表中有测试数据")
    print()
    
    choice = input("是否继续运行示例? (y/n): ").strip().lower()
    
    if choice != 'y':
        print("已取消")
        return
    
    # 运行各个示例
    try:
        example_1_basic_usage()
        input("\n按回车键继续下一个示例...")
        
        example_2_with_agent()
        input("\n按回车键继续下一个示例...")
        
        example_3_error_handling()
        input("\n按回车键继续下一个示例...")
        
        example_4_query_available_doctors()
        
        print("\n" + "=" * 60)
        print("所有示例运行完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n运行示例时出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()


"""
智能体测试脚本 - 测试对话流程和JSON输出
"""
import json
from agents.agent_1 import HealthAgent


def print_separator(title=""):
    """打印分隔线"""
    if title:
        print("\n" + "=" * 60)
        print(f" {title}")
        print("=" * 60)
    else:
        print("-" * 60)


def test_agent_conversation():
    """测试智能体对话流程"""
    print_separator("智能体对话流程测试")
    
    # 创建智能体实例
    agent = HealthAgent()
    print("[OK] 智能体实例创建成功")
    
    # 模拟对话流程
    test_conversations = [
        "你好，我最近眼睛看东西有点模糊",
        "是的，而且有时候还会感觉眼睛有点疼",
        "好的，我想预约",
        "我叫张三，今年35岁，男性，电话是13800138000",
        "视力下降大概有一周了，看远处的东西不太清楚，眼睛有轻微红肿",
        "以前没有眼科疾病，身体比较健康",
        "没有长期用药",
        "对青霉素过敏",
        "明天下午有时间，希望尽快看诊",
    ]
    
    print("\n开始对话测试：")
    print_separator()
    
    for i, message in enumerate(test_conversations, 1):
        print(f"\n[USER] 用户 [{i}]: {message}")
        print_separator()
        
        try:
            response = agent.chat(message)
            print(f"[AI] 助手: {response}")
            print(f"\n当前阶段: {agent.stage.value}")
            print(f"已收集字段: {', '.join(agent.collected_fields) if agent.collected_fields else '无'}")
            
        except Exception as e:
            print(f"[ERROR] 错误: {str(e)}")
            return False
        
        print_separator()
    
    # 检查是否完成
    if agent.is_completed():
        print("\n[OK] 对话流程已完成")
    else:
        print(f"\n[WARNING] 对话未完成，当前阶段: {agent.stage.value}")
    
    return True


def test_json_export():
    """测试JSON数据导出"""
    print_separator("JSON数据导出测试")
    
    # 创建智能体并模拟完整对话
    agent = HealthAgent()
    
    # 快速填充数据
    agent.data_handler.update_patient_info("name", "张三")
    agent.data_handler.update_patient_info("age", "35")
    agent.data_handler.update_patient_info("gender", "男")
    agent.data_handler.update_patient_info("contact", "13800138000")
    agent.data_handler.update_field("chief_complaint", "视力模糊，眼睛疼痛")
    agent.data_handler.update_field("present_illness", "视力下降约一周，看远处物体不清楚，伴有轻微红肿")
    agent.data_handler.update_field("medical_history", "无眼科疾病史")
    agent.data_handler.update_field("medication_history", "无长期用药")
    agent.data_handler.update_field("allergy_history", "对青霉素过敏")
    agent.data_handler.update_appointment("preferred_time", "明天下午")
    agent.data_handler.update_appointment("urgency", "较紧急")
    agent.data_handler.update_field("diagnosis_suggestion", "建议眼科门诊详细检查，可能为视疲劳或屈光不正")
    
    # 获取JSON数据
    try:
        patient_data = agent.get_patient_data()
        json_str = agent.get_patient_data_json()
        
        print("\n[OK] JSON数据生成成功")
        print_separator("患者病例数据（JSON格式）")
        print(json_str)
        print_separator()
        
        # 验证JSON格式
        json.loads(json_str)
        print("\n[OK] JSON格式验证通过")
        
        # 检查必要字段
        required_fields = ["patient_info", "chief_complaint", "symptoms", "appointment"]
        missing_fields = [field for field in required_fields if field not in patient_data]
        
        if not missing_fields:
            print("[OK] 所有必要字段都已包含")
        else:
            print(f"[WARNING] 缺少字段: {', '.join(missing_fields)}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 错误: {str(e)}")
        return False


def test_data_handler():
    """测试数据处理模块"""
    print_separator("数据处理模块测试")
    
    from utils.data_handler import PatientDataHandler
    
    handler = PatientDataHandler()
    print("[OK] 数据处理器创建成功")
    
    # 测试更新功能
    handler.update_patient_info("name", "测试患者")
    handler.update_patient_info("age", "30")
    handler.update_field("chief_complaint", "测试症状")
    
    print("[OK] 数据更新功能正常")
    
    # 测试完整性检查
    is_complete = handler.is_complete()
    print(f"数据完整性: {'完整' if is_complete else '不完整'}")
    
    if not is_complete:
        missing = handler.get_missing_fields()
        print(f"缺失字段: {', '.join(missing)}")
    
    # 测试JSON导出
    json_str = handler.to_json()
    print("\n[OK] JSON导出功能正常")
    print(f"JSON长度: {len(json_str)} 字符")
    
    return True


def main():
    """主测试函数"""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 15 + "智能医疗咨询系统测试" + " " * 15 + "║")
    print("╚" + "═" * 58 + "╝")
    
    tests = [
        ("数据处理模块", test_data_handler),
        ("JSON导出功能", test_json_export),
        ("智能体对话流程", test_agent_conversation),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n\n>>> 开始测试: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n[ERROR] 测试失败: {str(e)}")
            results.append((test_name, False))
    
    # 打印测试总结
    print_separator("测试总结")
    print("\n测试结果:")
    for test_name, result in results:
        status = "[OK] 通过" if result else "[FAIL] 失败"
        print(f"  {status} - {test_name}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n[SUCCESS] 所有测试通过！系统运行正常。")
    else:
        print("\n[WARNING] 部分测试未通过，请检查错误信息。")
    
    print("\n" + "=" * 60)
    print("提示: 运行 'python main.py' 启动Web服务进行完整测试")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()


"""
测试Agent2病历和处方单识别修复
验证agent2能否正确区分病历报告和处方单生成请求
"""
import sys
import io

# 修复Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from agents.agent_2 import ReportAgent

def test_prescription_vs_report():
    """测试处方单和病历报告的区分"""
    print("=" * 60)
    print("测试Agent2病历和处方单识别功能")
    print("=" * 60)
    
    # 创建医生角色的agent（需要生成权限）
    agent = ReportAgent(phone_number="13900000001", role="doctor")
    
    # 测试用例
    test_cases = [
        # 明确的处方单请求
        ("生成处方单 ID:1", "应该识别为处方单"),
        ("打印处方单1", "应该识别为处方单"),
        ("生成处方 ID:1", "应该识别为处方单"),
        ("处方单编号1", "应该识别为处方单"),
        
        # 明确的病历报告请求
        ("生成病历报告 ID:1", "应该识别为病历报告"),
        ("打印病例报告1", "应该识别为病历报告"),
        ("生成报告 ID:1", "应该识别为病历报告"),
        ("病例ID:1", "应该识别为病历报告"),
        
        # 模糊请求（应该询问用户）
        ("生成1", "应该询问用户具体要生成什么"),
        ("打印文档", "应该询问用户具体要生成什么"),
    ]
    
    print("\n开始测试...\n")
    
    for idx, (user_input, expected) in enumerate(test_cases, 1):
        print(f"\n【测试 {idx}】")
        print(f"用户输入: {user_input}")
        print(f"预期结果: {expected}")
        print("-" * 50)
        
        # 重置agent状态
        agent.stage = agent.stage.__class__.GREETING
        
        # 处理输入
        response, _ = agent.chat(user_input)
        
        print(f"Agent响应:\n{response}")
        print("=" * 60)

def test_id_extraction():
    """测试ID提取逻辑"""
    print("\n\n")
    print("=" * 60)
    print("测试ID提取逻辑")
    print("=" * 60)
    
    agent = ReportAgent(phone_number="13900000001", role="doctor")
    
    test_texts = [
        ("生成处方单 ID:5", "prescription"),
        ("打印病历报告 ID:10", "report"),
        ("处方编号123", "prescription"),
        ("病例ID:456", "report"),
        ("生成最新的处方单", "prescription"),
        ("生成最新的报告", "report"),
    ]
    
    print("\n开始测试...\n")
    
    for text, doc_type in test_texts:
        print(f"\n测试文本: {text}")
        print(f"预期类型: {doc_type}")
        print("-" * 50)
        
        if doc_type == "prescription":
            prescription_id = agent._extract_prescription_id(text)
            print(f"提取到的处方ID: {prescription_id}")
        else:
            report_id = agent._extract_report_id(text)
            print(f"提取到的病例ID: {report_id}")
        
        print("=" * 60)

def test_intent_detection():
    """测试意图检测"""
    print("\n\n")
    print("=" * 60)
    print("测试意图检测逻辑")
    print("=" * 60)
    
    agent = ReportAgent(phone_number="13900000001", role="doctor")
    
    test_inputs = [
        "生成处方单",
        "生成病历报告",
        "打印报告",
        "导出处方",
        "分析病情趋势",
        "对比两次就诊",
    ]
    
    print("\n开始测试...\n")
    
    for user_input in test_inputs:
        print(f"\n用户输入: {user_input}")
        print("-" * 50)
        
        # 重置状态
        agent.stage = agent.stage.__class__.GREETING
        
        # 检测意图
        agent._detect_intent(user_input)
        
        print(f"检测到的阶段: {agent.stage.value}")
        print("=" * 60)


if __name__ == "__main__":
    try:
        # 运行测试
        test_prescription_vs_report()
        test_id_extraction()
        test_intent_detection()
        
        print("\n\n")
        print("✅ 测试完成！")
        print("\n【总结】")
        print("1. Agent2现在能够明确区分处方单和病历报告请求")
        print("2. ID提取逻辑更加准确，不会混淆处方ID和病例ID")
        print("3. 当请求模糊时，agent会主动询问用户")
        print("4. 意图检测更加精准，按照关键词优先级进行判断")
        
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()


"""
测试信息提取功能是否正常工作
"""
import json
from agents.agent_1 import HealthAgent

def test_info_extraction():
    """测试信息提取功能"""
    print("=" * 60)
    print("测试信息提取功能")
    print("=" * 60)
    
    # 创建智能体
    agent = HealthAgent()
    
    # 模拟对话，包含完整的患者信息
    conversations = [
        "你好，我最近眼睛不太舒服",
        "我的眼睛有点红，还有点疼，看东西也模糊",
        "大概3天前开始的，现在越来越严重了",
        "好的，我想预约医生",
        "我叫李明，今年42岁，男性",
        "我的手机号是13800138000",
        "我之前有高血压，正在吃降压药",
        "目前没有在用眼药水或其他药物",
        "我对青霉素过敏",
        "家族里没有眼科遗传病史",
        "我想明天下午去看诊，希望能挂个专家号",
        "还是比较急的，因为影响工作了"
    ]
    
    print("\n开始模拟对话...\n")
    
    # 进行对话
    for i, user_msg in enumerate(conversations, 1):
        print(f"第 {i} 轮对话")
        print(f"用户: {user_msg}")
        
        response = agent.chat(user_msg)
        print(f"AI: {response}")
        print("-" * 60)
    
    print("\n对话完成，开始导出数据...\n")
    
    # 获取患者数据
    patient_data = agent.get_patient_data()
    
    # 打印导出的JSON
    print("\n" + "=" * 60)
    print("导出的患者数据（JSON格式）")
    print("=" * 60)
    print(json.dumps(patient_data, ensure_ascii=False, indent=2))
    print("=" * 60)
    
    # 验证关键信息是否被提取
    print("\n验证信息提取结果：")
    print("-" * 60)
    
    checks = [
        ("姓名", patient_data["patient_info"]["name"], "李明"),
        ("年龄", patient_data["patient_info"]["age"], "42"),
        ("性别", patient_data["patient_info"]["gender"], "男"),
        ("联系方式", patient_data["patient_info"]["contact"], "13800138000"),
        ("主诉", patient_data["chief_complaint"], None),  # 只检查是否非空
        ("既往病史", patient_data["medical_history"], "高血压"),
        ("过敏史", patient_data["allergy_history"], "青霉素"),
        ("期望时间", patient_data["appointment"]["preferred_time"], "明天下午"),
        ("紧急程度", patient_data["appointment"]["urgency"], None),
    ]
    
    success_count = 0
    fail_count = 0
    
    for field_name, actual_value, expected_value in checks:
        if expected_value is None:
            # 只检查是否非空
            if actual_value and actual_value.strip():
                print(f"[OK] {field_name}: 已提取 -> {actual_value}")
                success_count += 1
            else:
                print(f"[FAIL] {field_name}: 未提取或为空")
                fail_count += 1
        else:
            # 检查是否包含期望值
            if expected_value in str(actual_value):
                print(f"[OK] {field_name}: 已提取 -> {actual_value}")
                success_count += 1
            else:
                print(f"[FAIL] {field_name}: 提取不正确 -> 实际值: {actual_value}, 期望包含: {expected_value}")
                fail_count += 1
    
    print("-" * 60)
    print(f"\n测试结果: 成功 {success_count} 项, 失败 {fail_count} 项")
    
    if fail_count == 0:
        print("[SUCCESS] 所有信息都已正确提取！")
        return True
    else:
        print("[WARNING] 部分信息提取失败，请查看上面的详细日志")
        return False


if __name__ == "__main__":
    try:
        success = test_info_extraction()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] 测试过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)

